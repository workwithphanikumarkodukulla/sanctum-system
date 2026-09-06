"""Unit tests for the modular handwriting classifier and decision routing layer."""
from __future__ import annotations

import pytest
from PIL import Image

from app.core.config import settings
from app.extractors.handwriting import (
    HandwritingClassification,
    HandwritingDecision,
    handwriting_checker,
    handwriting_classifier,
)


def test_handwriting_decision_printed_text():
    """Verify clean text with high OCR confidence is decisively classified as PRINTED."""
    text = "The pressure safety valve PSV-101 was inspected in accordance with API 510 standards."
    decision: HandwritingDecision = handwriting_classifier.classify_region(
        text=text,
        confidence=0.95,
    )

    assert decision.classification == HandwritingClassification.PRINTED
    assert decision.confidence >= 0.90
    assert "printed" in decision.reason.lower()
    assert decision.signals["irregular_char_count"] == 0
    assert decision.signals["ocr_confidence"] == 0.95


def test_handwriting_decision_suspected_handwriting():
    """Verify low-confidence OCR with cursive punctuation noise is classified as HANDWRITTEN."""
    text = "Ap~rov^d by: J~hn D^e [12/05/2023]"
    decision: HandwritingDecision = handwriting_classifier.classify_region(
        text=text,
        confidence=0.55,
    )

    assert decision.classification == HandwritingClassification.HANDWRITTEN
    assert decision.confidence >= 0.80
    assert "handwritten" in decision.reason.lower()
    assert decision.signals["irregular_char_count"] >= 2
    assert "heuristic" in decision.reason.lower()


def test_handwriting_decision_explicit_keyword():
    """Verify presence of signature/handwriting keyword cues triggers suspected handwriting."""
    text = "Authorized Signature: _____________ Date: 2024-01-15"
    decision: HandwritingDecision = handwriting_classifier.classify_region(
        text=text,
        confidence=0.70,
    )

    assert decision.classification == HandwritingClassification.HANDWRITTEN
    assert decision.signals["has_handwriting_keyword"] is True


def test_handwriting_decision_uncertain_case():
    """Verify intermediate OCR confidence or conflicting signals returns UNCERTAIN."""
    # Faint printed text with low OCR confidence but zero cursive distortion
    faint_print = "SECTION 4.2 OPERATIONAL PARAMETERS"
    decision: HandwritingDecision = handwriting_classifier.classify_region(
        text=faint_print,
        confidence=0.74,  # Between SUSPECTED (0.68) and PRINTED (0.82) thresholds
    )

    assert decision.classification == HandwritingClassification.UNCERTAIN
    assert decision.confidence <= 0.70
    assert "uncertain" in decision.reason.lower()


def test_handwriting_checker_backward_compatibility():
    """Verify existing is_suspected_handwritten API operates consistently."""
    assert handwriting_checker.is_suspected_handwritten(
        crop=None,
        text="A~p^roved",
        confidence=0.50,
    ) is True

    assert handwriting_checker.is_suspected_handwritten(
        crop=None,
        text="Standard printed paragraph text.",
        confidence=0.96,
    ) is False


def test_handwriting_consensus_and_provenance_preservation():
    """Verify OCR-vs-VLM comparison preserves provenance for both matched and conflicted states."""
    # Matched consensus
    matched, text_res, conf_res, meta_ok = handwriting_checker.compare_consensus(
        ocr_text="P-101A Feed Pump",
        vision_text="P-101A Feed Pump",
    )
    assert matched is True
    assert text_res == "P-101A Feed Pump"
    assert conf_res >= 0.95
    assert meta_ok["consensus"] == "matched"
    assert meta_ok["requires_human_review"] is False
    assert meta_ok["provenance"]["ocr_model"] == "Tesseract"
    assert meta_ok["provenance"]["vlm_model"] == settings.OLLAMA_VISION_MODEL
    assert meta_ok["provenance"]["reconciliation"] == "consensus_agreement"

    # Diverged consensus: VLM is authoritative without human review
    matched_f, text_f, conf_f, meta_vlm = handwriting_checker.compare_consensus(
        ocr_text="T~101",
        vision_text="TK-101 Storage Tank",
    )
    assert matched_f is True
    assert text_f == "TK-101 Storage Tank"
    assert conf_f >= 0.85
    assert meta_vlm["consensus"] == "vlm_authoritative"
    assert meta_vlm["requires_human_review"] is False
    assert meta_vlm["authoritative_source"] == "vlm"
    assert meta_vlm["ocr_candidate"] == "T~101"
    assert meta_vlm["vlm_candidate"] == "TK-101 Storage Tank"
    assert meta_vlm["provenance"]["reconciliation"] == "handwriting_vlm_authoritative"


