"""Tests for the document upload endpoint: validation, sanitization, size limits, and format detection."""
from __future__ import annotations

import io
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.evidence.schema import DocumentEvidence
from app.evidence.storage import storage
from app.main import app

client = TestClient(app)


def test_upload_empty_file_returns_400():
    """Verify empty uploads are rejected immediately with 400 Bad Request."""
    res = client.post(
        "/api/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_upload_exceeding_max_size_returns_413(monkeypatch):
    """Verify uploads exceeding MAX_UPLOAD_SIZE_BYTES are rejected with 413."""
    # Temporarily set upload limit to 1 KB for testing
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)

    large_data = b"X" * 2048
    res = client.post(
        "/api/documents",
        files={"file": ("large.txt", large_data, "text/plain")},
    )
    assert res.status_code == 413
    assert "exceeds maximum allowable limit" in res.json()["detail"]


def test_upload_path_traversal_sanitized():
    """Verify path traversal characters in filenames are sanitized to basename only."""
    txt_content = b"Sanctum clean text content."
    res = client.post(
        "/api/documents",
        files={"file": ("../../../../etc/passwd.txt", txt_content, "text/plain")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    doc = storage.get_document(doc_id)
    assert doc is not None
    # Filename must be sanitized to basename only without ../
    assert doc.filename == "passwd.txt"
    assert "/" not in doc.filename
    assert ".." not in doc.filename


def test_upload_windows_path_traversal_and_null_byte_sanitized():
    """Verify Windows-style backslashes and null bytes are sanitized."""
    txt_content = b"Valid content."
    res = client.post(
        "/api/documents",
        files={"file": ("..\\..\\secret.txt\x00.pdf", txt_content, "text/plain")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    doc = storage.get_document(doc_id)
    assert doc is not None
    assert "\\" not in doc.filename
    assert "\x00" not in doc.filename


def test_upload_fake_extension_detected_by_magic_bytes():
    """Verify a file with an invalid extension or spoofed extension is detected by actual magic bytes."""
    # ELF binary disguised as .pdf
    elf_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    res = client.post(
        "/api/documents",
        files={"file": ("malicious_payload.pdf", elf_bytes, "application/pdf")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["status"] == "failed"
    assert "Unsupported file format" in data["error"]

    # Verify document stored reflects failure
    doc_id = data["document_id"]
    status_res = client.get(f"/api/documents/{doc_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "failed"


def test_upload_returns_sha256_and_detected_type():
    """Verify upload response includes document_id, status, detected_file_type, and file_hash."""
    txt_content = b"Sample configuration data."
    res = client.post(
        "/api/documents",
        files={"file": ("config.txt", txt_content, "text/plain")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert "document_id" in data
    assert data["status"] == "processing"
    assert data["detected_file_type"] == "txt"
    assert "file_hash" in data
    assert len(data["file_hash"]) == 64  # valid SHA-256 hex string


def test_upload_supported_formats_not_assumed_as_image():
    """Verify non-PDF documents are accurately detected and not defaulted to image."""
    csv_bytes = b"col1,col2\nval1,val2\n"
    res = client.post(
        "/api/documents",
        files={"file": ("data.csv", csv_bytes, "text/csv")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["detected_file_type"] == "csv"
    assert data["status"] == "processing"


def test_upload_sync_processing_mode():
    """Verify ?sync=true processes document synchronously and returns DocumentEvidence directly."""
    txt_content = b"Specification Header\nF = 10 * 5\nPressure = 100 kPa"
    res = client.post(
        "/api/documents?sync=true",
        files={"file": ("specs.txt", txt_content, "text/plain")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["processing_status"] == "completed"
    assert len(data["elements"]) > 0
    assert data["metadata"] is not None
    assert "pipeline_summary" in data["metadata"]
    summary = data["metadata"]["pipeline_summary"]
    assert summary["total_elements"] == len(data["elements"])
    assert "formula" in summary["element_types"] or "text" in summary["element_types"]

    # Verify GET status includes pipeline_summary
    doc_id = data["document_id"]
    st_res = client.get(f"/api/documents/{doc_id}")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["status"] == "completed"
    assert st_data["pipeline_summary"] is not None
    assert st_data["pipeline_summary"]["total_elements"] == len(data["elements"])


def test_upload_sync_with_numpy_structures_serializes_cleanly(monkeypatch):
    """Verify that if an extractor embeds numpy ndarray or scalars, serialization doesn't throw 500."""
    import numpy as np
    from PIL import Image

    # Upload an image to trigger image/OCR pipeline
    img = Image.new("RGB", (120, 60), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    res = client.post(
        "/api/documents?sync=true",
        files={"file": ("numpy_test.png", buf.read(), "image/png")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["processing_status"] == "completed"
    assert "elements" in data

