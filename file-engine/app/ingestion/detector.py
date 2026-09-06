"""File format detector utilizing content inspection, magic bytes, and safe fallbacks."""
from __future__ import annotations

import io
import mimetypes
import os
import zipfile
import logging
from app.ingestion.models import DetectedFileInfo, FileType

logger = logging.getLogger(__name__)

# Canonical Magic Bytes
MAGIC_PDF = b"%PDF"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_JPEG = b"\xff\xd8\xff"
MAGIC_TIFF_LE = b"II*\x00"
MAGIC_TIFF_BE = b"MM\x00*"
MAGIC_ZIP = b"PK\x03\x04"


class FileDetector:
    """Detects file format and MIME type using file bytes first, with extension fallback."""

    @classmethod
    def detect(cls, file_bytes: bytes, filename: str = "") -> DetectedFileInfo:
        file_size = len(file_bytes)
        ext = os.path.splitext(filename)[1].lower().lstrip(".")

        if file_size == 0:
            return DetectedFileInfo(
                file_type=FileType.UNKNOWN,
                mime_type="application/octet-stream",
                extension=ext,
                file_size=0,
                is_supported=False,
                detection_method="empty_file",
                error_message="Uploaded file is empty (0 bytes).",
            )

        # 1. Check direct PDF magic bytes
        if file_bytes.startswith(MAGIC_PDF):
            return DetectedFileInfo(
                file_type=FileType.PDF,
                mime_type="application/pdf",
                extension=ext or "pdf",
                file_size=file_size,
                is_supported=True,
                detection_method="magic_bytes",
            )

        # 2. Check raster image signatures
        # PNG
        if file_bytes.startswith(MAGIC_PNG):
            return DetectedFileInfo(
                file_type=FileType.PNG,
                mime_type="image/png",
                extension=ext or "png",
                file_size=file_size,
                is_supported=True,
                detection_method="magic_bytes",
            )

        # JPEG / JPG
        if file_bytes.startswith(MAGIC_JPEG):
            return DetectedFileInfo(
                file_type=FileType.JPEG,
                mime_type="image/jpeg",
                extension=ext or "jpg",
                file_size=file_size,
                is_supported=True,
                detection_method="magic_bytes",
            )

        # WEBP: "RIFF" .... "WEBP"
        if file_bytes.startswith(b"RIFF") and len(file_bytes) >= 12 and file_bytes[8:12] == b"WEBP":
            return DetectedFileInfo(
                file_type=FileType.WEBP,
                mime_type="image/webp",
                extension=ext or "webp",
                file_size=file_size,
                is_supported=True,
                detection_method="magic_bytes",
            )

        # TIFF (Little-Endian or Big-Endian)
        if file_bytes.startswith(MAGIC_TIFF_LE) or file_bytes.startswith(MAGIC_TIFF_BE):
            return DetectedFileInfo(
                file_type=FileType.TIFF,
                mime_type="image/tiff",
                extension=ext or "tiff",
                file_size=file_size,
                is_supported=True,
                detection_method="magic_bytes",
            )

        # 3. Check OpenXML Office archives (DOCX, PPTX, XLSX all start with PK\x03\x04)
        if file_bytes.startswith(MAGIC_ZIP):
            zip_res = cls._inspect_zip_manifest(file_bytes)
            if zip_res:
                ftype, mime, detected_ext = zip_res
                return DetectedFileInfo(
                    file_type=ftype,
                    mime_type=mime,
                    extension=ext or detected_ext,
                    file_size=file_size,
                    is_supported=True,
                    detection_method="zip_manifest",
                )
            # If it is a ZIP but not one of the supported Office OpenXML types
            if ext in ("docx", "pptx", "xlsx"):
                # Header was zip, but internal structure was corrupted or truncated
                return DetectedFileInfo(
                    file_type=FileType.UNKNOWN,
                    mime_type="application/zip",
                    extension=ext,
                    file_size=file_size,
                    is_supported=False,
                    detection_method="corrupted_office_zip",
                    error_message=f"Corrupted or invalid {ext.upper()} archive.",
                )
            return DetectedFileInfo(
                file_type=FileType.UNKNOWN,
                mime_type="application/zip",
                extension=ext or "zip",
                file_size=file_size,
                is_supported=False,
                detection_method="unsupported_zip",
                error_message="Unsupported generic ZIP archive. Expected DOCX, PPTX, or XLSX.",
            )

        # 4. Check if plain text or CSV
        text_info = cls._sniff_text_or_csv(file_bytes, ext)
        if text_info:
            return text_info

        # 5. Extension-based validation - never trust extension alone without content validation
        if ext == "pdf":
            return DetectedFileInfo(
                file_type=FileType.UNKNOWN,
                mime_type="application/pdf",
                extension="pdf",
                file_size=file_size,
                is_supported=False,
                detection_method="invalid_pdf_header",
                error_message="File has .pdf extension but lacks %PDF signature.",
            )
        elif ext in ("png", "jpg", "jpeg", "webp", "tiff", "tif"):
            try:
                from PIL import Image
                with Image.open(io.BytesIO(file_bytes)) as img:
                    img.verify()
                ft = FileType.PNG if ext == "png" else (
                    FileType.JPEG if ext in ("jpg", "jpeg") else (
                        FileType.WEBP if ext == "webp" else FileType.TIFF
                    )
                )
                return DetectedFileInfo(
                    file_type=ft,
                    mime_type=mimetypes.guess_type(filename)[0] or f"image/{ext}",
                    extension=ext,
                    file_size=file_size,
                    is_supported=True,
                    detection_method="image_verify",
                )
            except Exception:
                return DetectedFileInfo(
                    file_type=FileType.UNKNOWN,
                    mime_type=mimetypes.guess_type(filename)[0] or f"image/{ext}",
                    extension=ext,
                    file_size=file_size,
                    is_supported=False,
                    detection_method="corrupted_image",
                    error_message=f"File has .{ext} extension but is not a valid image.",
                )

        # 6. Reject unsupported or unknown binary files
        guessed_mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return DetectedFileInfo(
            file_type=FileType.UNKNOWN,
            mime_type=guessed_mime,
            extension=ext,
            file_size=file_size,
            is_supported=False,
            detection_method="unrecognized",
            error_message=f"Unsupported or unrecognized file format: '{ext or 'binary'}'.",
        )

    @staticmethod
    def _inspect_zip_manifest(file_bytes: bytes) -> tuple[FileType, str, str] | None:
        """Inspect entries inside a zip file to distinguish DOCX, PPTX, or XLSX."""
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                names = set(zf.namelist())

                # DOCX check
                if any(n.startswith("word/") for n in names) or "word/document.xml" in names:
                    return (
                        FileType.DOCX,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "docx",
                    )

                # PPTX check
                if any(n.startswith("ppt/") for n in names) or "ppt/presentation.xml" in names:
                    return (
                        FileType.PPTX,
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "pptx",
                    )

                # XLSX check
                if any(n.startswith("xl/") for n in names) or "xl/workbook.xml" in names:
                    return (
                        FileType.XLSX,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "xlsx",
                    )

                # Fallback: check [Content_Types].xml content if paths were non-standard
                if "[Content_Types].xml" in names:
                    content_types = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")
                    if "wordprocessingml" in content_types:
                        return (
                            FileType.DOCX,
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "docx",
                        )
                    if "presentationml" in content_types:
                        return (
                            FileType.PPTX,
                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                            "pptx",
                        )
                    if "spreadsheetml" in content_types:
                        return (
                            FileType.XLSX,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "xlsx",
                        )
        except Exception as exc:
            logger.debug("Failed reading zip manifest: %s", exc)
        return None

    @staticmethod
    def _sniff_text_or_csv(file_bytes: bytes, ext: str) -> DetectedFileInfo | None:
        """Check if file can be decoded as text, and distinguish CSV from plain TXT."""
        sample = file_bytes[:8192]

        # Check for excessive binary control characters (excluding tab, newline, carriage return)
        control_chars = sum(1 for b in sample if b < 32 and b not in (9, 10, 13))
        if control_chars > len(sample) * 0.05:
            return None  # Likely binary

        decoded_sample = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                decoded_sample = sample.decode(enc)
                break
            except UnicodeDecodeError:
                continue

        if decoded_sample is None:
            return None

        # Determine if CSV
        if ext == "csv":
            return DetectedFileInfo(
                file_type=FileType.CSV,
                mime_type="text/csv",
                extension="csv",
                file_size=len(file_bytes),
                is_supported=True,
                detection_method="content_and_extension",
            )

        # Inspect content structure for CSV delimiter consistency
        lines = [line.strip() for line in decoded_sample.splitlines() if line.strip()][:10]
        if len(lines) >= 2:
            # Check for comma, semicolon, or tab separation consistency
            for delimiter in (",", ";", "\t"):
                counts = [line.count(delimiter) for line in lines]
                if counts[0] > 0 and len(set(counts)) == 1:
                    return DetectedFileInfo(
                        file_type=FileType.CSV,
                        mime_type="text/csv",
                        extension=ext or "csv",
                        file_size=len(file_bytes),
                        is_supported=True,
                        detection_method="delimiter_sniff",
                    )

        # Standard plain text (either .txt or decodable text file)
        if ext in ("txt", "text", "log", "md") or not ext:
            return DetectedFileInfo(
                file_type=FileType.TXT,
                mime_type="text/plain",
                extension=ext or "txt",
                file_size=len(file_bytes),
                is_supported=True,
                detection_method="text_sniff",
            )

        return None


detector = FileDetector()
