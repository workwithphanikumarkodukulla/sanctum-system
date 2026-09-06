"""Evidence lookup endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from app.evidence.schema import EvidenceElement
from app.evidence.storage import storage

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

# NOTE: Authentication/Authorization Layer:
# In an enterprise deployment, inject an authentication dependency here.


@router.get("/{evidence_id}", response_model=EvidenceElement)
async def get_evidence_by_id(evidence_id: str) -> EvidenceElement:
    """Returns a single EvidenceElement by its element id (e.g. 'p1_e2')."""
    element = storage.get_element(evidence_id)
    if not element:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence element with ID '{evidence_id}' not found.",
        )
    return element
