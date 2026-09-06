"""Native DOCX parser using python-docx, extracting document structure in reading order."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Sequence

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.evidence.builder import EvidenceBuilder
from app.evidence.schema import EvidenceElement
from app.parsers.base import BaseParser

logger = logging.getLogger(__name__)


@dataclass
class DocxParagraph:
    """Structured representation of a DOCX paragraph."""
    index: int  # Paragraph index in document
    reading_order: int  # Overall reading order index
    text: str
    style: str
    is_heading: bool
    heading_level: int | None = None
    source_document: str = ""


@dataclass
class DocxTable:
    """Structured representation of a DOCX table."""
    index: int  # Table index in document
    reading_order: int  # Overall reading order index
    headers: list[str]
    rows: list[list[str]]
    num_rows: int
    num_cols: int
    source_document: str = ""

    @property
    def text(self) -> str:
        """Formatted markdown table text representation."""
        if not self.headers and not self.rows:
            return ""
        header_line = " | ".join(self.headers)
        sep_line = " | ".join(["---"] * len(self.headers))
        body_lines = [" | ".join(r) for r in self.rows]
        return f"{header_line}\n{sep_line}\n" + "\n".join(body_lines)


@dataclass
class DocxParseResult:
    """Structured result of DOCX parsing in reading order."""
    parser_name: str = "docx_parser"
    source_document: str = ""
    items: list[DocxParagraph | DocxTable] = field(default_factory=list)
    paragraphs: list[DocxParagraph] = field(default_factory=list)
    tables: list[DocxTable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    total_pages: int = 1
    parser_used: str = "python-docx"

    _cached_elements: list[EvidenceElement] | None = field(default=None, repr=False)
    _doc_id: str = field(default="doc", repr=False)
    _hash: str = field(default="", repr=False)

    def to_evidence_elements(
        self,
        document_id: str | None = None,
        file_hash: str | None = None,
    ) -> list[EvidenceElement]:
        """Convert structured DOCX items into canonical EvidenceElements."""
        doc_id = document_id or self._doc_id
        f_hash = file_hash or self._hash
        elements: list[EvidenceElement] = []

        for idx, item in enumerate(self.items, start=1):
            if isinstance(item, DocxParagraph):
                elem = EvidenceBuilder.build_element(
                    element_idx=idx,
                    document_id=doc_id,
                    page=1,
                    elem_type="text",
                    text=item.text,
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="python-docx",
                    file_hash=f_hash,
                    metadata={
                        "source_document": item.source_document,
                        "paragraph_index": item.index,
                        "reading_order": item.reading_order,
                        "style": item.style,
                        "is_heading": item.is_heading,
                        "heading_level": item.heading_level,
                    },
                )
                elements.append(elem)

            elif isinstance(item, DocxTable):
                elem = EvidenceBuilder.build_element(
                    element_idx=idx,
                    document_id=doc_id,
                    page=1,
                    elem_type="table",
                    text=item.text,
                    table_data={"headers": item.headers, "rows": item.rows},
                    bbox=[0.0, 0.0, 0.0, 0.0],
                    confidence=1.0,
                    extraction_model="python-docx",
                    file_hash=f_hash,
                    metadata={
                        "source_document": item.source_document,
                        "table_index": item.index,
                        "reading_order": item.reading_order,
                        "num_rows": item.num_rows,
                        "num_cols": item.num_cols,
                    },
                )
                elements.append(elem)

        return elements

    @property
    def elements(self) -> list[EvidenceElement]:
        """Convenience property for pipeline compatibility."""
        if self._cached_elements is None:
            self._cached_elements = self.to_evidence_elements()
        return self._cached_elements


class DocxParser(BaseParser):
    """Native parser for DOCX files extracting paragraphs, headings, and tables in reading order."""

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

    async def parse(
        self,
        file_bytes: bytes | BinaryIO | str | Path,
        filename: str = "",
        document_id: str = "doc",
        file_hash: str = "",
        **kwargs: Any,
    ) -> DocxParseResult:
        """Parse DOCX content into a structured DocxParseResult preserving reading order."""
        raw_bytes = self._read_bytes(file_bytes)
        source_doc = filename or "document.docx"

        if not raw_bytes:
            return DocxParseResult(
                parser_name="docx_parser",
                source_document=source_doc,
                items=[],
                paragraphs=[],
                tables=[],
                metadata={
                    "source_document": source_doc,
                    "total_items": 0,
                    "total_paragraphs": 0,
                    "total_tables": 0,
                    "is_empty": True,
                },
                _doc_id=document_id,
                _hash=file_hash,
            )

        doc = Document(io.BytesIO(raw_bytes))

        items: list[DocxParagraph | DocxTable] = []
        paragraphs: list[DocxParagraph] = []
        tables: list[DocxTable] = []

        para_counter = 0
        table_counter = 0
        reading_order = 0

        # Traverse body in exact reading order
        for child in doc.element.body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue

                para_counter += 1
                reading_order += 1

                style_name = para.style.name if para.style else "Normal"
                is_heading = style_name.lower().startswith("heading") or style_name.lower() == "title"

                heading_level = None
                if is_heading:
                    parts = style_name.split()
                    if len(parts) > 1 and parts[-1].isdigit():
                        heading_level = int(parts[-1])
                    elif style_name.lower() == "title":
                        heading_level = 0

                p_item = DocxParagraph(
                    index=para_counter,
                    reading_order=reading_order,
                    text=text,
                    style=style_name,
                    is_heading=is_heading,
                    heading_level=heading_level,
                    source_document=source_doc,
                )
                items.append(p_item)
                paragraphs.append(p_item)

            elif tag == "tbl":
                tbl = Table(child, doc)
                rows_data: list[list[str]] = []
                for row in tbl.rows:
                    row_cells = [cell.text.strip() for cell in row.cells]
                    rows_data.append(row_cells)

                if not rows_data:
                    continue

                table_counter += 1
                reading_order += 1

                headers = rows_data[0]
                body_rows = rows_data[1:] if len(rows_data) > 1 else []

                t_item = DocxTable(
                    index=table_counter,
                    reading_order=reading_order,
                    headers=headers,
                    rows=body_rows,
                    num_rows=len(rows_data),
                    num_cols=len(headers),
                    source_document=source_doc,
                )
                items.append(t_item)
                tables.append(t_item)

        meta = {
            "source_document": source_doc,
            "total_items": len(items),
            "total_paragraphs": len(paragraphs),
            "total_tables": len(tables),
            "is_empty": len(items) == 0,
        }

        return DocxParseResult(
            parser_name="docx_parser",
            source_document=source_doc,
            items=items,
            paragraphs=paragraphs,
            tables=tables,
            metadata=meta,
            total_pages=1,
            parser_used="python-docx",
            _doc_id=document_id,
            _hash=file_hash,
        )


docx_parser = DocxParser()
