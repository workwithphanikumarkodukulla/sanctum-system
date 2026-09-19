"""Comprehensive tests for the canonical EvidenceNormalizer layer across all document formats."""
from __future__ import annotations

import pytest

from app.evidence.schema import EvidenceElement
from app.parsers.csv import CsvParseResult
from app.parsers.docx import DocxParagraph, DocxParseResult, DocxTable
from app.parsers.image import ImageParseResult, ImageRegion
from app.parsers.pdf import PdfPageResult, PdfParseResult
from app.parsers.pptx import (
    PptxImageItem,
    PptxParseResult,
    PptxSlide,
    PptxTableItem,
    PptxTextItem,
)
from app.parsers.txt import TextBlockInfo, TxtParseResult
from app.parsers.xlsx import XlsxCell, XlsxParseResult, XlsxWorksheet
from app.processing.normalization import normalizer


def test_docx_normalization():
    """Verify DOCX parser results normalize into heading, list, text, and table EvidenceElements."""
    p_head = DocxParagraph(
        index=1,
        reading_order=1,
        text="Executive Summary",
        style="Heading 1",
        is_heading=True,
        heading_level=1,
        source_document="report.docx",
    )
    p_body = DocxParagraph(
        index=2,
        reading_order=2,
        text="This is a standard paragraph describing quarterly revenue.",
        style="Normal",
        is_heading=False,
        source_document="report.docx",
    )
    p_bullet = DocxParagraph(
        index=3,
        reading_order=3,
        text="• First key highlight",
        style="List Bullet",
        is_heading=False,
        source_document="report.docx",
    )
    tbl = DocxTable(
        index=1,
        reading_order=4,
        headers=["Quarter", "Revenue"],
        rows=[["Q1", "$1.2M"], ["Q2", "$1.5M"]],
        num_rows=3,
        num_cols=2,
        source_document="report.docx",
    )

    docx_res = DocxParseResult(
        source_document="report.docx",
        items=[p_head, p_body, p_bullet, tbl],
        paragraphs=[p_head, p_body, p_bullet],
        tables=[tbl],
    )

    elements = normalizer.normalize(
        parser_result=docx_res,
        document_id="doc_docx_001",
        file_hash="hash_docx_abc",
    )

    assert len(elements) == 4

    # 1. Heading element
    assert elements[0].type == "heading"
    assert elements[0].text == "Executive Summary"
    assert elements[0].confidence == 1.0
    assert elements[0].extraction_model == "python-docx"
    assert elements[0].reading_order == 1
    assert elements[0].document_id == "doc_docx_001"
    assert elements[0].file_hash == "hash_docx_abc"
    assert elements[0].provenance["source"] == "docx"
    assert elements[0].provenance["paragraph_index"] == 1

    # 2. Text element
    assert elements[1].type == "text"
    assert elements[1].reading_order == 2
    assert elements[1].confidence == 1.0

    # 3. List element
    assert elements[2].type == "list"
    assert elements[2].reading_order == 3
    assert elements[2].confidence == 1.0

    # 4. Table element
    assert elements[3].type == "table"
    assert elements[3].reading_order == 4
    assert elements[3].table_data == {
        "headers": ["Quarter", "Revenue"],
        "rows": [["Q1", "$1.2M"], ["Q2", "$1.5M"]],
    }
    assert elements[3].provenance["table_index"] == 1
    assert elements[3].confidence == 1.0


def test_pptx_normalization():
    """Verify PPTX parser results normalize slide-by-slide preserving slide index, reading order, and image items."""
    item_title = PptxTextItem(
        slide_number=1,
        reading_order=1,
        text="Project Sanctum Overview",
        is_title=True,
        shape_name="Title 1",
        shape_id=1,
        bbox=[10.0, 10.0, 500.0, 60.0],
    )
    item_bullet = PptxTextItem(
        slide_number=1,
        reading_order=2,
        text="- Item 1\n- Item 2",
        is_title=False,
        shape_name="Content 2",
        shape_id=2,
        bbox=[10.0, 70.0, 500.0, 200.0],
    )
    item_table = PptxTableItem(
        slide_number=1,
        reading_order=3,
        headers=["Metric", "Value"],
        rows=[["Throughput", "1000 ops/sec"]],
        num_rows=2,
        num_cols=2,
        shape_name="Table 3",
        shape_id=3,
        bbox=[10.0, 210.0, 500.0, 350.0],
    )
    item_img = PptxImageItem(
        slide_number=2,
        reading_order=1,
        shape_name="Picture 4",
        shape_id=4,
        content_type="image/png",
        size_bytes=4096,
        bbox=[50.0, 50.0, 400.0, 300.0],
    )

    slide1 = PptxSlide(slide_number=1, title="Project Sanctum Overview", items=[item_title, item_bullet, item_table])
    slide2 = PptxSlide(slide_number=2, title=None, items=[item_img])

    pptx_res = PptxParseResult(
        source_document="deck.pptx",
        slides=[slide1, slide2],
    )

    elements = normalizer.normalize(
        parser_result=pptx_res,
        document_id="doc_pptx_001",
        file_hash="hash_pptx_xyz",
    )

    assert len(elements) == 4

    # Title -> heading
    assert elements[0].type == "heading"
    assert elements[0].slide == 1
    assert elements[0].page == 1
    assert elements[0].confidence == 1.0
    assert elements[0].bbox == [10.0, 10.0, 500.0, 60.0]
    assert elements[0].provenance["shape_name"] == "Title 1"

    # Bullets -> list
    assert elements[1].type == "list"
    assert elements[1].slide == 1

    # Table
    assert elements[2].type == "table"
    assert elements[2].slide == 1
    assert elements[2].table_data["headers"] == ["Metric", "Value"]

    # Image shape -> image element without OCR
    assert elements[3].type == "image"
    assert elements[3].slide == 2
    assert elements[3].text is None
    assert elements[3].metadata["content_type"] == "image/png"
    assert elements[3].confidence == 1.0


