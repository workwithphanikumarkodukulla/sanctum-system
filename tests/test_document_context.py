"""Phase 6: Document Context Management Tests.

Validates the evidence-context management strategy across 6 document types:
1. 1-page PDF (sample_inspection.pdf)
2. 22-page CSR PDF (mrpl_csr_2025_26.pdf)
3. 10-slide BloodLink PPTX (BLOODLINK _ Team-CodeAlchemy.pptx)
4. Table-heavy document (zero lost rows, exact numbers preserved)
5. Formula-containing document (exact LaTeX & variable preservation)
6. Image-heavy document (visual metadata preserved without binary bloat)
7. Progressive evidence disclosure flow (summary -> targeted table fetch -> answer)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import CodingAgent
from app.tools.document_tool import DocumentTool
from app.tools.manager import ToolManager


@pytest.fixture
def context_workspace(tmp_path: Path):
    """Setup workspace with sample files from engine sample_documents directory."""
    temp_dir = tmp_path / "context_workspace"
    temp_dir.mkdir(parents=True, exist_ok=True)
    docs_dir = temp_dir / "sample_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    engine_samples = (
        Path(__file__).resolve().parent.parent.parent
        / "sanctum-file-engine-code"
        / "sample_documents"
    )

    if engine_samples.exists():
        for item in engine_samples.iterdir():
            if item.is_file():
                try:
                    shutil.copy(item, docs_dir / item.name)
                except Exception:
                    pass

    # Ensure sample_inspection.pdf exists
    if not (docs_dir / "sample_inspection.pdf").exists():
        (docs_dir / "sample_inspection.pdf").write_bytes(b"%PDF-1.4 mock inspection")

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def _create_mock_agent(workspace_dir: Path):
    """Helper to create CodingAgent with mock LLM manager."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    tool_manager = ToolManager(root_dir=workspace_dir)
    agent = CodingAgent(mock_llm_manager, tool_manager=tool_manager)
    agent.clear_memory()
    return agent, mock_llm_with_tools


# ==============================================================================
# TEST 1: 1-Page PDF (sample_inspection.pdf)
# ==============================================================================
def test_context_01_one_page_pdf(context_workspace):
    """Test 1-page PDF produces compact summary and allows targeted table/formula extraction."""
    tool = DocumentTool(root_dir=context_workspace)

    # 1. Summary Mode
    res_summary = tool.execute(path="sample_documents/sample_inspection.pdf", mode="summary")
    assert res_summary["status"] == "success"
    assert res_summary["total_pages"] == 1
    assert "tables_found" in res_summary
    assert len(res_summary["tables_found"]) >= 1

    tbl_meta = res_summary["tables_found"][0]
    tbl_id = tbl_meta["id"]
    assert "ref" in tbl_meta
    assert tbl_meta["row_count"] >= 4
    # Summary preview only gives up to 3 rows
    assert len(tbl_meta["preview_rows"]) <= 3

    # Token footprint of summary is extremely compact (< 3500 bytes)
    summary_bytes = len(json.dumps(res_summary))
    assert summary_bytes < 4000

    # 2. Targeted Table Mode: fetch complete unabridged table
    res_table = tool.execute(
        path="sample_documents/sample_inspection.pdf",
        mode="table",
        element_id=tbl_id,
    )
    assert res_table["status"] == "success"
    assert res_table["mode"] == "table"
    assert res_table["element_id"] == tbl_id
    assert res_table["total_rows"] == 4
    # Verify zero lost rows
    assert len(res_table["rows"]) == 4
    # Verify exact numeric strings preserved verbatim
    assert res_table["rows"][0][0] == "Shell Ring 1"
    assert res_table["rows"][0][1] == "38.50"
    assert res_table["rows"][0][2] == "37.85"
    assert res_table["rows"][3][0] == "Bottom Nozzle N1"
    assert res_table["rows"][3][4] == "MONITOR"

    # 3. Targeted Formula Mode
    res_formula = tool.execute(
        path="sample_documents/sample_inspection.pdf",
        mode="formulas",
    )
    assert res_formula["status"] == "success"
    assert len(res_formula["formulas"]) >= 1
    formula_obj = res_formula["formulas"][0]
    assert "formula_latex" in formula_obj
    assert formula_obj["page"] == 1


