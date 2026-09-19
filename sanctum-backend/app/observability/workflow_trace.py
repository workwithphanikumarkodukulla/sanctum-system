"""End-to-End Workflow Observability and Tracing for Sanctum.

Captures and correlates execution events across:
USER REQUEST
 ↓
AGENT DECISION
 ↓
WORKSPACE TOOL
 ↓
DOCUMENT TOOL
 ↓
DOCUMENT ENGINE (preserves existing ProcessingTrace)
 ↓
DOCUMENT EVIDENCE
 ↓
AGENT REASONING
 ↓
MATH/ACTION TOOL
 ↓
FINAL ANSWER
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


def _mask_secret_val(val: Any) -> Any:
    """Recursively mask secrets and truncate excessive raw text."""
    if isinstance(val, str):
        # Truncate raw large text dumps > 200 chars in metadata
        sanitized = re.sub(
            r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b|"
            r"\bsk-[a-zA-Z0-9]{20,}\b|"
            r"\bAKIA[0-9A-Z]{16}\b|"
            r"\bAIzaSy[A-Za-z0-9_-]{20,}\b|"
            r"\bxox[baprs]-[0-9]{10,}-[A-Za-z0-9]+\b|"
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
            "[REDACTED_SECRET]",
            val,
        )
        if len(sanitized) > 200:
            return sanitized[:197] + "..."
        return sanitized
    if isinstance(val, dict):
        return {
            k: ("[REDACTED_SECRET]" if any(s in k.lower() for s in ("password", "secret", "token", "key", "auth")) else _mask_secret_val(v))
            for k, v in val.items()
        }
    if isinstance(val, list):
        return [_mask_secret_val(x) for x in val[:10]]
    return val


def extract_safe_input_metadata(tool_name: str, args: dict[str, Any] | Any) -> dict[str, Any]:
    """Extract non-sensitive input metadata from tool arguments."""
    if not isinstance(args, dict):
        return {"raw_type": type(args).__name__}

    safe: dict[str, Any] = {}
    for key, value in args.items():
        # Exclude secrets and passwords entirely
        if any(s in key.lower() for s in ("password", "secret", "token", "auth")):
            continue

        # For content-heavy fields, log metadata rather than raw content
        if key in ("content", "text", "body", "code"):
            safe[f"{key}_length"] = len(str(value))
        elif key in ("sections_json", "slides_json", "sheets_json"):
            try:
                parsed = json.loads(value) if isinstance(value, str) else value
                safe[f"{key.replace('_json', '')}_count"] = len(parsed) if isinstance(parsed, list) else 1
            except Exception:
                safe[f"{key}_length"] = len(str(value))
        elif key == "substitutions":
            if isinstance(value, dict):
                safe["substitutions_variables"] = list(value.keys())
            elif isinstance(value, str) and value.strip():
                try:
                    p = json.loads(value)
                    safe["substitutions_variables"] = list(p.keys()) if isinstance(p, dict) else "custom"
                except Exception:
                    safe["substitutions"] = "custom_mapping"
        else:
            safe[key] = _mask_secret_val(value)

    return safe


def extract_safe_output_metadata(tool_name: str, result: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Extract safe output metadata, document IDs, file hashes, and evidence references."""
    special_fields: dict[str, Any] = {
        "document_id": None,
        "file_hash": None,
        "evidence_references": None,
        "math_operation": None,
        "action_result": None,
        "document_engine_trace": None,
    }
    safe_out: dict[str, Any] = {}

    # Attempt JSON parse if result is string
    res_obj = result
    if isinstance(result, str):
        try:
            res_obj = json.loads(result)
        except Exception:
            res_obj = {"raw_preview": _mask_secret_val(result[:200])}

    if not isinstance(res_obj, dict):
        return {"raw_type": type(res_obj).__name__}, special_fields

    # Extract DocumentTool metadata
    if "document_id" in res_obj:
        special_fields["document_id"] = res_obj["document_id"]
        safe_out["document_id"] = res_obj["document_id"]
    if "file_hash" in res_obj:
        special_fields["file_hash"] = res_obj["file_hash"]
        safe_out["file_hash"] = res_obj["file_hash"]
    if "file_size" in res_obj:
        safe_out["file_size_bytes"] = res_obj["file_size"]
    if "file_type" in res_obj:
        safe_out["file_type"] = res_obj["file_type"]
    if "total_pages" in res_obj:
        safe_out["total_pages"] = res_obj["total_pages"]
    if "overall_confidence" in res_obj:
        safe_out["confidence"] = res_obj["overall_confidence"]

    # Evidence references
    evidence_refs: list[str] = []
    if "element_id" in res_obj and res_obj["element_id"]:
        evidence_refs.append(f"element:{res_obj['element_id']}")
    if "total_tables" in res_obj:
        safe_out["tables_found"] = res_obj["total_tables"]
    if "total_formulas" in res_obj:
        safe_out["formulas_found"] = res_obj["total_formulas"]
    if "tables_found" in res_obj and isinstance(res_obj["tables_found"], list):
        for t in res_obj["tables_found"]:
            if isinstance(t, dict) and "element_id" in t:
                evidence_refs.append(f"table:{t['element_id']}")
    if "formulas_found" in res_obj and isinstance(res_obj["formulas_found"], list):
        for f in res_obj["formulas_found"]:
            if isinstance(f, dict) and "element_id" in f:
                evidence_refs.append(f"formula:{f['element_id']}")
    if evidence_refs:
        special_fields["evidence_references"] = evidence_refs

    # Document Engine processing trace
    prov = res_obj.get("provenance_summary") or {}
    if isinstance(prov, dict):
        if "parser" in prov:
            safe_out["parser"] = prov["parser"]
        if "processing_trace" in prov and isinstance(prov["processing_trace"], dict):
            special_fields["document_engine_trace"] = prov["processing_trace"]
    if "document_engine_trace" in res_obj and isinstance(res_obj["document_engine_trace"], dict):
        special_fields["document_engine_trace"] = res_obj["document_engine_trace"]

    # Extract MathTool metadata
    if "operation" in res_obj and "deterministic" in res_obj:
        special_fields["math_operation"] = res_obj.get("operation")
        safe_out["math_operation"] = res_obj.get("operation")
        safe_out["normalized_input"] = res_obj.get("normalized_input")
        safe_out["result"] = _mask_secret_val(res_obj.get("result"))
        safe_out["deterministic"] = res_obj.get("deterministic")
        safe_out["engine"] = res_obj.get("backend", {}).get("engine", "SymPy")

    # Extract Action Tool metadata (pptx, docx, pdf, xlsx, md)
    if any(k in res_obj for k in ("format", "file_exists", "created", "written")):
        act_res = {
            "file": res_obj.get("file") or res_obj.get("path"),
            "format": res_obj.get("format"),
            "file_exists": res_obj.get("file_exists"),
            "size_bytes": res_obj.get("size_bytes"),
            "status": res_obj.get("status", "success" if res_obj.get("file_exists") else "unknown"),
        }
        special_fields["action_result"] = act_res
        safe_out["action_result"] = act_res

    # Extract Workspace metadata
    if "items" in res_obj and isinstance(res_obj["items"], list):
        safe_out["items_count"] = len(res_obj["items"])
        safe_out["sample_items"] = [_mask_secret_val(i) for i in res_obj["items"][:5]]

    if "error" in res_obj and res_obj["error"]:
        safe_out["error"] = _mask_secret_val(res_obj["error"])

    return safe_out, special_fields


