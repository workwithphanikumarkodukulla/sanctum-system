"""Unit tests for the FileRouter layer proving correct parser mapping and protocol compliance."""
from __future__ import annotations

import pytest
from app.ingestion.detector import detector
from app.ingestion.models import DetectedFileInfo, FileType
from app.ingestion.router import DocumentParser, FileRouter, PlaceholderParser, router


def test_document_parser_protocol_conformance():
    """Verify that all default registered parsers conform to the DocumentParser protocol."""
    required_types = [
        FileType.PDF,
        FileType.DOCX,
        FileType.PPTX,
        FileType.XLSX,
        FileType.CSV,
        FileType.TXT,
        FileType.IMAGE,
        FileType.PNG,
        FileType.JPEG,
        FileType.WEBP,
        FileType.TIFF,
    ]

    for ftype in required_types:
        parser = router.get_parser(ftype)
        assert isinstance(parser, DocumentParser), f"Parser for {ftype} must satisfy DocumentParser protocol"
        assert hasattr(parser, "parse")
        assert callable(parser.parse)


def test_router_maps_all_supported_types():
    """Verify that every supported format resolves to its dedicated parser."""
    pdf_parser = router.get_parser(FileType.PDF)
    docx_parser = router.get_parser(FileType.DOCX)
    pptx_parser = router.get_parser(FileType.PPTX)
    xlsx_parser = router.get_parser(FileType.XLSX)
    csv_parser = router.get_parser(FileType.CSV)
    txt_parser = router.get_parser(FileType.TXT)
    img_parser = router.get_parser(FileType.IMAGE)

    # Ensure parsers for distinct categories are distinct instances
    parsers = [pdf_parser, docx_parser, pptx_parser, xlsx_parser, csv_parser, txt_parser, img_parser]
    assert len(set(id(p) for p in parsers)) == 7, "Each document format should map to its dedicated parser"

    # Ensure all image variants map to the image parser
    assert router.get_parser(FileType.PNG) is img_parser
    assert router.get_parser(FileType.JPEG) is img_parser
    assert router.get_parser(FileType.WEBP) is img_parser
    assert router.get_parser(FileType.TIFF) is img_parser


def test_router_via_detected_file_info():
    """Verify that router.route works end-to-end with detector output."""
    pdf_bytes = b"%PDF-1.4 sample content"
    detection = detector.detect(pdf_bytes, "doc.pdf")
    parser = router.route(detection)
    assert isinstance(parser, DocumentParser)
    assert parser is router.get_parser(FileType.PDF)


def test_router_rejects_unsupported_and_unknown():
    """Verify that unknown/unsupported types raise clear ValueErrors."""
    with pytest.raises(ValueError, match="No parser registered"):
        router.get_parser(FileType.UNKNOWN)

    with pytest.raises(ValueError, match="Unknown or unsupported"):
        router.get_parser("audio_mp3")

    # Unsupported DetectedFileInfo
    unsupported_info = DetectedFileInfo(
        file_type=FileType.UNKNOWN,
        mime_type="application/octet-stream",
        extension="bin",
        file_size=10,
        is_supported=False,
        detection_method="unrecognized",
        error_message="Unknown binary format",
    )
    with pytest.raises(ValueError, match="Cannot route unsupported file"):
        router.route(unsupported_info)


def test_custom_parser_registration():
    """Verify that new parsers can be registered or swapped dynamically."""
    test_router = FileRouter()

    class MockCustomDocxParser:
        async def parse(self, file_bytes: bytes, filename: str, document_id: str, file_hash: str, **kwargs):
            return "custom_docx_parsed"

    custom_parser = MockCustomDocxParser()
    test_router.register_parser(FileType.DOCX, custom_parser)

    retrieved = test_router.get_parser(FileType.DOCX)
    assert retrieved is custom_parser
    assert isinstance(retrieved, DocumentParser)


@pytest.mark.anyio
async def test_placeholder_parser_behavior():
    """Verify that placeholder parsers indicate they are not yet implemented."""
    placeholder = PlaceholderParser("FutureParser")
    assert isinstance(placeholder, DocumentParser)
    with pytest.raises(NotImplementedError, match="is a placeholder"):
        await placeholder.parse(b"", "dummy.ext", "doc_1", "hash_1")
