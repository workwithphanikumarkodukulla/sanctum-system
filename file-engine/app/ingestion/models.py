"""Data models for file ingestion, detection, and routing."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    CSV = "csv"
    TXT = "txt"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"
    TIFF = "tiff"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DetectedFileInfo:
    file_type: FileType
    mime_type: str
    extension: str
    file_size: int
    is_supported: bool
    detection_method: str
    error_message: str | None = None

    @property
    def is_image(self) -> bool:
        return self.file_type in (
            FileType.PNG,
            FileType.JPEG,
            FileType.WEBP,
            FileType.TIFF,
            FileType.IMAGE,
        )

    @property
    def is_office(self) -> bool:
        return self.file_type in (FileType.DOCX, FileType.PPTX, FileType.XLSX)
