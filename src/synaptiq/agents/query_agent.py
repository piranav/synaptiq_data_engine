"""
Query Agent - Main orchestrator for the knowledge retrieval pipeline.

Coordinates intent classification, strategy selection, retrieval execution,
and response synthesis using OpenAI Agents SDK.
"""

import os
from pathlib import Path
from typing import Optional, AsyncIterator, Any
import structlog

from config.settings import get_settings

# Set OPENAI_API_KEY from settings for the OpenAI Agents SDK
# The SDK reads this from the environment, not from a config object
_settings = get_settings()
if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = _settings.openai_api_key

from agents import Agent, Runner
from agents.result import RunResultStreaming

from synaptiq.storage.fuseki import FusekiStore
from synaptiq.storage.qdrant import QdrantStore
from synaptiq.processors.embedder import EmbeddingGenerator
from synaptiq.ontology.namespaces import get_sparql_prefixes, expand_synonyms

from .context import AgentContext
from .schemas import (
    IntentType,
    IntentClassification,
    RetrievalStrategy,
    QueryResponse,
    Citation,
    RetrievalMetadata,
)
from .prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    RESPONSE_SYNTHESIZER_SYSTEM_PROMPT,
    ORCHESTRATOR_SYSTEM_PROMPT,
)
from .tools import vector_search, get_concept_details
from .sparql_agent import create_sparql_agent, load_ontology_schema
from .session import get_session

logger = structlog.get_logger(__name__)