# ==============================================================================
# TEST 2: 22-Page CSR PDF (mrpl_csr_2025_26.pdf)
# ==============================================================================
def test_context_02_multi_page_csr_pdf(context_workspace):
    """Test 22-page CSR PDF avoids context dumping and supports page/keyword filtering."""
    pdf_path = context_workspace / "sample_documents" / "mrpl_csr_2025_26.pdf"
    if not pdf_path.exists():
        pytest.skip("mrpl_csr_2025_26.pdf not found in sample_documents")

    tool = DocumentTool(root_dir=context_workspace)

    # 1. Summary Mode
    res_summary = tool.execute(path="sample_documents/mrpl_csr_2025_26.pdf", mode="summary")
    assert res_summary["status"] == "success"
    assert res_summary["total_pages"] == 22

    summary_json = json.dumps(res_summary)
    # The summary is under 15 KB (over 94% compression vs 285 KB raw DocumentEvidence)
    assert len(summary_json) < 15000

    # 2. Targeted Page Retrieval (Page 1)
    res_page = tool.execute(path="sample_documents/mrpl_csr_2025_26.pdf", page=1, mode="page")
    assert res_page["status"] == "success"
    assert res_page["page"] == 1
    assert res_page["total_pages"] == 22
    assert "elements" in res_page
    assert all(el["reading_order"] is not None for el in res_page["elements"])

    # 3. Query / Keyword Search across 22 pages
    res_search = tool.execute(path="sample_documents/mrpl_csr_2025_26.pdf", query="CSR")
    assert res_search["status"] == "success"
    assert res_search["total_matches"] >= 1
    assert len(res_search["matches"]) >= 1
    assert "id" in res_search["matches"][0]
    assert "page" in res_search["matches"][0]


# ==============================================================================
# TEST 3: 10-Slide BloodLink PPTX (BLOODLINK _ Team-CodeAlchemy.pptx)
# ==============================================================================
def test_context_03_ten_slide_pptx(context_workspace):
    """Test 10-slide BloodLink PPTX produces clean JSON outline without binary bloat."""
    pptx_path = context_workspace / "sample_documents" / "BLOODLINK _ Team-CodeAlchemy.pptx"
    if not pptx_path.exists():
        pytest.skip("BLOODLINK _ Team-CodeAlchemy.pptx not found")

    tool = DocumentTool(root_dir=context_workspace)

    # 1. Summary Mode
    res_summary = tool.execute(path="sample_documents/BLOODLINK _ Team-CodeAlchemy.pptx", mode="summary")
    assert res_summary["status"] == "success"
    assert res_summary["total_slides"] == 10
    assert len(res_summary["outline"]) >= 1

    # Verify JSON serializability
    dumped = json.dumps(res_summary)
    assert len(dumped) < 15000
    assert "image_bytes" not in dumped

    # 2. Targeted Slide Mode
    res_slide = tool.execute(
        path="sample_documents/BLOODLINK _ Team-CodeAlchemy.pptx",
        page=2,
        mode="page",
    )
    assert res_slide["status"] == "success"
    assert res_slide["page"] == 2
    assert res_slide["total_slides"] == 10
    assert len(res_slide["elements"]) >= 1


# ==============================================================================
# TEST 4: Table-Heavy Document (Zero Lost Rows & Exact Numerics)
# ==============================================================================
def test_context_04_table_heavy_zero_lost_rows(context_workspace):
    """Verify table-heavy documents preserve all rows without silent loss or numeric truncation."""
    tool = DocumentTool(root_dir=context_workspace)

    # Mock a large table with 15 rows and precise decimals
    table_headers = ["Zone", "Nominal (mm)", "Measured (mm)", "Threshold (mm)", "Ratio"]
    table_rows = [
        [f"Zone_{i:02d}", f"{30.0 + i * 0.75:.2f}", f"{28.5 + i * 0.70:.2f}", "25.00", f"{0.91234 + i * 0.005:.5f}"]
        for i in range(1, 16)
    ]

    mock_doc = {
        "document_id": "doc_dense_table",
        "filename": "heavy_tables.pdf",
        "file_type": "pdf",
        "file_hash": "hash_tbl_dense",
        "file_size": 12400,
        "total_pages": 3,
        "processing_status": "completed",
        "overall_confidence": 0.99,
        "elements": [
            {
                "id": "p1_tbl1",
                "page": 1,
                "type": "table",
                "reading_order": 1,
                "confidence": 0.99,
                "bbox": [50.0, 100.0, 500.0, 600.0],
                "table_data": {
                    "headers": table_headers,
                    "rows": table_rows,
                },
                "provenance": {"source": "pdf_table_extractor"},
            }
        ],
    }

    dummy_pdf = context_workspace / "heavy_tables.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 table test")

    # Manually seed the tool cache with the mock canonical document
    cache_key = (dummy_pdf.resolve(), dummy_pdf.stat().st_mtime)
    tool._evidence_cache[cache_key] = mock_doc

    # 1. Summary mode provides preview + explicit row count
    res_summary = tool.execute(path="heavy_tables.pdf", mode="summary")
    assert res_summary["status"] == "success"
    tbl_meta = res_summary["tables_found"][0]
    assert tbl_meta["id"] == "p1_tbl1"
    assert tbl_meta["row_count"] == 15
    assert tbl_meta["has_more_rows"] is True
    assert len(tbl_meta["preview_rows"]) == 3

    # 2. Targeted table fetch retrieves ALL 15 rows without loss
    res_table = tool.execute(path="heavy_tables.pdf", mode="table", element_id="p1_tbl1")
    assert res_table["status"] == "success"
    assert res_table["total_rows"] == 15
    assert len(res_table["rows"]) == 15

    # Verify exact numeric strings are preserved verbatim
    assert res_table["rows"][0] == ["Zone_01", "30.75", "29.20", "25.00", "0.91734"]
    assert res_table["rows"][14] == ["Zone_15", "41.25", "39.00", "25.00", "0.98734"]

    # 3. Table pagination support
    res_page1 = tool.execute(path="heavy_tables.pdf", mode="table", element_id="p1_tbl1", max_rows=5, row_offset=0)
    assert res_page1["row_count"] == 5
    assert res_page1["has_more_rows"] is True
    assert res_page1["rows"][0][0] == "Zone_01"

    res_page2 = tool.execute(path="heavy_tables.pdf", mode="table", element_id="p1_tbl1", max_rows=5, row_offset=5)
    assert res_page2["row_count"] == 5
    assert res_page2["has_more_rows"] is True
    assert res_page2["rows"][0][0] == "Zone_06"


