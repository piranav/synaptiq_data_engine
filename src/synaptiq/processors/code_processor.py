"""
Code block processor for multimodal knowledge extraction.

Processes code blocks into:
1. Language detection
2. Natural language explanation
3. Extracted concepts (functions, imports, patterns)
4. Mermaid diagram parsing (for mermaid blocks)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from config.settings import get_settings
from synaptiq.processors.content_splitter import ContentBlock, ContentType

logger = structlog.get_logger(__name__)


@dataclass
class CodeExtractionResult:
    """Result of code processing."""
    language: str
    raw_code: str
    explanation: str
    extracted_concepts: list[str]
    combined_text: str
    
    # Mermaid-specific
    is_mermaid: bool = False
    mermaid_type: Optional[str] = None
    mermaid_components: list[str] = field(default_factory=list)
    mermaid_relationships: list[dict] = field(default_factory=list)


class CodeProcessor:
    """
    Processes code blocks for knowledge extraction.
    
    Creates:
    1. Natural language explanation
    2. Extracted concepts (function names, imports, etc.)
    3. For mermaid: parsed diagram structure
    """
    
    CODE_EXPLANATION_PROMPT = """Explain this code in plain English.

LANGUAGE: {language}

CODE:
```{language}
{code}
```

CONTEXT:
{context}

Provide a clear, concise explanation (2-3 sentences) that:
1. Describes what the code does
2. Mentions key functions, classes, or patterns used
3. Explains the purpose in the context of the note

Respond with just the explanation, no preamble."""

    MERMAID_ANALYSIS_PROMPT = """Analyze this Mermaid diagram.

DIAGRAM:
```mermaid
{code}
```

CONTEXT:
{context}

Provide:
1. A natural language description of what the diagram shows
2. The type of diagram (flowchart, sequence, class, state, etc.)

