"""End-to-end integration tests for EvidencePipeline routing, classification, formulas, and reconciliation."""
from __future__ import annotations

import pytest

from app.classification import ContentType
from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import DocumentEvidence, EvidenceElement
from app.processing.pipeline import pipeline


@pytest.mark.anyio
async def test_pipeline_formula_routing_and_sympy_execution():
    """Verify formulas in ingested documents are classified and extracted into canonical metadata without automatic computation."""
    txt_content = "2 * 150 + 50\n".encode("utf-8")

    doc: DocumentEvidence = await pipeline.process_document(
        document_id="doc_formula_calc",
        file_bytes=txt_content,
        filename="formula_test.txt",
    )

    assert doc.processing_status == "completed"
    assert len(doc.elements) >= 1

    formula_elem = doc.elements[0]
    assert formula_elem.type == "formula"
    assert formula_elem.formula_latex is not None
    assert "formula_details" in formula_elem.metadata
    assert formula_elem.metadata["formula_details"]["original_text"] == "2 * 150 + 50"
    # Document Engine does NOT perform automatic calculation during ingestion
    assert "calculated_value" not in formula_elem.metadata
    assert formula_elem.metadata["content_classification"]["content_type"] == ContentType.FORMULA.value


@pytest.mark.anyio
async def test_pipeline_markdown_table_routing():
    """Verify markdown tables in plain text documents are classified and routed to table_extractor."""
    table_txt = (
        "| Component | Tag | Rating |\n"
        "|-----------|-----|--------|\n"
        "| Safety Valve | PSV-101 | 600 kPa |\n"
        "| Control Valve | FCV-202 | 450 kPa |\n"
    ).encode("utf-8")

    doc = await pipeline.process_document(
        document_id="doc_pipe_tbl",
        file_bytes=table_txt,
        filename="pipeline_table.txt",
    )

    assert doc.processing_status == "completed"
    assert len(doc.elements) >= 1

    tbl_elem = doc.elements[0]
    assert tbl_elem.type == "table"
    assert tbl_elem.table_data is not None
    assert tbl_elem.table_data["headers"] == ["Component", "Tag", "Rating"]
    assert len(tbl_elem.table_data["rows"]) == 2
    assert tbl_elem.table_data["rows"][0] == ["Safety Valve", "PSV-101", "600 kPa"]


@pytest.mark.anyio
async def test_pipeline_handwriting_reconciliation_integration():
    """Verify multi-candidate OCR and VLM readings undergo reconciliation in EvidencePipeline."""
    element = EvidenceBuilder.build_element(
        element_idx=1,
        document_id="doc_hw_test",
        page=1,
        elem_type="text",
        text="Feed Compresor Line",
        bbox=[10.0, 20.0, 300.0, 60.0],
        confidence=0.75,
        extraction_model="Tesseract",
        file_hash="hash_hw",
        metadata={
            "enrichment_provenance": {
                "ocr_candidate": "Feed Compresor Line",
                "vlm_candidate": "Feed Compressor Line",
                "ocr_model": "Tesseract",
                "vlm_model": "gemma4",
            }
        },
    )

    routed = await pipeline.route_and_enrich_elements(
        elements=[element],
        document_id="doc_hw_test",
        file_hash="hash_hw",
    )

    assert len(routed) == 1
    elem = routed[0]
    assert "reconciliation" in elem.metadata
    assert elem.metadata["reconciliation"]["agreement_status"] == "minor_ocr_difference"
    # Confidence is boosted upon minor OCR difference reconciliation
    assert elem.confidence >= 0.85
    assert elem.metadata["reconciliation"]["candidate_a"]["text"] == "Feed Compresor Line"
    assert elem.metadata["reconciliation"]["candidate_b"]["text"] == "Feed Compressor Line"


@pytest.mark.anyio
async def test_pipeline_conflict_flags_human_review():
    """Verify conflicting numbers between OCR and VLM trigger requires_human_review=True."""
    element = EvidenceBuilder.build_element(
        element_idx=2,
        document_id="doc_conflict",
        page=2,
        elem_type="text",
        text="Set point: 450 kPa",
        bbox=[10.0, 100.0, 250.0, 140.0],
        confidence=0.85,
        extraction_model="Tesseract",
        file_hash="hash_conflict",
        metadata={
            "enrichment_provenance": {
                "ocr_candidate": "Set point: 450 kPa",
                "vlm_candidate": "Set point: 480 kPa",
                "ocr_model": "Tesseract",
                "vlm_model": "gemma4",
            }
        },
    )

    routed = await pipeline.route_and_enrich_elements(
        elements=[element],
        document_id="doc_conflict",
        file_hash="hash_conflict",
    )

    assert len(routed) == 1
    elem = routed[0]
    assert elem.metadata.get("requires_human_review") is True
    assert elem.metadata["reconciliation"]["agreement_status"] == "material_disagreement"
    # Both candidates preserved
    assert elem.metadata["reconciliation"]["candidate_a"]["text"] == "Set point: 450 kPa"
    assert elem.metadata["reconciliation"]["candidate_b"]["text"] == "Set point: 480 kPa"
    # Confidence discounted on material conflict
    assert elem.confidence <= 0.50


@pytest.mark.anyio
async def test_pipeline_spatial_and_provenance_preservation():
    """Verify page, slide, sheet, row, bbox, and provenance coordinates are strictly preserved."""
    element = EvidenceBuilder.build_element(
        element_idx=7,
        document_id="doc_coords",
        page=3,
        slide=2,
        sheet="Sheet1",
        row=12,
        elem_type="text",
        text="Normal paragraph line with standard telemetry.",
        bbox=[55.0, 120.0, 480.0, 160.0],
        confidence=0.92,
        extraction_model="PyMuPDF-Direct",
        file_hash="hash_coords",
        metadata={"custom_flag": "important"},
    )

    routed = await pipeline.route_and_enrich_elements(
        elements=[element],
        document_id="doc_coords",
        file_hash="hash_coords",
    )

    elem = routed[0]
    assert elem.reading_order == 7
    assert elem.page == 3
    assert elem.slide == 2
    assert elem.sheet == "Sheet1"
    assert elem.row == 12
    assert elem.bbox == [55.0, 120.0, 480.0, 160.0]
    assert elem.file_hash == "hash_coords"
    assert elem.metadata["custom_flag"] == "important"
    assert "content_classification" in elem.metadata
