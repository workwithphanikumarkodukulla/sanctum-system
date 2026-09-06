"""Unit tests for the modular Document Content Classifier."""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from app.classification import (
    ClassificationResult,
    ClassificationStrategy,
    ContentClassifier,
    ContentType,
    content_classifier,
)
from app.evidence.schema import EvidenceElement


def test_classify_text_paragraph():
    """Verify regular paragraph text is classified as ContentType.TEXT."""
    text = (
        "The Sanctum Multimodal Evidence Engine provides auditable, deterministic "
        "document processing for mission-critical enterprise workloads."
    )
    result = content_classifier.classify_region(text=text)

    assert result.content_type == ContentType.TEXT
    assert result.confidence >= 0.90
    assert "prose" in result.reason.lower() or "text" in result.reason.lower()
    assert result.metadata.get("strategy") == "text_pattern_strategy"


def test_classify_native_docx_and_pptx_metadata():
    """Verify native parser metadata (table, heading, shape) classifies deterministically."""
    # Table via metadata
    table_result = content_classifier.classify_region(
        text="Sample table",
        metadata={"source": "docx_table", "total_rows": 5},
    )
    assert table_result.content_type == ContentType.TABLE
    assert table_result.confidence == 1.0
    assert "table" in table_result.reason.lower()

    # Heading via metadata
    heading_result = content_classifier.classify_region(
        text="SECTION 4: SYSTEM ARCHITECTURE",
        metadata={"is_heading": True, "heading_level": 1},
    )
    assert heading_result.content_type == ContentType.TEXT
    assert heading_result.confidence == 1.0

    # Image shape via metadata
    image_result = content_classifier.classify_region(
        metadata={"shape_type": "PICTURE", "source": "pptx_image"},
    )
    assert image_result.content_type == ContentType.IMAGE
    assert image_result.confidence == 1.0


def test_classify_markdown_and_tab_delimited_tables():
    """Verify pipe and tab-delimited text tables are classified as ContentType.TABLE."""
    # Markdown pipe table
    pipe_table = (
        "| Parameter | Value | Status |\n"
        "|---|---|---|\n"
        "| Pressure | 150 psi | OK |\n"
        "| Temperature | 320 C | Nominal |"
    )
    res_pipe = content_classifier.classify_region(text=pipe_table)
    assert res_pipe.content_type == ContentType.TABLE
    assert res_pipe.confidence >= 0.90
    assert "pipe table" in res_pipe.reason.lower()

    # Tab-delimited table
    tab_table = "Tag\tService\tFlowrate\nFCV-101\tFuel Gas\t450 gpm\nPCV-202\tSteam\t1200 lb/hr"
    res_tab = content_classifier.classify_region(text=tab_table)
    assert res_tab.content_type == ContentType.TABLE
    assert res_tab.confidence >= 0.90
    assert "tab" in res_tab.reason.lower()


def test_classify_xlsx_and_latex_formulas():
    """Verify spreadsheet formulas and LaTeX expressions are classified as ContentType.FORMULA."""
    # Spreadsheet formula
    excel_formula = "=SUM(B2:B10) * 1.18"
    res_excel = content_classifier.classify_region(text=excel_formula)
    assert res_excel.content_type == ContentType.FORMULA
    assert res_excel.confidence >= 0.95

    # LaTeX equation
    latex_eq = r"\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}"
    res_latex = content_classifier.classify_region(text=latex_eq)
    assert res_latex.content_type == ContentType.FORMULA
    assert res_latex.confidence >= 0.95
    assert "latex" in res_latex.reason.lower()

    # Unicode math symbols
    unicode_math = "∑(x_i - μ)^2 / N ≥ 0.05"
    res_unicode = content_classifier.classify_region(text=unicode_math)
    assert res_unicode.content_type == ContentType.FORMULA
    assert res_unicode.confidence >= 0.85


def test_classify_image_raster():
    """Verify high-variance photographic or complex visual crop is classified as ContentType.IMAGE."""
    # Create synthetic high-variance image (noise pattern simulating photo/diagram crop)
    np_img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(np_img)

    result = content_classifier.classify_region(image=img)
    assert result.content_type == ContentType.IMAGE
    assert result.confidence >= 0.80
    assert "variance" in result.reason.lower() or "image" in result.reason.lower()


def test_classify_handwriting_region():
    """Verify low-confidence OCR with irregular character artifacts is classified as ContentType.HANDWRITING."""
    handwriting_ocr = "Signed: J~hn D^e [date: 12/04/23]"
    result = content_classifier.classify_region(
        text=handwriting_ocr,
        metadata={"confidence": 0.55, "handwriting_checked": True},
    )
    assert result.content_type == ContentType.HANDWRITING
    assert result.confidence >= 0.80
    assert "handwriting" in result.reason.lower()