def test_xlsx_normalization():
    """Verify XLSX normalization extracts tables and formula elements with cell coordinates and sheet provenance."""
    fc = XlsxCell(
        coordinate="B4",
        row=4,
        column=2,
        value="=SUM(B1:B3)",
        value_str="=SUM(B1:B3)",
        is_formula=True,
        formula="=SUM(B1:B3)",
        is_empty=False,
        data_type="formula",
    )

    ws = XlsxWorksheet(
        name="Finances",
        sheet_index=1,
        max_row=4,
        max_column=2,
        merged_cells=["A1:B1"],
        headers=["Month", "Amount"],
        data_rows=[["Jan", "100"], ["Feb", "200"], ["Mar", "300"]],
        formula_cells=[fc],
    )

    xlsx_res = XlsxParseResult(
        source_document="budget.xlsx",
        worksheets=[ws],
    )

    elements = normalizer.normalize(
        parser_result=xlsx_res,
        document_id="doc_xlsx_001",
        file_hash="hash_xlsx_123",
    )

    assert len(elements) == 2

    # Grid table
    tbl_elem = elements[0]
    assert tbl_elem.type == "table"
    assert tbl_elem.sheet == "Finances"
    assert tbl_elem.page == 1
    assert tbl_elem.confidence == 1.0
    assert tbl_elem.table_data["headers"] == ["Month", "Amount"]
    assert tbl_elem.metadata["merged_ranges"] == ["A1:B1"]
    assert tbl_elem.provenance["source"] == "xlsx"
    assert tbl_elem.provenance["sheet"] == "Finances"

    # Formula element
    f_elem = elements[1]
    assert f_elem.type == "formula"
    assert f_elem.text == "=SUM(B1:B3)"
    assert f_elem.formula_latex == "=SUM(B1:B3)"
    assert f_elem.sheet == "Finances"
    assert f_elem.row == 4
    assert f_elem.column == 2
    assert f_elem.confidence == 1.0
    assert f_elem.provenance["cell_coordinate"] == "B4"


def test_csv_normalization():
    """Verify CSV normalization outputs structured table evidence with dialect provenance."""
    csv_res = CsvParseResult(
        source_document="data.csv",
        headers=["id", "name", "score"],
        rows=[["1", "Alice", "95"], ["2", "Bob", "88"]],
        all_rows=[["id", "name", "score"], ["1", "Alice", "95"], ["2", "Bob", "88"]],
        num_rows=3,
        num_cols=3,
        delimiter=";",
        has_header=True,
    )

    elements = normalizer.normalize(
        parser_result=csv_res,
        document_id="doc_csv_001",
        file_hash="hash_csv_456",
    )

    assert len(elements) == 1
    elem = elements[0]
    assert elem.type == "table"
    assert elem.confidence == 1.0
    assert elem.table_data["headers"] == ["id", "name", "score"]
    assert elem.table_data["rows"] == [["1", "Alice", "95"], ["2", "Bob", "88"]]
    assert elem.metadata["delimiter"] == ";"
    assert elem.provenance["delimiter"] == ";"
    assert elem.reading_order == 1


def test_txt_normalization():
    """Verify TXT normalization assigns line bounds, reading order, and block types."""
    b_head = TextBlockInfo(start_line=1, end_line=1, line_count=1, text="# Title of Text Document")
    b_list = TextBlockInfo(start_line=3, end_line=5, line_count=3, text="• First item\n• Second item\n• Third item")
    b_para = TextBlockInfo(start_line=7, end_line=8, line_count=2, text="This is a paragraph.\nIt continues here.")

    txt_res = TxtParseResult(
        extracted_text="# Title of Text Document\n\n• First item\n• Second item\n• Third item\n\nThis is a paragraph.\nIt continues here.",
        blocks=[b_head, b_list, b_para],
        metadata={"encoding": "utf-8"},
    )

    elements = normalizer.normalize(
        parser_result=txt_res,
        document_id="doc_txt_001",
        file_hash="hash_txt_789",
    )

    assert len(elements) == 3

    assert elements[0].type == "heading"
    assert elements[0].row == 1
    assert elements[0].reading_order == 1
    assert elements[0].confidence == 1.0
    assert elements[0].provenance["start_line"] == 1

    assert elements[1].type == "list"
    assert elements[1].row == 3
    assert elements[1].reading_order == 2

    assert elements[2].type == "text"
    assert elements[2].row == 7
    assert elements[2].reading_order == 3


