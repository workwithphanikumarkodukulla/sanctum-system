"""File routing engine mapping detected file types to dedicated document parsers."""
from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

from app.ingestion.models import DetectedFileInfo, FileType

logger = logging.getLogger(__name__)


@runtime_checkable
class DocumentParser(Protocol):
    """Protocol defining the interface for all document and data parsers."""

    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        file_hash: str,
        **kwargs: Any,
    ) -> Any:
        """Parse raw file bytes into normalized evidence output."""
        ...


class PlaceholderParser:
    """Explicit placeholder for parsers under development."""

    def __init__(self, parser_name: str) -> None:
        self.parser_name = parser_name

    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        file_hash: str,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError(
            f"Parser '{self.parser_name}' is a placeholder and has not been initialized."
        )

    def __repr__(self) -> str:
        return f"<PlaceholderParser name='{self.parser_name}'>"


class FileRouter:
    """Decoupled routing engine that maps detected file types to their registered DocumentParser."""

    def __init__(self) -> None:
        self._registry: dict[FileType, DocumentParser] = {}
        self._init_default_registry()

    def _init_default_registry(self) -> None:
        """Initialize registry with actual parsers if available, or clean placeholders."""
        try:
            from app.parsers.pdf import pdf_parser
            self._registry[FileType.PDF] = pdf_parser
        except (ImportError, AttributeError):
            self._registry[FileType.PDF] = PlaceholderParser("PDFParser")

        try:
            from app.parsers.docx import docx_parser
            self._registry[FileType.DOCX] = docx_parser
        except (ImportError, AttributeError):
            self._registry[FileType.DOCX] = PlaceholderParser("DocxParser")

        try:
            from app.parsers.pptx import pptx_parser
            self._registry[FileType.PPTX] = pptx_parser
        except (ImportError, AttributeError):
            self._registry[FileType.PPTX] = PlaceholderParser("PptxParser")

        try:
            from app.parsers.xlsx import xlsx_parser
            self._registry[FileType.XLSX] = xlsx_parser
        except (ImportError, AttributeError):
            self._registry[FileType.XLSX] = PlaceholderParser("XlsxParser")

        try:
            from app.parsers.csv import csv_parser
            self._registry[FileType.CSV] = csv_parser
        except (ImportError, AttributeError):
            self._registry[FileType.CSV] = PlaceholderParser("CsvParser")

        try:
            from app.parsers.txt import txt_parser
            self._registry[FileType.TXT] = txt_parser
        except (ImportError, AttributeError):
            self._registry[FileType.TXT] = PlaceholderParser("TxtParser")

        try:
            from app.parsers.image import image_parser
            img_parser = image_parser
        except (ImportError, AttributeError):
            img_parser = PlaceholderParser("ImageParser")

        # Map generic and specific raster formats to image parser
        self._registry[FileType.IMAGE] = img_parser
        self._registry[FileType.PNG] = img_parser
        self._registry[FileType.JPEG] = img_parser
        self._registry[FileType.WEBP] = img_parser
        self._registry[FileType.TIFF] = img_parser

    def get_parser(self, file_type: FileType | str) -> DocumentParser:
        """Retrieve the registered parser for a given FileType.

        Args:
            file_type: A FileType enum value or string key.

        Returns:
            DocumentParser instance.

        Raises:
            ValueError: If file_type is unsupported or has no registered parser.
        """
        if isinstance(file_type, str):
            try:
                file_type = FileType(file_type.lower())
            except ValueError:
                raise ValueError(f"Unknown or unsupported file type: '{file_type}'")

        parser = self._registry.get(file_type)
        if not parser:
            logger.error("No parser registered for file type: %s", file_type)
            raise ValueError(f"No parser registered for file type: '{file_type.value}'")
        return parser

    def route(self, detected_info: DetectedFileInfo) -> DocumentParser:
        """Convenience method to route directly from a DetectedFileInfo object."""
        if not detected_info.is_supported or detected_info.file_type == FileType.UNKNOWN:
            raise ValueError(
                f"Cannot route unsupported file: {detected_info.error_message or 'Unknown type'}"
            )
        return self.get_parser(detected_info.file_type)

    def register_parser(self, file_type: FileType, parser: DocumentParser) -> None:
        """Register or override a parser for a specific FileType."""
        self._registry[file_type] = parser

    def get_registered_types(self) -> list[FileType]:
        """List all currently registered FileTypes."""
        return list(self._registry.keys())


router = FileRouter()