Respond in JSON format:
{{
    "description": "Description of the diagram",
    "type": "flowchart|sequence|class|state|er|gantt|pie|other",
    "main_topic": "The main subject of the diagram"
}}"""

    def __init__(self, model: str = "gpt-4.1"):
        """
        Initialize the code processor.
        
        Args:
            model: OpenAI model for explanation generation
        """
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.model = model
    
    async def process(self, block: ContentBlock) -> CodeExtractionResult:
        """
        Process a code content block.
        
        Args:
            block: ContentBlock with type CODE or MERMAID
            
        Returns:
            CodeExtractionResult with explanation and concepts
        """
        if block.type not in (ContentType.CODE, ContentType.MERMAID):
            raise ValueError(f"Expected CODE or MERMAID block, got {block.type}")
        
        language = block.metadata.get("language", "")
        is_mermaid = block.type == ContentType.MERMAID or language == "mermaid"
        
        logger.info(
            "Processing code block",
            language=language,
            is_mermaid=is_mermaid,
            length=len(block.content),
        )
        
        if is_mermaid:
            return await self._process_mermaid(block)
        else:
            return await self._process_code(block)
    
    async def _process_code(self, block: ContentBlock) -> CodeExtractionResult:
        """Process a regular code block."""
        language = block.metadata.get("language", "unknown")
        
        # 1. Generate explanation
        explanation = await self._generate_explanation(
            block.content,
            language,
            block.context_before,
            block.context_after,
        )
        
        # 2. Extract concepts
        concepts = self._extract_code_concepts(block.content, language)
        
        # 3. Build combined text
        combined_text = self._build_combined_text(block, explanation)
        
        return CodeExtractionResult(
            language=language,
            raw_code=block.content,
            explanation=explanation,
            extracted_concepts=concepts,
            combined_text=combined_text,
        )
    
    async def _process_mermaid(self, block: ContentBlock) -> CodeExtractionResult:
        """Process a mermaid diagram block."""
        # 1. Parse mermaid structure
        mermaid_type = self._detect_mermaid_type(block.content)
        components = self._extract_mermaid_components(block.content)
        relationships = self._extract_mermaid_relationships(block.content)
        
        # 2. Generate explanation via LLM
        explanation = await self._generate_mermaid_explanation(
            block.content,
            block.context_before,
            block.context_after,
        )
        
        # 3. Build combined text
        combined_text = self._build_combined_text(
            block,
            f"Mermaid {mermaid_type} diagram: {explanation}",
        )
        
        return CodeExtractionResult(
            language="mermaid",
            raw_code=block.content,
            explanation=explanation,
            extracted_concepts=components,
            combined_text=combined_text,
            is_mermaid=True,
            mermaid_type=mermaid_type,
            mermaid_components=components,
            mermaid_relationships=relationships,
        )
    
    async def _generate_explanation(
        self,
        code: str,
        language: str,
        context_before: str,
        context_after: str,
    ) -> str:
        """Generate code explanation using LLM."""
        try:
            context = f"Before: {context_before}\nAfter: {context_after}" if (context_before or context_after) else "(no context)"
            
            prompt = self.CODE_EXPLANATION_PROMPT.format(
                language=language or "unknown",
                code=code[:2000],  # Limit code length
                context=context,
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.warning("Failed to generate code explanation", error=str(e))
            return f"Code block in {language or 'unknown language'}"
    
    async def _generate_mermaid_explanation(
        self,
        code: str,
        context_before: str,
        context_after: str,
    ) -> str:
        """Generate mermaid diagram explanation."""
        try:
            context = f"Before: {context_before}\nAfter: {context_after}" if (context_before or context_after) else "(no context)"
            
            prompt = self.MERMAID_ANALYSIS_PROMPT.format(
                code=code,
                context=context,
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            import json
            try:
                result = json.loads(content)
                return result.get("description", content)
            except json.JSONDecodeError:
                return content
        
        except Exception as e:
            logger.warning("Failed to generate mermaid explanation", error=str(e))
            return "Mermaid diagram"
    
    def _extract_code_concepts(self, code: str, language: str) -> list[str]:
        """Extract concepts from code (function names, imports, etc.)."""
        concepts = set()
        
        # Python patterns
        if language in ("python", "py"):
            # Function definitions
            for match in re.finditer(r"def\s+(\w+)", code):
                concepts.add(match.group(1))
            
            # Class definitions
            for match in re.finditer(r"class\s+(\w+)", code):
                concepts.add(match.group(1))
            
            # Imports
            for match in re.finditer(r"import\s+(\w+)", code):
                concepts.add(match.group(1))
            for match in re.finditer(r"from\s+(\w+)", code):
                concepts.add(match.group(1))
        
        # JavaScript/TypeScript patterns
        elif language in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
            # Function definitions
            for match in re.finditer(r"function\s+(\w+)", code):
                concepts.add(match.group(1))
            
            # Arrow functions assigned to const/let/var
            for match in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=])\s*=>", code):
                concepts.add(match.group(1))
            
            # Class definitions
            for match in re.finditer(r"class\s+(\w+)", code):
                concepts.add(match.group(1))
            
            # Imports
            for match in re.finditer(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", code):
                module = match.group(1).split("/")[-1]
                concepts.add(module)
        
        # General patterns for any language
        # CamelCase identifiers
        for match in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", code):
            concepts.add(match.group(1))
        
        return list(concepts)
    
    def _detect_mermaid_type(self, code: str) -> str:
        """Detect the type of mermaid diagram."""
        code_lower = code.strip().lower()
        
        if code_lower.startswith(("graph ", "flowchart ")):
            return "flowchart"
        elif code_lower.startswith("sequencediagram"):
            return "sequence"
        elif code_lower.startswith("classdiagram"):
            return "class"
        elif code_lower.startswith("statediagram"):
            return "state"
        elif code_lower.startswith("erdiagram"):
            return "er"
        elif code_lower.startswith("gantt"):
            return "gantt"
        elif code_lower.startswith("pie"):
            return "pie"
        elif code_lower.startswith("mindmap"):
            return "mindmap"
        elif code_lower.startswith("timeline"):
            return "timeline"
        else:
            return "unknown"
    
    def _extract_mermaid_components(self, code: str) -> list[str]:
        """Extract node/component names from mermaid diagram."""
        components = set()
        
        # Match node definitions like A[Label] or A(Label) or A{Label}
        for match in re.finditer(r"(\w+)[\[\(\{]([^\]\)\}]+)[\]\)\}]", code):
            node_id = match.group(1)
            label = match.group(2)
            components.add(label.strip())
        
        # Match simple node references
        for match in re.finditer(r"^\s*(\w+)\s*$", code, re.MULTILINE):
            components.add(match.group(1))
        
        return list(components)
    
    def _extract_mermaid_relationships(self, code: str) -> list[dict]:
        """Extract relationships/edges from mermaid diagram."""
        relationships = []
        
        # Common arrow patterns
        arrow_patterns = [
            r"(\w+)\s*-->\s*(\w+)",           # A --> B
            r"(\w+)\s*--->\s*(\w+)",          # A ---> B
            r"(\w+)\s*--\s*([^-]+)\s*-->\s*(\w+)",   # A -- label --> B
            r"(\w+)\s*==>\s*(\w+)",           # A ==> B
            r"(\w+)\s*-\.->\s*(\w+)",         # A -.-> B
        ]
        
        for pattern in arrow_patterns:
            for match in re.finditer(pattern, code):
                groups = match.groups()
                if len(groups) == 2:
                    relationships.append({
                        "from": groups[0],
                        "to": groups[1],
                        "label": None,
                    })
                elif len(groups) == 3:
                    relationships.append({
                        "from": groups[0],
                        "to": groups[2],
                        "label": groups[1].strip(),
                    })
        
        return relationships
    
    def _build_combined_text(self, block: ContentBlock, explanation: str) -> str:
        """Build combined text for embedding."""
        parts = []
        
        if block.context_before:
            parts.append(block.context_before)
        
        block_type = "MERMAID DIAGRAM" if block.type == ContentType.MERMAID else "CODE"
        parts.append(f"[{block_type}: {explanation}]")
        
        if block.context_after:
            parts.append(block.context_after)
        
        return " ".join(parts)
