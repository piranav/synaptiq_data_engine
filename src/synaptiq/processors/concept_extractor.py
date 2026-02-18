"""
LLM-based concept extractor for enriching chunks with semantic metadata.

Uses OpenAI GPT models to extract:
- Key concepts/topics
- Definitions with actual definition text
- Claims and relationships between concepts
- Concept relationships (isA, partOf, prerequisiteFor, relatedTo)
"""

import asyncio
import json
import re
from typing import Optional

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings
from synaptiq.core.exceptions import ProcessingError, RateLimitError
from synaptiq.core.schemas import Chunk
from synaptiq.processors.base import BaseProcessor

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DOMAIN CLUSTERS FOR RELATIONSHIP INFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

# When multiple concepts from the same domain appear in a chunk without explicit
# relationships, we can infer they are "relatedTo" each other
DOMAIN_CLUSTERS: dict[str, set[str]] = {
    "physics": {
        "gravity", "gravitational", "relativity", "spacetime", "mass", "energy",
        "wave", "particle", "quantum", "field", "force", "momentum", "velocity",
        "acceleration", "newton", "einstein", "photon", "electron", "proton",
        "neutron", "quark", "boson", "fermion", "higgs", "string theory",
        "black hole", "cosmology", "astrophysics", "thermodynamics", "entropy",
        "electromagnetic", "magnetism", "nuclear", "atomic", "subatomic",
    },
    "ai_ml": {
        "neural", "network", "learning", "training", "model", "inference",
        "deep", "layer", "weight", "bias", "gradient", "backpropagation",
        "activation", "optimization", "loss", "accuracy", "transformer",
        "attention", "embedding", "classifier", "regression", "clustering",
        "reinforcement", "agent", "reward", "policy", "supervised", "unsupervised",
        "artificial intelligence", "machine learning", "ai", "ml", "neural network",
    },
    "oracle": {
        "oracle", "database", "sql", "plsql", "cloud", "oci", "exadata",
        "autonomous", "fusion", "erp", "hcm", "scm", "apex", "ords",
    },
    "mathematics": {
        "algebra", "calculus", "geometry", "topology", "statistics", "probability",
        "matrix", "vector", "tensor", "derivative", "integral", "function",
        "equation", "theorem", "proof", "set", "group", "ring", "field",
    },
}




class ExtractedRelationship(BaseModel):
    """A relationship between two concepts extracted from text."""
    
    source_concept: str = Field(
        ...,
        description="The source concept in the relationship",
    )
    relation_type: str = Field(
        ...,
        description="Type of relationship: is_a, part_of, prerequisite_for, related_to, used_in, opposite_of",
    )
    target_concept: str = Field(
        ...,
        description="The target concept in the relationship",
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score for this relationship (0-1)",
    )


class ConceptExtractionResult(BaseModel):
    """Result of concept extraction for a single chunk."""

    concepts: list[str] = Field(
        default_factory=list,
        description="Key concepts, topics, and entities mentioned in the text",
    )
    has_definition: bool = Field(
        default=False,
        description="Whether the text contains a definition of a concept",
    )
    defined_concept: Optional[str] = Field(
        default=None,
        description="The concept being defined, if has_definition is True",
    )
    definition_text: Optional[str] = Field(
        default=None,
        description="The actual definition text, if has_definition is True",
    )
    claims: list[str] = Field(
        default_factory=list,
        description="Key claims or assertions made in the text",
    )
    relationships: list[ExtractedRelationship] = Field(
        default_factory=list,
        description="Relationships between concepts found in the text",
    )


class BatchExtractionResult(BaseModel):
    """Result of batch concept extraction."""

    results: list[ConceptExtractionResult]


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge extraction assistant for building personal knowledge graphs. Your task is to analyze text chunks and extract structured information including concepts, definitions, and relationships between concepts.

For each text chunk, extract:

1. **Concepts** (max 6 per chunk): Key topics and entities at the granularity of textbook chapter titles or glossary entries — not individual terms or overly broad fields.
   - GOOD granularity: "convolutional neural network", "gradient descent", "Fourier transform"
   - TOO BROAD: "machine learning", "physics", "mathematics"
   - TOO NARROW: "step size", "weight value", "pixel"
   Focus on:
   - Technical terms and named methods/algorithms
   - Named entities (people, organizations, specific technologies)
   - Domain-specific concepts that would appear in a textbook index
   - Prefer multi-word compound terms over single generic words

2. **Definitions**: Determine if the text contains a definition. Look for patterns like:
   - "X is Y" / "X refers to Y" / "X means Y" / "X is defined as Y"
   - Explicit explanations of what something is
   If a definition is found, extract the COMPLETE definition text.

3. **Claims**: Key assertions, facts, or statements being made (max 3).

4. **Relationships** (max 3 per chunk): Identify ONLY the strongest, most explicit relationships between concepts.
   IMPORTANT: Prefer specific relationship types over generic ones. Use this priority order:
   - Taxonomic: "X is a type of Y", "X is a Y" → is_a (HIGHEST priority)
   - Compositional: "X is part of Y", "X contains Y" → part_of
   - Prerequisites: "X requires Y", "understanding X needs Y" → prerequisite_for
   - Usage: "X is used in Y", "X applies to Y" → used_in
   - Opposition: "X is the opposite of Y", "unlike X, Y" → opposite_of
   - Association: → related_to (LAST RESORT — only if NO other type applies)

   Rules for relationships:
   - Only extract relationships that are EXPLICITLY stated or strongly implied in the text
   - Do NOT create relationships just because two concepts co-occur in the same chunk
   - Do NOT use related_to as a catch-all — if you cannot identify a specific relationship type, skip the relationship entirely
   - Each relationship must have a confidence >= 0.8 to be worth extracting

Respond in JSON format with this structure:
{
    "concepts": ["concept1", "concept2", ...],
    "has_definition": true/false,
    "defined_concept": "concept name or null",
    "definition_text": "the actual definition text or null",
    "claims": ["claim1", "claim2", ...],
    "relationships": [
        {"source_concept": "X", "relation_type": "is_a", "target_concept": "Y", "confidence": 0.9},
        ...
    ]
}"""

BATCH_EXTRACTION_PROMPT = """Analyze the following text chunks and extract concepts, definitions, claims, and relationships from each.

{chunks}

Respond with a JSON object containing a "results" array with one result object per chunk, in the same order as the input.
Each result should have:
- concepts (array of strings, max 6) — textbook-index-level terms, not single generic words
- has_definition (boolean)
- defined_concept (string or null)
- definition_text (string or null - the actual definition if has_definition is true)
- claims (array of strings, max 3)
- relationships (array of objects, max 3) — ONLY explicit relationships with confidence >= 0.8
  - Prefer is_a, part_of, prerequisite_for, used_in, opposite_of over related_to
  - Do NOT use related_to just because two concepts co-occur

Valid relation_type values (in priority order): is_a, part_of, prerequisite_for, used_in, opposite_of, related_to

