"""Native CSV parser using Python's standard csv module, preserving rows, columns, and quoted fields."""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Sequence

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


@dataclass
class CsvParseResult:
    """Structured result of CSV parsing containing preserved rows, columns, and dialect metadata."""
    parser_name: str = "csv_parser"
    source_document: str = ""
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    all_rows: list[list[str]] = field(default_factory=list)
    num_rows: int = 0
    num_cols: int = 0
    delimiter: str = ","
    has_header: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    total_pages: int = 1
    parser_used: str = "csv"

    _cached_elements: list[EvidenceElement] | None = field(default=None, repr=False)
    _doc_id: str = field(default="doc", repr=False)
    _hash: str = field(default="", repr=False)

    @property
    def text(self) -> str:
        """Markdown formatted representation of the table."""
        if not self.headers and not self.rows:
            return ""
        header_line = " | ".join(self.headers)
        sep_line = " | ".join(["---"] * len(self.headers))
        body_lines = [" | ".join(r) for r in self.rows]
        return f"{header_line}\n{sep_line}\n" + "\n".join(body_lines)

    def to_evidence_elements(
        self,
        document_id: str | None = None,
        file_hash: str | None = None,
    ) -> list[EvidenceElement]:
        """Convert structured CSV data into canonical EvidenceElements."""
        doc_id = document_id or self._doc_id
        f_hash = file_hash or self._hash

        if not self.all_rows:
            return []

        elem = EvidenceBuilder.build_element(
            element_idx=1,
            document_id=doc_id,
            page=1,
            elem_type="table",
            text=self.text,
            table_data={"headers": self.headers, "rows": self.rows},
            bbox=[0.0, 0.0, 0.0, 0.0],
            confidence=1.0,
            extraction_model="csv",
            file_hash=f_hash,
            metadata={
                "source_document": self.source_document,
                "delimiter": self.delimiter,
                "total_rows": self.num_rows,
                "total_columns": self.num_cols,
                "has_header": self.has_header,
            },
        )
        return [elem]

    @property
    def elements(self) -> list[EvidenceElement]:
        """Convenience property for pipeline compatibility."""
        if self._cached_elements is None:
            self._cached_elements = self.to_evidence_elements()
        return self._cached_elements


class CsvParser(BaseParser):
    """Parses CSV files into structured rows and columns using Python's standard csv module."""

    SUPPORTED_ENCODINGS: Sequence[str] = (
        "utf-8-sig",
        "utf-8",
        "latin-1",
        "cp1252",
        "iso-8859-1",
    )

    @classmethod
    def _read_bytes(cls, input_data: bytes | BinaryIO | str | Path) -> bytes:
        if hasattr(input_data, "read"):
            return input_data.read()
        if isinstance(input_data, (str, Path)):
            with open(input_data, "rb") as f:
                return f.read()
        if isinstance(input_data, bytes):
            return input_data
        if isinstance(input_data, (bytearray, memoryview)):
            return bytes(input_data)
        raise TypeError(f"Expected bytes, Path, or file stream, got {type(input_data).__name__}")

    @classmethod
    def decode_safely(cls, raw_bytes: bytes) -> tuple[str, str]:
        """Safely decode raw bytes with encoding fallback."""
        if not raw_bytes:
            return "", "utf-8"

        for enc in cls.SUPPORTED_ENCODINGS:
            try:
                return raw_bytes.decode(enc), enc
            except (UnicodeDecodeError, LookupError):
                continue

        return raw_bytes.decode("utf-8", errors="replace"), "utf-8-replace"

    async def parse(
        self,
        file_bytes: bytes | BinaryIO | str | Path,
        filename: str = "",
        document_id: str = "doc",
        file_hash: str = "",
        **kwargs: Any,
    ) -> CsvParseResult:
        """Parse CSV input into a structured CsvParseResult preserving row and column order."""
        raw_bytes = self._read_bytes(file_bytes)
        source_doc = filename or "data.csv"

        if not raw_bytes:
            return CsvParseResult(
                parser_name="csv_parser",
                source_document=source_doc,
                headers=[],
                rows=[],
                all_rows=[],
                num_rows=0,
                num_cols=0,
                metadata={"is_empty": True, "source_document": source_doc},
                total_pages=1,
                parser_used="csv",
                _doc_id=document_id,
                _hash=file_hash,
            )

        decoded_text, encoding_used = self.decode_safely(raw_bytes)

        # Detect dialect / delimiter
        sample = decoded_text[:8192]
        delimiter = ","
        has_header = True

        if sample.strip():
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t", "|"])
                delimiter = dialect.delimiter
            except Exception:
                # Fallback heuristics
                first_line = sample.splitlines()[0] if sample.splitlines() else ""
                for delim in (",", ";", "\t", "|"):
                    if delim in first_line:
                        delimiter = delim
                        break

        reader = csv.reader(
            io.StringIO(decoded_text),
            delimiter=delimiter,
            quotechar='"',
            doublequote=True,
            skipinitialspace=True,
        )

        all_rows: list[list[str]] = []
        for r in reader:
            # Skip completely empty lines
            if any(cell.strip() for cell in r):
                all_rows.append([cell.strip() for cell in r])

        if not all_rows:
            return CsvParseResult(
                parser_name="csv_parser",
                source_document=source_doc,
                headers=[],
                rows=[],
                all_rows=[],
                num_rows=0,
                num_cols=0,
                delimiter=delimiter,
                has_header=False,
                metadata={"is_empty": True, "encoding": encoding_used, "source_document": source_doc},
                total_pages=1,
                parser_used="csv",
                _doc_id=document_id,
                _hash=file_hash,
            )

        num_cols = max(len(r) for r in all_rows)

        # In standard CSV document ingestion, row 0 defines column headers
        headers = all_rows[0]
        body_rows = all_rows[1:] if len(all_rows) > 1 else []

        meta = {
            "source_document": source_doc,
            "encoding": encoding_used,
            "delimiter": delimiter,
            "has_header": has_header,
            "total_rows": len(all_rows),
            "num_data_rows": len(body_rows),
            "num_cols": num_cols,
            "is_empty": False,
        }

        return CsvParseResult(
            parser_name="csv_parser",
            source_document=source_doc,
            headers=headers,
            rows=body_rows,
            all_rows=all_rows,
            num_rows=len(all_rows),
            num_cols=num_cols,
            delimiter=delimiter,
            has_header=has_header,
            metadata=meta,
            total_pages=1,
            parser_used="csv",
            _doc_id=document_id,
            _hash=file_hash,
        )


csv_parser = CsvParser()
