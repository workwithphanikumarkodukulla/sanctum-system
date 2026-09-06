"""Data models for document content classification."""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Canonical classification categories for document regions and content elements."""
    TEXT = "text"
    TABLE = "table"
    FORMULA = "formula"
    IMAGE = "image"
    HANDWRITING = "handwriting"
    DIAGRAM = "diagram"
    UNKNOWN = "unknown"


class ClassificationResult(BaseModel):
    """Detailed result of content classification for a document region or element."""
    content_type: ContentType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    reason: str = Field(description="Deterministic explanation or evidence for the classification")
    source_region: dict[str, Any] | None = Field(
        default=None,
        description="Bounding coordinates, source metadata, or region index",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted classification signals (e.g. math symbols, table delimiters, handwriting scores)",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_type": self.content_type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "source_region": self.source_region,
            "metadata": self.metadata,
        }