Example response format:
{{"results": [
    {{
        "concepts": ["tensor", "matrix", "multi-dimensional array"],
        "has_definition": true,
        "defined_concept": "tensor",
        "definition_text": "A tensor is a multi-dimensional array that generalizes scalars, vectors, and matrices.",
        "claims": ["Tensors generalize matrices to higher dimensions"],
        "relationships": [
            {{"source_concept": "tensor", "relation_type": "is_a", "target_concept": "multi-dimensional array", "confidence": 0.95}},
            {{"source_concept": "matrix", "relation_type": "prerequisite_for", "target_concept": "tensor", "confidence": 0.85}}
        ]
    }},
    {{
        "concepts": ["convolutional neural network", "deep learning"],
        "has_definition": false,
        "defined_concept": null,
        "definition_text": null,
        "claims": [],
        "relationships": [
            {{"source_concept": "convolutional neural network", "relation_type": "is_a", "target_concept": "deep learning", "confidence": 0.9}}
        ]
    }}
]}}"""


class ConceptExtractor(BaseProcessor):
    """
    LLM-based concept extraction using OpenAI.
    
    Extracts:
    - Key concepts/topics from each chunk
    - Definitions with actual definition text
    - Claims and key assertions
    - Relationships between concepts (is_a, part_of, prerequisite_for, etc.)
    
    Features:
    - Batch processing for efficiency (reduces API calls)
    - Heuristic pre-filtering to skip obvious non-definition chunks
    - Retry logic with exponential backoff
    - Configurable model and parameters
    """

    def __init__(
        self,
        model: str = "gpt-4.1",
        extract_concepts: bool = True,
        detect_definitions: bool = True,
        extract_claims: bool = True,
        extract_relationships: bool = True,
        max_concepts_per_chunk: int = 10,
        max_claims_per_chunk: int = 5,
        max_relationships_per_chunk: int = 5,
        batch_size: int = 5,
        use_heuristics: bool = True,
    ):
        """
        Initialize the concept extractor.
        
        Args:
            model: OpenAI model to use (default: gpt-4.1)
            extract_concepts: Whether to extract concepts
            detect_definitions: Whether to detect definitions
            extract_claims: Whether to extract claims
            extract_relationships: Whether to extract relationships between concepts
            max_concepts_per_chunk: Maximum concepts to extract per chunk
            max_claims_per_chunk: Maximum claims to extract per chunk
            max_relationships_per_chunk: Maximum relationships to extract per chunk
            batch_size: Number of chunks to process per API call
            use_heuristics: Use pattern matching to pre-filter definition detection
        """
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

        self.model = model
        self.extract_concepts = extract_concepts
        self.detect_definitions = detect_definitions
        self.extract_claims = extract_claims
        self.extract_relationships = extract_relationships
        self.max_concepts_per_chunk = max_concepts_per_chunk
        self.max_claims_per_chunk = max_claims_per_chunk
        self.max_relationships_per_chunk = max_relationships_per_chunk
        self.batch_size = batch_size
        self.use_heuristics = use_heuristics

        logger.info(
            "ConceptExtractor initialized",
            model=self.model,
            batch_size=batch_size,
            extract_concepts=extract_concepts,
            detect_definitions=detect_definitions,
            extract_claims=extract_claims,
            extract_relationships=extract_relationships,
        )

    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """
        Process chunks to extract concepts, definitions, claims, and relationships.
        
        Args:
            chunks: Input chunks
            
        Returns:
            Chunks with concepts[], has_definition, relationships, and metadata populated
        """
        if not chunks:
            return chunks

        logger.info("ConceptExtractor processing", chunk_count=len(chunks))

        # Process in batches for efficiency
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            logger.debug(
                "Processing batch",
                batch_start=i,
                batch_size=len(batch),
            )

            try:
                results = await self._extract_batch(batch)

                # Update chunks with extraction results
                for chunk, result in zip(batch, results):
                    chunk.concepts = result.concepts[: self.max_concepts_per_chunk]
                    chunk.has_definition = result.has_definition

                    # Store additional metadata
                    chunk.metadata["defined_concept"] = result.defined_concept
                    chunk.metadata["definition_text"] = result.definition_text
                    chunk.metadata["claims"] = result.claims[: self.max_claims_per_chunk]
                    
                    # Store relationships in metadata
                    relationships_list = [
                        {
                            "source_concept": r.source_concept,
                            "relation_type": r.relation_type,
                            "target_concept": r.target_concept,
                            "confidence": r.confidence,
                        }
                        for r in result.relationships[: self.max_relationships_per_chunk]
                    ]
                    
                    # NOTE: Domain-inferred relatedTo relationships removed.
                    # They generated O(n^2) weak links per chunk and created
                    # noise in both the graph and visualization. Relationships
                    # are now only created from explicit LLM extraction or
                    # heuristic patterns.
                    
                    chunk.metadata["relationships"] = relationships_list

            except Exception as e:
                logger.error(
                    "Batch extraction failed, using fallback",
                    batch_start=i,
                    error=str(e),
                )
                # Fallback to heuristics only
                for chunk in batch:
                    chunk.concepts = self._extract_concepts_heuristic(chunk.text)
                    chunk.has_definition = self._detect_definition_patterns(chunk.text)
                    chunk.metadata["relationships"] = self._extract_relationships_heuristic(chunk.text)

        logger.info(
            "ConceptExtractor complete",
            chunk_count=len(chunks),
            chunks_with_definitions=sum(1 for c in chunks if c.has_definition),
            total_relationships=sum(
                len(c.metadata.get("relationships", [])) for c in chunks
            ),
        )

        return chunks

    @retry(
        retry=retry_if_exception_type((RateLimitError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
    )
    async def _extract_batch(
        self, chunks: list[Chunk]
    ) -> list[ConceptExtractionResult]:
        """
        Extract concepts from a batch of chunks in a single API call.
        
        Args:
            chunks: Batch of chunks to process
            
        Returns:
            List of extraction results
        """
        # Format chunks for the prompt
        chunks_text = "\n\n".join(
            f"[CHUNK {i+1}]\n{chunk.text}"
            for i, chunk in enumerate(chunks)
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": BATCH_EXTRACTION_PROMPT.format(chunks=chunks_text),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=3000,  # Increased for relationship extraction
            )
            content = response.choices[0].message.content
            
            # Log the full LLM response so we can see it in Celery logs
            logger.debug("LLM RESPONSE", full_content=content)
            
            if not content:
                logger.warning("Empty response from LLM")
                return [self._extract_heuristic_result(c.text) for c in chunks]
            
            # Clean up content - remove markdown code blocks if present
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code block wrapper
                lines = content.split("\n")
                # Remove first line (```json or ```) and last line (```)
                if lines[-1].strip() == "```":
                    lines = lines[1:-1]
                else:
                    lines = lines[1:]
                content = "\n".join(lines)
            
            # Parse JSON
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse LLM response as JSON",
                    error=str(e),
                    content_preview=content[:200] if content else "empty",
                )
                return [self._extract_heuristic_result(c.text) for c in chunks]

            logger.debug(
                "LLM response parsed",
                parsed_type=type(parsed).__name__,
                parsed_keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
            )

            # Handle different response formats
            raw_results = []
            if isinstance(parsed, dict):
                # Expected format: {"results": [...]}
                raw_results = parsed.get("results", [])
                
                # Validate that results is actually a list
                if raw_results and not isinstance(raw_results, list):
                    logger.warning(
                        "Results field is not a list",
                        results_type=type(raw_results).__name__,
                    )
                    # If results is a dict, wrap it in a list
                    if isinstance(raw_results, dict):
                        raw_results = [raw_results]
                    else:
                        raw_results = []
                
                # Sometimes LLM returns results at top level without "results" key
                if not raw_results and len(parsed) > 0:
                    # Check if the dict contains numbered keys like "1", "2", etc.
                    keys = list(parsed.keys())
                    if all(k.isdigit() for k in keys):
                        raw_results = [parsed.get(k) for k in sorted(keys, key=int)]
                    # Or check if it's a single result (when only one chunk)
                    elif "concepts" in parsed:
                        raw_results = [parsed]
                        
            elif isinstance(parsed, list):
                # Sometimes LLM returns just the array directly
                raw_results = parsed

            if not raw_results:
                logger.warning(
                    "No results found in LLM response",
                    parsed_keys=list(parsed.keys()) if isinstance(parsed, dict) else "list",
                )
                return [self._extract_heuristic_result(c.text) for c in chunks]

            logger.debug(
                "Processing raw results",
                raw_results_count=len(raw_results),
                first_result_type=type(raw_results[0]).__name__ if raw_results else None,
            )

            # Parse results
            results = []
            for i, chunk in enumerate(chunks):
                if i < len(raw_results):
                    raw = raw_results[i]
                    if isinstance(raw, dict):
                        # Safely extract each field
                        concepts = raw.get("concepts") if isinstance(raw.get("concepts"), list) else []
                        has_def = bool(raw.get("has_definition", False))
                        defined = raw.get("defined_concept")
                        definition_text = raw.get("definition_text")
                        claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
                        
                        # Parse relationships
                        raw_relationships = raw.get("relationships", [])
                        relationships = []
                        if isinstance(raw_relationships, list):
                            for rel in raw_relationships:
                                if isinstance(rel, dict):
                                    try:
                                        relationships.append(
                                            ExtractedRelationship(
                                                source_concept=rel.get("source_concept", ""),
                                                relation_type=rel.get("relation_type", "related_to"),
                                                target_concept=rel.get("target_concept", ""),
                                                confidence=float(rel.get("confidence", 1.0)),
                                            )
                                        )
                                    except (ValueError, TypeError) as e:
                                        logger.warning(
                                            "Failed to parse relationship",
                                            rel=rel,
                                            error=str(e),
                                        )
                        
                        results.append(
                            ConceptExtractionResult(
                                concepts=concepts,
                                has_definition=has_def,
                                defined_concept=defined,
                                definition_text=definition_text,
                                claims=claims,
                                relationships=relationships,
                            )
                        )
                    else:
                        logger.warning(
                            f"Unexpected result format at index {i}",
                            raw_type=type(raw).__name__,
                            raw_preview=str(raw)[:100] if raw else "empty",
                        )
                        results.append(self._extract_heuristic_result(chunk.text))
                else:
                    # Fallback if LLM didn't return enough results
                    results.append(self._extract_heuristic_result(chunk.text))

            return results

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response", error=str(e))
            # Fallback to heuristics
            return [self._extract_heuristic_result(c.text) for c in chunks]

        except Exception as e:
            error_message = str(e).lower()
            if "rate limit" in error_message:
                logger.warning("Rate limit hit, will retry", error=str(e))
                raise RateLimitError(
                    message="OpenAI rate limit exceeded",
                    retry_after=60,
                    cause=e,
                )
            # Log the full error for debugging
            logger.error("Unexpected error in concept extraction", error=str(e), error_type=type(e).__name__)
            raise

    async def _extract_single(self, text: str) -> ConceptExtractionResult:
        """
        Extract concepts from a single text chunk.
        
        Used as fallback for failed batches.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=1000,
            )

            content = response.choices[0].message.content
            parsed = json.loads(content)

            # Parse relationships
            raw_relationships = parsed.get("relationships", [])
            relationships = []
            if isinstance(raw_relationships, list):
                for rel in raw_relationships:
                    if isinstance(rel, dict):
                        try:
                            relationships.append(
                                ExtractedRelationship(
                                    source_concept=rel.get("source_concept", ""),
                                    relation_type=rel.get("relation_type", "related_to"),
                                    target_concept=rel.get("target_concept", ""),
                                    confidence=float(rel.get("confidence", 1.0)),
                                )
                            )
                        except (ValueError, TypeError):
                            pass

            return ConceptExtractionResult(
                concepts=parsed.get("concepts", []),
                has_definition=parsed.get("has_definition", False),
                defined_concept=parsed.get("defined_concept"),
                definition_text=parsed.get("definition_text"),
                claims=parsed.get("claims", []),
                relationships=relationships,
            )

        except Exception as e:
            logger.warning("Single extraction failed", error=str(e))
            return self._extract_heuristic_result(text)

    def _extract_heuristic_result(self, text: str) -> ConceptExtractionResult:
        """
        Extract concepts using heuristics (fallback).
        """
        return ConceptExtractionResult(
            concepts=self._extract_concepts_heuristic(text),
            has_definition=self._detect_definition_patterns(text),
            defined_concept=None,
            definition_text=None,
            claims=[],
            relationships=self._extract_relationships_heuristic_models(text),
        )

    def _extract_concepts_heuristic(self, text: str) -> list[str]:
        """
        Extract concepts using simple NLP heuristics.
        
        Extracts capitalized terms and common technical patterns.
        """
        concepts = set()
        
        # Common stop words to filter out
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "we", "us", "our", "you", "your", "he", "she", "him", "her", "his",
            "i", "me", "my", "if", "then", "else", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "also", "now", "here", "there",
            "again", "further", "once", "however", "therefore", "finally",
            "first", "second", "third", "one", "two", "three", "new", "old",
            "let", "see", "get", "make", "know", "take", "come", "think",
            "look", "want", "give", "use", "find", "tell", "ask", "work",
            "seem", "feel", "try", "leave", "call", "keep", "put", "mean",
            "become", "show", "hear", "play", "run", "move", "live", "believe",
            "case", "point", "part", "place", "thing", "way", "fact", "group",
            "number", "time", "year", "people", "state", "world", "area",
        }

        # Extract capitalized multi-word terms (potential proper nouns/technical terms)
        # Require at least 2 characters and filter stop words
        capitalized = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
        for term in capitalized:
            term_lower = term.lower()
            if len(term) > 2 and term_lower not in stop_words:
                concepts.add(term_lower)

        # Extract terms in quotes (likely important concepts)
        quoted = re.findall(r'"([^"]+)"', text)
        for q in quoted:
            if len(q) < 50 and q.lower() not in stop_words:
                concepts.add(q.lower())

        # Extract technical/scientific patterns
        technical_patterns = [
            # Math/physics terms
            r"\b(tensor|vector|matrix|scalar|rotation|transformation|coordinate\s+system)\b",
            r"\b(equation|formula|derivative|integral|function|variable|constant)\b",
            r"\b(angle|dimension|component|magnitude|direction|origin)\b",
            # General technical terms
            r"\b(\w+\s+(?:network|learning|model|algorithm|function|system|theory|method|matrix|tensor|vector)s?)\b",
            r"\b((?:deep|machine|reinforcement|supervised|unsupervised|linear|nonlinear)\s+\w+)\b",
            r"\b(\w+(?:ization|isation|ology|ometry|istics|ation))\b",
            # Compound technical terms
            r"\b(rotation\s+matrix|identity\s+matrix|coordinate\s+system|tensor\s+components?)\b",
            r"\b(first\s+order|second\s+order)\s+(tensor|derivative|equation)\b",
        ]

        for pattern in technical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                if isinstance(m, tuple):
                    m = " ".join(m)
                m_lower = m.lower().strip()
                if m_lower and m_lower not in stop_words and len(m_lower) > 2:
                    concepts.add(m_lower)

        # Filter and sort by relevance (longer terms often more specific)
        filtered_concepts = [c for c in concepts if c not in stop_words]
        filtered_concepts.sort(key=lambda x: (-len(x.split()), x))
        
        return filtered_concepts[: self.max_concepts_per_chunk]

    def _detect_definition_patterns(self, text: str) -> bool:
        """
        Detect if text contains a definition using regex patterns.
        """
        definition_patterns = [
            # "X is Y" patterns
            r"\b\w+\s+(?:is|are)\s+(?:a|an|the)\s+\w+",
            r"\b\w+\s+(?:is|are)\s+defined\s+as\b",
            r"\b\w+\s+refers?\s+to\b",
            r"\b\w+\s+means?\s+(?:that|a|an|the)\b",
            # Explicit definition markers
            r"\bdef(?:ine|inition)?\s*[:=]",
            r"\b(?:by\s+)?definition\b",
            r"\bknown\s+as\b",
            r"\bcalled\s+(?:a|an|the)?\s*\w+",
            # Question-answer definitions
            r"what\s+is\s+(?:a|an|the)?\s*\w+\??",
        ]

        for pattern in definition_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _extract_relationships_heuristic(self, text: str) -> list[dict]:
        """
        Extract relationships using heuristics (fallback).
        Returns list of dicts for metadata storage.
        """
        relationships = []
        
        # Pattern: "X is a Y" / "X is a type of Y"
        is_a_patterns = [
            r"(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(?:a|an)\s+(?:type\s+of\s+)?(\w+(?:\s+\w+)?)",
            r"(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(?:a|an)\s+kind\s+of\s+(\w+(?:\s+\w+)?)",
        ]
        
        for pattern in is_a_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    relationships.append({
                        "source_concept": match[0].lower().strip(),
                        "relation_type": "is_a",
                        "target_concept": match[1].lower().strip(),
                        "confidence": 0.7,
                    })
        
        # Pattern: "X is part of Y" / "X contains Y"
        part_of_patterns = [
            r"(\w+(?:\s+\w+)?)\s+(?:is|are)\s+part\s+of\s+(\w+(?:\s+\w+)?)",
            r"(\w+(?:\s+\w+)?)\s+contains?\s+(\w+(?:\s+\w+)?)",
        ]
        
        for pattern in part_of_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    relationships.append({
                        "source_concept": match[0].lower().strip(),
                        "relation_type": "part_of",
                        "target_concept": match[1].lower().strip(),
                        "confidence": 0.7,
                    })
        
        # Pattern: "X requires Y" / "to understand X, you need Y"
        prereq_patterns = [
            r"(\w+(?:\s+\w+)?)\s+requires?\s+(\w+(?:\s+\w+)?)",
            r"(?:to\s+)?understand(?:ing)?\s+(\w+(?:\s+\w+)?)\s+(?:requires?|needs?)\s+(\w+(?:\s+\w+)?)",
        ]
        
        for pattern in prereq_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match) == 2:
                    relationships.append({
                        "source_concept": match[1].lower().strip(),
                        "relation_type": "prerequisite_for",
                        "target_concept": match[0].lower().strip(),
                        "confidence": 0.7,
                    })
        
        return relationships[:self.max_relationships_per_chunk]

    def _extract_relationships_heuristic_models(self, text: str) -> list[ExtractedRelationship]:
        """
        Extract relationships using heuristics (fallback).
        Returns list of ExtractedRelationship models.
        """
        raw_relationships = self._extract_relationships_heuristic(text)
        return [
            ExtractedRelationship(
                source_concept=r["source_concept"],
                relation_type=r["relation_type"],
                target_concept=r["target_concept"],
                confidence=r["confidence"],
            )
            for r in raw_relationships
        ]
    
    def _infer_domain_relationships(
        self,
        concepts: list[str],
        existing_relationships: list[dict],
    ) -> list[dict]:
        """
        Infer relationships between concepts in the same domain.
        
        If concepts like "gravity" and "general relativity" both appear in a chunk,
        and they're both in the physics domain, infer a "related_to" relationship.
        
        Args:
            concepts: List of extracted concept labels
            existing_relationships: Already extracted relationships to avoid duplicates
            
        Returns:
            List of inferred relationships to add
        """
        inferred = []
        
        # Create a set of existing relationships for quick lookup
        existing_pairs = set()
        for r in existing_relationships:
            pair = (r["source_concept"].lower(), r["target_concept"].lower())
            existing_pairs.add(pair)
            existing_pairs.add((pair[1], pair[0]))  # Bidirectional check
        
        # Find which domain each concept belongs to
        concept_domains: dict[str, set[str]] = {}
        for concept in concepts:
            concept_lower = concept.lower()
            for domain_name, domain_terms in DOMAIN_CLUSTERS.items():
                # Check if concept matches or contains any domain term
                for term in domain_terms:
                    if term in concept_lower or concept_lower in term:
                        if concept_lower not in concept_domains:
                            concept_domains[concept_lower] = set()
                        concept_domains[concept_lower].add(domain_name)
                        break
        
        # Create relationships between concepts in the same domain
        concept_list = list(concept_domains.keys())
        for i, concept1 in enumerate(concept_list):
            for concept2 in concept_list[i+1:]:
                # Check if they share a domain
                shared_domains = concept_domains[concept1] & concept_domains[concept2]
                if shared_domains and (concept1, concept2) not in existing_pairs:
                    inferred.append({
                        "source_concept": concept1,
                        "relation_type": "related_to",
                        "target_concept": concept2,
                        "confidence": 0.6,  # Lower confidence for inferred
                    })
        
        return inferred


class ConceptExtractorDisabled(BaseProcessor):
    """
    No-op concept extractor for when extraction is disabled.
    
    Use this to skip concept extraction entirely:
        pipeline = Pipeline(processors=[ConceptExtractorDisabled()])
    """

    async def process(self, chunks: list[Chunk]) -> list[Chunk]:
        """Pass chunks through unchanged."""
        logger.debug("ConceptExtractor disabled, skipping extraction")
        return chunks
