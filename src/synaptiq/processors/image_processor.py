"""
Image processor for multimodal knowledge extraction.

Uses GPT-4o vision to analyze images and extract:
1. Image type classification (diagram, screenshot, chart, photo)
2. Natural language description
3. Components/entities (for diagrams)
4. OCR text (for screenshots)
5. Data points (for charts)
"""

import base64
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from io import BytesIO

import structlog
from openai import AsyncOpenAI

from config.settings import get_settings
from synaptiq.processors.content_splitter import ContentBlock, ContentType

logger = structlog.get_logger(__name__)


class ImageType(Enum):
    """Types of images that can be processed."""
    DIAGRAM = "diagram"          # Flowcharts, architecture, mind maps
    SCREENSHOT = "screenshot"    # UI, code, terminal, documents
    CHART = "chart"              # Bar, line, pie, data visualizations
    PHOTO = "photo"              # Real-world photos, whiteboard
    UNKNOWN = "unknown"


@dataclass
class ImageExtractionResult:
    """Result of image processing."""
    image_type: ImageType
    description: str
    components: list[str]
    relationships: list[dict]
    ocr_text: Optional[str]
    data_points: Optional[dict]
    combined_text: str
    concepts: list[str] = field(default_factory=list)
    
    # Image metadata
    original_url: Optional[str] = None
    s3_key: Optional[str] = None
    s3_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    size_bytes: Optional[int] = None


