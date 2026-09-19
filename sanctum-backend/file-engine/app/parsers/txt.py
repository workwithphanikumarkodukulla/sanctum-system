"""Native plain text parser with safe multi-encoding decoding and line-level tracking."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, BinaryIO, Sequence

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.parsers.base import BaseParser, ParseResult

logger = logging.getLogger(__name__)


@dataclass
class TextLineInfo:
    """Represents a single line of text with source location information."""
    line_number: int
    text: str
    char_count: int


@dataclass
class TextBlockInfo:
    """Represents a logical paragraph or chunk of text with line span coordinates."""
    start_line: int
    end_line: int
    line_count: int
    text: str


@dataclass
class TxtParseResult(ParseResult):
    """Structured parsing result for plain text files, compatible with EvidenceElement normalization."""
    parser_name: str = "txt_parser"
    extracted_text: str = ""
    lines: list[TextLineInfo] = field(default_factory=list)
    blocks: list[TextBlockInfo] = field(default_factory=list)


class TxtParser(BaseParser):
    """Parses plain text from bytes or file-like streams into structured text and EvidenceElements."""

    SUPPORTED_ENCODINGS: Sequence[str] = (
        "utf-8",
        "utf-8-sig",
        "latin-1",
        "cp1252",
        "iso-8859-1",
    )

    @classmethod
    def _read_bytes(cls, input_data: bytes | BinaryIO | io.BytesIO) -> bytes:
        """Extract bytes from raw bytes or a file-like object."""
        if hasattr(input_data, "read"):
            return input_data.read()
        if isinstance(input_data, bytes):
            return input_data
        if isinstance(input_data, (bytearray, memoryview)):
            return bytes(input_data)
        raise TypeError(f"Expected bytes or file-like object, got {type(input_data).__name__}")

    @classmethod
    def decode_safely(cls, raw_bytes: bytes) -> tuple[str, str, bool]:
        """Attempt safe decoding across supported encodings with fallback.

        Returns:
            tuple of (decoded_text, used_encoding, had_replacement_errors)
        """
        if not raw_bytes:
            return "", "utf-8", False

        # 1. Try standard encodings sequentially
        for enc in cls.SUPPORTED_ENCODINGS:
            try:
                text = raw_bytes.decode(enc)
                return text, enc, False
            except (UnicodeDecodeError, LookupError):
                continue

        # 2. Final fallback: UTF-8 with replacement characters (never crashes)
        fallback_text = raw_bytes.decode("utf-8", errors="replace")
        return fallback_text, "utf-8-replace", True

    async def parse(
        self,
        file_bytes: bytes | BinaryIO,
        filename: str = "",
        document_id: str = "doc_txt",
        file_hash: str = "",
        **kwargs: Any,
    ) -> TxtParseResult:
        """Parse text input into structured lines, blocks, and canonical EvidenceElements."""
        raw_bytes = self._read_bytes(file_bytes)
        file_size = len(raw_bytes)

        # 1. Decode text safely without OCR or AI calls
        decoded_text, encoding_used, had_errors = self.decode_safely(raw_bytes)

        if not decoded_text:
            return TxtParseResult(
                elements=[],
                total_pages=1,
                parser_used="text",
                parser_name="txt_parser",
                extracted_text="",
                lines=[],
                blocks=[],
                metadata={
                    "encoding": encoding_used,
                    "file_size": file_size,
                    "total_lines": 0,
                    "total_chars": 0,
                    "is_empty": True,
                    "decoding_replacement_fallback": had_errors,
                },
            )

        # 2. Split preserving exact line structure
        raw_lines = decoded_text.splitlines()
        total_lines = len(raw_lines)

        line_records: list[TextLineInfo] = []
        for line_idx, line in enumerate(raw_lines, start=1):
            line_records.append(
                TextLineInfo(
                    line_number=line_idx,
                    text=line,
                    char_count=len(line),
                )
            )

        # 3. Group paragraphs while preserving start/end source line coordinates
        blocks: list[TextBlockInfo] = []
        elements: list[EvidenceElement] = []
        current_block_lines: list[str] = []
        start_line = 1
        elem_idx = 1

        for line_no, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if stripped:
                if not current_block_lines:
                    start_line = line_no
                current_block_lines.append(stripped)
            else:
                if current_block_lines:
                    block_text = "\n".join(current_block_lines)
                    block_info = TextBlockInfo(
                        start_line=start_line,
                        end_line=line_no - 1,
                        line_count=len(current_block_lines),
                        text=block_text,
                    )
                    blocks.append(block_info)

                    elem = EvidenceBuilder.build_element(
                        element_idx=elem_idx,
                        document_id=document_id,
                        page=1,
                        elem_type="text",
                        text=block_text,
                        bbox=[0.0, 0.0, 0.0, 0.0],
                        confidence=1.0,
                        extraction_model="text",
                        file_hash=file_hash,
                        row=start_line,
                        metadata={
                            "start_line": start_line,
                            "end_line": line_no - 1,
                            "line_count": len(current_block_lines),
                            "encoding": encoding_used,
                        },
                    )
                    elements.append(elem)
                    elem_idx += 1
                    current_block_lines = []

        # Flush final block
        if current_block_lines:
            block_text = "\n".join(current_block_lines)
            block_info = TextBlockInfo(
                start_line=start_line,
                end_line=total_lines,
                line_count=len(current_block_lines),
                text=block_text,
            )
            blocks.append(block_info)

            elem = EvidenceBuilder.build_element(
                element_idx=elem_idx,
                document_id=document_id,
                page=1,
                elem_type="text",
                text=block_text,
                bbox=[0.0, 0.0, 0.0, 0.0],
                confidence=1.0,
                extraction_model="text",
                file_hash=file_hash,
                row=start_line,
                metadata={
                    "start_line": start_line,
                    "end_line": total_lines,
                    "line_count": len(current_block_lines),
                    "encoding": encoding_used,
                },
            )
            elements.append(elem)

        meta: dict[str, Any] = {
            "parser_name": "txt_parser",
            "encoding": encoding_used,
            "file_size": file_size,
            "total_lines": total_lines,
            "total_chars": len(decoded_text),
            "total_blocks": len(blocks),
            "decoding_replacement_fallback": had_errors,
        }

        return TxtParseResult(
            elements=elements,
            total_pages=1,
            parser_used="text",
            parser_name="txt_parser",
            extracted_text=decoded_text,
            lines=line_records,
            blocks=blocks,
            metadata=meta,
        )


txt_parser = TxtParser()
