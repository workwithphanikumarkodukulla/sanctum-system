"""Base parser interface and parse result definition."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from app.evidence.schema import EvidenceElement


@dataclass
class ParseResult:
    elements: list[EvidenceElement] = field(default_factory=list)
    total_pages: int = 1
    parser_used: str = "unknown"
    metadata: dict[str, Any] | None = None


class BaseParser(ABC):
    """Abstract interface for all document and data parsers."""

    @abstractmethod
    async def parse(
        self,
        file_bytes: bytes,
        filename: str,
        document_id: str,
        file_hash: str,
    ) -> ParseResult:
        """Parse raw file bytes into normalized EvidenceElements and total pages."""
        pass
