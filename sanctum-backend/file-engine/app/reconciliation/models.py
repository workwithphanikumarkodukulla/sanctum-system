"""Domain models and schemas for evidence reconciliation."""
from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AgreementStatus(str, Enum):
    """Categorization of comparison between two extraction candidates."""
    EXACT_MATCH = "exact_match"
    WHITESPACE_DIFFERENCE = "whitespace_difference"
    PUNCTUATION_DIFFERENCE = "punctuation_difference"
    MINOR_OCR_DIFFERENCE = "minor_ocr_difference"
    MATERIAL_DISAGREEMENT = "material_disagreement"


class DisagreementCategory(str, Enum):
    """Specific categories of divergence detected between candidates."""
    NUMBER_MISMATCH = "number_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    DATE_MISMATCH = "date_mismatch"
    NAME_MISMATCH = "name_mismatch"
    FORMULA_MISMATCH = "formula_mismatch"
    TEXT_DIVERGENCE = "text_divergence"


class DisagreementDetail(BaseModel):
    """Specific explanation of a detected divergence."""
    category: DisagreementCategory
    field_name: str = Field(description="Name or token group involved in disagreement")
    candidate_a_value: Any = Field(description="Value from ExtractionResult A")
    candidate_b_value: Any = Field(description="Value from ExtractionResult B")
    description: str = Field(description="Human-readable audit explanation")

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "field_name": self.field_name,
            "candidate_a_value": self.candidate_a_value,
            "candidate_b_value": self.candidate_b_value,
            "description": self.description,
        }


class ExtractionResult(BaseModel):
    """Standardized representation of an extraction candidate from any engine."""
    text: str | None = Field(default=None, description="Extracted text string")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    extraction_method: str = Field(default="unknown", description="Engine or model identifier")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Extraction provenance")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional extraction metadata")

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "extraction_method": self.extraction_method,
            "provenance": self.provenance,
            "metadata": self.metadata,
        }


class ReconciliationResult(BaseModel):
    """Result of reconciling two extraction candidates."""
    final_text: str | None
    final_confidence: float = Field(ge=0.0, le=1.0)
    agreement_status: AgreementStatus
    disagreement_details: list[DisagreementDetail] = Field(default_factory=list)
    requires_review: bool
    candidate_a: ExtractionResult
    candidate_b: ExtractionResult
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_text": self.final_text,
            "final_confidence": self.final_confidence,
            "agreement_status": self.agreement_status.value,
            "disagreement_details": [d.to_dict() for d in self.disagreement_details],
            "requires_review": self.requires_review,
            "candidate_a": self.candidate_a.to_dict(),
            "candidate_b": self.candidate_b.to_dict(),
            "provenance": self.provenance,
            "metadata": self.metadata,
        }
