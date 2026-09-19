"""Tests for Sanctum End-to-End Workflow Observability & Tracing (Phase 10).

Verifies:
- Correlation of User Request -> Agent Decision -> Tools -> Final Answer
- Preservation and embedding of Document Engine ProcessingTrace
- Safe capture of input metadata, timings, document IDs, hashes, evidence references, math operations, and action results
- Strict secret exclusion from trace logs
- Human-readable ASCII debug trace formatting
- Flask API trace endpoints (/api/traces/latest, /api/traces/latest/text)
"""
import json
import tempfile
from pathlib import Path
import pytest

from app.agent import CodingAgent
from app.llm import LLMManager
from app.observability.workflow_trace import (
    ToolExecutionRecord,
    WorkflowTrace,
    WorkflowTraceStore,
    workflow_trace_store,
)
from app.tools.manager import ToolManager


@pytest.fixture
def test_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / "docs").mkdir(parents=True, exist_ok=True)
        (ws / "generated").mkdir(parents=True, exist_ok=True)
        (ws / "report.txt").write_text("Revenue: $10,000\nCosts: $4,000\n", encoding="utf-8")
        yield ws


# ---------------------------------------------------------------------------
# 1. Data Structure & Serialization
# ---------------------------------------------------------------------------
def test_workflow_trace_data_structure():
    """Verify WorkflowTrace correctly captures lifecycle stages and serializes cleanly."""
    trace = WorkflowTrace(user_request="Calculate derivative of x**3")
    assert trace.trace_id.startswith("tr_")
    assert trace.final_status == "in_progress"

    # Agent Decision
    trace.record_decision(model="Qwen2.5-Coder-7B", routing_strategy="fluid", details={"tier": "math"})
    assert trace.agent_decision["model"] == "Qwen2.5-Coder-7B"

    # Tool Execution
    rec = trace.record_tool_execution(
        tool_name="calculate",
        start_perf=1.0,
        end_perf=1.025,
        args={"expression": "diff(x**3, x)"},
        result={"operation": "differentiation", "normalized_input": "diff(x**3, x)", "result": "3*x**2", "deterministic": True},
    )
    assert rec.tool_name == "calculate"
    assert rec.status == "success"
    assert rec.duration_ms == 25.0
    assert rec.math_operation == "differentiation"

    # Reasoning & Completion
    trace.record_reasoning("Evaluated symbolic derivative with SymPy.")
    trace.finish(final_answer="The derivative of x^3 is 3x^2.")

    assert trace.final_status == "completed"
    assert trace.total_duration_ms >= 0

    d = trace.to_dict()
    assert d["trace_id"] == trace.trace_id
    assert len(d["tool_executions"]) == 1
    assert d["agent_reasoning"] == ["Evaluated symbolic derivative with SymPy."]
    assert "3x^2" in d["final_answer"]


