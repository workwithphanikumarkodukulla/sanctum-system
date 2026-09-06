"""Production Hardening and Performance Benchmark Test Suite for Sanctum System.

Phase 13 Production Hardening Audits:
- Latency & Benchmarks: DocumentTool cache hits (<5ms), MathTool SymPy (<5ms), Workspace search.
- Cache & Memory Bounds: LRU eviction capping cache to MAX_CACHE_ENTRIES (50), zero memory leak.
- Concurrency: Thread safety under 10 concurrent threads without deadlock or race conditions.
- Noise Exclusion: Workspace search pruning .git, .venv, node_modules, __pycache__.
- Progressive Disclosure: Context efficiency preventing excessive LLM context token inflation.
- Duplicate Tool Call Prevention: Short-circuiting identical read-only tool calls within a turn.
- Resilience: Timeout and ConnectionError handling with actionable hints.
- Deterministic Math & Provenance: Invariants preserved across all workloads.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.agent import CodingAgent, _make_langchain_tools
from app.config import Config
from app.tools.document_tool import DocumentTool
from app.tools.sympy_tool import MathTool
from app.tools.workspace import WorkspaceTool


@pytest.fixture
def hardening_workspace():
    """Create a temporary workspace for production hardening benchmarks."""
    temp_dir = Path(tempfile.mkdtemp(prefix="sanctum_hardening_ws_"))

    # Sample doc
    doc_path = temp_dir / "financial_report.pdf"
    doc_path.write_bytes(b"%PDF-1.4 sample content for hardening tests")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_document_tool_cache_hit_latency_benchmark(hardening_workspace):
    """Verify that cached DocumentEvidence access is sub-5ms and avoids network calls."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")
    pdf_path = hardening_workspace / "financial_report.pdf"

    mock_evidence = {
        "document_id": "doc_bench_001",
        "file_hash": "hash_bench_001",
        "processing_status": "completed",
        "page_count": 3,
        "elements": [
            {
                "id": "p1_e1", "type": "title", "content": "Financial Report 2026",
                "page": 1, "reading_order": 1, "confidence": 0.99,
            },
            {
                "id": "p1_e2", "type": "table", "page": 1, "reading_order": 2,
                "confidence": 0.98,
                "table_data": {
                    "headers": ["Quarter", "Revenue ($M)", "Profit ($M)"],
                    "rows": [["Q1", "100", "20"], ["Q2", "120", "25"]],
                },
            },
        ],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_evidence

    with patch("requests.post", return_value=mock_response) as mock_post:
        # First call: Cache miss (network call to Document Engine)
        t0 = time.perf_counter()
        res1 = doc_tool.execute(path="financial_report.pdf", mode="summary")
        t_miss = (time.perf_counter() - t0) * 1000

        assert res1["status"] == "success"
        assert res1["document_id"] == "doc_bench_001"
        assert mock_post.call_count == 1

        # Subsequent calls: 100 cache hits
        hit_latencies = []
        for _ in range(100):
            t_start = time.perf_counter()
            res_hit = doc_tool.execute(path="financial_report.pdf", mode="summary")
            t_end = time.perf_counter()
            hit_latencies.append((t_end - t_start) * 1000)
            assert res_hit["status"] == "success"

        mean_hit_latency = sum(hit_latencies) / len(hit_latencies)
        # Network post count must still be 1 (0 additional network calls)
        assert mock_post.call_count == 1
        # Mean cache hit latency must be well under 5ms (usually < 0.5ms)
        assert mean_hit_latency < 5.0, f"Cache hit latency {mean_hit_latency:.3f}ms exceeded 5ms threshold"


def test_document_tool_bounded_lru_eviction(hardening_workspace):
    """Verify that DocumentTool caps cache at MAX_CACHE_ENTRIES (50) and evicts in LRU order."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")
    assert doc_tool.MAX_CACHE_ENTRIES == 50

    # Create 60 small files
    created_files = []
    for i in range(60):
        f = hardening_workspace / f"doc_{i:03d}.pdf"
        f.write_bytes(f"%PDF-1.4 file number {i}".encode("utf-8"))
        created_files.append(f)

    with patch("requests.post") as mock_post:
        def fake_post(*args, **kwargs):
            files_arg = kwargs.get("files", {})
            filename = files_arg.get("file", ("unknown", b""))[0]
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "document_id": f"id_{filename}",
                "processing_status": "completed",
                "page_count": 1,
                "elements": [],
            }
            return resp

        mock_post.side_effect = fake_post

        for f in created_files:
            res = doc_tool.execute(path=f.name, mode="summary")
            assert res["status"] == "success"

        # Cache size must be exactly bounded to 50
        assert len(doc_tool._evidence_cache) == 50
        assert len(doc_tool._cache_order) == 50

        # Oldest files (doc_000 through doc_009) should have been evicted
        for i in range(10):
            old_f = created_files[i].resolve()
            old_mtime = old_f.stat().st_mtime
            assert (old_f, old_mtime) not in doc_tool._evidence_cache

        # Newest file (doc_059) must be in cache
        latest_f = created_files[59].resolve()
        latest_mtime = latest_f.stat().st_mtime
        assert (latest_f, latest_mtime) in doc_tool._evidence_cache


def test_document_tool_multithreaded_concurrency(hardening_workspace):
    """Verify that concurrent access from 10 threads is thread-safe and produces no data race or corruption."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")

    # Seed 5 distinct documents
    docs = []
    for i in range(5):
        d = hardening_workspace / f"concurrent_doc_{i}.pdf"
        d.write_bytes(f"%PDF-1.4 concurrent {i}".encode("utf-8"))
        docs.append(d.name)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "document_id": "thread_safe_doc",
        "processing_status": "completed",
        "page_count": 1,
        "elements": [{"id": "e1", "type": "paragraph", "content": "Thread safe content"}],
    }

    with patch("requests.post", return_value=mock_resp):
        def worker(doc_name: str) -> dict:
            return doc_tool.execute(path=doc_name, mode="summary")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            tasks = [executor.submit(worker, docs[i % len(docs)]) for i in range(40)]
            results = [t.result() for t in concurrent.futures.as_completed(tasks)]

        assert len(results) == 40
        for r in results:
            assert r["status"] == "success"
            assert r["document_id"] == "thread_safe_doc"


