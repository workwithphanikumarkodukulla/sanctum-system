# Sanctum Multimodal Evidence Engine

A self-contained, high-performance, deterministic document and image processing engine designed to ingest industrial documents, engineering reports, spreadsheets, presentations, and technical imagery, producing fully cited, verified, and structured **Canonical Evidence JSON**.

The engine adheres strictly to deterministic routing, symbolic calculation, confidence-gated vision escalation, and multi-candidate evidence reconciliation. It does **not** hallucinate calculations with LLMs or treat engine confidence as calibrated accuracy.

---

## Intelligent Document & Multimodal Pipeline

```
                                  [ Input File ]
                 (PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG, WEBP, TIFF)
                                        |
                                        v
                          +----------------------------+
                          |   FileDetector (Ingestion) |  <-- Magic bytes, OpenXML manifest,
                          +----------------------------+      anti-spoofing, content sniffing
                                        |
                                        v
                          +----------------------------+
                          |   FileRouter (Dispatch)    |
                          +----------------------------+
                                        |
            +---------------------------+----------------------------+
            |                           |                            |
            v                           v                            v
    [ Native Parsers ]          [ Visual OCR Engine ]        [ Office Parsers ]
    (PyMuPDF direct text,        (Tesseract OCR with         (python-docx, python-pptx,
     csv, plain text)            preprocessing fallback)      openpyxl formulas verbatim)
            |                           |                            |
            +---------------------------+----------------------------+
                                        |
                                        v
                          +----------------------------+
                          |    ContentClassifier       |  <-- Paragraph, Heading, Table,
                          +----------------------------+      Formula, Image, Handwriting
                                        |
            +---------------------------+----------------------------+
            |                           |                            |
            v                           v                            v
    [ Table Extractor ]       [ Formula Extractor ]       [ Handwriting / OCR ]
    (Structured rows/cols,     (LaTeX formatting,          (Confidence & Suspicion Gate)
     headers, cell coords)      variables, and SymPy)                |
                                        |                            v
                                        v                 [ Low Conf / Suspicious? ]
                             [ Deterministic Math ]                  |
                             (Pure SymPy Execution)        +---------+---------+
                                                           |                   |
                                                        (No: High Conf)    (Yes: Suspicious)
                                                           |                   |
                                                           v                   v
                                                      [ Accept OCR ]     [ Crop Escalate ]
                                                           |             (Local VLM: gemma4)
                                                           |                   |
                                                           |                   v
                                                           |          [ Evidence Reconciler ]
                                                           |          (Preserves candidates;
                                                           |           flags conflicts)
                                                           |                   |
            +----------------------------------------------+-------------------+
            |
            v
+-----------------------------------------------------------------------------------+
|                        Canonical Evidence Normalization                           |
|       - EvidenceElement: id, bbox, confidence, reading order, provenance          |
|       - DocumentEvidence: overall confidence, pipeline summary metrics            |
+-----------------------------------------------------------------------------------+
```

---

## Core Intelligent Capabilities

### 1. Robust File Ingestion & Security (Anti-Spoofing)
- **Content Inspection First**: Never trusts file extensions alone. Uses magic bytes (`%PDF`, `\x89PNG`, `\xff\xd8\xff`, `RIFF...WEBP`, `II*`/`MM*`) and ZIP manifest inspection (`word/`, `ppt/`, `xl/`).
- **Malicious Payload Protection**: Blocks binary payloads disguised as documents (e.g. ELF or PE executables renamed to `.pdf`).
- **Path Traversal & Null-Byte Neutralization**: Basename sanitization prevents directory traversal attacks (`../../`) and null-byte bypasses.
- **Configurable Limits**: Rejects empty files ($0$ bytes) with `400 Bad Request` and files exceeding `MAX_UPLOAD_SIZE_BYTES` with `413 Content Too Large`.

### 2. Multi-Format Native & Visual Extraction
- **PDF**: Dual-path engine. Native text and font metadata extracted directly via PyMuPDF; scanned pages rendered to 200 DPI and processed via OCR.
- **DOCX & PPTX**: Extracts document headings, paragraphs, slide shapes, and table matrices with spatial coordinates.
- **XLSX & CSV**: Preserves formulas verbatim (`=SUM(...)`, `=AVERAGE(...)`), multi-worksheet structures, merged cell ranges, and dialect-sniffed CSV data.
- **Raster Images**: Supports PNG, JPG/JPEG, WEBP, and TIFF with automated contrast and sharpness preprocessing.

### 3. Content Classification
- Dynamically classifies regions into **`text`**, **`table`**, **`formula`**, **`image`**, **`handwriting`**, and **`heading`**.
- Structural tables and tabular text are routed to dedicated matrix parsers.

### 4. Deterministic Formula Processing with SymPy
- **Zero LLM Math Hallucination**: Mathematical expressions ($P = \rho \cdot g \cdot h$, $F = m \cdot a$, $x^2 - 16 = 0$) are extracted as structured syntax, mapped to LaTeX, and passed to a sandboxed **SymPy** engine.
- Supports symbolic solving, variable substitutions, and verified numerical output.

### 5. Confidence & Suspicion Gate (Conditional VLM Escalation)
- **Heuristic Quality Signal**: Raw OCR confidence is treated strictly as an engine-provided quality signal (`"engine_quality_routing_signal"`), not a probability of correctness.
- **VLM is Conditional**: High-confidence printed text bypasses VLM completely to minimize compute and latency.
- **Lightweight Suspicion Gate**: Escalates to VLM if confidence is below threshold **or** if lightweight anomaly checks trigger:
  - Digit-letter confusions (e.g. `5O00`, `1O0`, `l23`).
  - Broken decimals (`5..00`).
  - Repeated punctuation noise (`....`, `;;;;`).
  - Unbalanced brackets or malformed formula operator sequences.
