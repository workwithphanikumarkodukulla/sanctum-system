"""Canonical Evidence Schema for the Multimodal Evidence Engine."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


def _sanitize_for_pydantic(obj: Any) -> Any:
    """Recursively convert numpy arrays, numpy scalars, and other non-standard types to JSON-safe primitives."""
    if obj is None:
        return None
    if hasattr(obj, "tolist") and callable(obj.tolist):
        return _sanitize_for_pydantic(obj.tolist())
    if hasattr(obj, "item") and callable(obj.item):
        return obj.item()
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_pydantic(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_pydantic(item) for item in obj]
    return obj


class EvidenceElement(BaseModel):
    id: str  # e.g. "p1_e2" or "doc123_e001"
    document_id: str
    page: int = 1
    type: Literal["text", "heading", "table", "formula", "image", "list", "handwriting", "diagram"]
    text: str | None = None
    table_data: dict[str, Any] | None = None  # {"headers": [...], "rows": [[...]]}
    formula_latex: str | None = None
    formula_variables: dict[str, Any] | None = None
    bbox: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])  # [x1, y1, x2, y2]
    confidence: float  # 0.0 to 1.0
    extraction_model: str  # e.g. "PyMuPDF", "openpyxl", "python-docx", "python-pptx", "csv", "Tesseract"
    file_hash: str
    timestamp: str
    sheet: str | None = None
    slide: int | None = None
    row: int | None = None
    column: int | None = None
    reading_order: int | None = None
    provenance: dict[str, Any] | str | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Audit metadata, layout properties, cell coordinates, or consensus notes",
    )

    @field_validator("metadata", "table_data", "formula_variables", "provenance", mode="before", check_fields=False)
    @classmethod
    def _sanitize_fields(cls, v: Any) -> Any:
        return _sanitize_for_pydantic(v)


class WorksheetInfo(BaseModel):
    """Metadata describing a single spreadsheet worksheet."""
    name: str
    index: int = 1
    row_count: int = 0
    column_count: int = 0
    has_formulas: bool = False
    merged_ranges: list[str] = Field(default_factory=list)


class DocumentMetadata(BaseModel):
    """Canonical document-level metadata model across all supported formats."""
    document_id: str
    filename: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    file_hash: str | None = None
    processing_status: Literal["processing", "completed", "failed"] = "processing"
    parser_used: str | None = None
    total_pages: int = 1
    total_slides: int | None = None
    worksheets: list[WorksheetInfo] | None = None
    created_at: str | None = None
    completed_at: str | None = None
    processing_time_ms: float | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Arbitrary creation, extraction, or processing metadata",
    )

    @field_validator("metadata", mode="before", check_fields=False)
    @classmethod
    def _sanitize_metadata(cls, v: Any) -> Any:
        return _sanitize_for_pydantic(v)


class DocumentEvidence(DocumentMetadata):
    """Canonical Evidence representation for a processed document, inheriting all metadata."""
    elements: list[EvidenceElement] = Field(default_factory=list)
    overall_confidence: float = 0.0

    def to_metadata(self) -> DocumentMetadata:
        """Extract canonical document metadata without the elements payload."""
        data = self.model_dump(exclude={"elements", "overall_confidence"})
        return DocumentMetadata(**data)

    @classmethod
    def from_metadata(
        cls,
        metadata: DocumentMetadata,
        elements: list[EvidenceElement] | None = None,
        overall_confidence: float = 0.0,
    ) -> DocumentEvidence:
        """Construct DocumentEvidence from DocumentMetadata and elements."""
        data = metadata.model_dump()
        data["elements"] = elements or []
        data["overall_confidence"] = overall_confidence
        return cls(**data)