def test_handwriting_thresholds_configurable():
    """Verify thresholds are exposed via Settings and affect decisions dynamically."""
    assert hasattr(settings, "HANDWRITING_SUSPECTED_THRESHOLD")
    assert hasattr(settings, "HANDWRITING_PRINTED_THRESHOLD")
    assert hasattr(settings, "HANDWRITING_VLM_REREAD_THRESHOLD")
    assert settings.HANDWRITING_SUSPECTED_THRESHOLD == 0.68
    assert settings.HANDWRITING_PRINTED_THRESHOLD == 0.82


def test_printed_text_with_poor_ocr_not_mislabeled_as_handwriting():
    """Verify printed text with genuinely poor OCR is classified as UNCERTAIN, not HANDWRITTEN."""
    poor_ocr_printed_samples = [
        ("The terms and conditions of this purchase agreement shall remain in full force.", 0.48),
        ("The inspection of pressure vessel PV-102 was completed per standard procedure.", 0.52),
        ("All rights reserved. Reproduction in whole or in part without permission is prohibited.", 0.45),
        ("Contractor shall submit monthly progress reports detailing project milestones.", 0.50),
    ]

    for text, conf in poor_ocr_printed_samples:
        decision = handwriting_classifier.classify_region(
            text=text,
            confidence=conf,
        )

        # Must NOT be misclassified as handwriting
        assert decision.classification != HandwritingClassification.HANDWRITTEN, (
            f"Poor OCR printed text was erroneously classified as HANDWRITTEN: '{text}'"
        )
        assert decision.classification == HandwritingClassification.UNCERTAIN
        assert decision.confidence == 0.60
        assert "degraded/faint printed text" in decision.reason.lower() or "poor scan" in decision.reason.lower()
        assert decision.signals["cursive_char_count"] == 0
        assert decision.signals["mid_word_caps_count"] == 0
        assert decision.signals["document_has_handwriting"] is False


@pytest.mark.anyio
async def test_handwritten_image_fixture_multi_region_consistency(monkeypatch):
    """Verify all regions of a predominantly handwritten document are classified consistently as handwriting."""
    from pathlib import Path
    from unittest.mock import AsyncMock
    from app.models.vision_client import vision_client
    from app.processing.pipeline import pipeline

    # Mock VLM response so unit tests do not require Ollama / avoid network timeouts
    monkeypatch.setattr(
        vision_client,
        "reread_cropped_region",
        AsyncMock(return_value=("", 0.0)),
    )

    fixture_path = Path(__file__).parent.parent / "sample_documents" / "handwritten_note.png"
    assert fixture_path.exists(), "handwritten_note.png fixture must exist"

    with open(fixture_path, "rb") as f:
        file_bytes = f.read()

    doc = await pipeline.process_document(
        document_id="doc_test_hw_consistency",
        file_bytes=file_bytes,
        filename="handwritten_note.png",
    )

    assert doc.processing_status == "completed"
    assert len(doc.elements) >= 1, "Expected coherent handwriting element from handwritten note"

    # All body regions from this handwritten note must be classified consistently as handwriting
    handwriting_count = sum(1 for el in doc.elements if el.type == "handwriting")
    assert handwriting_count == len(doc.elements), (
        f"Expected all {len(doc.elements)} elements to be 'handwriting', but found types: "
        f"{[el.type for el in doc.elements]}"
    )

    # Ensure no element was misclassified as table
    table_count = sum(1 for el in doc.elements if el.type == "table")
    assert table_count == 0, "No handwritten cursive region should be misclassified as a table"

    # Verify audit signals are preserved on every handwritten element
    for el in doc.elements:
        meta = el.metadata or {}
        assert "ocr_candidate" in meta, f"Missing ocr_candidate on element {el.id}"
        assert meta["ocr_candidate"] == el.text or meta["ocr_candidate"] is not None
        assert "ocr_confidence" in meta, f"Missing ocr_confidence on element {el.id}"
        assert meta["ocr_confidence"] == el.confidence or meta["raw_ocr_confidence"] is not None
        assert meta.get("handwriting_classification") == "handwritten"
        assert "suspicion_signals" in meta
        assert "vlm_escalation_status" in meta
        # If VLM was empty or unavailable, original OCR candidate must be preserved without fabrication
        if meta.get("vlm_result_empty"):
            assert meta["vlm_escalation_status"] == "attempted_empty_or_unavailable"
            assert el.text == meta["ocr_candidate"], "Original OCR transcription must be preserved when VLM is empty"