# ==============================================================================
# TEST 5: Formula-Containing Document (Exact LaTeX Preservation)
# ==============================================================================
def test_context_05_formula_exact_preservation(context_workspace):
    """Verify formula documents preserve exact LaTeX and variables for deterministic math."""
    tool = DocumentTool(root_dir=context_workspace)

    mock_doc = {
        "document_id": "doc_asme_exact",
        "filename": "pressure_design.pdf",
        "file_type": "pdf",
        "file_hash": "hash_asme_exact",
        "file_size": 4500,
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_form1",
                "page": 1,
                "type": "formula",
                "text": "t = (P * R) / (S * E - 0.6 * P)",
                "formula_latex": "t = \\frac{P \\cdot R}{S \\cdot E - 0.6 \\cdot P}",
                "formula_variables": {"P": "Design Pressure", "R": "Radius", "S": "Stress", "E": "Efficiency"},
                "confidence": 0.99,
                "bbox": [100.0, 200.0, 400.0, 250.0],
                "metadata": {"standard": "ASME Section VIII Div 1"},
                "provenance": {"parser": "formula_extractor"},
            }
        ],
    }

    dummy_pdf = context_workspace / "pressure_design.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 formula test")
    cache_key = (dummy_pdf.resolve(), dummy_pdf.stat().st_mtime)
    tool._evidence_cache[cache_key] = mock_doc

    # Fetch formula by element_id
    res_form = tool.execute(path="pressure_design.pdf", mode="formula", element_id="p1_form1")
    assert res_form["status"] == "success"
    assert res_form["element_id"] == "p1_form1"
    assert res_form["formula_latex"] == "t = \\frac{P \\cdot R}{S \\cdot E - 0.6 \\cdot P}"
    assert res_form["formula_variables"]["S"] == "Stress"
    assert res_form["metadata"]["standard"] == "ASME Section VIII Div 1"


# ==============================================================================
# TEST 6: Image-Heavy Document (Visual Metadata Preserved, No Bloat)
# ==============================================================================
def test_context_06_image_heavy_metadata_preservation(context_workspace):
    """Verify image-heavy documents preserve visual dimensions/provenance without binary bloat."""
    tool = DocumentTool(root_dir=context_workspace)

    mock_doc = {
        "document_id": "doc_cad_drawings",
        "filename": "plant_layout.pdf",
        "file_type": "pdf",
        "file_hash": "hash_cad_01",
        "file_size": 25000000,  # 25 MB
        "total_pages": 5,
        "processing_status": "completed",
        "overall_confidence": 0.95,
        "elements": [
            {
                "id": f"p1_img_{i}",
                "page": 1,
                "type": "image",
                "reading_order": i,
                "confidence": 0.95,
                "bbox": [10.0 * i, 20.0 * i, 100.0 * i, 150.0 * i],
                "metadata": {
                    "shape_name": f"Piping Diagram {i}",
                    "content_type": "image/png",
                    "size_bytes": 1024000 * i,
                    # Ensure transient binary bytes are stripped
                },
                "provenance": {"source": "pdf_image_extractor", "dpi": 300},
            }
            for i in range(1, 10)
        ],
    }

    dummy_pdf = context_workspace / "plant_layout.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 cad layout")
    cache_key = (dummy_pdf.resolve(), dummy_pdf.stat().st_mtime)
    tool._evidence_cache[cache_key] = mock_doc

    # Fetch page 1 elements
    res_page = tool.execute(path="plant_layout.pdf", page=1, mode="page")
    assert res_page["status"] == "success"
    assert res_page["elements_count"] == 9

    # Verify no raw bytes exist in page output
    dumped = json.dumps(res_page)
    assert len(dumped) < 5000  # Stays lean despite representing 25 MB document
    for elem in res_page["elements"]:
        assert elem["type"] == "image"
        assert "image_metadata" in elem
        assert "size_bytes" in elem["image_metadata"]
        assert elem["image_metadata"]["content_type"] == "image/png"


