"""Central processing trace and audit log layer for Sanctum File Engine."""
from __future__ import annotations

import contextvars
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

TraceStatus = Literal["success", "error", "skipped", "started", "info"]


@dataclass
class TraceEvent:
    """Individual execution event in the document processing lifecycle."""
    stage: str
    component: str
    event: str
    status: TraceStatus = "success"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "component": self.component,
            "event": self.event,
            "status": self.status,
        }
        if self.duration_ms is not None:
            payload["duration_ms"] = self.duration_ms
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.error:
            payload["error"] = self.error
        return payload


class ProcessingTrace:
    """Complete, provable execution trace for an uploaded document."""

    def __init__(
        self,
        document_id: str,
        filename: str = "",
        file_hash: str = "",
        file_size: int = 0,
        detected_type: str = "",
    ) -> None:
        self.document_id = document_id
        self.filename = filename
        self.file_hash = file_hash
        self.file_size = file_size
        self.detected_type = detected_type
        self.start_time: float = time.perf_counter()
        self.end_time: float | None = None
        self.status: str = "processing"
        self.events: list[TraceEvent] = []

    def record_event(
        self,
        stage: str,
        component: str,
        event: str,
        status: TraceStatus = "success",
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> TraceEvent:
        """Append an auditable event to the trace."""
        trace_event = TraceEvent(
            stage=stage,
            component=component,
            event=event,
            status=status,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            metadata=dict(metadata or {}),
            error=error,
        )
        self.events.append(trace_event)
        return trace_event

    def finish(self, status: str = "completed") -> None:
        """Mark the trace as completed."""
        self.end_time = time.perf_counter()
        self.status = status

    @property
    def total_duration_ms(self) -> float:
        end = self.end_time or time.perf_counter()
        return round((end - self.start_time) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        """Machine-readable JSON serialization."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "file_hash": self.file_hash,
            "file_size": self.file_size,
            "detected_type": self.detected_type,
            "status": self.status,
            "total_duration_ms": self.total_duration_ms,
            "total_events": len(self.events),
            "events": [e.to_dict() for e in self.events],
        }

    def to_human_readable(self) -> str:
        """Clean, professional human-readable ASCII audit trace."""
        lines: list[str] = [
            "=" * 60,
            "SANCTUM DOCUMENT PROCESSING TRACE",
            "=" * 60,
            f"Document:     {self.filename or 'unknown'}",
            f"Document ID:  {self.document_id}",
            f"SHA256:       {self.file_hash}",
            f"File Size:    {self.file_size} bytes",
            f"Detected Type:{self.detected_type or 'unknown'}",
            f"Total Time:   {self.total_duration_ms:.1f} ms",
            "-" * 60,
        ]

        step_idx = 1
        for e in self.events:
            dur_str = f" ({e.duration_ms:.1f}ms)" if e.duration_ms is not None else ""
            lines.append(f"[{step_idx:02d}] {e.stage} — {e.event}{dur_str}")
            lines.append(f"     Component: {e.component}")
            lines.append(f"     Status:    {e.status.upper()}")

            if e.metadata:
                for k, v in e.metadata.items():
                    if isinstance(v, (dict, list)) and len(str(v)) > 80:
                        lines.append(f"     {k}: {type(v).__name__} (len={len(v)})")
                    else:
                        lines.append(f"     {k}: {v}")

            if e.error:
                lines.append(f"     Error:     {e.error}")

            lines.append("")
            step_idx += 1

        lines.append("=" * 60)
        lines.append(f"PIPELINE STATUS: {self.status.upper()}")
        lines.append("=" * 60)
        return "\n".join(lines)


import threading

class TraceStore:
    """In-memory thread-safe storage for document processing traces."""

    def __init__(self) -> None:
        self._traces: dict[str, ProcessingTrace] = {}
        self._lock = threading.Lock()

    def save(self, trace: ProcessingTrace) -> None:
        with self._lock:
            self._traces[trace.document_id] = trace

    def get(self, document_id: str) -> ProcessingTrace | None:
        with self._lock:
            return self._traces.get(document_id)

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()


# Global singleton trace store
trace_store = TraceStore()

# Asyncio context variable for the currently running document trace
_current_trace_var: contextvars.ContextVar[ProcessingTrace | None] = contextvars.ContextVar(
    "current_processing_trace",
    default=None,
)


def get_current_trace() -> ProcessingTrace | None:
    """Retrieve the currently active processing trace for this asyncio context."""
    return _current_trace_var.get()


def set_current_trace(trace: ProcessingTrace | None) -> contextvars.Token:
    """Set the active processing trace for this asyncio context."""
    return _current_trace_var.set(trace)


def reset_current_trace(token: contextvars.Token | None) -> None:
    """Safely reset the active processing trace for this asyncio context."""
    if token is not None:
        try:
            _current_trace_var.reset(token)
            return
        except Exception:
            pass
    _current_trace_var.set(None)