@dataclass
class ToolExecutionRecord:
    """Detailed record of a single tool selection and execution."""
    tool_name: str
    start_time: str
    end_time: str
    duration_ms: float
    status: Literal["success", "error", "failed"]
    input_metadata: dict[str, Any] = field(default_factory=dict)
    output_metadata: dict[str, Any] = field(default_factory=dict)
    document_id: str | None = None
    file_hash: str | None = None
    evidence_references: list[str] | None = None
    math_operation: str | None = None
    action_result: dict[str, Any] | None = None
    document_engine_trace: dict[str, Any] | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "tool_name": self.tool_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "input_metadata": self.input_metadata,
            "output_metadata": self.output_metadata,
        }
        if self.document_id:
            data["document_id"] = self.document_id
        if self.file_hash:
            data["file_hash"] = self.file_hash
        if self.evidence_references:
            data["evidence_references"] = self.evidence_references
        if self.math_operation:
            data["math_operation"] = self.math_operation
        if self.action_result:
            data["action_result"] = self.action_result
        if self.document_engine_trace:
            data["document_engine_trace"] = self.document_engine_trace
        if self.error:
            data["error"] = self.error
        return data


class WorkflowTrace:
    """Provable, end-to-end trace connecting User Request -> Agent Decision -> Tools -> Final Answer."""

    def __init__(self, user_request: str, trace_id: str | None = None) -> None:
        self.trace_id: str = trace_id or f"tr_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        self.start_utc: str = datetime.now(timezone.utc).isoformat()
        self._start_perf: float = time.perf_counter()
        self.end_utc: str | None = None
        self.total_duration_ms: float = 0.0

        self.user_request: str = _mask_secret_val(user_request)
        self.agent_decision: dict[str, Any] = {}
        self.tool_executions: list[ToolExecutionRecord] = []
        self.agent_reasoning: list[str] = []
        self.final_answer: str = ""
        self.final_status: Literal["completed", "failed", "partial", "in_progress"] = "in_progress"

    def record_decision(self, model: str, routing_strategy: str = "auto", details: dict[str, Any] | None = None) -> None:
        """Record initial agent decision and routing selection."""
        self.agent_decision = {
            "model": model,
            "routing_strategy": routing_strategy,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def record_reasoning(self, text: str) -> None:
        """Record intermediate agent reasoning step or thought summary."""
        sanitized = _mask_secret_val(text.strip())
        if sanitized and sanitized not in self.agent_reasoning:
            self.agent_reasoning.append(sanitized)

    def record_tool_execution(
        self,
        tool_name: str,
        start_perf: float,
        end_perf: float,
        args: dict[str, Any] | Any,
        result: Any,
    ) -> ToolExecutionRecord:
        """Capture completed tool execution with timings and domain-specific metadata."""
        start_iso = datetime.now(timezone.utc).isoformat()
        end_iso = datetime.now(timezone.utc).isoformat()
        duration_ms = round((end_perf - start_perf) * 1000, 2)

        input_meta = extract_safe_input_metadata(tool_name, args)
        output_meta, specials = extract_safe_output_metadata(tool_name, result)

        # Determine success / error status
        is_error = False
        err_msg = output_meta.get("error")
        if err_msg:
            is_error = True
        elif isinstance(result, dict) and (result.get("status") in ("error", "failed") or result.get("success") is False):
            is_error = True
            err_msg = str(result.get("error") or "Operation failed")

        status: Literal["success", "error", "failed"] = "error" if is_error else "success"

        record = ToolExecutionRecord(
            tool_name=tool_name,
            start_time=start_iso,
            end_time=end_iso,
            duration_ms=duration_ms,
            status=status,
            input_metadata=input_meta,
            output_metadata=output_meta,
            document_id=specials["document_id"],
            file_hash=specials["file_hash"],
            evidence_references=specials["evidence_references"],
            math_operation=specials["math_operation"],
            action_result=specials["action_result"],
            document_engine_trace=specials["document_engine_trace"],
            error=err_msg,
        )
        self.tool_executions.append(record)
        return record

    def finish(self, final_answer: str, status: Literal["completed", "failed", "partial"] | None = None) -> None:
        """Complete workflow trace and calculate total elapsed duration."""
        end_perf = time.perf_counter()
        self.end_utc = datetime.now(timezone.utc).isoformat()
        self.total_duration_ms = round((end_perf - self._start_perf) * 1000, 2)
        self.final_answer = _mask_secret_val(final_answer)

        if status:
            self.final_status = status
        else:
            has_failures = any(t.status in ("error", "failed") for t in self.tool_executions)
            has_successes = any(t.status == "success" for t in self.tool_executions)
            if has_failures and not has_successes:
                self.final_status = "failed"
            elif has_failures and has_successes:
                self.final_status = "partial"
            else:
                self.final_status = "completed"

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation of the complete workflow trace."""
        return {
            "trace_id": self.trace_id,
            "start_time": self.start_utc,
            "end_time": self.end_utc,
            "total_duration_ms": self.total_duration_ms,
            "final_status": self.final_status,
            "user_request": self.user_request,
            "agent_decision": self.agent_decision,
            "tool_executions": [t.to_dict() for t in self.tool_executions],
            "agent_reasoning": self.agent_reasoning,
            "final_answer": self.final_answer,
        }

    def to_human_readable(self) -> str:
        """Render a clean, hierarchical ASCII debug trace demonstrating the full execution flow."""
        lines: list[str] = [
            "=" * 78,
            "SANCTUM END-TO-END WORKFLOW TRACE",
            "=" * 78,
            f"Trace ID:       {self.trace_id}",
            f"Start Time:     {self.start_utc}",
            f"Duration:       {self.total_duration_ms:.1f} ms",
            f"Final Status:   {self.final_status.upper()}",
            "-" * 78,
            "",
            "[01] USER REQUEST",
            f"    \"{self.user_request}\"",
            "",
            "[02] AGENT DECISION",
            f"    Model:      {self.agent_decision.get('model', 'default-local')}",
            f"    Strategy:   {self.agent_decision.get('routing_strategy', 'auto')}",
        ]

        step_num = 3
        for t in self.tool_executions:
            lines.append("")
            # Categorize tool
            category = "TOOL EXECUTION"
            if t.tool_name in ("find_files", "list_files", "workspace_tree", "file_info"):
                category = "WORKSPACE TOOL"
            elif t.tool_name in ("read_document",):
                category = "DOCUMENT TOOL"
            elif t.tool_name in ("calculate",):
                category = "MATH TOOL"
            elif t.tool_name.startswith("generate_") or t.tool_name in ("create_file", "write_file", "run_command"):
                category = "ACTION TOOL"

            lines.append(f"[{step_num:02d}] {category}: {t.tool_name}")
            lines.append(f"     Status:    {t.status.upper()} ({t.duration_ms:.1f} ms)")

            if t.input_metadata:
                in_parts = [f"{k}={v!r}" for k, v in t.input_metadata.items()]
                lines.append(f"     Inputs:    {', '.join(in_parts)}")

            if t.document_id:
                hash_disp = f" (SHA256: {t.file_hash[:12]}...)" if t.file_hash else ""
                lines.append(f"     Document:  {t.document_id}{hash_disp}")

            if t.evidence_references:
                lines.append(f"     Evidence:  {', '.join(t.evidence_references)}")

            if t.math_operation:
                lines.append(f"     Operation: {t.math_operation}")
                if "normalized_input" in t.output_metadata:
                    lines.append(f"     Formula:   {t.output_metadata['normalized_input']}")
                if "result" in t.output_metadata:
                    lines.append(f"     Result:    {t.output_metadata['result']}")

            if t.action_result:
                act_file = t.action_result.get("file") or "unknown"
                exists = "verified on disk" if t.action_result.get("file_exists") else "unverified"
                size = f", {t.action_result.get('size_bytes', 0)} bytes" if t.action_result.get("size_bytes") else ""
                lines.append(f"     Action:    {act_file} ({exists}{size})")

            # Document Engine nested trace if available
            if t.document_engine_trace:
                lines.append("     ┌── [DOCUMENT ENGINE TRACE]")
                de_events = t.document_engine_trace.get("events", [])
                for de_idx, ev in enumerate(de_events[:8], 1):
                    dur = f" ({ev.get('duration_ms')}ms)" if ev.get("duration_ms") is not None else ""
                    comp = f" ({ev.get('component')})" if ev.get("component") else ""
                    lines.append(f"     │   [{de_idx:02d}] {ev.get('stage')}{comp} — {ev.get('event')}{dur} [{ev.get('status', '').upper()}]")
                if len(de_events) > 8:
                    lines.append(f"     │   [... {len(de_events) - 8} more Document Engine events ...]")
                lines.append("     └── [END DOCUMENT ENGINE TRACE]")

            if t.error:
                lines.append(f"     Error:     {t.error}")

            step_num += 1

        if self.agent_reasoning:
            lines.append("")
            lines.append(f"[{step_num:02d}] AGENT REASONING")
            for r in self.agent_reasoning:
                lines.append(f"    • {r}")
            step_num += 1

        lines.append("")
        lines.append(f"[{step_num:02d}] FINAL ANSWER")
        # Indent final answer cleanly
        ans_lines = self.final_answer.splitlines()
        for al in ans_lines[:15]:
            lines.append(f"    {al}")
        if len(ans_lines) > 15:
            lines.append(f"    [... {len(ans_lines) - 15} more lines ...]")

        lines.append("-" * 78)
        lines.append(f"WORKFLOW STATUS: {self.final_status.upper()}")
        lines.append("=" * 78)
        return "\n".join(lines)


class WorkflowTraceStore:
    """Thread-safe in-memory store for workflow execution traces."""

    def __init__(self, max_traces: int = 50) -> None:
        self._traces: dict[str, WorkflowTrace] = {}
        self._order: list[str] = []
        self._max_traces: int = max_traces
        self._lock = threading.Lock()

    def save(self, trace: WorkflowTrace) -> None:
        with self._lock:
            self._traces[trace.trace_id] = trace
            if trace.trace_id in self._order:
                self._order.remove(trace.trace_id)
            self._order.append(trace.trace_id)

            # Evict oldest traces if exceeding maximum
            while len(self._order) > self._max_traces:
                oldest = self._order.pop(0)
                self._traces.pop(oldest, None)

    def get(self, trace_id: str) -> WorkflowTrace | None:
        with self._lock:
            return self._traces.get(trace_id)

    def get_latest(self) -> WorkflowTrace | None:
        with self._lock:
            if not self._order:
                return None
            return self._traces.get(self._order[-1])

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._order.clear()


# Global trace store instance
workflow_trace_store = WorkflowTraceStore()