@pytest.mark.anyio
async def test_handwriting_vlm_reconciliation_when_available(monkeypatch):
    """Verify VLM escalation status, candidates, and reconciliation when VLM returns a transcription."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    # Mock vision client returning corrected transcription
    monkeypatch.setattr(
        vision_client,
        "reread_cropped_region",
        AsyncMock(return_value=("Dear Magnus, The International Business team", 0.95)),
    )

    img = Image.new("RGB", (200, 80), color=(255, 255, 255))
    result = await region_enricher.enrich_region(
        crop=img,
        ocr_text="Dear Mag~us, The {nternational",
        ocr_confidence=0.45,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="Tesseract",
    )

    assert result.vlm_invoked is True
    assert result.metadata["vlm_escalation_status"] == "completed"
    assert result.metadata["ocr_candidate"] == "Dear Mag~us, The {nternational"
    assert result.metadata["vlm_candidate"] == "Dear Magnus, The International Business team"
    assert "reconciliation" in result.metadata
    assert result.final_text is not None


def test_cursive_handwriting_classified_even_with_high_ocr_confidence():
    """Verify cursive text with high OCR confidence (0.95) is classified as HANDWRITTEN."""
    cursive_sample = "Deak Magnus, Tilburg University wishes to express ouk gratitude fer youk lectures"
    decision = handwriting_classifier.classify_region(
        text=cursive_sample,
        confidence=0.95,
    )

    assert decision.classification == HandwritingClassification.HANDWRITTEN
    assert decision.signals["has_cursive_confusion"] is True
    assert decision.signals["ocr_confidence"] == 0.95


@pytest.mark.anyio
async def test_handwriting_mandatory_vlm_escalation_even_with_high_ocr_confidence(monkeypatch):
    """1 & 2. Verify handwriting with high OCR confidence (0.95) MUST still trigger VLM escalation."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    vlm_mock = AsyncMock(return_value=("Transcribed text by VLM", 0.94))
    monkeypatch.setattr(vision_client, "reread_cropped_region", vlm_mock)

    crop = Image.new("RGB", (150, 50), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="Deak Magnus, ouk gratitude",
        ocr_confidence=0.96,  # Very high OCR confidence
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="PaddleOCR",
    )

    assert vlm_mock.called, "VLM must be called for handwriting even with high OCR confidence"
    assert res.vlm_invoked is True
    assert res.metadata["handwriting_override"] is True
    assert res.metadata["vlm_escalation_reason"] == "handwriting_override"
    assert res.metadata["ocr_candidate"] == "Deak Magnus, ouk gratitude"
    assert res.metadata["vlm_candidate"] == "Transcribed text by VLM"


@pytest.mark.anyio
async def test_printed_text_does_not_trigger_vlm(monkeypatch):
    """3. Verify printed text with high confidence does NOT trigger VLM."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    vlm_mock = AsyncMock()
    monkeypatch.setattr(vision_client, "reread_cropped_region", vlm_mock)

    crop = Image.new("RGB", (200, 40), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="The vessel operating pressure is 120 MPa.",
        ocr_confidence=0.95,
        content_type="text",
        metadata={"handwriting_classification": "printed"},
        model_name="PaddleOCR",
    )

    assert not vlm_mock.called, "VLM should NOT be called for clean printed text"
    assert res.vlm_invoked is False
    assert res.metadata.get("vlm_escalation_status") == "not_needed"
    assert res.final_text == "The vessel operating pressure is 120 MPa."


@pytest.mark.anyio
async def test_handwriting_successful_vlm_reconciliation_agreement(monkeypatch):
    """4. Verify handwriting + matching VLM -> consensus without human review."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    vlm_mock = AsyncMock(return_value=("Approved by John Doe", 0.95))
    monkeypatch.setattr(vision_client, "reread_cropped_region", vlm_mock)

    crop = Image.new("RGB", (120, 40), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="Approved by John Doe",
        ocr_confidence=0.75,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="PaddleOCR",
    )

    assert res.vlm_invoked is True
    assert res.metadata["reconciliation"]["consensus"] == "matched"
    assert res.metadata["reconciliation"]["requires_human_review"] is False
    assert res.confidence >= 0.95


