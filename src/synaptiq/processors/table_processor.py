"""
Table processor for multimodal knowledge extraction.

Processes markdown/HTML tables into:
1. Structured JSON (for precise queries)
2. Natural language description (for semantic search)
3. Row-level facts (for fact retrieval)
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from config.settings import get_settings
from synaptiq.processors.content_splitter import ContentBlock, ContentType

logger = structlog.get_logger(__name__)


@dataclass
class TableStructure:
    """Parsed table structure."""
    headers: list[str]
    rows: list[dict[str, str]]
    row_count: int
    column_count: int
    raw_markdown: str


@dataclass
class TableExtractionResult:
    """Result of table processing."""
    structured: TableStructure
    description: str
    row_facts: list[str]
    combined_text: str
    concepts: list[str] = field(default_factory=list)


class TableProcessor:
    """
    Processes tables for knowledge extraction.
    
    Creates dual representation:
    1. Structured JSON for exact queries
    2. Natural language description for semantic search
    3. Row-level facts for fact retrieval
    """
    
    TABLE_DESCRIPTION_PROMPT = """Analyze this table and provide a natural language description.

TABLE:
{table_markdown}

CONTEXT BEFORE:
{context_before}

CONTEXT AFTER:
{context_after}

Provide a comprehensive description that:
1. Explains what the table is about
2. Summarizes the key information
3. Highlights any notable patterns or comparisons
4. Mentions the most important data points

Keep the description concise (2-4 sentences) but informative.
Focus on what someone would want to know when searching for this table.

Respond with just the description, no preamble."""

    ROW_FACTS_PROMPT = """Extract individual facts from each row of this table.

TABLE:
{table_markdown}

HEADERS: {headers}

For each row, create a simple factual statement that captures the key information.
These facts should be self-contained and understandable without seeing the table.

Format: Return a JSON array of strings, one fact per row.
Example: ["GPT-4 has 1.7 trillion parameters and 128K context window", "Claude 3 has 200K context window and is fast"]