- **Critical Region Threshold**: Stricter configurable threshold (`CRITICAL_REGION_THRESHOLD = 0.85`) for engineering specifications and formulas.

### 6. Multi-Candidate Evidence Reconciliation
- When VLM is invoked, [EvidenceReconciler](app/reconciliation/reconciler.py) compares the primary OCR and VLM readings:
  - **Exact Agreement**: Confidence boosted appropriately; no human review required.
  - **Formatting & Minor Variations**: Punctuation, whitespace, and label delimiters (`:` vs `=`) normalized safely.
  - **Material Conflicts (Numbers, Units, Formulas)**: **Strictly flags `requires_human_review = True` and preserves both candidates (`ocr_candidate`, `vlm_candidate`) in provenance and metadata without silent overwriting.**

---

## Canonical Evidence Schema

Every document output adheres to the canonical Pydantic model in `app/evidence/schema.py`:

```json
{
  "document_id": "doc_9f8e7d6c5b4a",
  "filename": "inspection_report.pdf",
  "file_type": "pdf",
  "file_size": 2830,
  "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "processing_status": "completed",
  "total_pages": 1,
  "overall_confidence": 0.9650,
  "metadata": {
    "pipeline_summary": {
      "total_elements": 9,
      "element_types": { "heading": 1, "text": 6, "table": 1, "formula": 1 },
      "vlm_escalations": 0,
      "reconciliations": 0,
      "conflicts_requiring_review": 0,
      "formulas_calculated": 1
    },
    "ocr_confidence_semantics": "engine_quality_routing_signal"
  },
  "elements": [
    {
      "id": "p1_e1",
      "document_id": "doc_9f8e7d6c5b4a",
      "page": 1,
      "type": "table",
      "text": "Inspection Zone | Nominal (mm) | Measured (mm) | Compliance",
      "table_data": {
        "headers": ["Inspection Zone", "Nominal (mm)", "Measured (mm)", "Compliance"],
        "rows": [
          ["Shell Ring 1", "38.50", "37.85", "PASS"],
          ["Bottom Nozzle N1", "25.40", "22.80", "MONITOR"]
        ]
      },
      "formula_latex": null,
      "formula_variables": null,
      "bbox": [54.0, 180.5, 558.0, 310.2],
      "confidence": 0.98,
      "extraction_model": "PyMuPDF",
      "reading_order": 1,
      "provenance": { "source": "native_layout" }
    }
  ]
}
```

---

## Quickstart & Verification

### 1. Environment Setup
Requires **Python 3.11** or **3.12**:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Live Jury Demonstration Suite
Run the interactive jury demonstration script, which executes all 8 core workflows:

```bash
PYTHONPATH=. venv/bin/python scripts/demo_jury_workflow.py
```

Output:
```
================================================================================
  DEMONSTRATION EXECUTION SUMMARY
================================================================================
#    Capability Tested                      Result     Latency   
-----------------------------------------------------------------
1    Digital Engineering PDF                PASS       494.2ms
2    SymPy Math Execution                   PASS       157.6ms
3    XLSX Formula & Sheet Extraction        PASS        17.6ms
4    PPTX Slide Extraction                  PASS        14.1ms
5    Confidence & Suspicion Gate            PASS         0.7ms
6    OCR/VLM Reconciliation                 PASS         0.2ms
7    Security & Magic Bytes                 PASS         0.1ms
8    MRPL CSR PDF Benchmark                 PASS      5773.4ms
-----------------------------------------------------------------
ALL 8 JURY CAPABILITY WORKFLOWS PASSED WITH 100% SUCCESS.
```

### 3. Automated Test Suite (183 Tests)
Run the full unit and regression test suite:

```bash
pytest -v
```

All **183 tests** pass with zero regressions.

---

## API Documentation

### Start Server
```bash
uvicorn app.main:app --port 8001 --reload
```
Interactive Swagger documentation: `http://localhost:8001/docs`

### 1. Ingest Document
- **Asynchronous Mode (Default):**
  ```bash
  curl -X POST "http://localhost:8001/api/documents" \
    -F "file=@sample_documents/sample_inspection.pdf"
  ```
  Returns `202 Accepted` with `document_id`.

- **Synchronous Mode (Instant Evaluation):**
  ```bash
  curl -X POST "http://localhost:8001/api/documents?sync=true" \
    -F "file=@sample_documents/sample_inspection.pdf"
  ```
  Returns `200 OK` with the complete `DocumentEvidence` payload.

### 2. Check Document Status & Metrics
```bash
curl -X GET "http://localhost:8001/api/documents/{document_id}"
```
Returns:
```json
{
  "document_id": "doc_9f8e7d6c5b4a",
  "status": "completed",
  "pages": 1,
  "overall_confidence": 0.9650,
  "pipeline_summary": {
    "total_elements": 9,
    "element_types": { "text": 7, "table": 1, "formula": 1 },
    "vlm_escalations": 0,
    "reconciliations": 0,
    "conflicts_requiring_review": 0,
    "formulas_calculated": 1
  }
}
```

### 3. Retrieve Full Canonical Evidence
```bash
curl -X GET "http://localhost:8001/api/documents/{document_id}/evidence"
```

### 4. Health Check
```bash
curl -X GET "http://localhost:8001/health"
```
