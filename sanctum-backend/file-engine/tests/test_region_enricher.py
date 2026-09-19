"""Unit tests for the generalized RegionEnricher service using mocked VLM responses."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest
from PIL import Image, ImageDraw

from app.parsers.image import ImageParser
from app.parsers.ocr_enricher import OCREnricher, RegionEnricher, region_enricher


@pytest.fixture
def sample_crop() -> Image.Image:
    """Create a simple test image crop."""
    img = Image.new("RGB", (100, 40), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "Crop Test", fill=(0, 0, 0))
    return img


# 1. High-confidence OCR bypasses VLM
@pytest.mark.anyio
async def test_region_enricher_high_confidence_bypasses_vlm(sample_crop: Image.Image):
    """If OCR confidence >= threshold, return OCR result directly without calling VLM."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Perfect Printed Heading",
            ocr_confidence=0.96,
            content_type="text",
            threshold=0.80,
            model_name="Tesseract",
        )

        mock_vlm.assert_not_called()
        assert res.vlm_invoked is False
        assert res.final_text == "Perfect Printed Heading"
        assert res.ocr_result == "Perfect Printed Heading"
        assert res.vlm_result is None
        assert res.confidence == 0.96
        assert res.extraction_method == "Tesseract"
        assert res.provenance["source"] == "ocr_direct"
        assert res.provenance["vlm_invoked"] is False


# 2. Low-confidence OCR escalates ONLY the cropped region to VLM
@pytest.mark.anyio
async def test_region_enricher_low_confidence_escalates_only_crop(sample_crop: Image.Image):
    """If OCR confidence < threshold, send ONLY that region crop to local VLM."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Clear Corrected Heading", 0.94)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="C1ear C0rrected Hcad1ng",
            ocr_confidence=0.52,
            content_type="text",
            threshold=0.80,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        # Verify specifically that ONLY the crop image was passed to VLM, not an entire document
        passed_crop = mock_vlm.call_args[0][0]
        assert passed_crop is sample_crop
        assert passed_crop.size == (100, 40)

        assert res.vlm_invoked is True
        assert res.final_text == "Clear Corrected Heading"
        assert res.ocr_result == "C1ear C0rrected Hcad1ng"
        assert res.vlm_result == "Clear Corrected Heading"
        assert res.confidence == 0.94
        assert "Tesseract+" in res.extraction_method
        assert res.provenance["source"] == "vlm_visual_escalation"
        assert res.provenance["ocr_candidate"] == "C1ear C0rrected Hcad1ng"
        assert res.provenance["vlm_candidate"] == "Clear Corrected Heading"


# 3. Handwriting region with consensus match
@pytest.mark.anyio
async def test_region_enricher_handwriting_consensus_matched(sample_crop: Image.Image):
    """Handwriting region compares OCR and VLM; consensus match yields boosted confidence."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Authorized by J. Smith", 0.85)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Authorized by J. Smith",
            ocr_confidence=0.62,
            content_type="handwriting",
            threshold=0.75,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert res.final_text == "Authorized by J. Smith"
        assert res.ocr_result == "Authorized by J. Smith"
        assert res.vlm_result == "Authorized by J. Smith"
        assert res.confidence >= 0.95  # High consensus confidence
        assert res.provenance["authoritative_source"] == "vlm"
        assert res.provenance["consensus"] == "matched"


