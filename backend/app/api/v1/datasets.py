"""Catalog + OCR validation APIs for real FDA_NDC / DrugBank datasets."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.models.auth import User
from app.security.rbac import require_pharmacist
from app.services.datasets import (
    DISCLAIMER,
    catalog_available,
    catalog_db_path,
    get_meta,
    suggest_medicines,
)
from app.services.datasets.overview import catalog_overview, lookup_medicine
from app.services.formulary_catalog import catalog_display_name
from app.services.ocr import validate_prescription_image

router = APIRouter(tags=["datasets-ocr"])


class SuggestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    top_k: int = Field(default=10, ge=1, le=25)
    context_strength: str | None = None


@router.get("/catalog/status")
def catalog_status(pharmacist: User = Depends(require_pharmacist)):
    ready = catalog_available()
    meta = get_meta() if ready else {}
    return {
        "available": ready,
        "catalog_db": str(catalog_db_path()),
        "meta": meta,
        "disclaimer": DISCLAIMER,
    }


@router.get("/catalog/overview")
def catalog_overview_endpoint(pharmacist: User = Depends(require_pharmacist)):
    """Award-facing dataset provenance summary (FDA NDC / DrugBank / SPL)."""
    return catalog_overview()


@router.get("/catalog/lookup")
def catalog_lookup(
    q: str = Query(min_length=1, max_length=200),
    top_k: int = Query(default=8, ge=1, le=25),
    pharmacist: User = Depends(require_pharmacist),
):
    """Browse a medicine in the unified FDA/DrugBank catalog with source provenance."""
    return lookup_medicine(q, top_k=top_k)


@router.post("/catalog/suggest")
def catalog_suggest(body: SuggestRequest, pharmacist: User = Depends(require_pharmacist)):
    if not catalog_available():
        raise HTTPException(
            status_code=503,
            detail="Medicine catalog not built. Run: python -m app.services.datasets.build_index",
        )
    hits = suggest_medicines(
        body.query,
        top_k=body.top_k,
        context_strength=body.context_strength,
    )
    return {
        "disclaimer": DISCLAIMER,
        "query": body.query,
        "candidates": [
            {
                **asdict(h),
                "canonical_name": catalog_display_name(h.canonical_name) or h.canonical_name,
            }
            for h in hits
        ],
        "note": "Top candidates only — pharmacist must confirm. No silent auto-select.",
    }


@router.post("/ocr/validate-image")
async def ocr_validate_image(
    file: UploadFile = File(...),
    pharmacist: User = Depends(require_pharmacist),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image upload")
    result = validate_prescription_image(raw)
    return {
        "disclaimer": result.disclaimer,
        "catalog_ready": result.catalog_ready,
        "ocr": result.ocr,
        "medicines": [
            {
                "ocr_line": m.ocr_line,
                "ocr_confidence": m.ocr_confidence,
                "candidates": m.candidates,
            }
            for m in result.medicines
        ],
        "warnings": result.warnings,
    }