def test_workspace_noise_directory_pruning(hardening_workspace):
    """Verify that find_files and list_files prune .git, .venv, node_modules, and __pycache__ for sub-50ms searches."""
    ws_tool = WorkspaceTool(root_dir=hardening_workspace)

    # Populate noisy directories with hundreds of files
    for noise_dir in [".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"]:
        nd = hardening_workspace / noise_dir / "deep_subdir"
        nd.mkdir(parents=True, exist_ok=True)
        for i in range(25):
            (nd / f"noise_file_{i}.txt").write_text("noise")

    # Root valid files
    (hardening_workspace / "valid_annual_report.pdf").write_text("valid report")
    (hardening_workspace / "docs").mkdir(exist_ok=True)
    (hardening_workspace / "docs" / "quarterly_budget.xlsx").write_text("budget")

    # Benchmark find_files
    t0 = time.perf_counter()
    res = ws_tool.find_files(pattern="*annual_report*")
    t_search = (time.perf_counter() - t0) * 1000

    assert res["count"] == 1
    assert res["matches"][0]["filename"] == "valid_annual_report.pdf"
    # Must complete fast without visiting noisy files
    assert t_search < 50.0, f"Workspace search took {t_search:.2f}ms, expected < 50ms"

    # Verify recursive list_files does not include noisy items
    res_list = ws_tool.list_files(recursive=True)
    all_items = res_list["items"]
    for noise in [".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"]:
        assert not any(item.startswith(noise) for item in all_items), f"Noise dir {noise} found in list_files"