# 4. Handwriting region with candidate divergence: VLM authoritative
@pytest.mark.anyio
async def test_region_enricher_handwriting_consensus_conflicted(sample_crop: Image.Image):
    """Handwriting divergence between OCR and VLM: VLM is authoritative without human review."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Rejected - Signature Mismatch", 0.85)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Approved - Signature Valid",
            ocr_confidence=0.60,
            content_type="handwriting",
            threshold=0.75,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert res.final_text == "Rejected - Signature Mismatch"
        assert res.ocr_result == "Approved - Signature Valid"
        assert res.vlm_result == "Rejected - Signature Mismatch"
        assert res.provenance["authoritative_source"] == "vlm"
        assert res.metadata["requires_human_review"] is False


# 5. Standalone image parser enrichment integration
@pytest.mark.anyio
async def test_region_enricher_standalone_image_integration(sample_crop: Image.Image):
    """Standalone raster image regions are enriched through region_enricher."""
    class MockExtractor:
        def extract(self, img):
            return [{
                "type": "text",
                "bbox": [5.0, 5.0, 80.0, 30.0],
                "text": "Poor OCR",
                "confidence": 0.40,
                "extraction_model": "Tesseract",
                "raw": {},
            }]

    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("High Quality VLM Text", 0.91)

        parser = ImageParser(extractor=MockExtractor())
        result = await parser.parse(
            file_bytes=sample_crop,
            filename="standalone_photo.png",
            document_id="doc_standalone",
            file_hash="hash_standalone",
        )

        assert len(result.extracted_regions) == 1
        reg = result.extracted_regions[0]
        assert reg.text == "High Quality VLM Text"
        assert reg.confidence == 0.91
        assert "enrichment_provenance" in reg.raw
        assert reg.raw["enrichment_provenance"]["vlm_invoked"] is True
        assert result.metadata["vlm_invoked"] is True


# 6. Embedded image in document enrichment
@pytest.mark.anyio
async def test_region_enricher_embedded_image_enrichment(sample_crop: Image.Image):
    """Images embedded in documents (e.g. DOCX/PPTX shapes) can be enriched via enrich_embedded_image."""
    class MockExtractor:
        def extract(self, img):
            return [{
                "type": "image",
                "bbox": [0.0, 0.0, 100.0, 40.0],
                "text": "Diagram Fig 3.1",
                "confidence": 0.45,
                "extraction_model": "Tesseract",
            }]

    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Diagram Fig 3.1: Architecture Flowchart", 0.88)

        res = await region_enricher.enrich_embedded_image(
            image=sample_crop,
            content_type="image",
            threshold=0.80,
            extractor=MockExtractor(),
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert res.ocr_result == "Diagram Fig 3.1"
        assert res.vlm_result == "Diagram Fig 3.1: Architecture Flowchart"
        assert res.final_text == "Diagram Fig 3.1: Architecture Flowchart"
        assert res.confidence == 0.88


# 7. Scanned PDF page region enrichment delegates to crop only
@pytest.mark.anyio
async def test_region_enricher_scanned_pdf_delegation():
    """Scanned PDF elements send only the specific low-confidence crop, not the full page."""
    full_page = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    raw_elements = [
        {
            "type": "text",
            "bbox": [50.0, 50.0, 300.0, 90.0],
            "text": "Header line with high confidence",
            "confidence": 0.95,
            "extraction_model": "Tesseract",
        },
        {
            "type": "text",
            "bbox": [50.0, 150.0, 300.0, 200.0],
            "text": "Blurry smeared paragraph line",
            "confidence": 0.42,
            "extraction_model": "Tesseract",
        },
    ]

    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Sharp Enriched Paragraph Line", 0.90)

        elements = await OCREnricher.enrich_and_build_elements(
            raw_elements=raw_elements,
            page_image=full_page,
            page_num=1,
            document_id="doc_pdf_scan",
            file_hash="hash_scan",
        )

        # VLM should be called exactly ONCE (for the blurry line), NOT for the high-confidence header
        assert mock_vlm.call_count == 1
        crop_passed = mock_vlm.call_args[0][0]
        # Crop size corresponds to bbox [50, 150, 300, 200] with standard padding -> (258, 58), definitely not full page (800, 1000)
        assert crop_passed.size == (258, 58)
        assert crop_passed.size != full_page.size

        assert len(elements) == 2
        # First element bypassed VLM
        assert elements[0].text == "Header line with high confidence"
        assert elements[0].confidence == 0.95
        assert elements[0].metadata["enrichment_provenance"]["vlm_invoked"] is False

        # Second element enriched by VLM
        assert elements[1].text == "Sharp Enriched Paragraph Line"
        assert elements[1].confidence == 0.90
        assert elements[1].metadata["enrichment_provenance"]["vlm_invoked"] is True
        assert elements[1].metadata["enrichment_provenance"]["ocr_candidate"] == "Blurry smeared paragraph line"
        assert elements[1].metadata["enrichment_provenance"]["vlm_candidate"] == "Sharp Enriched Paragraph Line"


# 8. Graceful fallback when VLM is offline or returns blank
@pytest.mark.anyio
async def test_region_enricher_vlm_offline_graceful_fallback(sample_crop: Image.Image):
    """When VLM is unavailable or returns blank, fall back to OCR safely without raising errors."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = (None, 0.0)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Original OCR Text",
            ocr_confidence=0.55,
            content_type="text",
            threshold=0.80,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is False
        assert res.final_text == "Original OCR Text"
        assert res.ocr_result == "Original OCR Text"
        assert res.vlm_result is None
        assert res.confidence == 0.55
        assert res.metadata["vlm_result_empty"] is True
        assert res.provenance["source"] == "ocr_fallback_after_vlm_empty"