@pytest.mark.anyio
async def test_handwriting_vlm_failure_preserves_ocr_candidate(monkeypatch):
    """5. Verify handwriting + VLM failure/empty -> preserves OCR candidate without fabrication."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    # Simulate VLM unavailable or returning empty
    monkeypatch.setattr(vision_client, "reread_cropped_region", AsyncMock(return_value=(None, 0.0)))

    crop = Image.new("RGB", (120, 40), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="J~hn D^e Signature",
        ocr_confidence=0.65,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="PaddleOCR",
    )

    assert res.final_text == "J~hn D^e Signature"
    assert res.vlm_invoked is False
    assert res.metadata["ocr_candidate"] == "J~hn D^e Signature"
    assert res.metadata["vlm_candidate"] is None
    assert res.metadata["vlm_escalation_status"] == "attempted_empty_or_unavailable"
    assert res.metadata.get("vlm_result_empty") is True


@pytest.mark.anyio
async def test_handwriting_ocr_vlm_disagreement_vlm_authoritative_no_human_review(monkeypatch):
    """3. Verify handwriting + OCR/VLM disagreement: VLM authoritative, requires_human_review=False, OCR preserved."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    # OCR read 'ouk lecture', VLM read 'our lectures'
    monkeypatch.setattr(vision_client, "reread_cropped_region", AsyncMock(return_value=("our lectures", 0.92)))

    crop = Image.new("RGB", (120, 40), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="ouk lecture",
        ocr_confidence=0.90,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="PaddleOCR",
    )

    assert res.vlm_invoked is True
    assert res.final_text == "our lectures"
    assert res.extraction_method == settings.OLLAMA_VISION_MODEL
    assert res.metadata["requires_human_review"] is False
    assert res.provenance["authoritative_source"] == "vlm"
    assert res.provenance["requires_human_review"] is False
    assert res.metadata["ocr_candidate"] == "ouk lecture"
    assert res.metadata["vlm_candidate"] == "our lectures"
    assert res.confidence >= 0.85