def test_progressive_disclosure_context_guard(hardening_workspace):
    """Verify that progressive disclosure protects LLM context from excessive table token dumps."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")
    pdf_file = hardening_workspace / "massive_table.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 large table document")

    # Generate 150 rows table
    rows = [[f"Row {r}", f"Val {r * 10}", f"Note {r}"] for r in range(150)]
    mock_evidence = {
        "document_id": "doc_table_150",
        "processing_status": "completed",
        "page_count": 1,
        "elements": [
            {
                "id": "p1_t1",
                "type": "table",
                "page": 1,
                "table_data": {
                    "headers": ["Item", "Quantity", "Description"],
                    "rows": rows,
                },
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_evidence

    with patch("requests.post", return_value=mock_resp):
        # 1. Default summary mode
        summary_res = doc_tool.execute(path="massive_table.pdf", mode="summary")
        summary_json_str = json.dumps(summary_res)

        # Summary must include table schema and row count without dumping all 150 rows
        assert summary_res["tables_found"][0]["row_count"] == 150
        assert summary_res["tables_found"][0]["id"] == "p1_t1"
        assert len(summary_json_str) < 2000, f"Summary payload {len(summary_json_str)} bytes was too large"

        # 2. Targeted table query fetches full unabridged data when explicitly requested
        table_res = doc_tool.execute(path="massive_table.pdf", mode="table", element_id="p1_t1")
        assert table_res["total_rows"] == 150
        assert len(table_res["rows"]) == 150


def test_agent_deduplicates_repeated_read_tools(hardening_workspace):
    """Verify that the agent detects duplicate read-only tool calls and avoids redundant re-execution."""
    mock_llm_manager = MagicMock()
    mock_llm_manager.model_name = "test-model"
    mock_llm = MagicMock()
    mock_llm_manager._llm = mock_llm

    mock_llm_with_tools = MagicMock()
    mock_llm.bind_tools.return_value = mock_llm_with_tools

    from app.tools.manager import ToolManager
    tool_manager = ToolManager(root_dir=hardening_workspace)
    (hardening_workspace / "sample_test.txt").write_text("Hello from Sanctum hardening test.")

    agent = CodingAgent(mock_llm_manager, tool_manager=tool_manager)
    agent.clear_memory()

    # Simulate LLM returning two identical read_file calls in the same turn
    from langchain_core.messages import AIMessage
    call1 = {"name": "read_file", "args": {"path": "sample_test.txt"}, "id": "c1"}
    call2 = {"name": "read_file", "args": {"path": "sample_test.txt"}, "id": "c2"}

    llm_resp1 = AIMessage(content="", tool_calls=[call1, call2])
    llm_resp2 = AIMessage(content="Here is the file summary.", tool_calls=[])

    mock_llm_with_tools.invoke.side_effect = [llm_resp1, llm_resp2]

    out = agent.chat("Read sample_test.txt twice.")

    # Both tool actions recorded, with the second one short-circuited as already_executed
    actions = out["tool_actions"]
    assert len(actions) == 2
    assert "already_executed" in actions[1]["result"]


def test_document_tool_timeout_resilience(hardening_workspace):
    """Verify that DocumentTool handles Document Engine timeouts with structured error."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")

    with patch("requests.post", side_effect=requests.exceptions.Timeout("Request timed out")):
        res = doc_tool.execute(path="financial_report.pdf", mode="summary")
        assert res["status"] == "error"
        assert res["timeout"] is True
        assert "timed out" in res["error"]


def test_document_tool_connection_error_resilience(hardening_workspace):
    """Verify that DocumentTool handles unreachable Document Engine with actionable hint."""
    doc_tool = DocumentTool(root_dir=hardening_workspace, engine_url="http://127.0.0.1:8001")

    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        res = doc_tool.execute(path="financial_report.pdf", mode="summary")
        assert res["status"] == "error"
        assert "Could not connect to Document Engine" in res["error"]
        assert "Ensure the Document Engine service is running" in res["error"]


def test_oversized_document_protection(hardening_workspace):
    """Verify that files exceeding MAX_DOCUMENT_SIZE_BYTES (50MB) are rejected immediately."""
    doc_tool = DocumentTool(root_dir=hardening_workspace)
    huge_file = hardening_workspace / "huge.pdf"

    import stat
    huge_file.write_bytes(b"%PDF-1.4 header")
    with patch.object(Path, "stat") as mock_stat:
        mock_res = MagicMock()
        mock_res.st_size = 60 * 1024 * 1024
        mock_res.st_mtime = 12345.0
        mock_res.st_mode = stat.S_IFREG | 0o644
        mock_stat.return_value = mock_res

        res = doc_tool.execute(path="huge.pdf")
        assert res["status"] == "error"
        assert res.get("oversized") is True
        assert "exceeds maximum allowable size" in res["error"]


def test_deterministic_sympy_math_latency_benchmark():
    """Verify that MathTool calculates symbolic and numeric math deterministically in sub-millisecond time."""
    math_tool = MathTool()

    # Warm-up calculus, integrals, and solvers to complete dynamic module imports
    math_tool.execute(expression="diff(x, x)")
    math_tool.execute(expression="integrate(x, x)")
    math_tool.execute(expression="solve(x - 1, x)")

    expressions = [
        ("diff(3*x**2 + 5*x - 7, x)", "derivative"),
        ("integrate(x**2, x)", "integral"),
        ("solve(x**2 - 4, x)", "roots"),
        ("1245000 + 450000 + 380000", "addition"),
        ("(1250 - 1000) / 1000 * 100", "percentage"),
    ]

    latencies = []
    for _ in range(5):  # 5 steady-state production runs
        for expr, label in expressions:
            t0 = time.perf_counter()
            res = math_tool.execute(expression=expr)
            t_eval = (time.perf_counter() - t0) * 1000
            latencies.append(t_eval)

            assert res["status"] == "success"
            assert res["result"] is not None

    mean_eval_latency = sum(latencies) / len(latencies)
    # Steady-state SymPy evaluation averages under 5ms (typically < 1ms)
    assert mean_eval_latency < 5.0, f"Mean SymPy latency {mean_eval_latency:.3f}ms exceeded 5ms threshold"
