"""Unit tests for general EvidenceReconciler covering exact match, whitespace, punctuation,
OCR typos, numbers, units, dates, names, formulas, and candidate preservation."""
from __future__ import annotations

import pytest

from app.reconciliation import (
    AgreementStatus,
    DisagreementCategory,
    EvidenceReconciler,
    ExtractionResult,
    ReconciliationResult,
    evidence_reconciler,
)


# 1. Exact match
def test_reconcile_exact_match():
    """Identical text extractions yield EXACT_MATCH, boosted confidence, and requires_review=False."""
    res_a = ExtractionResult(
        text="Normal operating pressure is 450 kPa.",
        confidence=0.85,
        extraction_method="Tesseract",
        provenance={"source": "ocr"},
    )
    res_b = ExtractionResult(
        text="Normal operating pressure is 450 kPa.",
        confidence=0.88,
        extraction_method="Ollama-gemma4",
        provenance={"source": "vlm"},
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert isinstance(recon, ReconciliationResult)
    assert recon.agreement_status == AgreementStatus.EXACT_MATCH
    assert recon.requires_review is False
    assert recon.final_text == "Normal operating pressure is 450 kPa."
    # Confidence is boosted above the maximum input confidence
    assert recon.final_confidence > 0.88
    assert recon.final_confidence <= 0.99
    assert len(recon.disagreement_details) == 0
    # Both candidates preserved
    assert recon.candidate_a.text == res_a.text
    assert recon.candidate_b.text == res_b.text
    assert recon.provenance["confidence_boosted"] is True


# 2. Whitespace differences
def test_reconcile_whitespace_differences():
    """Differences only in tabs, newlines, or multiple spaces yield WHITESPACE_DIFFERENCE without review."""
    res_a = ExtractionResult(
        text="Inspection Report\nLine B\tStatus: OK",
        confidence=0.82,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Inspection Report   Line B Status: OK",
        confidence=0.89,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.WHITESPACE_DIFFERENCE
    assert recon.requires_review is False
    assert recon.final_confidence > 0.89
    assert len(recon.disagreement_details) == 0
    # Selected higher confidence candidate text
    assert recon.final_text == res_b.text


# 3. Punctuation differences
def test_reconcile_punctuation_differences():
    """Differences limited to quotes, hyphens, periods yield PUNCTUATION_DIFFERENCE without review."""
    res_a = ExtractionResult(
        text="Valve PSV-101 (Inspected).",
        confidence=0.80,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Valve PSV-101 Inspected",
        confidence=0.86,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.PUNCTUATION_DIFFERENCE
    assert recon.requires_review is False
    assert recon.final_confidence > 0.86
    assert len(recon.disagreement_details) == 0


# 4. Minor OCR typo
def test_reconcile_minor_ocr_typo():
    """Single character non-semantic typo (e.g. 'Compressor' vs 'Compresor') yields MINOR_OCR_DIFFERENCE."""
    res_a = ExtractionResult(
        text="Feed Compresor Line B operational",
        confidence=0.78,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Feed Compressor Line B operational",
        confidence=0.92,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MINOR_OCR_DIFFERENCE
    assert recon.requires_review is False
    assert recon.final_confidence >= 0.92
    assert recon.final_text == "Feed Compressor Line B operational"
    assert len(recon.disagreement_details) == 0


# 5. Different numbers (semantic material disagreement)
def test_reconcile_different_numbers():
    """Conflicting numbers (e.g. 450 kPa vs 480 kPa) flag NUMBER_MISMATCH and requires_review=True."""
    res_a = ExtractionResult(
        text="Design Pressure: 450 kPa",
        confidence=0.90,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Design Pressure: 480 kPa",
        confidence=0.92,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    # Confidence is discounted rather than boosted
    assert recon.final_confidence <= 0.50
    # Check specific disagreement category
    assert any(d.category == DisagreementCategory.NUMBER_MISMATCH for d in recon.disagreement_details)
    # Both candidates strictly preserved - no silent overwriting!
    assert recon.candidate_a.text == "Design Pressure: 450 kPa"
    assert recon.candidate_b.text == "Design Pressure: 480 kPa"


# 6. Different units (semantic material disagreement)
def test_reconcile_different_units():
    """Conflicting physical units (e.g. 450 kPa vs 450 psi) flag UNIT_MISMATCH and requires_review=True."""
    res_a = ExtractionResult(
        text="Maximum Threshold: 450 kPa",
        confidence=0.85,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Maximum Threshold: 450 psi",
        confidence=0.88,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    assert recon.final_confidence <= 0.50
    unit_mismatches = [d for d in recon.disagreement_details if d.category == DisagreementCategory.UNIT_MISMATCH]
    assert len(unit_mismatches) >= 1
    assert "kpa" in unit_mismatches[0].candidate_a_value
    assert "psi" in unit_mismatches[0].candidate_b_value


# 7. Completely different text (text divergence)
def test_reconcile_completely_different_text():
    """Unrelated divergent strings flag TEXT_DIVERGENCE and requires_review=True."""
    res_a = ExtractionResult(
        text="Section 3: Pipeline flow diagram",
        confidence=0.75,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Vendor Signature: Approved and verified by QA manager",
        confidence=0.80,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    assert recon.final_confidence <= 0.40
    assert any(d.category == DisagreementCategory.TEXT_DIVERGENCE for d in recon.disagreement_details)


# 8. Different dates
def test_reconcile_different_dates():
    """Conflicting calendar dates flag DATE_MISMATCH and requires_review=True."""
    res_a = ExtractionResult(
        text="Scheduled Maintenance Date: 2026-03-15",
        confidence=0.88,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Scheduled Maintenance Date: 2026-03-18",
        confidence=0.89,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    assert any(d.category == DisagreementCategory.DATE_MISMATCH for d in recon.disagreement_details)


# 9. Different names
def test_reconcile_different_names():
    """Conflicting person names flag NAME_MISMATCH and requires_review=True."""
    res_a = ExtractionResult(
        text="Certified by Dr. Robert Smith",
        confidence=0.85,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Certified by Dr. David Miller",
        confidence=0.87,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    assert any(d.category == DisagreementCategory.NAME_MISMATCH for d in recon.disagreement_details)


# 10. Different formulas
def test_reconcile_different_formulas():
    """Conflicting mathematical formulas flag FORMULA_MISMATCH and requires_review=True."""
    res_a = ExtractionResult(
        text="Calculate E = m * c^2",
        confidence=0.88,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Calculate E = m * c^3",
        confidence=0.90,
        extraction_method="Ollama-gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)

    assert recon.agreement_status == AgreementStatus.MATERIAL_DISAGREEMENT
    assert recon.requires_review is True
    # In addition to formula mismatch, number mismatch is detected (2 vs 3)
    assert any(d.category in (DisagreementCategory.FORMULA_MISMATCH, DisagreementCategory.NUMBER_MISMATCH) for d in recon.disagreement_details)


# 11. Serialization and metadata preservation
def test_reconcile_serialization():
    """ReconciliationResult serializes cleanly to dict with auditable details."""
    res_a = ExtractionResult(
        text="Sample A 100 kg",
        confidence=0.80,
        extraction_method="EngineA",
        provenance={"run_id": "1"},
    )
    res_b = ExtractionResult(
        text="Sample B 200 kg",
        confidence=0.85,
        extraction_method="EngineB",
        provenance={"run_id": "2"},
    )

    recon = evidence_reconciler.reconcile(res_a, res_b)
    data = recon.to_dict()

    assert data["agreement_status"] == "material_disagreement"
    assert data["requires_review"] is True
    assert "disagreement_details" in data
    assert len(data["disagreement_details"]) >= 1
    assert data["candidate_a"]["extraction_method"] == "EngineA"
    assert data["candidate_b"]["extraction_method"] == "EngineB"


# 12. Handwriting: VLM authoritative on candidate disagreement
def test_reconcile_handwriting_vlm_authoritative_on_disagreement():
    """For handwriting, VLM is authoritative when candidates disagree; requires_review=False."""
    res_a = ExtractionResult(
        text="es NOTES Dear ie",
        confidence=0.55,
        extraction_method="Tesseract",
        provenance={"source": "ocr"},
    )
    res_b = ExtractionResult(
        text="NOTES Dear Magnus, Business law",
        confidence=0.92,
        extraction_method="gemma4",
        provenance={"source": "vlm"},
    )

    recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)

    assert recon.final_text == "NOTES Dear Magnus, Business law"
    assert recon.requires_review is False
    assert recon.final_confidence >= 0.90
    assert recon.provenance["authoritative_source"] == "vlm"
    assert recon.provenance["reason"] == "handwriting_vlm_authoritative"
    assert recon.candidate_a.text == "es NOTES Dear ie"
    assert recon.candidate_b.text == "NOTES Dear Magnus, Business law"


# 13. Handwriting: VLM and OCR agreement
def test_reconcile_handwriting_agreement_no_human_review():
    """For handwriting, when OCR and VLM agree, requires_review=False and VLM text is returned."""
    res_a = ExtractionResult(
        text="Approved by Magnus",
        confidence=0.75,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="Approved by Magnus",
        confidence=0.95,
        extraction_method="gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)

    assert recon.final_text == "Approved by Magnus"
    assert recon.requires_review is False
    assert recon.provenance["authoritative_source"] == "vlm"
    assert recon.metadata["consensus"] == "matched"


# 14. Handwriting: VLM failure / empty falls back to OCR
def test_reconcile_handwriting_vlm_empty_ocr_fallback():
    """For handwriting, when VLM is empty/unavailable, OCR is preserved as fallback without review."""
    res_a = ExtractionResult(
        text="Handwritten signature text",
        confidence=0.68,
        extraction_method="Tesseract",
    )
    res_b = ExtractionResult(
        text="",
        confidence=0.0,
        extraction_method="gemma4",
    )

    recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)

    assert recon.final_text == "Handwritten signature text"
    assert recon.requires_review is False
    assert recon.provenance["authoritative_source"] == "ocr_fallback"
    assert recon.candidate_a.text == "Handwritten signature text"


# 15. Handwriting: Both empty yields empty without fabrication
def test_reconcile_handwriting_both_empty_no_fabrication():
    """When both OCR and VLM yield empty results, return empty string without fabricating text."""
    res_a = ExtractionResult(text="", confidence=0.0, extraction_method="Tesseract")
    res_b = ExtractionResult(text="", confidence=0.0, extraction_method="gemma4")

    recon = evidence_reconciler.reconcile(res_a, res_b, is_handwritten=True)

    assert recon.final_text == ""
    assert recon.requires_review is False
    assert recon.provenance["authoritative_source"] == "none"
