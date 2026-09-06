"""Evidence builder to assemble extracted elements into the canonical schema."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from app.evidence.schema import DocumentEvidence, EvidenceElement


def _make_serializable(obj: Any) -> Any:
    """Recursively convert numpy arrays, numpy scalars, and other non-standard types to JSON-safe primitives."""
    if obj is None:
        return None
    if hasattr(obj, "tolist") and callable(obj.tolist):
        return _make_serializable(obj.tolist())
    if hasattr(obj, "item") and callable(obj.item):
        return obj.item()
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(item) for item in obj]
    return obj


class EvidenceBuilder:
    @staticmethod
    def build_element(
        *,
        element_idx: int,
        document_id: str,
        page: int = 1,
        elem_type: str,
        text: str | None = None,
        table_data: dict | None = None,
        formula_latex: str | None = None,
        formula_variables: dict | None = None,
        bbox: Sequence[float] | None = None,
        confidence: float = 1.0,
        extraction_model: str,
        file_hash: str,
        sheet: str | None = None,
        slide: int | None = None,
        row: int | None = None,
        column: int | None = None,
        reading_order: int | None = None,
        provenance: dict | str | None = None,
        metadata: dict | None = None,
        custom_id: str | None = None,
    ) -> EvidenceElement:
        element_id = custom_id or f"p{page}_e{element_idx}"
        timestamp = datetime.now(timezone.utc).isoformat()
        clamped_confidence = max(0.0, min(1.0, float(confidence)))
        clean_bbox = [round(float(coord), 2) for coord in (bbox or [0.0, 0.0, 0.0, 0.0])]

        return EvidenceElement(
            id=element_id,
            document_id=document_id,
            page=page,
            type=elem_type,  # type: ignore[arg-type]
            text=text,
            table_data=_make_serializable(table_data),
            formula_latex=formula_latex,
            formula_variables=_make_serializable(formula_variables),
            bbox=clean_bbox,
            confidence=round(clamped_confidence, 4),
            extraction_model=extraction_model,
            file_hash=file_hash,
            timestamp=timestamp,
            sheet=sheet,
            slide=slide,
            row=row,
            column=column,
            reading_order=reading_order if reading_order is not None else element_idx,
            provenance=_make_serializable(provenance),
            metadata=_make_serializable(metadata),
        )

    @staticmethod
    def assemble_document(
        *,
        document_id: str,
        total_pages: int,
        elements: list[EvidenceElement],
        status: str = "completed",
        error: str | None = None,
        filename: str | None = None,
        file_type: str | None = None,
        mime_type: str | None = None,
        file_size: int | None = None,
        file_hash: str | None = None,
        parser_used: str | None = None,
        total_slides: int | None = None,
        worksheets: list | None = None,
        created_at: str | None = None,
        completed_at: str | None = None,
        processing_time_ms: float | None = None,
        metadata: dict | None = None,
    ) -> DocumentEvidence:
        if elements:
            overall_conf = sum(el.confidence for el in elements) / len(elements)
        else:
            overall_conf = 0.0

        return DocumentEvidence(
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            mime_type=mime_type,
            file_size=file_size,
            file_hash=file_hash,
            parser_used=parser_used,
            total_pages=total_pages,
            total_slides=total_slides,
            worksheets=worksheets,
            created_at=created_at,
            completed_at=completed_at,
            processing_time_ms=processing_time_ms,
            metadata=_make_serializable(metadata),
            elements=elements,
            overall_confidence=round(overall_conf, 4),
            processing_status=status,  # type: ignore[arg-type]
            error=error,
        )