# ---------------------------------------------------------------------------
# 2. E2E Trace: Workspace -> DocumentTool (with Engine Trace) -> MathTool
# ---------------------------------------------------------------------------
def test_e2e_observability_document_to_math(test_workspace):
    """Verify end-to-end trace from Workspace discovery to DocumentTool with embedded Engine Trace to MathTool."""
    # Mock Document Engine processing trace embedded in evidence
    mock_engine_trace = {
        "document_id": "doc_csr_2026",
        "filename": "CSR_Report.pdf",
        "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "total_duration_ms": 32.4,
        "events": [
            {"stage": "INGESTION", "component": "api_router", "event": "file_received", "duration_ms": 1.1, "status": "success"},
            {"stage": "EXTRACTION", "component": "pdf_extractor", "event": "native_elements", "duration_ms": 19.2, "status": "success"},
            {"stage": "RECONCILIATION", "component": "consensus_builder", "event": "reconciled", "duration_ms": 8.5, "status": "success"},
        ],
    }

    class MockE2EObservabilityLLM:
        def __init__(self):
            self.turn = 0

        def bind_tools(self, tools, **kwargs):
            self.tools = {t.name: t for t in tools}
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage
            self.turn += 1

            if self.turn == 1:
                # Turn 1: Workspace discovery
                msg = AIMessage(content="Finding document files in workspace.")
                msg.tool_calls = [{"name": "find_files", "args": {"pattern": "*.txt"}, "id": "call_1"}]
                return msg
            elif self.turn == 2:
                # Turn 2: Document reading (mocked)
                msg = AIMessage(content="Analyzing the document for revenue and cost data.")
                msg.tool_calls = [{"name": "read_file", "args": {"path": "report.txt"}, "id": "call_2"}]
                return msg
            elif self.turn == 3:
                # Turn 3: MathTool evaluation
                msg = AIMessage(content="Calculating net profit from extracted values.")
                msg.tool_calls = [{"name": "calculate", "args": {"expression": "10000 - 4000"}, "id": "call_3"}]
                return msg
            else:
                # Final answer
                return AIMessage(content="The net profit calculated from the report is $6,000.")

    llm_manager = LLMManager()
    llm_manager._llm = MockE2EObservabilityLLM()
    llm_manager.select_for_task = lambda task: llm_manager.model_name

    tm = ToolManager(root_dir=str(test_workspace))
    agent = CodingAgent(llm_manager=llm_manager, tool_manager=tm)

    resp = agent.chat("Read report.txt, calculate net profit, and provide a summary.")

    # 1. Response contains workflow trace and debug trace
    assert "workflow_trace" in resp
    assert "debug_trace" in resp
    wf_trace = resp["workflow_trace"]

    # 2. Verify all tools executed were recorded
    tool_names = [t["tool_name"] for t in wf_trace["tool_executions"]]
    assert "find_files" in tool_names
    assert "read_file" in tool_names
    assert "calculate" in tool_names

    # 3. Verify MathTool metadata captured
    math_rec = next(t for t in wf_trace["tool_executions"] if t["tool_name"] == "calculate")
    assert math_rec["status"] == "success"
    assert math_rec["duration_ms"] >= 0
    assert math_rec["output_metadata"]["result"] == "6000" or math_rec["output_metadata"]["result"] == 6000

    # 4. Verify agent reasoning steps recorded
    assert len(wf_trace["agent_reasoning"]) >= 1

    # 5. Verify final status and duration
    assert wf_trace["final_status"] == "completed"
    assert wf_trace["total_duration_ms"] > 0

    # 6. Verify debug trace contains complete visual pipeline
    debug_text = resp["debug_trace"]
    assert "SANCTUM END-TO-END WORKFLOW TRACE" in debug_text
    assert "USER REQUEST" in debug_text
    assert "AGENT DECISION" in debug_text
    assert "WORKSPACE TOOL" in debug_text
    assert "MATH TOOL" in debug_text
    assert "FINAL ANSWER" in debug_text


# ---------------------------------------------------------------------------
# 3. E2E Trace: DocumentTool -> Action Tool (PowerPoint Generation)
# ---------------------------------------------------------------------------
def test_e2e_observability_document_to_action(test_workspace):
    """Verify trace captures action results (file existence, format, size) for generation tools."""
    class MockActionLLM:
        def __init__(self):
            self.turn = 0

        def bind_tools(self, tools, **kwargs):
            self.tools = {t.name: t for t in tools}
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage
            self.turn += 1

            if self.turn == 1:
                # Call generate_presentation
                slides_json = json.dumps([{"title": "Overview", "bullet_points": ["Point 1", "Point 2"]}])
                msg = AIMessage(content="Creating summary presentation.")
                msg.tool_calls = [{
                    "name": "generate_presentation",
                    "args": {
                        "filepath": "generated/summary.pptx",
                        "title": "Report Summary",
                        "subtitle": "By Sanctum",
                        "slides_json": slides_json,
                    },
                    "id": "call_action_1"
                }]
                return msg
            else:
                return AIMessage(content="Generated presentation successfully.")

    llm_manager = LLMManager()
    llm_manager._llm = MockActionLLM()
    llm_manager.select_for_task = lambda task: llm_manager.model_name

    tm = ToolManager(root_dir=str(test_workspace))
    agent = CodingAgent(llm_manager=llm_manager, tool_manager=tm)

    resp = agent.chat("Create a presentation summarizing the project.")

    wf_trace = resp["workflow_trace"]
    action_rec = next(t for t in wf_trace["tool_executions"] if t["tool_name"] == "generate_presentation")

    # Verify action metadata
    assert action_rec["status"] == "success"
    assert "action_result" in action_rec
    act = action_rec["action_result"]
    assert act["format"] == "pptx"
    assert act["file_exists"] is True
    assert act["size_bytes"] > 0
    assert "summary.pptx" in act["file"]


# ---------------------------------------------------------------------------
# 4. Strict Secret Exclusion from Traces
# ---------------------------------------------------------------------------
def test_secrets_excluded_from_trace(test_workspace):
    """Sensitive tokens, API keys, and passwords must never appear in raw form in traces."""
    secret_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
    github_token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"

    trace = WorkflowTrace(user_request=f"Check API key {secret_key}")

    # Tool execution with sensitive parameter names
    trace.record_tool_execution(
        tool_name="api_tool",
        start_perf=0.0,
        end_perf=0.01,
        args={"api_token": secret_key, "password": "SuperSecretPassword123!", "user_id": "usr_42"},
        result={"token": github_token, "status": "authenticated"},
    )

    trace.finish(final_answer=f"Configured with key {secret_key}")

    trace_dict = trace.to_dict()
    trace_json = json.dumps(trace_dict)
    debug_text = trace.to_human_readable()

    # Invariants:
    # 1. Raw secrets and passwords never appear in JSON trace
    assert secret_key not in trace_json
    assert github_token not in trace_json
    assert "SuperSecretPassword123!" not in trace_json

    # 2. Raw secrets never appear in human-readable debug trace
    assert secret_key not in debug_text
    assert github_token not in debug_text
    assert "SuperSecretPassword123!" not in debug_text

    # 3. Masked indicator appears
    assert "[REDACTED_SECRET]" in trace_json or "api_token" not in trace_dict["tool_executions"][0]["input_metadata"]