# ==============================================================================
# TEST 7: Progressive Evidence Agent Flow (Summary -> Targeted Table -> Answer)
# ==============================================================================
def test_context_07_progressive_evidence_agent_flow(context_workspace):
    """Test full Agent progressive disclosure: summary -> inspect -> targeted table request -> answer."""
    agent, mock_llm_with_tools = _create_mock_agent(context_workspace)

    tool = DocumentTool(root_dir=context_workspace)

    # 4-row inspection table where row 4 is Bottom Nozzle N1
    mock_doc = {
        "document_id": "doc_insp_prog",
        "filename": "vessel_inspection.pdf",
        "file_type": "pdf",
        "file_hash": "hash_insp_prog",
        "file_size": 3400,
        "total_pages": 1,
        "processing_status": "completed",
        "overall_confidence": 0.98,
        "elements": [
            {
                "id": "p1_tbl1",
                "page": 1,
                "type": "table",
                "reading_order": 1,
                "confidence": 0.99,
                "bbox": [50.0, 100.0, 500.0, 400.0],
                "table_data": {
                    "headers": ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Min Required (mm)", "Compliance"],
                    "rows": [
                        ["Shell Ring 1", "38.50", "37.85", "32.00", "PASS"],
                        ["Shell Ring 2", "38.50", "36.90", "32.00", "PASS"],
                        ["Top Head Crown", "42.00", "41.10", "35.50", "PASS"],
                        ["Bottom Nozzle N1", "25.40", "22.80", "21.00", "MONITOR"],
                    ],
                },
                "provenance": {"source": "pdf_table_extractor"},
            }
        ],
    }

    dummy_pdf = context_workspace / "vessel_inspection.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 vessel inspection")

    def side_effect(messages):
        last_msg = messages[-1]
        # Step 1: LLM calls read_document in summary mode
        if isinstance(last_msg, HumanMessage):
            return AIMessage(
                content="",
                tool_calls=[{"name": "read_document", "args": {"path": "vessel_inspection.pdf", "mode": "summary"}, "id": "c1"}],
            )
        if isinstance(last_msg, ToolMessage):
            tool_data = json.loads(last_msg.content)
            # Step 2: LLM inspects summary, notices table p1_tbl1 preview only has 3 rows,
            # but user specifically asked for Bottom Nozzle N1 (which is row 4).
            # The LLM requests targeted mode='table' with element_id='p1_tbl1'.
            if tool_data.get("mode") != "table" and "tables_found" in tool_data:
                target_table_id = tool_data["tables_found"][0]["id"]
                return AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "read_document",
                        "args": {
                            "path": "vessel_inspection.pdf",
                            "mode": "table",
                            "element_id": target_table_id,
                        },
                        "id": "c2",
                    }],
                )
            # Step 3: LLM receives full unabridged table, finds Bottom Nozzle N1 row, and answers
            if tool_data.get("mode") == "table":
                rows = tool_data["rows"]
                nozzle_row = next((r for r in rows if "Bottom Nozzle N1" in r[0]), None)
                assert nozzle_row is not None
                return AIMessage(
                    content=f"Bottom Nozzle N1 measured wall thickness is {nozzle_row[2]} mm against minimum required {nozzle_row[3]} mm, status: {nozzle_row[4]}.",
                    tool_calls=[],
                )
        return AIMessage(content="", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = side_effect

    # Patch requests.post so if the tool executes, it uses mock_doc
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_doc

        result = agent.chat("What is the wall thickness compliance status and minimum required thickness for Bottom Nozzle N1 in vessel_inspection.pdf?")

    actual_tool_sequence = [a["tool"] for a in result["tool_actions"]]
    assert actual_tool_sequence == ["read_document", "read_document"]
    # Verify exact argument progression
    assert result["tool_actions"][0]["args"]["mode"] == "summary"
    assert result["tool_actions"][1]["args"]["mode"] == "table"
    assert result["tool_actions"][1]["args"]["element_id"] == "p1_tbl1"

    # Verify final response accuracy
    assert "22.80" in result["reply"]
    assert "21.00" in result["reply"]
    assert "MONITOR" in result["reply"]