@pytest.mark.anyio
async def test_handwriting_vlm_empty_falls_back_to_ocr_safely(monkeypatch):
    """5 & 7. Verify handwriting + empty VLM response falls back to OCR without fabrication."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    monkeypatch.setattr(vision_client, "reread_cropped_region", AsyncMock(return_value=("", 0.0)))

    crop = Image.new("RGB", (120, 40), color=(255, 255, 255))
    res = await region_enricher.enrich_region(
        crop=crop,
        ocr_text="handwritten notes",
        ocr_confidence=0.72,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
        model_name="Tesseract",
    )

    assert res.final_text == "handwritten notes"
    assert res.metadata["requires_human_review"] is False
    assert res.provenance["authoritative_source"] == "ocr_fallback"
    assert res.metadata["ocr_candidate"] == "handwritten notes"
    assert res.metadata["vlm_candidate"] is None


@pytest.mark.anyio
async def test_vlm_receives_only_cropped_region_not_full_document(monkeypatch):
    """7. Verify VLM receives specifically the cropped bounding box, not a full document."""
    from unittest.mock import AsyncMock
    from app.parsers.ocr_enricher import region_enricher
    from app.models.vision_client import vision_client

    received_crops = []

    async def mock_reread(crop_img):
        received_crops.append(crop_img)
        return "Inspected", 0.90

    monkeypatch.setattr(vision_client, "reread_cropped_region", mock_reread)

    # Specific small crop dimension (80x30)
    region_crop = Image.new("RGB", (80, 30), color=(200, 200, 200))
    await region_enricher.enrich_region(
        crop=region_crop,
        ocr_text="Ins~ected",
        ocr_confidence=0.60,
        content_type="handwriting",
        metadata={"handwriting_classification": "handwritten"},
    )

    assert len(received_crops) == 1
    assert received_crops[0].size == (80, 30), "VLM must receive only the specific region crop"


# ------------------------------------------------------------------------------
# Targeted Whole-Image Handwriting VLM & Validation Tests
# ------------------------------------------------------------------------------

def test_validate_handwriting_vlm_output_success():
    """Test valid handwriting transcription with legitimate text."""
    from app.extractors.handwriting import validate_handwriting_vlm_output

    sample_text = (
        "NOTES\nDear Magnus,\n"
        "The International Business Law Team at Tilburg University wishes to express our gratitude.\n"
        "This is very very important work.\n"
        "Kind regards,\nErik, Tronel & Sanita"
    )
    is_valid, cleaned, reason = validate_handwriting_vlm_output(sample_text)
    assert is_valid is True
    assert reason is None
    assert "Dear Magnus" in cleaned
    assert "very very important" in cleaned


def test_validate_handwriting_vlm_output_strips_chat_wrappers():
    """Test stripping conversational chat wrappers from VLM response."""
    from app.extractors.handwriting import validate_handwriting_vlm_output

    wrapped_text = (
        "Here is the faithful transcription of the handwritten note:\n"
        "NOTES\nDear Magnus,\nThank you for the lecture."
    )
    is_valid, cleaned, reason = validate_handwriting_vlm_output(wrapped_text)
    assert is_valid is True
    assert not cleaned.startswith("Here is")
    assert cleaned.startswith("NOTES\nDear Magnus")


def test_validate_handwriting_vlm_output_catches_repetition_loop():
    """Test catching degenerative 3+ word phrase loops."""
    from app.extractors.handwriting import validate_handwriting_vlm_output

    loop_text = (
        "NOTES\nDear Magnus,\n"
        "accessible to our students accessible to our students accessible to our students\n"
        "Kind regards"
    )
    is_valid, cleaned, reason = validate_handwriting_vlm_output(loop_text)
    assert is_valid is False
    assert reason == "repetitive_phrase_loop"


def test_validate_handwriting_vlm_output_catches_excessive_repeated_lines():
    """Test catching consecutive identical repeated lines."""
    from app.extractors.handwriting import validate_handwriting_vlm_output

    repeated_lines = "Line A\nDuplicate text\nDuplicate text\nDuplicate text\nLine B"
    is_valid, cleaned, reason = validate_handwriting_vlm_output(repeated_lines)
    assert is_valid is False
    assert reason == "excessive_repeated_lines"


def test_validate_handwriting_vlm_output_catches_empty():
    """Test handling of empty or whitespace responses."""
    from app.extractors.handwriting import validate_handwriting_vlm_output

    is_valid, cleaned, reason = validate_handwriting_vlm_output("   \n\t  ")
    assert is_valid is False
    assert reason == "empty_output"


@pytest.mark.anyio
async def test_image_parser_whole_image_handwriting_vlm(monkeypatch):
    """Verify ImageParser sends full image to VLM for handwriting without OCR fragmentation."""
    from unittest.mock import AsyncMock
    from app.parsers.image import image_parser
    from app.models.vision_client import vision_client

    full_images_received = []

    async def mock_transcribe(img, keep_alive=None):
        full_images_received.append(img)
        return "NOTES\nDear Magnus,\nThank you for your guest lectures.", 0.95, {"success": True}

    monkeypatch.setattr(vision_client, "transcribe_handwriting", mock_transcribe)

    # Mock extractor to simulate OCR returning text with handwriting signals
    def mock_extract(img):
        return [
            {"type": "text", "text": "NOTES Dear Magnus", "confidence": 0.65, "bbox": [10, 10, 100, 30]},
            {"type": "text", "text": "Thank you for guest lectures", "confidence": 0.60, "bbox": [10, 40, 100, 60]},
        ]

    monkeypatch.setattr(image_parser.extractor, "extract", mock_extract)

    test_img = Image.new("RGB", (300, 400), color=(255, 255, 255))
    res = await image_parser.parse(test_img, filename="test_handwritten_note.png")

    assert len(full_images_received) == 1
    assert full_images_received[0].size == (300, 400), "VLM must receive full image, not OCR crops"
    assert len(res.extracted_regions) == 1, "Handwritten document should yield ONE coherent handwriting region"
    region = res.extracted_regions[0]
    assert region.type == "handwriting"
    assert "Dear Magnus" in region.text
    assert region.raw["authoritative_source"] == "vlm"
    assert region.raw["requires_human_review"] is False
    assert "NOTES Dear Magnus" in region.raw["ocr_candidate"]
    assert region.raw["full_image_vlm"] is True


@pytest.mark.anyio
async def test_image_parser_handwriting_repetition_loop_falls_back_to_ocr(monkeypatch):
    """Verify ImageParser safely falls back to OCR if VLM produces a repetition loop."""
    from app.parsers.image import image_parser
    from app.models.vision_client import vision_client

    async def mock_transcribe(img, keep_alive=None):
        # Repetitive degenerative loop
        return "looping loop text looping loop text looping loop text", 0.95, {"success": True}

    monkeypatch.setattr(vision_client, "transcribe_handwriting", mock_transcribe)

    def mock_extract(img):
        return [
            {"type": "text", "text": "Safe OCR Candidate Text", "confidence": 0.70, "bbox": [10, 10, 100, 30]},
        ]

    monkeypatch.setattr(image_parser.extractor, "extract", mock_extract)

    test_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    res = await image_parser.parse(test_img, filename="handwritten_note.png")

    assert len(res.extracted_regions) == 1
    region = res.extracted_regions[0]
    assert region.text == "Safe OCR Candidate Text"
    assert region.raw["authoritative_source"] == "ocr_fallback"
    assert region.raw["requires_human_review"] is False
    assert region.raw["vlm_rejection_reason"] == "repetitive_phrase_loop"