# 9. Suspicious characters trigger VLM despite high OCR confidence
@pytest.mark.anyio
async def test_suspicious_characters_trigger_vlm_despite_high_confidence(sample_crop: Image.Image):
    """Region with high OCR confidence (e.g. 0.92) but suspicious digit-letter confusion escalates to VLM."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Pressure: 5000 kPa", 0.95)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Pressure: 5O00 kPa",  # 5O00 has digit-letter 'O' confusion
            ocr_confidence=0.92,
            content_type="text",
            threshold=0.68,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert "numeric_letter_confusion" in res.metadata.get("suspicion_signals", [])
        assert res.final_text == "Pressure: 5000 kPa"


# 10. OCR confidence is treated as a routing quality signal, not an accuracy guarantee
@pytest.mark.anyio
async def test_ocr_confidence_semantics_in_provenance(sample_crop: Image.Image):
    """Verify that raw OCR confidence is preserved with explicit routing semantics."""
    res = await region_enricher.enrich_region(
        crop=sample_crop,
        ocr_text="Standard verified document text",
        ocr_confidence=0.94,
        content_type="text",
        threshold=0.68,
        model_name="Tesseract",
    )

    assert res.vlm_invoked is False
    assert res.provenance["raw_ocr_confidence"] == 0.94
    assert res.provenance["ocr_confidence_semantics"] == "engine_quality_routing_signal"
    assert res.metadata["ocr_confidence_semantics"] == "engine_quality_routing_signal"
    assert res.metadata["raw_ocr_confidence"] == 0.94


# 11. OCR/VLM numeric disagreement is preserved as a conflict
@pytest.mark.anyio
async def test_vlm_reconciliation_numeric_disagreement_preserved_as_conflict(sample_crop: Image.Image):
    """Numeric disagreement between OCR and VLM flags conflict and preserves both candidates."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("Tank Capacity: 500 L", 0.91)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="Tank Capacity: 5000 L",
            ocr_confidence=0.55,
            content_type="engineering_spec",
            threshold=0.68,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert res.ocr_result == "Tank Capacity: 5000 L"
        assert res.vlm_result == "Tank Capacity: 500 L"
        # Conflict must be flagged for human review
        assert res.metadata.get("requires_human_review") is True
        assert res.provenance.get("requires_review") is True
        assert res.provenance["agreement_status"] == "material_disagreement"
        # Both candidates strictly preserved
        assert res.provenance["ocr_candidate"] == "Tank Capacity: 5000 L"
        assert res.provenance["vlm_candidate"] == "Tank Capacity: 500 L"
        assert any(d["category"] == "number_mismatch" for d in res.provenance["disagreements"])