def test_image_normalization_preserves_ocr_confidence():
    """Verify Image OCR normalization strictly preserves the raw OCR confidence and coordinates."""
    r1 = ImageRegion(
        region_index=1,
        type="text",
        bbox=[12.0, 34.0, 150.0, 70.0],
        text="Sanctum Secure Vault",
        confidence=0.8842,
        extraction_model="Tesseract",
        raw={"word_count": 3},
    )
    r2 = ImageRegion(
        region_index=2,
        type="table",
        bbox=[20.0, 100.0, 400.0, 300.0],
        text="Table of Data",
        confidence=0.9250,
        extraction_model="Tesseract",
        raw={"lines": 5},
    )

    img_res = ImageParseResult(
        source_document="scan.png",
        image_width=800,
        image_height=600,
        image_format="PNG",
        extracted_regions=[r1, r2],
    )

    elements = normalizer.normalize(
        parser_result=img_res,
        document_id="doc_img_001",
        file_hash="hash_img_ocr",
    )

    assert len(elements) == 2

    # OCR confidence must NOT be overwritten to 1.0!
    assert elements[0].confidence == 0.8842
    assert elements[0].type == "text"
    assert elements[0].bbox == [12.0, 34.0, 150.0, 70.0]
    assert elements[0].extraction_model == "Tesseract"
    assert elements[0].provenance["source"] == "image_ocr"
    assert elements[0].provenance["region_index"] == 1

    assert elements[1].confidence == 0.9250
    assert elements[1].type == "table"
    assert elements[1].bbox == [20.0, 100.0, 400.0, 300.0]


def test_pdf_normalization_preserves_multipage_and_ocr_confidence():
    """Verify PDF normalization preserves per-page elements, reading order, and OCR confidence."""
    e1 = EvidenceElement(
        id="p1_e1",
        document_id="temp_doc",
        page=1,
        type="text",
        text="Digital page paragraph",
        bbox=[10.0, 20.0, 200.0, 40.0],
        confidence=1.0,
        extraction_model="PyMuPDF-Direct",
        file_hash="old_hash",
        timestamp="2026-09-05T00:00:00Z",
    )
    e2 = EvidenceElement(
        id="p2_e1",
        document_id="temp_doc",
        page=2,
        type="text",
        text="Scanned OCR text paragraph",
        bbox=[15.0, 25.0, 300.0, 60.0],
        confidence=0.8125,
        extraction_model="PyMuPDF+OCR",
        file_hash="old_hash",
        timestamp="2026-09-05T00:00:00Z",
    )

    page1 = PdfPageResult(
        page_number=1,
        is_digital=True,
        text="Digital page paragraph",
        extraction_method="PyMuPDF-Direct",
        elements=[e1],
    )
    page2 = PdfPageResult(
        page_number=2,
        is_digital=False,
        text="Scanned OCR text paragraph",
        extraction_method="PyMuPDF+OCR",
        elements=[e2],
    )

    pdf_res = PdfParseResult(
        source_document="doc.pdf",
        pages=[page1, page2],
    )

    elements = normalizer.normalize(
        parser_result=pdf_res,
        document_id="doc_pdf_normalized",
        file_hash="hash_pdf_target",
    )

    assert len(elements) == 2

    # Page 1 digital element
    assert elements[0].document_id == "doc_pdf_normalized"
    assert elements[0].file_hash == "hash_pdf_target"
    assert elements[0].page == 1
    assert elements[0].confidence == 1.0
    assert elements[0].reading_order == 1
    assert elements[0].provenance["extraction_method"] == "PyMuPDF-Direct"

    # Page 2 scanned element
    assert elements[1].document_id == "doc_pdf_normalized"
    assert elements[1].file_hash == "hash_pdf_target"
    assert elements[1].page == 2
    assert elements[1].confidence == 0.8125
    assert elements[1].reading_order == 2
    assert elements[1].provenance["extraction_method"] == "PyMuPDF+OCR"


def test_fallback_element_normalization():
    """Verify raw EvidenceElements or custom objects normalize with assigned reading order and fallback provenance."""
    e = EvidenceElement(
        id="raw_1",
        document_id="old_doc",
        page=1,
        type="text",
        text="Arbitrary extracted text",
        confidence=0.9,
        extraction_model="custom_parser",
        file_hash="old_hash",
        timestamp="2026-09-05T00:00:00Z",
    )

    # Test direct list of elements
    normalized_list = normalizer.normalize([e], document_id="new_doc_id", file_hash="new_file_hash")
    assert len(normalized_list) == 1
    assert normalized_list[0].document_id == "new_doc_id"
    assert normalized_list[0].file_hash == "new_file_hash"
    assert normalized_list[0].reading_order == 1
    assert normalized_list[0].provenance["source"] == "generic"