class ImageProcessor:
    """
    Processes images using GPT-4o vision for knowledge extraction.
    
    Type-specific extraction:
    - Diagrams: Components, relationships, flow
    - Screenshots: OCR, UI elements
    - Charts: Axis labels, data series, trends
    - Photos: General description, key concepts
    """
    
    CLASSIFICATION_PROMPT = """Classify this image into one of these categories:
- DIAGRAM: Flowcharts, architecture diagrams, mind maps, system diagrams
- SCREENSHOT: UI screenshots, code editor, terminal, document screenshots
- CHART: Bar charts, line graphs, pie charts, data visualizations
- PHOTO: Real-world photographs, whiteboard photos, handwritten notes

Respond with just the category name (DIAGRAM, SCREENSHOT, CHART, or PHOTO)."""

    DIAGRAM_PROMPT = """Analyze this diagram in detail.

CONTEXT FROM NOTE:
{context}

Provide:
1. A comprehensive description of what the diagram shows
2. All labeled components/nodes in the diagram
3. Relationships and connections between components
4. The flow or process being depicted
5. Key concepts illustrated

Respond in JSON format:
{{
    "description": "Detailed description of the diagram...",
    "diagram_type": "flowchart|architecture|mindmap|sequence|other",
    "components": ["Component A", "Component B", ...],
    "relationships": [
        {{"from": "A", "to": "B", "label": "connects to"}},
        ...
    ],
    "key_concepts": ["concept1", "concept2", ...]
}}"""

    SCREENSHOT_PROMPT = """Analyze this screenshot.

CONTEXT FROM NOTE:
{context}

Extract:
1. A description of what the screenshot shows
2. All visible text (OCR)
3. UI elements and their labels
4. Any code snippets if present
5. Key information displayed

Respond in JSON format:
{{
    "description": "Description of the screenshot...",
    "screenshot_type": "code_editor|terminal|ui|document|other",
    "ocr_text": "All extracted text from the image...",
    "ui_elements": ["Button: Submit", "Input: Username", ...],
    "code_snippets": ["def function()...", ...],
    "key_concepts": ["concept1", "concept2", ...]
}}"""

    CHART_PROMPT = """Analyze this chart/graph.

CONTEXT FROM NOTE:
{context}

Extract:
1. Chart type (bar, line, pie, scatter, etc.)
2. Title and axis labels
3. Data series and approximate values
4. Visible trends or patterns
5. Key insights from the data

Respond in JSON format:
{{
    "description": "Description of what the chart shows...",
    "chart_type": "bar|line|pie|scatter|area|other",
    "title": "Chart title if visible",
    "x_axis": "X axis label",
    "y_axis": "Y axis label",
    "data_series": [
        {{"name": "Series A", "trend": "increasing", "approx_values": [10, 20, 30]}}
    ],
    "key_insights": ["Insight 1", "Insight 2"],
    "key_concepts": ["concept1", "concept2", ...]
}}"""

    PHOTO_PROMPT = """Describe this photo.

CONTEXT FROM NOTE:
{context}

Provide:
1. A detailed description of what's in the photo
2. Any text visible (signs, labels, handwriting)
3. Key objects or subjects
4. Relevance to the context if applicable

Respond in JSON format:
{{
    "description": "Description of the photo...",
    "photo_type": "whiteboard|handwritten|real_world|other",
    "visible_text": "Any text visible in the photo",
    "objects": ["object1", "object2", ...],
    "key_concepts": ["concept1", "concept2", ...]
}}"""

    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the image processor.
        
        Args:
            model: OpenAI vision model (default: gpt-4o)
        """
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        self.model = model
    
    async def process(
        self,
        block: ContentBlock,
        image_bytes: Optional[bytes] = None,
    ) -> ImageExtractionResult:
        """
        Process an image content block.
        
        Args:
            block: ContentBlock with type IMAGE
            image_bytes: Image data (if already fetched)
            
        Returns:
            ImageExtractionResult with analysis
        """
        if block.type != ContentType.IMAGE:
            raise ValueError(f"Expected IMAGE block, got {block.type}")
        
        image_url = block.metadata.get("url", "")
        is_base64 = block.metadata.get("is_base64", False)
        
        logger.info(
            "Processing image",
            url=image_url[:100] if image_url else "no url",
            is_base64=is_base64,
        )
        
        # Prepare image for vision API
        if image_bytes:
            image_data = self._encode_image(image_bytes)
        elif is_base64 and image_url.startswith("data:"):
            image_data = image_url
        elif image_url:
            image_data = image_url
        else:
            logger.warning("No image data available")
            return self._create_empty_result(block)
        
        # 1. Classify image type
        image_type = await self._classify_image(image_data)
        
        # 2. Extract based on type
        context = f"{block.context_before}\n{block.context_after}".strip()
        
        if image_type == ImageType.DIAGRAM:
            extraction = await self._extract_diagram(image_data, context)
        elif image_type == ImageType.SCREENSHOT:
            extraction = await self._extract_screenshot(image_data, context)
        elif image_type == ImageType.CHART:
            extraction = await self._extract_chart(image_data, context)
        else:
            extraction = await self._extract_photo(image_data, context)
        
        # 3. Build combined text
        combined_text = self._build_combined_text(block, extraction, image_type)
        
        logger.info(
            "Image processed",
            type=image_type.value,
            components=len(extraction.get("components", [])),
        )
        
        return ImageExtractionResult(
            image_type=image_type,
            description=extraction.get("description", ""),
            components=extraction.get("components", extraction.get("objects", [])),
            relationships=extraction.get("relationships", []),
            ocr_text=extraction.get("ocr_text", extraction.get("visible_text")),
            data_points=extraction.get("data_series"),
            combined_text=combined_text,
            concepts=extraction.get("key_concepts", []),
            original_url=image_url if not is_base64 else None,
        )
    
    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image bytes to base64 data URL."""
        # Detect image format from magic bytes
        if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        elif image_bytes[:2] == b'\xff\xd8':
            mime_type = "image/jpeg"
        elif image_bytes[:6] in (b'GIF87a', b'GIF89a'):
            mime_type = "image/gif"
        elif image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
            mime_type = "image/webp"
        else:
            mime_type = "image/png"  # Default to PNG
        
        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"
    
    async def _classify_image(self, image_data: str) -> ImageType:
        """Classify image type using vision model."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.CLASSIFICATION_PROMPT},
                            self._create_image_content(image_data),
                        ],
                    }
                ],
                max_tokens=50,
            )
            
            result = response.choices[0].message.content.strip().upper()
            
            if "DIAGRAM" in result:
                return ImageType.DIAGRAM
            elif "SCREENSHOT" in result:
                return ImageType.SCREENSHOT
            elif "CHART" in result:
                return ImageType.CHART
            elif "PHOTO" in result:
                return ImageType.PHOTO
            else:
                return ImageType.UNKNOWN
        
        except Exception as e:
            logger.warning("Failed to classify image", error=str(e))
            return ImageType.UNKNOWN
    
    def _create_image_content(self, image_data: str) -> dict:
        """Create image content for OpenAI API."""
        if image_data.startswith("data:"):
            return {
                "type": "image_url",
                "image_url": {"url": image_data}
            }
        else:
            return {
                "type": "image_url",
                "image_url": {"url": image_data}
            }
    
    async def _extract_diagram(self, image_data: str, context: str) -> dict:
        """Extract information from diagram."""
        return await self._call_vision_api(
            self.DIAGRAM_PROMPT.format(context=context or "(no context)"),
            image_data,
        )
    
    async def _extract_screenshot(self, image_data: str, context: str) -> dict:
        """Extract information from screenshot."""
        return await self._call_vision_api(
            self.SCREENSHOT_PROMPT.format(context=context or "(no context)"),
            image_data,
        )
    
    async def _extract_chart(self, image_data: str, context: str) -> dict:
        """Extract information from chart."""
        return await self._call_vision_api(
            self.CHART_PROMPT.format(context=context or "(no context)"),
            image_data,
        )
    
    async def _extract_photo(self, image_data: str, context: str) -> dict:
        """Extract information from photo."""
        return await self._call_vision_api(
            self.PHOTO_PROMPT.format(context=context or "(no context)"),
            image_data,
        )
    
    async def _call_vision_api(self, prompt: str, image_data: str) -> dict:
        """Call vision API with prompt and image."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            self._create_image_content(image_data),
                        ],
                    }
                ],
                max_tokens=1000,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            try:
                # Extract JSON from response (may have markdown code blocks)
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {"description": content}
            except json.JSONDecodeError:
                return {"description": content}
        
        except Exception as e:
            logger.warning("Vision API call failed", error=str(e))
            return {"description": "Image analysis failed"}
    
    def _build_combined_text(
        self,
        block: ContentBlock,
        extraction: dict,
        image_type: ImageType,
    ) -> str:
        """Build combined text for embedding."""
        parts = []
        
        if block.context_before:
            parts.append(block.context_before)
        
        # Build image description
        description = extraction.get("description", "Image")
        type_label = image_type.value.upper()
        
        if image_type == ImageType.DIAGRAM:
            components = extraction.get("components", [])
            if components:
                parts.append(f"[{type_label}: {description}. Components: {', '.join(components[:5])}]")
            else:
                parts.append(f"[{type_label}: {description}]")
        
        elif image_type == ImageType.SCREENSHOT:
            ocr_text = extraction.get("ocr_text", "")
            if ocr_text:
                parts.append(f"[{type_label}: {description}. Text: {ocr_text[:200]}]")
            else:
                parts.append(f"[{type_label}: {description}]")
        
        elif image_type == ImageType.CHART:
            insights = extraction.get("key_insights", [])
            if insights:
                parts.append(f"[{type_label}: {description}. Insights: {'; '.join(insights[:3])}]")
            else:
                parts.append(f"[{type_label}: {description}]")
        
        else:
            parts.append(f"[{type_label}: {description}]")
        
        if block.context_after:
            parts.append(block.context_after)
        
        return " ".join(parts)
    
    def _create_empty_result(self, block: ContentBlock) -> ImageExtractionResult:
        """Create empty result when image cannot be processed."""
        return ImageExtractionResult(
            image_type=ImageType.UNKNOWN,
            description="Image could not be processed",
            components=[],
            relationships=[],
            ocr_text=None,
            data_points=None,
            combined_text=f"{block.context_before} [IMAGE: Unable to process] {block.context_after}",
            original_url=block.metadata.get("url"),
        )
