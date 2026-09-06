"""Focused security tests for the document ingestion and processing pipeline."""
from __future__ import annotations

import hashlib
import logging
import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.evidence.storage import storage
from app.main import app

client = TestClient(app)


def test_security_path_traversal_attempts():
    """Verify that path traversal filenames are sanitized and cannot escape."""
    traversal_filenames = [
        "../../../../etc/passwd",
        "../../../../Windows/System32/cmd.exe",
        "..\\..\\..\\boot.ini",
        "/etc/shadow",
        "C:\\Windows\\win.ini",
    ]

    for raw_name in traversal_filenames:
        res = client.post(
            "/api/documents",
            files={"file": (raw_name, b"Safe file content\n", "text/plain")},
        )
        assert res.status_code in (200, 202)
        doc_id = res.json()["document_id"]

        doc = storage.get_document(doc_id)
        assert doc is not None
        # Must not contain directory separators or parent directory references
        assert ".." not in doc.filename
        assert "/" not in doc.filename
        assert "\\" not in doc.filename


def test_security_null_byte_injection():
    """Verify null bytes are stripped from filenames to prevent poisoning."""
    res = client.post(
        "/api/documents",
        files={"file": ("report.pdf\x00.sh", b"Text contents\n", "text/plain")},
    )
    assert res.status_code in (200, 202)
    doc_id = res.json()["document_id"]

    doc = storage.get_document(doc_id)
    assert doc is not None
    assert "\x00" not in doc.filename


def test_security_size_limit_enforced(monkeypatch):
    """Verify file size limit is strictly enforced with HTTP 413."""
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 500)

    oversized = b"A" * 1000
    res = client.post(
        "/api/documents",
        files={"file": ("overflow.txt", oversized, "text/plain")},
    )
    assert res.status_code == 413
    assert "exceeds maximum allowable limit" in res.json()["detail"]


def test_security_file_type_not_trusted_from_extension_alone():
    """Verify spoofed extensions (e.g. Mach-O / ELF / random binary named .pdf) are rejected."""
    # Mach-O 64-bit binary header: \xcf\xfa\xed\xfe
    macho_bytes = b"\xcf\xfa\xed\xfe\x07\x00\x00\x01\x03\x00\x00\x00\x02\x00\x00\x00"

    res = client.post(
        "/api/documents",
        files={"file": ("fake_document.pdf", macho_bytes, "application/pdf")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["status"] == "failed"
    assert "Unsupported file format" in data["error"]


def test_security_sha256_calculated_correctly():
    """Verify SHA-256 returned by upload matches actual cryptographic checksum."""
    payload = b"Sanctum Air-Gapped Evidence Engine Cryptographic Verification Payload"
    expected_hash = hashlib.sha256(payload).hexdigest()

    res = client.post(
        "/api/documents",
        files={"file": ("crypto_test.txt", payload, "text/plain")},
    )
    assert res.status_code in (200, 202)
    data = res.json()
    assert data["file_hash"] == expected_hash

    # Verify stored document matches
    doc = storage.get_document(data["document_id"])
    assert doc is not None
    assert doc.file_hash == expected_hash


def test_security_malformed_files_do_not_crash_api():
    """Verify truncated or corrupted files of supported types fail gracefully without crashing."""
    malformed_samples = [
        ("corrupted.docx", b"PK\x03\x04corrupted_docx_bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("corrupted.pptx", b"PK\x03\x04corrupted_pptx_bytes", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("corrupted.xlsx", b"PK\x03\x04corrupted_xlsx_bytes", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("corrupted.png", b"\x89PNG\r\n\x1a\ncorrupted_png_chunk_data", "image/png"),
    ]

    for fname, data, mime in malformed_samples:
        res = client.post(
            "/api/documents",
            files={"file": (fname, data, mime)},
        )
        assert res.status_code in (200, 202)
        doc_id = res.json()["document_id"]

        status_res = client.get(f"/api/documents/{doc_id}")
        assert status_res.status_code == 200
        # Pipeline must handle malformed data without crashing (either failed cleanly or handled)
        assert status_res.json()["status"] in ("completed", "failed")


def test_security_no_sensitive_content_in_logs(caplog):
    """Verify sensitive content from uploaded documents is not emitted to the application log."""
    secret_marker = "SUPER_CONFIDENTIAL_TOKEN_987654321_DO_NOT_LOG"
    file_bytes = f"Title: Secret Document\n{secret_marker}\n".encode("utf-8")

    with caplog.at_level(logging.INFO):
        res = client.post(
            "/api/documents",
            files={"file": ("confidential.txt", file_bytes, "text/plain")},
        )
        assert res.status_code in (200, 202)

    # Assert secret text does NOT appear in log stream
    for record in caplog.records:
        assert secret_marker not in record.message