class QueryAgent:
    """
    Main query agent that orchestrates the retrieval pipeline.
    
    Components:
    1. Intent Classifier - Determines query type
    2. Strategy Selector - Maps intent to retrieval strategy
    3. SPARQL Agent - Queries knowledge graph
    4. Vector Tool - Searches embeddings
    5. Response Synthesizer - Generates final response
    """
    
    def __init__(
        self,
        fuseki_store: Optional[FusekiStore] = None,
        qdrant_store: Optional[QdrantStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the query agent.
        
        Args:
            fuseki_store: SPARQL client (creates new if not provided)
            qdrant_store: Vector store client (creates new if not provided)
            embedding_generator: Embeddings generator (creates new if not provided)
        """
        self.fuseki = fuseki_store or FusekiStore()
        self.qdrant = qdrant_store or QdrantStore()
        self.embedder = embedding_generator or EmbeddingGenerator()
        
        # Load ontology schema
        self.ontology_schema = load_ontology_schema()
        self.prefixes = get_sparql_prefixes()
        
        # Create sub-agents
        self._init_agents()
        
        logger.info("QueryAgent initialized")
    
    def _init_agents(self):
        """Initialize all sub-agents."""
        # Intent Classifier
        self.intent_classifier = Agent[AgentContext](
            name="Intent Classifier",
            instructions=INTENT_CLASSIFIER_SYSTEM_PROMPT,
            model="gpt-5.2",
            output_type=IntentClassification,
        )
        
        # SPARQL Agent
        self.sparql_agent = create_sparql_agent(
            ontology_schema=self.ontology_schema,
            prefixes=self.prefixes,
        )
        
        # Response Synthesizer
        self.synthesizer = Agent[AgentContext](
            name="Response Synthesizer",
            instructions=RESPONSE_SYNTHESIZER_SYSTEM_PROMPT,
            model="gpt-5.2",
            output_type=QueryResponse,
        )
        
        # Main Orchestrator
        self.orchestrator = Agent[AgentContext](
            name="Query Orchestrator",
            instructions=ORCHESTRATOR_SYSTEM_PROMPT,
            model="gpt-5.2",
            tools=[
                vector_search,
                get_concept_details,
                self.sparql_agent.as_tool(
                    tool_name="query_knowledge_graph",
                    tool_description="Query the user's knowledge graph using SPARQL. Use this for definitions, relationships, and source-based lookups.",
                ),
            ],
        )
    
    def _create_context(self, user_id: str) -> AgentContext:
        """Create agent context for a request."""
        return AgentContext(
            user_id=user_id,
            fuseki_store=self.fuseki,
            qdrant_store=self.qdrant,
            embedding_generator=self.embedder,
            ontology_schema=self.ontology_schema,
        )
    
    def _select_strategy(self, intent: IntentClassification) -> RetrievalStrategy:
        """Map intent to retrieval strategy."""
        mapping = {
            IntentType.DEFINITION: RetrievalStrategy.GRAPH_FIRST,
            IntentType.EXPLORATION: RetrievalStrategy.GRAPH_FIRST,
            IntentType.RELATIONSHIP: RetrievalStrategy.GRAPH_ONLY,
            IntentType.SOURCE_RECALL: RetrievalStrategy.GRAPH_FIRST,
            IntentType.SEMANTIC_SEARCH: RetrievalStrategy.VECTOR_FIRST,
            IntentType.INVENTORY: RetrievalStrategy.GRAPH_ONLY,
            IntentType.GENERAL: RetrievalStrategy.LLM_ONLY,
        }
        return mapping.get(intent.intent, RetrievalStrategy.HYBRID)
    
    async def _execute_strategy(
        self,
        strategy: RetrievalStrategy,
        query: str,
        context: AgentContext,
        intent: IntentClassification,
    ) -> dict:
        """
        Execute the selected retrieval strategy with fallbacks.
        
        Returns dict with:
        - source: 'graph', 'vector', or 'llm_knowledge'
        - results: Retrieved data
        - fallback_chain: List of sources tried
        """
        fallback_chain = []
        
        if strategy == RetrievalStrategy.LLM_ONLY:
            return {
                "source": "llm_knowledge",
                "results": [],
                "fallback_chain": fallback_chain,
            }

        vector_document_ids = await self._resolve_vector_document_scope(
            context, intent
        )
        
        if strategy in (RetrievalStrategy.GRAPH_FIRST, RetrievalStrategy.GRAPH_ONLY):
            # Try graph first
            fallback_chain.append("graph")
            graph_results = await self._query_graph(query, context, intent)
            
            if graph_results:
                # GRAPH_FIRST: also query vector to supplement with actual content
                if strategy == RetrievalStrategy.GRAPH_FIRST:
                    fallback_chain.append("vector")
                    vector_results = await self._query_vector(
                        query,
                        context,
                        document_ids=vector_document_ids,
                    )
                    
                    return {
                        "source": "graph_and_vector" if vector_results else "graph",
                        "results": {
                            "graph": graph_results,
                            "vector": vector_results or [],
                        } if vector_results else graph_results,
                        "fallback_chain": fallback_chain,
                    }
                
                # GRAPH_ONLY: return graph results only
                return {
                    "source": "graph",
                    "results": graph_results,
                    "fallback_chain": fallback_chain,
                }
            
            # Fallback to vector (unless GRAPH_ONLY)
            if strategy == RetrievalStrategy.GRAPH_FIRST:
                fallback_chain.append("vector")
                vector_results = await self._query_vector(
                    query,
                    context,
                    document_ids=vector_document_ids,
                )
                
                if vector_results:
                    return {
                        "source": "vector",
                        "results": vector_results,
                        "fallback_chain": fallback_chain,
                    }
        
        elif strategy == RetrievalStrategy.VECTOR_FIRST:
            # Try vector first
            fallback_chain.append("vector")
            vector_results = await self._query_vector(
                query,
                context,
                document_ids=vector_document_ids,
            )
            
            if vector_results:
                # Enrich with graph data
                fallback_chain.append("graph")
                graph_enrichment = await self._enrich_with_graph(
                    vector_results, context, intent
                )
                
                return {
                    "source": "vector",
                    "results": vector_results,
                    "graph_enrichment": graph_enrichment,
                    "fallback_chain": fallback_chain,
                }
            
            # Fallback to graph
            fallback_chain.append("graph")
            graph_results = await self._query_graph(query, context, intent)
            
            if graph_results:
                return {
                    "source": "graph",
                    "results": graph_results,
                    "fallback_chain": fallback_chain,
                }
        
        elif strategy == RetrievalStrategy.HYBRID:
            # Execute both in parallel (simplified - sequential for now)
            fallback_chain.extend(["graph", "vector"])
            
            graph_results = await self._query_graph(query, context, intent)
            vector_results = await self._query_vector(
                query,
                context,
                document_ids=vector_document_ids,
            )
            
            if graph_results or vector_results:
                return {
                    "source": "hybrid",
                    "results": {
                        "graph": graph_results,
                        "vector": vector_results,
                    },
                    "fallback_chain": fallback_chain,
                }
        
        # Ultimate fallback: LLM knowledge
        fallback_chain.append("llm_knowledge")
        return {
            "source": "llm_knowledge",
            "results": [],
            "fallback_chain": fallback_chain,
        }
    
    async def _query_graph(
        self,
        query: str,
        context: AgentContext,
        intent: IntentClassification,
    ) -> list[dict]:
        """
        Query the knowledge graph based on intent and entities.
        
        Returns structured graph data AND the actual chunk text linked
        to concepts via definedIn/mentionedIn, so the synthesizer has
        rich textual evidence (not just labels and relationship names).
        """
        try:
            results = []
            
            # Special handling for INVENTORY intent - list all concepts
            if intent.intent == IntentType.INVENTORY:
                return await self._query_inventory(context)

            # SOURCE_RECALL is primarily source-filter driven.
            if intent.intent == IntentType.SOURCE_RECALL and intent.source_filter:
                return await self._query_source_recall(
                    context=context,
                    source_filter=intent.source_filter,
                    entity_terms=intent.entities,
                )
            
            # Look up each entity, expanding synonyms at query time
            for entity in intent.entities:
                concept_uri = None
                
                # Try the original term and all its synonyms
                search_terms = expand_synonyms(entity)
                for term in search_terms:
                    concept_uri = await context.fuseki_store.concept_exists(
                        context.user_id, term
                    )
                    if concept_uri:
                        break
                
                if not concept_uri:
                    # Try fuzzy match as last resort
                    for term in search_terms:
                        similar = await context.fuseki_store.find_similar_concepts(
                            context.user_id, term, limit=3
                        )
                        if similar:
                            concept_uri = similar[0].get("concept")
                            break
                
                if concept_uri:
                    details = await context.fuseki_store.get_concept_with_definition(
                        context.user_id, concept_uri
                    )
                    relationships = await context.fuseki_store.get_concept_relationships(
                        context.user_id, concept_uri
                    )
                    
                    # Fetch chunk text linked to this concept for richer context
                    chunk_texts = await self._fetch_concept_chunks(
                        context, concept_uri
                    )
                    
                    results.append({
                        "uri": concept_uri,
                        "entity": entity,
                        "details": details,
                        "relationships": relationships,
                        "chunk_texts": chunk_texts,
                    })
            
            return results
            
        except Exception as e:
            logger.error("Graph query failed", error=str(e))
            return []

    @staticmethod
    def _escape_sparql_literal(value: str) -> str:
        """Escape a string so it is safe inside SPARQL quoted literals."""
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
        )

    async def _resolve_source_document_ids(
        self,
        context: AgentContext,
        source_filter: str,
    ) -> list[str]:
        """Find document IDs in the user's graph whose source title matches a filter."""
        if not source_filter.strip():
            return []

        source_term = self._escape_sparql_literal(source_filter.lower().strip())
        sparql = f"""
        SELECT DISTINCT ?documentId
        WHERE {{
            ?source a syn:Source ;
                    syn:sourceTitle ?sourceTitle ;
                    syn:documentId ?documentId .
            FILTER(CONTAINS(LCASE(?sourceTitle), "{source_term}"))
        }}
        LIMIT 100
        """

        rows = await context.fuseki_store.query(
            user_id=context.user_id,
            sparql=sparql,
        )
        return [row["documentId"] for row in rows if row.get("documentId")]

    async def _resolve_vector_document_scope(
        self,
        context: AgentContext,
        intent: IntentClassification,
    ) -> Optional[list[str]]:
        """
        Build vector document constraints from intent.

        Returning:
        - `None`: no document constraint
        - `[]`: constrained but no matching sources (vector query should return empty)
        - `[doc_id, ...]`: constrain vector search to these sources
        """
        if not intent.source_filter:
            return None

        try:
            document_ids = await self._resolve_source_document_ids(
                context=context,
                source_filter=intent.source_filter,
            )
            logger.info(
                "Resolved source filter to document scope",
                source_filter=intent.source_filter,
                document_count=len(document_ids),
            )
            return document_ids
        except Exception as e:
            logger.warning(
                "Failed to resolve source filter for vector scope",
                source_filter=intent.source_filter,
                error=str(e),
            )
            return None

    async def _query_source_recall(
        self,
        context: AgentContext,
        source_filter: str,
        entity_terms: list[str],
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Query concepts/chunks that came from sources matching `source_filter`."""
        source_term = self._escape_sparql_literal(source_filter.lower().strip())
        entity_filters: list[str] = []
        for term in entity_terms:
            normalized = term.lower().strip()
            if not normalized:
                continue
            escaped = self._escape_sparql_literal(normalized)
            entity_filters.append(f'CONTAINS(LCASE(?label), "{escaped}")')
            entity_filters.append(
                f'CONTAINS(LCASE(COALESCE(?definitionText, "")), "{escaped}")'
            )

        entity_filter_clause = ""
        if entity_filters:
            entity_filter_clause = f"FILTER({' || '.join(entity_filters)})"

        sparql = f"""
        SELECT ?concept ?label ?definitionText ?sourceTitle ?sourceUrl ?chunkText ?linkType
        WHERE {{
            ?source a syn:Source ;
                    syn:sourceTitle ?sourceTitle .
            OPTIONAL {{ ?source syn:sourceUrl ?sourceUrl }}
            FILTER(CONTAINS(LCASE(?sourceTitle), "{source_term}"))

            ?chunk syn:derivedFrom ?source .
            {{
                ?concept syn:definedIn ?chunk .
                BIND("defined" AS ?linkType)
            }}
            UNION
            {{
                ?concept syn:mentionedIn ?chunk .
                BIND("mentioned" AS ?linkType)
            }}

            ?concept a syn:Concept ;
                     syn:label ?label .
            OPTIONAL {{
                ?concept syn:hasDefinition ?def .
                ?def syn:definitionText ?definitionText .
            }}
            OPTIONAL {{ ?chunk syn:chunkText ?chunkText }}
            {entity_filter_clause}
        }}
        ORDER BY ?label
        LIMIT {max(limit * 6, 100)}
        """

        rows = await context.fuseki_store.query(
            user_id=context.user_id,
            sparql=sparql,
        )
        if not rows:
            return []

        concepts: dict[str, dict[str, Any]] = {}
        for row in rows:
            concept_uri = row.get("concept")
            if not concept_uri:
                continue

            concept = concepts.setdefault(
                concept_uri,
                {
                    "uri": concept_uri,
                    "entity": row.get("label", "Unknown"),
                    "details": {
                        "label": row.get("label"),
                        "definitionText": row.get("definitionText"),
                        "sourceTitle": row.get("sourceTitle"),
                        "sourceUrl": row.get("sourceUrl"),
                    },
                    "relationships": [],
                    "chunk_texts": [],
                },
            )

            if row.get("definitionText") and not concept["details"].get("definitionText"):
                concept["details"]["definitionText"] = row.get("definitionText")
            if row.get("sourceTitle") and not concept["details"].get("sourceTitle"):
                concept["details"]["sourceTitle"] = row.get("sourceTitle")
            if row.get("sourceUrl") and not concept["details"].get("sourceUrl"):
                concept["details"]["sourceUrl"] = row.get("sourceUrl")

            chunk_text = row.get("chunkText", "")
            if chunk_text:
                concept["chunk_texts"].append(
                    {
                        "text": chunk_text,
                        "source_title": row.get("sourceTitle", ""),
                        "source_url": row.get("sourceUrl", ""),
                        "link_type": row.get("linkType", "mentioned"),
                    }
                )

        results = list(concepts.values())[:limit]
        for concept in results:
            concept["chunk_texts"].sort(
                key=lambda chunk: 0 if chunk["link_type"] == "defined" else 1
            )
        return results

    async def _fetch_concept_chunks(
        self,
        context: AgentContext,
        concept_uri: str,
        max_chunks: int = 5,
    ) -> list[dict]:
        """
        Fetch the actual chunk text linked to a concept via definedIn
        and mentionedIn. This bridges the gap between structured graph
        data and rich textual evidence for the synthesizer.
        """
        try:
            sparql = f"""
            SELECT ?chunkText ?sourceTitle ?sourceUrl ?linkType
            WHERE {{
                {{
                    <{concept_uri}> syn:definedIn ?chunk .
                    ?chunk syn:chunkText ?chunkText .
                    BIND("defined" AS ?linkType)
                }}
                UNION
                {{
                    <{concept_uri}> syn:mentionedIn ?chunk .
                    ?chunk syn:chunkText ?chunkText .
                    BIND("mentioned" AS ?linkType)
                }}
                OPTIONAL {{
                    ?chunk syn:derivedFrom ?source .
                    ?source syn:sourceTitle ?sourceTitle .
                    ?source syn:sourceUrl ?sourceUrl .
                }}
            }}
            LIMIT {max_chunks}
            """
            
            results = await context.fuseki_store.query(
                user_id=context.user_id,
                sparql=sparql,
            )
            
            chunks = []
            for r in results:
                chunks.append({
                    "text": r.get("chunkText", ""),
                    "source_title": r.get("sourceTitle", ""),
                    "source_url": r.get("sourceUrl", ""),
                    "link_type": r.get("linkType", "mentioned"),
                })
            
            # Sort so "defined" chunks come first (more relevant)
            chunks.sort(key=lambda c: 0 if c["link_type"] == "defined" else 1)
            
            return chunks
            
        except Exception as e:
            logger.warning("Failed to fetch concept chunks", error=str(e))
            return []
    
    async def _query_inventory(self, context: AgentContext) -> list[dict]:
        """Query all concepts for inventory/overview requests."""
        try:
            # SPARQL to get all concepts with definitions
            sparql = """
            SELECT DISTINCT ?label ?definitionText ?sourceTitle
            WHERE {
                ?concept a syn:Concept .
                ?concept syn:label ?label .
                OPTIONAL {
                    ?concept syn:hasDefinition ?def .
                    ?def syn:definitionText ?definitionText .
                }
                OPTIONAL {
                    ?concept syn:definedIn ?chunk .
                    ?chunk syn:derivedFrom ?source .
                    ?source syn:sourceTitle ?sourceTitle .
                }
            }
            ORDER BY ?label
            LIMIT 50
            """
            
            query_results = await context.fuseki_store.query(
                user_id=context.user_id,
                sparql=sparql,
            )
            
            logger.info("Inventory query complete", result_count=len(query_results))
            
            # Format results - FusekiStore.query() already extracts values from bindings
            results = []
            for r in query_results:
                results.append({
                    "entity": r.get("label", "Unknown"),
                    "details": {
                        "definitionText": r.get("definitionText"),
                        "sourceTitle": r.get("sourceTitle"),
                    },
                    "relationships": [],
                })
            
            return results
            
        except Exception as e:
            logger.error("Inventory query failed", error=str(e))
            return []
    
    async def _query_vector(
        self,
        query: str,
        context: AgentContext,
        document_ids: Optional[list[str]] = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Query the vector store for similar content."""
        try:
            if document_ids == []:
                logger.info("Vector query skipped: constrained source scope has no documents")
                return []

            # Generate query embedding
            query_vector = await context.embedding_generator.generate_single(query)
            
            # Search
            results = await context.qdrant_store.search(
                query_vector=query_vector,
                user_id=context.user_id,
                limit=top_k,
                document_ids=document_ids,
            )
            
            logger.info("Vector search results", count=len(results), results=results)
            
            return results
            
        except Exception as e:
            logger.error("Vector query failed", error=str(e))
            return []
    
    async def _enrich_with_graph(
        self,
        vector_results: list[dict],
        context: AgentContext,
        intent: IntentClassification,
    ) -> list[dict]:
        """Enrich vector results with graph data."""
        enrichments = []
        
        # Extract concepts mentioned in vector results
        for result in vector_results[:3]:  # Limit to top 3
            concepts = result.get("payload", {}).get("concepts", [])
            
            for concept in concepts[:2]:  # Limit concepts per result
                try:
                    concept_uri = await context.fuseki_store.concept_exists(
                        context.user_id, concept
                    )
                    if concept_uri:
                        details = await context.fuseki_store.get_concept_with_definition(
                            context.user_id, concept_uri
                        )
                        if details:
                            enrichments.append({
                                "concept": concept,
                                "details": details,
                            })
                except Exception:
                    pass
        
        return enrichments
    
    def _extract_sources_from_retrieval(
        self,
        retrieval_results: dict,
    ) -> list[dict]:
        """Extract source information from retrieval results."""
        sources = []
        source = retrieval_results.get("source", "")
        results = retrieval_results.get("results", [])
        
        if source == "vector":
            for r in results:
                payload = r.get("payload", {})
                sources.append({
                    "title": payload.get("source_title", ""),
                    "url": payload.get("source_url", ""),
                    "type": payload.get("source_type", ""),
                    "text": payload.get("text", "")[:200],
                    "timestamp": payload.get("timestamp_start_ms"),
                })
        elif source == "graph":
            for r in results:
                details = r.get("details", {})
                sources.append({
                    "title": details.get("sourceTitle", "") or r.get("entity", ""),
                    "url": details.get("sourceUrl", ""),
                    "type": "graph",
                    "text": details.get("definitionText", "")[:200] if details.get("definitionText") else "",
                })
        elif source == "graph_and_vector":
            graph = results.get("graph", [])
            vector = results.get("vector", [])
            for r in graph:
                details = r.get("details", {})
                sources.append({
                    "title": details.get("sourceTitle", "") or r.get("entity", ""),
                    "url": details.get("sourceUrl", ""),
                    "type": "graph",
                    "text": details.get("definitionText", "")[:200] if details.get("definitionText") else "",
                })
            for r in vector:
                payload = r.get("payload", {})
                sources.append({
                    "title": payload.get("source_title", ""),
                    "url": payload.get("source_url", ""),
                    "type": payload.get("source_type", ""),
                    "text": payload.get("text", "")[:200],
                    "timestamp": payload.get("timestamp_start_ms"),
                })
        elif source == "hybrid":
            vector = results.get("vector", [])
            graph = results.get("graph", [])
            for r in vector:
                payload = r.get("payload", {})
                sources.append({
                    "title": payload.get("source_title", ""),
                    "url": payload.get("source_url", ""),
                    "type": payload.get("source_type", ""),
                    "text": payload.get("text", "")[:200],
                })
            for r in graph:
                details = r.get("details", {})
                sources.append({
                    "title": details.get("sourceTitle", "") or r.get("entity", ""),
                    "url": details.get("sourceUrl", ""),
                    "type": "graph",
                    "text": details.get("definitionText", "")[:200] if details.get("definitionText") else "",
                })
        
        return sources
    
    def _enrich_citations(
        self,
        response: QueryResponse,
        retrieval_results: dict,
    ) -> QueryResponse:
        """
        Enrich citations with actual source information from retrieval.
        
        The LLM synthesizer may not correctly populate source titles,
        so we post-process to inject actual source info from retrieval results.
        """
        sources = self._extract_sources_from_retrieval(retrieval_results)
        
        if not sources or not response.citations:
            return response
        
        # Map citations to sources by index
        for i, citation in enumerate(response.citations):
            if i < len(sources):
                src = sources[i]
                # Only replace if LLM didn't provide a good title
                if not citation.title or citation.title == "Unknown" or len(citation.title) < 3:
                    citation.title = src.get("title") or citation.title
                # Always set URL if available and not already set
                if not citation.url and src.get("url"):
                    citation.url = src.get("url")
                # Set source type if not set
                if not citation.source_type or citation.source_type == "unknown":
                    citation.source_type = src.get("type", "unknown")
        
        return response
    
    def _format_synthesis_input(
        self,
        query: str,
        intent: IntentClassification,
        retrieval_results: dict,
    ) -> str:
        """Format input for the response synthesizer."""
        parts = [
            f"## User Query\n{query}",
            f"\n## Intent Classification\n- Type: {intent.intent.value}\n- Entities: {', '.join(intent.entities)}\n- Confidence: {intent.confidence}",
        ]
        
        source = retrieval_results.get("source", "llm_knowledge")
        results = retrieval_results.get("results", [])
        
        if source == "graph":
            parts.append("\n## Graph Results")
            for r in results:
                parts.append(f"\n### Concept: {r.get('entity', 'Unknown')}")
                details = r.get("details", {})
                if details:
                    if details.get("definitionText"):
                        parts.append(f"Definition: {details['definitionText']}")
                    if details.get("sourceTitle"):
                        parts.append(f"Source: {details['sourceTitle']}")
                
                relationships = r.get("relationships", [])
                if relationships:
                    parts.append("Relationships:")
                    for rel in relationships[:5]:
                        parts.append(f"  - {rel.get('relationType', '?')} → {rel.get('relatedLabel', '?')}")
                
                # Include chunk text from the graph for richer context
                chunk_texts = r.get("chunk_texts", [])
                if chunk_texts:
                    parts.append("\nRelevant passages from your knowledge base:")
                    for ct in chunk_texts[:3]:
                        link_label = "Defines" if ct.get("link_type") == "defined" else "Mentions"
                        parts.append(f"\n[{link_label}] {ct.get('text', '')[:500]}")
                        if ct.get("source_title"):
                            parts.append(f"  — Source: {ct['source_title']}")
        
        elif source == "vector":
            parts.append("\n## Vector Results")
            for i, r in enumerate(results, 1):
                payload = r.get("payload", {})
                parts.append(f"\n### Result {i} (score: {r.get('score', 0):.2f})")
                parts.append(f"Text: {payload.get('text', '')[:500]}...")
                if payload.get("source_title"):
                    parts.append(f"Source: {payload['source_title']}")
                if payload.get("source_url"):
                    parts.append(f"URL: {payload['source_url']}")
        
        elif source == "graph_and_vector":
            parts.append("\n## Knowledge Graph Results")
            graph = results.get("graph", [])
            vector = results.get("vector", [])
            
            for r in graph:
                parts.append(f"\n### Concept: {r.get('entity', 'Unknown')}")
                details = r.get("details", {})
                if details:
                    if details.get("definitionText"):
                        parts.append(f"Definition: {details['definitionText']}")
                    if details.get("sourceTitle"):
                        parts.append(f"Source: {details['sourceTitle']}")
                relationships = r.get("relationships", [])
                if relationships:
                    parts.append("Relationships:")
                    for rel in relationships[:5]:
                        parts.append(f"  - {rel.get('relationType', '?')} → {rel.get('relatedLabel', '?')}")
                
                chunk_texts = r.get("chunk_texts", [])
                if chunk_texts:
                    parts.append("\nRelevant passages from your knowledge base:")
                    for ct in chunk_texts[:3]:
                        link_label = "Defines" if ct.get("link_type") == "defined" else "Mentions"
                        parts.append(f"\n[{link_label}] {ct.get('text', '')[:500]}")
                        if ct.get("source_title"):
                            parts.append(f"  — Source: {ct['source_title']}")
            
            if vector:
                parts.append("\n## Related Content from Notes")
                for i, r in enumerate(vector, 1):
                    payload = r.get("payload", {})
                    parts.append(f"\n### Excerpt {i} (score: {r.get('score', 0):.2f})")
                    parts.append(f"Text: {payload.get('text', '')[:500]}...")
                    if payload.get("source_title"):
                        parts.append(f"Source: {payload['source_title']}")
        
        elif source == "hybrid":
            parts.append("\n## Combined Results")
            graph = results.get("graph", [])
            vector = results.get("vector", [])
            
            if graph:
                parts.append("\n### From Knowledge Graph:")
                for r in graph:
                    details = r.get("details", {}) or {}
                    parts.append(f"- {r.get('entity', 'Unknown')}: {details.get('definitionText', 'No definition')[:200]}")
                    chunk_texts = r.get("chunk_texts", [])
                    for ct in chunk_texts[:2]:
                        parts.append(f"  Passage: {ct.get('text', '')[:300]}")
            
            if vector:
                parts.append("\n### From Vector Search:")
                for r in vector[:3]:
                    payload = r.get("payload", {})
                    parts.append(f"- {payload.get('text', '')[:200]}...")
        
        elif source == "llm_knowledge":
            parts.append("\n## No Results from Personal Knowledge Base")
            parts.append("Please answer based on general knowledge and indicate that this is not from the user's notes.")
        
        parts.append(f"\n## Retrieval Metadata\n- Source: {source}\n- Fallback Chain: {' → '.join(retrieval_results.get('fallback_chain', []))}")
        
        return "\n".join(parts)
    
    async def query(
        self,
        user_id: str,
        query: str,
        session_id: str,
    ) -> QueryResponse:
        """
        Execute a query against the user's knowledge base.
        
        Args:
            user_id: User identifier
            query: Natural language query
            session_id: Conversation session ID
            
        Returns:
            QueryResponse with answer, citations, and metadata
        """
        logger.info(
            "Query agent processing",
            user_id=user_id,
            query=query[:50],
            session_id=session_id,
        )
        
        # Create context
        context = self._create_context(user_id)
        
        # Get session for conversation history
        session = await get_session(session_id, user_id)
        
        try:
            # Step 1: Classify intent
            intent_result = await Runner.run(
                self.intent_classifier,
                query,
                context=context,
            )
            intent: IntentClassification = intent_result.final_output
            
            logger.info(
                "Intent classified",
                intent=intent.intent.value,
                entities=intent.entities,
                confidence=intent.confidence,
            )
            
            # Step 2: Select strategy
            strategy = self._select_strategy(intent)
            logger.info("Strategy selected", strategy=strategy.value)
            
            # Step 3: Execute retrieval
            retrieval_results = await self._execute_strategy(
                strategy, query, context, intent
            )
            
            retrieval_source = retrieval_results.get("source")
            raw_results = retrieval_results.get("results", [])
            if isinstance(raw_results, dict):
                result_count = sum(
                    len(v) for v in raw_results.values() if isinstance(v, list)
                )
            else:
                result_count = len(raw_results)
            
            logger.info(
                "Retrieval complete",
                source=retrieval_source,
                result_count=result_count,
            )
            
            # Step 4: Synthesize response with session for history
            synthesis_input = self._format_synthesis_input(
                query, intent, retrieval_results
            )
            
            response_result = await Runner.run(
                self.synthesizer,
                synthesis_input,
                context=context,
                session=session,
            )
            
            response: QueryResponse = response_result.final_output
            
            # Post-process citations to inject actual source titles from retrieval
            response = self._enrich_citations(response, retrieval_results)
            
            # Add retrieval metadata
            response.retrieval_metadata = RetrievalMetadata(
                retrieval_source=retrieval_results.get("source", "llm_knowledge"),
                fallback_chain=retrieval_results.get("fallback_chain", []),
                has_citations=len(response.citations) > 0,
                confidence=response.confidence,
            )
            
            logger.info(
                "Query complete",
                source_type=response.source_type,
                citation_count=len(response.citations),
                confidence=response.confidence,
            )
            
            return response
            
        except Exception as e:
            logger.error("Query failed", error=str(e))
            # Return a fallback response
            return QueryResponse(
                answer=f"I apologize, but I encountered an error while processing your query. Please try again.",
                citations=[],
                concepts_referenced=[],
                confidence=0.0,
                source_type="error",
                retrieval_metadata=RetrievalMetadata(
                    retrieval_source="error",
                    fallback_chain=[],
                    has_citations=False,
                    confidence=0.0,
                ),
            )
    
    async def query_stream(
        self,
        user_id: str,
        query: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        Execute a query with streaming response.
        
        Args:
            user_id: User identifier
            query: Natural language query
            session_id: Conversation session ID
            
        Yields:
            Streaming response chunks
        """
        logger.info(
            "Query agent streaming",
            user_id=user_id,
            query=query[:50],
            session_id=session_id,
        )
        
        # Create context
        context = self._create_context(user_id)
        
        # Get session
        session = await get_session(session_id, user_id)
        
        try:
            # Step 1: Classify intent (non-streaming)
            intent_result = await Runner.run(
                self.intent_classifier,
                query,
                context=context,
            )
            intent: IntentClassification = intent_result.final_output
            
            # Step 2: Select strategy
            strategy = self._select_strategy(intent)
            
            # Step 3: Execute retrieval
            retrieval_results = await self._execute_strategy(
                strategy, query, context, intent
            )
            
            # Step 4: Stream synthesis response
            synthesis_input = self._format_synthesis_input(
                query, intent, retrieval_results
            )
            
            # Use streaming runner
            async with Runner.run_streamed(
                self.orchestrator,  # Use orchestrator for streaming
                synthesis_input,
                context=context,
                session=session,
            ) as stream:
                async for event in stream.stream_events():
                    # Yield text delta events
                    if hasattr(event, 'data') and hasattr(event.data, 'delta'):
                        yield event.data.delta
            
        except Exception as e:
            logger.error("Streaming query failed", error=str(e))
            yield f"Error: {str(e)}"
    
    async def close(self):
        """Close underlying connections."""
        await self.fuseki.close()
        await self.qdrant.close()
        logger.info("QueryAgent closed")