Only output the JSON array, no other text."""

    def __init__(self, model: str = "gpt-4.1"):
        """
        Initialize the table processor.
        
        Args:
            model: OpenAI model for description generation
        """
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.model = model
    
    async def process(self, block: ContentBlock) -> TableExtractionResult:
        """
        Process a table content block.
        
        Args:
            block: ContentBlock with type TABLE
            
        Returns:
            TableExtractionResult with all representations
        """
        if block.type != ContentType.TABLE:
            raise ValueError(f"Expected TABLE block, got {block.type}")
        
        logger.info("Processing table", format=block.metadata.get("format", "unknown"))
        
        # 1. Parse to structured format
        if block.metadata.get("format") == "html":
            structured = self._parse_html_table(block.content)
        else:
            structured = self._parse_markdown_table(block.content)
        
        # 2. Generate natural language description
        description = await self._generate_description(
            structured.raw_markdown,
            block.context_before,
            block.context_after,
        )
        
        # 3. Extract row-level facts
        row_facts = await self._extract_row_facts(structured)
        
        # 4. Build combined text for embedding
        combined_text = self._build_combined_text(block, description)
        
        # 5. Extract concepts from description
        concepts = self._extract_concepts(description, structured)
        
        logger.info(
            "Table processed",
            rows=structured.row_count,
            cols=structured.column_count,
            facts=len(row_facts),
        )
        
        return TableExtractionResult(
            structured=structured,
            description=description,
            row_facts=row_facts,
            combined_text=combined_text,
            concepts=concepts,
        )
    
    def _parse_markdown_table(self, content: str) -> TableStructure:
        """Parse markdown table to structured format."""
        lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
        
        if len(lines) < 2:
            return TableStructure(
                headers=[],
                rows=[],
                row_count=0,
                column_count=0,
                raw_markdown=content,
            )
        
        # Parse header row
        headers = self._parse_table_row(lines[0])
        
        # Skip separator row (|---|---|)
        data_start = 1
        if len(lines) > 1 and re.match(r"^\|[\s\-:|]+\|$", lines[1]):
            data_start = 2
        
        # Parse data rows
        rows = []
        for line in lines[data_start:]:
            values = self._parse_table_row(line)
            if values:
                row_dict = {}
                for i, header in enumerate(headers):
                    if i < len(values):
                        row_dict[header] = values[i]
                    else:
                        row_dict[header] = ""
                rows.append(row_dict)
        
        return TableStructure(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers),
            raw_markdown=content,
        )
    
    def _parse_table_row(self, line: str) -> list[str]:
        """Parse a single table row."""
        # Remove leading/trailing pipes
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        
        # Split by pipe and clean
        cells = [cell.strip() for cell in line.split("|")]
        return cells
    
    def _parse_html_table(self, content: str) -> TableStructure:
        """Parse HTML table to structured format."""
        # Simple regex-based parsing (could use BeautifulSoup for complex cases)
        headers = []
        rows = []
        
        # Extract headers from <th> tags
        header_matches = re.findall(r"<th[^>]*>(.*?)</th>", content, re.IGNORECASE | re.DOTALL)
        headers = [self._clean_html(h) for h in header_matches]
        
        # Extract rows
        row_matches = re.findall(r"<tr[^>]*>(.*?)</tr>", content, re.IGNORECASE | re.DOTALL)
        for row_html in row_matches:
            cell_matches = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.IGNORECASE | re.DOTALL)
            if cell_matches:
                values = [self._clean_html(c) for c in cell_matches]
                if headers:
                    row_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(values):
                            row_dict[header] = values[i]
                        else:
                            row_dict[header] = ""
                    rows.append(row_dict)
                else:
                    # No headers, use indices
                    rows.append({str(i): v for i, v in enumerate(values)})
        
        # Convert to markdown for storage
        raw_markdown = self._to_markdown(headers, rows)
        
        return TableStructure(
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers) if headers else (len(rows[0]) if rows else 0),
            raw_markdown=raw_markdown,
        )
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        return re.sub(r"<[^>]+>", "", text).strip()
    
    def _to_markdown(self, headers: list[str], rows: list[dict]) -> str:
        """Convert structured table to markdown."""
        if not headers and not rows:
            return ""
        
        lines = []
        
        # Header row
        if headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # Data rows
        for row in rows:
            if headers:
                values = [str(row.get(h, "")) for h in headers]
            else:
                values = [str(v) for v in row.values()]
            lines.append("| " + " | ".join(values) + " |")
        
        return "\n".join(lines)
    
    async def _generate_description(
        self,
        table_markdown: str,
        context_before: str,
        context_after: str,
    ) -> str:
        """Generate natural language description using LLM."""
        try:
            prompt = self.TABLE_DESCRIPTION_PROMPT.format(
                table_markdown=table_markdown,
                context_before=context_before or "(no context)",
                context_after=context_after or "(no context)",
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.warning("Failed to generate table description", error=str(e))
            # Fallback to simple description
            return f"Table with {table_markdown.count('|') // 2} columns"
    
    async def _extract_row_facts(self, structured: TableStructure) -> list[str]:
        """Extract individual facts from each row."""
        if not structured.rows:
            return []
        
        try:
            prompt = self.ROW_FACTS_PROMPT.format(
                table_markdown=structured.raw_markdown,
                headers=", ".join(structured.headers),
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON array
            facts = json.loads(content)
            if isinstance(facts, list):
                return [str(f) for f in facts]
            return []
        
        except Exception as e:
            logger.warning("Failed to extract row facts", error=str(e))
            # Fallback: create simple facts from rows
            return self._fallback_row_facts(structured)
    
    def _fallback_row_facts(self, structured: TableStructure) -> list[str]:
        """Create simple facts from rows as fallback."""
        facts = []
        for row in structured.rows:
            if structured.headers and row:
                # Use first column as subject
                first_header = structured.headers[0]
                subject = row.get(first_header, "Item")
                
                # Build fact from other columns
                parts = []
                for header in structured.headers[1:]:
                    value = row.get(header, "")
                    if value:
                        parts.append(f"{header}: {value}")
                
                if parts:
                    facts.append(f"{subject} - {', '.join(parts)}")
        
        return facts
    
    def _build_combined_text(self, block: ContentBlock, description: str) -> str:
        """Build combined text for embedding."""
        parts = []
        
        if block.context_before:
            parts.append(block.context_before)
        
        parts.append(f"[TABLE: {description}]")
        
        if block.context_after:
            parts.append(block.context_after)
        
        return " ".join(parts)
    
    def _extract_concepts(
        self,
        description: str,
        structured: TableStructure
    ) -> list[str]:
        """Extract concept candidates from table."""
        concepts = set()
        
        # Add headers as potential concepts
        for header in structured.headers:
            if len(header) > 2 and not header.isdigit():
                concepts.add(header.lower())
        
        # Extract capitalized terms from description
        words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", description)
        for word in words:
            if len(word) > 2:
                concepts.add(word.lower())
        
        # Extract values from first column (often entities)
        if structured.rows and structured.headers:
            first_header = structured.headers[0]
            for row in structured.rows:
                value = row.get(first_header, "")
                if value and len(value) > 2 and not value.isdigit():
                    concepts.add(value.lower())
        
        return list(concepts)
