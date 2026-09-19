"""CLI tool to process and demonstrate ANY document or image through the Sanctum Evidence Engine.

Usage:
    PYTHONPATH=. venv/bin/python scripts/process_file.py <path_to_file> [--output <output_json_path>]

Examples:
    PYTHONPATH=. venv/bin/python scripts/process_file.py sample_documents/sample_inspection.pdf
    PYTHONPATH=. venv/bin/python scripts/process_file.py sample_documents/ocr_test.png
    PYTHONPATH=. venv/bin/python scripts/process_file.py /path/to/my_report.docx
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from app.ingestion.detector import detector
from app.processing.pipeline import pipeline


# ANSI Colors
class Colors:
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


async def process_single_file(file_path: Path, output_json: Path | None = None) -> None:
    if not file_path.exists():
        print(f"{Colors.BOLD}{Colors.RED}Error: File not found: {file_path}{Colors.RESET}")
        sys.exit(1)

    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  SANCTUM MULTIMODAL EVIDENCE ENGINE - FILE PROCESSOR{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

    print(f"{Colors.BOLD}Processing File:{Colors.RESET} {file_path.resolve()}")
    file_bytes = file_path.read_bytes()
    file_size_kb = len(file_bytes) / 1024
    print(f"{Colors.DIM}Size: {file_size_kb:.2f} KB ({len(file_bytes)} bytes){Colors.RESET}")

    # 1. Ingestion & Detection
    t0 = time.perf_counter()
    detection = detector.detect(file_bytes, filename=file_path.name)
    print(f"\n{Colors.BOLD}{Colors.BLUE}[1] Ingestion & Content Detection:{Colors.RESET}")
    print(f"  • Detected File Type: {Colors.BOLD}{detection.file_type.value.upper()}{Colors.RESET}")
    print(f"  • MIME Type:          {detection.mime_type}")
    print(f"  • Detection Method:   {detection.detection_method}")
    print(f"  • Supported:          {detection.is_supported}")

    if not detection.is_supported:
        print(f"\n{Colors.BOLD}{Colors.RED}File rejected: {detection.error_message}{Colors.RESET}\n")
        return

    # 2. Pipeline Execution
    print(f"\n{Colors.BOLD}{Colors.BLUE}[2] Executing Full Intelligent Pipeline...{Colors.RESET}")
    doc_id = f"doc_{file_path.stem[:10]}_{int(time.time())}"
    doc = await pipeline.process_document(
        document_id=doc_id,
        file_bytes=file_bytes,
        filename=file_path.name,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    # 3. Summary Metrics
    meta = doc.metadata or {}
    summary = meta.get("pipeline_summary", {})
    type_counts = summary.get("element_types", {})

    print(f"\n{Colors.BOLD}{Colors.GREEN}✓ Processing Complete!{Colors.RESET} ({elapsed_ms:.1f}ms)")
    print(f"{Colors.BOLD}{Colors.CYAN}{'-'*80}{Colors.RESET}")
    print(f"  • Document ID:        {doc.document_id}")
    print(f"  • Status:             {doc.processing_status.upper()}")
    print(f"  • Total Pages/Slides: {doc.total_pages or doc.total_slides or 1}")
    print(f"  • Parser Used:        {doc.parser_used}")
    print(f"  • Overall Confidence: {doc.overall_confidence:.4f}")
    print(f"  • Total Elements:     {len(doc.elements)}")
    print(f"  • Elements by Type:   {dict(type_counts)}")

    # 4. Detailed Intelligent Highlights
    # Formulas with SymPy
    formulas = [el for el in doc.elements if el.type == "formula" or (el.metadata and "formula_processing" in el.metadata)]
    if formulas:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[★] Classified Formulas & SymPy Computations ({len(formulas)}):{Colors.RESET}")
        for i, f_el in enumerate(formulas, 1):
            f_meta = f_el.metadata or {}
            calc_val = f_meta.get("calculated_value")
            latex = f_el.formula_latex or f_el.text
            calc_str = f" {Colors.GREEN}──► SymPy Computed: {calc_val}{Colors.RESET}" if calc_val is not None else ""
            print(f"    {i}. LaTeX: '{latex}'{calc_str}")

    # Structured Tables
    tables = [el for el in doc.elements if el.type == "table" or el.table_data]
    if tables:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[★] Extracted Structured Tables ({len(tables)}):{Colors.RESET}")
        for i, t_el in enumerate(tables, 1):
            td = t_el.table_data or {}
            headers = td.get("headers", [])
            row_count = len(td.get("rows", []))
            print(f"    {i}. Page {t_el.page} Table: {len(headers)} columns, {row_count} rows. Headers: {headers[:4]}")

    # Spreadsheets / Worksheets
    if doc.worksheets:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[★] Spreadsheet Worksheets ({len(doc.worksheets)}):{Colors.RESET}")
        for ws in doc.worksheets:
            print(f"    • Sheet '{ws.name}': {ws.row_count} rows, {ws.column_count} cols, has_formulas={ws.has_formulas}")

    # Vision Escalations & Reconciliations
    vlm_elements = [el for el in doc.elements if (el.metadata or {}).get("escalated_to_vision") or (el.metadata or {}).get("enrichment_provenance", {}).get("vlm_invoked")]
    if vlm_elements:
        print(f"\n{Colors.BOLD}{Colors.YELLOW}[★] Vision Escalations ({len(vlm_elements)}):{Colors.RESET}")
        for v_el in vlm_elements:
            prov = (v_el.metadata or {}).get("enrichment_provenance", {})
            print(f"    • Element {v_el.id} escalated to {prov.get('vlm_model')}: '{v_el.text}'")

    conflicts = [el for el in doc.elements if (el.metadata or {}).get("requires_human_review")]
    if conflicts:
        print(f"\n{Colors.BOLD}{Colors.RED}[!] Conflicts Requiring Human Review ({len(conflicts)}):{Colors.RESET}")
        for c_el in conflicts:
            prov = (c_el.metadata or {}).get("enrichment_provenance", {})
            print(f"    • Element {c_el.id}: OCR='{prov.get('ocr_candidate')}' vs VLM='{prov.get('vlm_candidate')}'")

    # 5. Processing Trace / Audit Log Output
    from app.observability.processing_trace import trace_store

    trace = trace_store.get(doc.document_id)
    if not trace and meta.get("processing_trace"):
        pt_dict = meta["processing_trace"]
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}  SANCTUM AUDIT LOG & COMPONENT EXECUTION TRACE{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
        print(f"Total Time: {pt_dict.get('total_duration_ms', 0):.1f} ms | Events: {len(pt_dict.get('events', []))}")
        for idx, ev in enumerate(pt_dict.get("events", []), 1):
            dur = f" ({ev.get('duration_ms')}ms)" if ev.get("duration_ms") is not None else ""
            print(f"[{idx:02d}] {ev.get('stage')} ──► {ev.get('event')}{dur}")
            print(f"     Component: {ev.get('component')} | Status: {ev.get('status', '').upper()}")
            for k, v in ev.get("metadata", {}).items():
                print(f"     {k}: {v}")
            if ev.get("error"):
                print(f"     Error: {ev.get('error')}")
            print()
    elif trace:
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}  SANCTUM AUDIT LOG & COMPONENT EXECUTION TRACE{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
        print(trace.to_human_readable())

    # 6. Output JSON
    out_file = output_json or Path(f"evidence_{file_path.stem}.json")
    def _default(obj):
        if hasattr(obj, "tolist"):
            return obj.tolist()
        return str(obj)
    out_file.write_text(json.dumps(doc.model_dump(mode="python"), default=_default, indent=2), encoding="utf-8")
    print(f"\n{Colors.BOLD}Canonical DocumentEvidence JSON exported to:{Colors.RESET} {out_file.resolve()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Process any document/image through the Sanctum Evidence Engine.")
    parser.add_argument("file_path", type=str, help="Path to document or image file.")
    parser.add_argument("--output", "-o", type=str, default=None, help="Optional output JSON path.")
    parser.add_argument("--trace", action="store_true", default=True, help="Display human-readable audit trace.")
    args = parser.parse_args()

    asyncio.run(process_single_file(Path(args.file_path), Path(args.output) if args.output else None))


if __name__ == "__main__":
    main()