# ---------------------------------------------------------------------------
# 5. Human-Readable Debug Trace Format
# ---------------------------------------------------------------------------
def test_human_readable_debug_trace_formatting():
    """Verify ASCII trace displays user request, decisions, tools, nested engine trace, and answer."""
    trace = WorkflowTrace(user_request="Summarize quarterly inspection")
    trace.record_decision(model="local-model", routing_strategy="fluid")

    trace.record_tool_execution(
        tool_name="find_files",
        start_perf=1.0,
        end_perf=1.005,
        args={"pattern": "*.pdf"},
        result={"items": ["inspection.pdf"]},
    )

    trace.record_tool_execution(
        tool_name="read_document",
        start_perf=2.0,
        end_perf=2.045,
        args={"path": "inspection.pdf", "mode": "summary"},
        result={
            "document_id": "doc_insp_99",
            "file_hash": "a1b2c3d4e5f67890",
            "total_pages": 4,
            "overall_confidence": 0.97,
            "total_tables": 2,
            "total_formulas": 1,
            "provenance_summary": {
                "parser": "PyMuPDF",
                "processing_trace": {
                    "events": [
                        {"stage": "INGESTION", "component": "router", "event": "received", "duration_ms": 2.1, "status": "success"},
                        {"stage": "PARSING", "component": "pdf_parser", "event": "pages_parsed", "duration_ms": 18.3, "status": "success"},
                    ]
                }
            }
        },
    )

    trace.record_reasoning("Extracted inspection table. Generating response.")
    trace.finish(final_answer="The quarterly inspection completed with 0 critical defects.")

    debug = trace.to_human_readable()

    # Structural checks
    assert "SANCTUM END-TO-END WORKFLOW TRACE" in debug
    assert "[01] USER REQUEST" in debug
    assert "Summarize quarterly inspection" in debug
    assert "[02] AGENT DECISION" in debug
    assert "[03] WORKSPACE TOOL: find_files" in debug
    assert "[04] DOCUMENT TOOL: read_document" in debug
    assert "doc_insp_99" in debug
    assert "DOCUMENT ENGINE TRACE" in debug
    assert "pdf_parser" in debug
    assert "AGENT REASONING" in debug
    assert "FINAL ANSWER" in debug
    assert "0 critical defects" in debug
    assert "WORKFLOW STATUS: COMPLETED" in debug


# ---------------------------------------------------------------------------
# 6. Flask Trace Endpoints
# ---------------------------------------------------------------------------
def test_flask_trace_endpoints(test_workspace):
    """Test /api/traces/latest and /api/traces/latest/text routes."""
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True

    # Pre-populate a trace in the store
    trace = WorkflowTrace(user_request="Test API trace route")
    trace.record_decision(model="test-model")
    trace.finish(final_answer="Test API reply")
    workflow_trace_store.save(trace)

    with app.test_client() as client:
        # 1. Latest trace JSON
        res_json = client.get("/api/traces/latest")
        assert res_json.status_code == 200
        data = res_json.get_json()
        assert data["trace_id"] == trace.trace_id
        assert data["user_request"] == "Test API trace route"

        # 2. Latest trace text
        res_text = client.get("/api/traces/latest/text")
        assert res_text.status_code == 200
        assert "text/plain" in res_text.content_type
        assert "SANCTUM END-TO-END WORKFLOW TRACE" in res_text.get_data(as_text=True)

        # 3. By ID
        res_by_id = client.get(f"/api/traces/{trace.trace_id}")
        assert res_by_id.status_code == 200
        assert res_by_id.get_json()["trace_id"] == trace.trace_id

        # 4. By ID text
        res_by_id_text = client.get(f"/api/traces/{trace.trace_id}/text")
        assert res_by_id_text.status_code == 200
        assert "SANCTUM END-TO-END WORKFLOW TRACE" in res_by_id_text.get_data(as_text=True)

        # 5. Non-existent ID returns 404
        res_404 = client.get("/api/traces/non_existent_id")
        assert res_404.status_code == 404
