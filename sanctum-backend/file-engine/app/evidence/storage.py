"""Thread-safe in-memory storage for documents and evidence elements."""
from __future__ import annotations

import threading
from typing import Dict, Optional
from app.evidence.schema import DocumentEvidence, EvidenceElement


class EvidenceStorage:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._documents: Dict[str, DocumentEvidence] = {}
        self._elements_index: Dict[str, EvidenceElement] = {}

    def save(self, doc: DocumentEvidence) -> None:
        with self._lock:
            self._documents[doc.document_id] = doc
            for elem in doc.elements:
                self._elements_index[elem.id] = elem

    def get_document(self, document_id: str) -> Optional[DocumentEvidence]:
        with self._lock:
            return self._documents.get(document_id)

    def get_element(self, element_id: str) -> Optional[EvidenceElement]:
        with self._lock:
            return self._elements_index.get(element_id)

    def get_page_elements(self, document_id: str, page_number: int) -> list[EvidenceElement]:
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return []
            return [el for el in doc.elements if el.page == page_number]

    def clear(self) -> None:
        with self._lock:
            self._documents.clear()
            self._elements_index.clear()


storage = EvidenceStorage()
