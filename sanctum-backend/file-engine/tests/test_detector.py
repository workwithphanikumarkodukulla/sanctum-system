"""Unit tests for the FileDetector layer covering all supported and unsupported formats."""
from __future__ import annotations

import io
import zipfile
import pytest

from app.ingestion.detector import detector
from app.ingestion.models import FileType


def create_mock_zip(file_entries: list[str]) -> bytes:
    """Helper to create an in-memory zip archive with the specified entry names."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in file_entries:
            zf.writestr(entry, f"Dummy content for {entry}")
    return buf.getvalue()


# --- Supported Format Detection Tests ---

def test_detect_pdf():
    # PDF magic bytes alone
    pdf_bytes = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    res = detector.detect(pdf_bytes, filename="")
    assert res.file_type == FileType.PDF
    assert res.mime_type == "application/pdf"
    assert res.is_supported is True
    assert res.detection_method == "magic_bytes"

    # PDF with extension
    res2 = detector.detect(pdf_bytes, filename="document.pdf")
    assert res2.file_type == FileType.PDF
    assert res2.is_supported is True


def test_detect_docx():
    docx_bytes = create_mock_zip(["[Content_Types].xml", "word/document.xml", "_rels/.rels"])
    res = detector.detect(docx_bytes, filename="report.docx")
    assert res.file_type == FileType.DOCX
    assert "wordprocessingml" in res.mime_type
    assert res.is_supported is True
    assert res.detection_method == "zip_manifest"


def test_detect_pptx():
    pptx_bytes = create_mock_zip(["[Content_Types].xml", "ppt/presentation.xml", "_rels/.rels"])
    res = detector.detect(pptx_bytes, filename="slides.pptx")
    assert res.file_type == FileType.PPTX
    assert "presentationml" in res.mime_type
    assert res.is_supported is True
    assert res.detection_method == "zip_manifest"


def test_detect_xlsx():
    xlsx_bytes = create_mock_zip(["[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"])
    res = detector.detect(xlsx_bytes, filename="finance.xlsx")
    assert res.file_type == FileType.XLSX
    assert "spreadsheetml" in res.mime_type
    assert res.is_supported is True
    assert res.detection_method == "zip_manifest"


def test_detect_images():
    # PNG signature: \x89PNG\r\n\x1a\n
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    res_png = detector.detect(png_bytes, filename="photo.png")
    assert res_png.file_type == FileType.PNG
    assert res_png.mime_type == "image/png"
    assert res_png.is_image is True
    assert res_png.is_supported is True
    assert res_png.detection_method == "magic_bytes"

    # JPEG signature: \xff\xd8\xff
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
    res_jpeg = detector.detect(jpeg_bytes, filename="photo.jpg")
    assert res_jpeg.file_type == FileType.JPEG
    assert res_jpeg.mime_type == "image/jpeg"
    assert res_jpeg.is_image is True
    assert res_jpeg.is_supported is True
    assert res_jpeg.detection_method == "magic_bytes"

    # WEBP signature: RIFF....WEBP
    webp_bytes = b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00"
    res_webp = detector.detect(webp_bytes, filename="graphic.webp")
    assert res_webp.file_type == FileType.WEBP
    assert res_webp.mime_type == "image/webp"
    assert res_webp.is_image is True
    assert res_webp.is_supported is True
    assert res_webp.detection_method == "magic_bytes"

    # TIFF Little-Endian signature: II*\x00
    tiff_le = b"II*\x00\x08\x00\x00\x00\x01\x00"
    res_tiff_le = detector.detect(tiff_le, filename="scan_le.tiff")
    assert res_tiff_le.file_type == FileType.TIFF
    assert res_tiff_le.mime_type == "image/tiff"
    assert res_tiff_le.is_image is True
    assert res_tiff_le.is_supported is True

    # TIFF Big-Endian signature: MM\x00*
    tiff_be = b"MM\x00*\x00\x00\x00\x08\x00\x01"
    res_tiff_be = detector.detect(tiff_be, filename="scan_be.tif")
    assert res_tiff_be.file_type == FileType.TIFF
    assert res_tiff_be.mime_type == "image/tiff"
    assert res_tiff_be.is_image is True
    assert res_tiff_be.is_supported is True


def test_detect_csv():
    # Comma-delimited content without filename
    csv_bytes = b"ID,Name,Value,Unit\n1,Sensor-A,45.2,degC\n2,Sensor-B,48.1,degC\n"
    res = detector.detect(csv_bytes, filename="")
    assert res.file_type == FileType.CSV
    assert res.mime_type == "text/csv"
    assert res.is_supported is True
    assert res.detection_method == "delimiter_sniff"

    # Semicolon-delimited CSV
    sc_bytes = b"ColA;ColB;ColC\n100;200;300\n400;500;600\n"
    res_sc = detector.detect(sc_bytes, filename="data.csv")
    assert res_sc.file_type == FileType.CSV
    assert res_sc.is_supported is True

    # CSV by extension with generic text
    res_ext = detector.detect(b"plain single column text\nval1\nval2\n", filename="items.csv")
    assert res_ext.file_type == FileType.CSV
    assert res_ext.is_supported is True


def test_detect_txt():
    txt_bytes = b"Operating manual for industrial compressor.\nFollow safety protocol 101.\n"
    res = detector.detect(txt_bytes, filename="manual.txt")
    assert res.file_type == FileType.TXT
    assert res.mime_type == "text/plain"
    assert res.is_supported is True
    assert res.detection_method == "text_sniff"


# --- Unsupported and Edge Case Tests ---

def test_detect_empty_file():
    res = detector.detect(b"", filename="empty.pdf")
    assert res.file_type == FileType.UNKNOWN
    assert res.file_size == 0
    assert res.is_supported is False
    assert res.error_message == "Uploaded file is empty (0 bytes)."


def test_detect_unsupported_zip():
    # A generic ZIP containing files like logs or pictures, not an Office OpenXML format
    generic_zip = create_mock_zip(["notes.txt", "data.json", "config.yaml"])
    res = detector.detect(generic_zip, filename="archive.zip")
    assert res.file_type == FileType.UNKNOWN
    assert res.is_supported is False
    assert "Expected DOCX, PPTX, or XLSX" in (res.error_message or "")


def test_detect_corrupted_office_zip():
    # Corrupted zip claiming to be docx
    corrupted_docx = b"PK\x03\x04not_a_valid_zip_content"
    res = detector.detect(corrupted_docx, filename="corrupt.docx")
    assert res.file_type == FileType.UNKNOWN
    assert res.is_supported is False
    assert "Corrupted or invalid DOCX archive" in (res.error_message or "")


def test_detect_unsupported_binary():
    # ELF binary header
    elf_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    res = detector.detect(elf_bytes, filename="program.bin")
    assert res.file_type == FileType.UNKNOWN
    assert res.is_supported is False
    assert "Unsupported or unrecognized" in (res.error_message or "")


def test_detect_unsupported_media():
    # MP4 / video signature
    mp4_bytes = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41"
    res = detector.detect(mp4_bytes, filename="video.mp4")
    assert res.file_type == FileType.UNKNOWN
    assert res.is_supported is False
    assert res.mime_type == "video/mp4"