# 12. OCR/VLM formula disagreement is preserved as a conflict
@pytest.mark.anyio
async def test_vlm_reconciliation_formula_disagreement_preserved_as_conflict(sample_crop: Image.Image):
    """Mathematical formula disagreement flags conflict and preserves both candidates."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("E = m * c^3", 0.92)

        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="E = m * c^2",
            ocr_confidence=0.60,
            content_type="formula",
            threshold=0.85,
            model_name="Tesseract",
        )

        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True
        assert res.metadata.get("requires_human_review") is True
        assert res.provenance.get("requires_review") is True
        assert res.provenance["ocr_candidate"] == "E = m * c^2"
        assert res.provenance["vlm_candidate"] == "E = m * c^3"
        assert any(d["category"] in ("formula_mismatch", "number_mismatch") for d in res.provenance["disagreements"])


# 13. Critical region threshold escalation
@pytest.mark.anyio
async def test_critical_region_threshold_escalation(sample_crop: Image.Image):
    """Formula and critical engineering specs use CRITICAL_REGION_THRESHOLD (0.85)."""
    with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
        mock_vlm.return_value = ("P_max = 12.5 MPa", 0.95)

        # Confidence is 0.78 (which is above standard 0.68, but below critical threshold 0.85)
        res = await region_enricher.enrich_region(
            crop=sample_crop,
            ocr_text="P_max = 12.5 MPa",
            ocr_confidence=0.78,
            content_type="formula",
            model_name="Tesseract",
        )

        # Should escalate to VLM because 0.78 < CRITICAL_REGION_THRESHOLD (0.85)
        mock_vlm.assert_called_once()
        assert res.vlm_invoked is True


# 14. Handwriting override: high-confidence OCR on handwritten text ALWAYS escalates to VLM
@pytest.mark.anyio
async def test_handwritten_region_high_ocr_confidence_triggers_handwriting_override(sample_crop: Image.Image):
    """High OCR confidence on handwriting does not bypass VLM; HANDWRITING_OVERRIDE event is recorded."""
    from app.observability.processing_trace import set_current_trace, ProcessingTrace

    trace = ProcessingTrace(document_id="doc_hw_override_test")
    token = set_current_trace(trace)
    try:
        with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
            # Gemma4 provides the correct reading ("Dear Magnus, our team") fixing PaddleOCR's "Deak Magnus, ouk team"
            mock_vlm.return_value = ("Dear Magnus, our team", 0.96)

            res = await region_enricher.enrich_region(
                crop=sample_crop,
                ocr_text="Deak Magnus, ouk team",
                ocr_confidence=0.95,  # High OCR confidence that would normally bypass gate
                content_type="handwriting",
                metadata={"handwriting_classification": "handwritten"},
                threshold=0.80,
                model_name="PaddleOCR",
            )

            # Assert VLM was called despite 0.95 >= 0.80
            mock_vlm.assert_called_once()
            assert res.vlm_invoked is True
            # VLM reading is chosen as primary result on conflict
            assert res.final_text == "Dear Magnus, our team"
            assert res.ocr_result == "Deak Magnus, ouk team"
            # VLM is authoritative on handwriting; requires_human_review is False
            assert res.metadata.get("requires_human_review") is False
            assert res.provenance.get("authoritative_source") == "vlm"
            assert res.metadata.get("handwriting_override") is True
            assert res.provenance.get("handwriting_override") is True

            # Verify HANDWRITING_OVERRIDE was recorded in the processing trace
            events = trace.to_dict()["events"]
            hw_override_events = [e for e in events if e.get("event") == "HANDWRITING_OVERRIDE"]
            assert len(hw_override_events) == 1
            evt = hw_override_events[0]
            assert evt["stage"] == "CONFIDENCE_GATE"
            assert evt["component"] == "ConfidenceGate"
            assert evt["metadata"]["decision"] == "ESCALATE"
            assert evt["metadata"]["confidence"] == 0.95
    finally:
        set_current_trace(None)


# 15. Mixed document: printed region respects confidence threshold while handwritten region always escalates
@pytest.mark.anyio
async def test_mixed_document_printed_and_handwritten_confidence_gating(sample_crop: Image.Image):
    """Printed text at 0.95 confidence skips VLM, while handwritten text at 0.95 confidence escalates."""
    from app.observability.processing_trace import set_current_trace, ProcessingTrace

    trace = ProcessingTrace(document_id="doc_mixed_gating_test")
    token = set_current_trace(trace)
    try:
        with patch("app.models.vision_client.vision_client.reread_cropped_region", new_callable=AsyncMock) as mock_vlm:
            mock_vlm.return_value = ("Handwritten annotation verified", 0.90)

            # Region 1: Printed heading with high confidence (0.95)
            res_printed = await region_enricher.enrich_region(
                crop=sample_crop,
                ocr_text="Standard Printed Heading",
                ocr_confidence=0.95,
                content_type="text",
                metadata={"handwriting_classification": "printed"},
                threshold=0.80,
                model_name="PaddleOCR",
            )

            # Printed region must bypass VLM
            assert res_printed.vlm_invoked is False
            assert res_printed.final_text == "Standard Printed Heading"
            mock_vlm.assert_not_called()

            # Region 2: Handwritten annotation with identical high confidence (0.95)
            res_handwritten = await region_enricher.enrich_region(
                crop=sample_crop,
                ocr_text="Handwritten annotat1on",
                ocr_confidence=0.95,
                content_type="handwriting",
                metadata={"handwriting_classification": "handwritten"},
                threshold=0.80,
                model_name="PaddleOCR",
            )

            # Handwritten region must escalate to VLM despite high OCR confidence
            assert res_handwritten.vlm_invoked is True
            mock_vlm.assert_called_once()

            # Trace should contain HANDWRITING_OVERRIDE for handwritten, and ACCEPT for printed
            events = trace.to_dict()["events"]
            decisions = [e for e in events if e.get("event") in ("CONFIDENCE_EVALUATED", "HANDWRITING_OVERRIDE")]
            assert any(e.get("event") == "HANDWRITING_OVERRIDE" for e in decisions)
            assert any(e.get("metadata", {}).get("decision") == "ACCEPT" for e in decisions)
    finally:
        set_current_trace(None)


