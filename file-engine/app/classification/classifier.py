"""ContentClassifier coordinating deterministic metadata, pattern, and visual strategies."""
from __future__ import annotations

import logging
from typing import Any
from PIL import Image

from app.classification.models import ClassificationResult, ContentType
from app.classification.strategies import (
    ClassificationStrategy,
    MetadataClassificationStrategy,
    TextPatternClassificationStrategy,
    VisualRegionClassificationStrategy,
)
from app.evidence.schema import EvidenceElement

logger = logging.getLogger(__name__)


class ContentClassifier:
    """Classifies document regions and extracted elements into canonical content types."""

    def __init__(self, strategies: list[ClassificationStrategy] | None = None) -> None:
        self.strategies: list[ClassificationStrategy] = strategies or [
            MetadataClassificationStrategy(),
            TextPatternClassificationStrategy(),
            VisualRegionClassificationStrategy(),
        ]

    def register_strategy(self, strategy: ClassificationStrategy, index: int | None = None) -> None:
        """Register a new classification strategy (e.g. specialized ML layout models)."""
        if index is not None:
            self.strategies.insert(index, strategy)
        else:
            self.strategies.append(strategy)
        logger.info("Registered classification strategy: %s", getattr(strategy, "strategy_name", type(strategy).__name__))

    def classify_region(
        self,
        text: str | None = None,
        image: Image.Image | None = None,
        metadata: dict[str, Any] | None = None,
        bbox: list[float] | None = None,
        source_region: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """Classify a document region or bounding area using configured strategies in priority order.

        Args:
            text: Extracted or OCR text in the region.
            image: Rendered or cropped image of the region.
            metadata: Parser or layout metadata attributes.
            bbox: Bounding box coordinates [x1, y1, x2, y2].
            source_region: Optional provenance/source context.

        Returns:
            ClassificationResult with content_type, confidence, reason, and metadata.
        """
        source_dict = source_region or {}
        if bbox and "bbox" not in source_dict:
            source_dict["bbox"] = bbox

        for strategy in self.strategies:
            if strategy.can_classify(text=text, image=image, metadata=metadata, bbox=bbox):
                result = strategy.classify(text=text, image=image, metadata=metadata, bbox=bbox)
                if result is not None:
                    if not result.source_region:
                        result.source_region = source_dict if source_dict else None
                    return result

        # Ambiguous / Unknown fallback
        return ClassificationResult(
            content_type=ContentType.UNKNOWN,
            confidence=0.20,
            reason="Ambiguous or empty region with insufficient text or visual features to classify.",
            source_region=source_dict if source_dict else None,
            metadata={"text_length": len(text) if text else 0, "has_image": image is not None},
        )

    def classify_element(self, element: EvidenceElement) -> ClassificationResult:
        """Classify an already extracted EvidenceElement based on its content, type, and metadata."""
        meta = dict(element.metadata or {})
        # Enrich metadata from element attributes
        if element.table_data is not None:
            meta["table_data"] = element.table_data
            meta["is_table"] = True
        if element.formula_latex is not None or element.type == "formula":
            meta["formula_latex"] = element.formula_latex
            meta["is_formula"] = True
        if element.type == "heading":
            meta["is_heading"] = True
        if element.type == "list":
            meta["is_list"] = True
        if element.type == "handwriting":
            meta["is_handwriting"] = True
            meta["elem_type"] = "handwriting"
        if element.type == "image":
            meta["is_image"] = True
            meta["elem_type"] = "image"
        if "type" not in meta:
            meta["type"] = element.type
        if "confidence" not in meta:
            meta["confidence"] = element.confidence
        if element.extraction_model:
            meta.setdefault("extraction_model", element.extraction_model)
        if isinstance(element.provenance, dict) and "source" in element.provenance:
            meta.setdefault("source", element.provenance["source"])

        source_region = {
            "element_id": element.id,
            "document_id": element.document_id,
            "page": element.page,
            "slide": element.slide,
            "sheet": element.sheet,
            "row": element.row,
            "bbox": element.bbox,
            "extraction_model": element.extraction_model,
        }

        return self.classify_region(
            text=element.text,
            metadata=meta,
            bbox=element.bbox,
            source_region=source_region,
        )


content_classifier = ContentClassifier()