def test_classify_diagram_and_pid_region():
    """Verify P&ID instrumentation tags and schematic keywords classify as ContentType.DIAGRAM."""
    pid_text = "Refer to P&ID DWG-4012: Loop with FCV-101 and PT-204B regulating feed pressure."
    result = content_classifier.classify_region(text=pid_text)
    assert result.content_type == ContentType.DIAGRAM
    assert result.confidence >= 0.85
    assert "p&id" in result.reason.lower() or "schematic" in result.reason.lower()
    assert "FCV-101" in result.metadata.get("pid_tags", [])


def test_classify_ambiguous_and_unknown_region():
    """Verify empty or unclassifiable region falls back to ContentType.UNKNOWN with low confidence."""
    # Blank / whitespace only
    res_empty = content_classifier.classify_region(text="   \n   ")
    assert res_empty.content_type == ContentType.UNKNOWN
    assert res_empty.confidence <= 0.30
    assert "ambiguous" in res_empty.reason.lower()

    # None inputs
    res_none = content_classifier.classify_region(text=None, image=None, metadata=None)
    assert res_none.content_type == ContentType.UNKNOWN
    assert res_none.confidence <= 0.30


def test_classify_evidence_element():
    """Verify ContentClassifier.classify_element inspects EvidenceElement properties."""
    elem = EvidenceElement(
        id="p1_e3",
        document_id="doc_test_123",
        page=1,
        type="table",
        text="| Col A | Col B |\n| 1 | 2 |",
        table_data={"headers": ["Col A", "Col B"], "rows": [["1", "2"]]},
        bbox=[10.0, 20.0, 300.0, 150.0],
        confidence=1.0,
        extraction_model="python-docx",
        file_hash="abc123hash",
        timestamp="2026-09-05T00:00:00Z",
    )
    result = content_classifier.classify_element(elem)

    assert result.content_type == ContentType.TABLE
    assert result.confidence == 1.0
    assert result.source_region is not None
    assert result.source_region.get("element_id") == "p1_e3"
    assert result.source_region.get("document_id") == "doc_test_123"


def test_custom_strategy_pluggability():
    """Verify a custom strategy can be registered and take precedence."""
    class CustomFormulaStrategy:
        strategy_name = "custom_formula_strategy"

        def can_classify(self, text=None, image=None, metadata=None, bbox=None) -> bool:
            return bool(text and "SPECIAL_MATH_TOKEN" in text)

        def classify(self, text=None, image=None, metadata=None, bbox=None) -> ClassificationResult | None:
            return ClassificationResult(
                content_type=ContentType.FORMULA,
                confidence=0.99,
                reason="Special custom formula token detected.",
                metadata={"strategy": self.strategy_name},
            )

    classifier = ContentClassifier()
    # Prepend custom strategy
    classifier.register_strategy(CustomFormulaStrategy(), index=0)

    res = classifier.classify_region(text="Equation with SPECIAL_MATH_TOKEN inside.")
    assert res.content_type == ContentType.FORMULA
    assert res.confidence == 0.99
    assert res.reason == "Special custom formula token detected."


def test_classify_math_vs_prose_discrimination():
    """Verify exact multi-signal math vs prose discrimination."""
    # 1. "Solve: x² - 5x + 6 = 0" -> FORMULA
    r1 = content_classifier.classify_region(text="Solve: x² - 5x + 6 = 0")
    assert r1.content_type == ContentType.FORMULA
    assert r1.confidence >= 0.85

    # 2. "d/dx (x³ + 2x² - 5x + 1)" -> FORMULA
    r2 = content_classifier.classify_region(text="d/dx (x³ + 2x² - 5x + 1)")
    assert r2.content_type == ContentType.FORMULA
    assert r2.confidence >= 0.90

    # 3. "∫ x² dx" -> FORMULA
    r3 = content_classifier.classify_region(text="∫ x² dx")
    assert r3.content_type == ContentType.FORMULA
    assert r3.confidence >= 0.90

    # 4. "Please solve the equation tomorrow" -> TEXT
    r4 = content_classifier.classify_region(text="Please solve the equation tomorrow")
    assert r4.content_type == ContentType.TEXT
    assert "prose" in r4.reason.lower() or "text" in r4.reason.lower()

    # 5. "The pressure was 120 MPa" -> TEXT
    r5 = content_classifier.classify_region(text="The pressure was 120 MPa")
    assert r5.content_type == ContentType.TEXT

    # 6. Confidence variation based on signal strength
    high_signal = content_classifier.classify_region(
        text="Standard operating procedure for reactor shutdown sequence.",
        metadata={"confidence": 0.98},
    )
    low_signal = content_classifier.classify_region(
        text="r",
        metadata={"confidence": 0.70},
    )
    assert high_signal.confidence > low_signal.confidence
    assert high_signal.confidence != 0.92
    assert low_signal.confidence != 0.92

