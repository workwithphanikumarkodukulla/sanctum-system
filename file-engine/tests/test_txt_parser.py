"""Unit tests for the TxtParser covering UTF-8, multiline, empty, and alternative/invalid encodings."""
from __future__ import annotations

import io
import pytest

from app.evidence.schema import EvidenceElement
from app.parsers.txt import TxtParser, TxtParseResult, txt_parser


@pytest.mark.anyio
async def test_txt_parser_normal_utf8():
    """Verify normal UTF-8 text parsing, content preservation, and metadata."""
    sample_text = "System Initialized.\nPressure levels steady at 450 kPa.\nAll safety valves operational."
    raw_bytes = sample_text.encode("utf-8")

    result: TxtParseResult = await txt_parser.parse(
        file_bytes=raw_bytes,
        filename="system.txt",
        document_id="doc_test_1",
        file_hash="hash123",
    )

    assert result.parser_name == "txt_parser"
    assert result.extracted_text == sample_text
    assert result.metadata["encoding"] == "utf-8"
    assert result.metadata["total_lines"] == 3
    assert result.metadata["total_chars"] == len(sample_text)
    assert len(result.lines) == 3
    assert result.lines[0].text == "System Initialized."
    assert result.lines[0].line_number == 1
    assert result.lines[1].text == "Pressure levels steady at 450 kPa."
    assert result.lines[1].line_number == 2

    # Evidence element normalization check
    assert len(result.elements) >= 1
    elem = result.elements[0]
    assert isinstance(elem, EvidenceElement)
    assert elem.document_id == "doc_test_1"
    assert elem.type == "text"
    assert elem.confidence == 1.0
    assert elem.extraction_model == "text"


@pytest.mark.anyio
async def test_txt_parser_multiline_and_paragraphs():
    """Verify multiline text with blank lines separates paragraphs while preserving line numbers."""
    multiline_text = (
        "Header Paragraph: Overview of Unit 4.\n"
        "Second line of first block.\n"
        "\n"
        "Second Paragraph: Critical Warning.\n"
        "Check coolant flow rate immediately.\n"
        "\n"
        "Conclusion: Sign off required."
    )
    raw_bytes = multiline_text.encode("utf-8")

    result = await txt_parser.parse(
        file_bytes=raw_bytes,
        filename="multiline.txt",
        document_id="doc_multi",
        file_hash="hash_multi",
    )

    assert result.metadata["total_lines"] == 7
    assert len(result.blocks) == 3

    # Check first block coordinates
    block1 = result.blocks[0]
    assert block1.start_line == 1
    assert block1.end_line == 2
    assert "Overview of Unit 4." in block1.text

    # Check second block coordinates
    block2 = result.blocks[1]
    assert block2.start_line == 4
    assert block2.end_line == 5
    assert "Critical Warning." in block2.text

    # Check third block coordinates
    block3 = result.blocks[2]
    assert block3.start_line == 7
    assert block3.end_line == 7
    assert "Conclusion: Sign off required." in block3.text

    # Verify elements match blocks
    assert len(result.elements) == 3
    assert result.elements[0].row == 1
    assert result.elements[1].row == 4
    assert result.elements[2].row == 7


@pytest.mark.anyio
async def test_txt_parser_empty_file():
    """Verify empty input returns empty elements without error."""
    result = await txt_parser.parse(
        file_bytes=b"",
        filename="empty.txt",
        document_id="doc_empty",
        file_hash="hash_empty",
    )

    assert result.parser_name == "txt_parser"
    assert result.extracted_text == ""
    assert len(result.lines) == 0
    assert len(result.blocks) == 0
    assert len(result.elements) == 0
    assert result.metadata["is_empty"] is True
    assert result.metadata["total_lines"] == 0


@pytest.mark.anyio
async def test_txt_parser_alternative_encoding_latin1():
    """Verify graceful handling of non-UTF8 alternative encodings like Latin-1 / ISO-8859-1."""
    # Text with Latin-1 specific characters (accented characters: é, ñ, ü, ©, °)
    latin1_text = "Rapport d'inspection: vanne n 4 - température: 85°C. Statut: vérifié."
    latin1_bytes = latin1_text.encode("latin-1")

    # Ensure this byte sequence is indeed different from UTF-8
    with pytest.raises(UnicodeDecodeError):
        latin1_bytes.decode("utf-8")

    result = await txt_parser.parse(
        file_bytes=latin1_bytes,
        filename="report_latin1.txt",
        document_id="doc_lat",
        file_hash="hash_lat",
    )

    assert result.metadata["encoding"] == "latin-1"
    assert result.metadata["decoding_replacement_fallback"] is False
    assert "température: 85°C" in result.extracted_text
    assert "vérifié" in result.extracted_text
    assert len(result.elements) == 1


@pytest.mark.anyio
async def test_txt_parser_invalid_encoding_fallback():
    """Verify arbitrary corrupted byte sequences are decoded via fallback without crashing."""
    # Byte sequences that are invalid in UTF-8
    corrupted_bytes = b"\xff\xfe\x99\x80\x81\x82Random Text at the end"

    # Should not raise any exception
    result = await txt_parser.parse(
        file_bytes=corrupted_bytes,
        filename="corrupt.txt",
        document_id="doc_corrupt",
        file_hash="hash_corrupt",
    )

    assert result.parser_name == "txt_parser"
    assert len(result.extracted_text) > 0
    assert "Random Text at the end" in result.extracted_text


@pytest.mark.anyio
async def test_txt_parser_file_like_stream_input():
    """Verify parser works seamlessly with file-like objects (BytesIO)."""
    stream = io.BytesIO(b"Data stream content line 1\nLine 2 from buffer")
    result = await txt_parser.parse(
        file_bytes=stream,
        filename="buffer.txt",
        document_id="doc_buf",
        file_hash="hash_buf",
    )

    assert result.metadata["total_lines"] == 2
    assert result.lines[0].text == "Data stream content line 1"
    assert result.lines[1].text == "Line 2 from buffer"
