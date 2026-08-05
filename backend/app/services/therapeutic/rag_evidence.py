"""Spec O4 — retrieve-first evidence RAG over local FDA SPL / catalog label sections.

Never writes dose/frequency. Optional Groq summary only over retrieved excerpts.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Retrieved label excerpts for decision-support only. Not prescribing advice. "
    "Pharmacist must verify against full labelling and patient context."
)

INSUFFICIENT_EVIDENCE_MESSAGE = "Insufficient evidence — pharmacist review required."


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def retrieve_label_excerpts(
    *,
    medicine_name: str,
    indication: str | None = None,
    catalog_medicine_id: int | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Keyword retrieval over medicine_catalog.label_sections (FAISS-compatible shape)."""
    from app.core.config import settings

    if not getattr(settings, "ENABLE_SPEC_RAG", True):
        return {
            "enabled": False,
            "status": "disabled",
            "method": "catalog_label_sections",
            "excerpts": [],
            "disclaimer": DISCLAIMER,
        }

    try:
        from app.services.datasets.catalog_store import catalog_available, _connect
    except Exception:
        return {
            "enabled": True,
            "status": "catalog_unavailable",
            "method": "catalog_label_sections",
            "excerpts": [],
            "disclaimer": DISCLAIMER,
        }

    if not catalog_available():
        return {
            "enabled": True,
            "status": "catalog_unavailable",
            "method": "catalog_label_sections",
            "excerpts": [],
            "disclaimer": DISCLAIMER,
        }

    query = f"{medicine_name or ''} {indication or ''}".strip()
    q_tokens = _tokenize(query)
    excerpts: list[dict[str, Any]] = []

    with _connect() as conn:
        rows = []
        if catalog_medicine_id is not None:
            rows = conn.execute(
                """
                SELECT medicine_id, section_key, section_text, source
                FROM label_sections
                WHERE medicine_id = ?
                LIMIT 40
                """,
                (int(catalog_medicine_id),),
            ).fetchall()
        if not rows and medicine_name:
            like = f"%{(medicine_name or '')[:40]}%"
            med = conn.execute(
                """
                SELECT id FROM medicines
                WHERE lower(canonical_name) LIKE lower(?)
                LIMIT 1
                """,
                (like,),
            ).fetchone()
            if med:
                rows = conn.execute(
                    """
                    SELECT medicine_id, section_key, section_text, source
                    FROM label_sections
                    WHERE medicine_id = ?
                    LIMIT 40
                    """,
                    (int(med["id"]),),
                ).fetchall()

        scored: list[tuple[float, Any]] = []
        for row in rows:
            text = row["section_text"] or ""
            if len(text) < 40:
                continue
            tokens = _tokenize(text)
            overlap = len(q_tokens & tokens) if q_tokens else 1
            density = overlap / max(len(q_tokens), 1)
            scored.append((density + min(len(text), 800) / 8000.0, row))
        scored.sort(key=lambda x: -x[0])
        for score, row in scored[:top_k]:
            text = (row["section_text"] or "").strip()
            excerpts.append(
                {
                    "rank": len(excerpts) + 1,
                    "section_key": row["section_key"],
                    "source": row["source"] or "FDA_SPL",
                    "score": round(float(score), 4),
                    "excerpt": text[:600],
                    "medicine_id": row["medicine_id"],
                }
            )

    return {
        "enabled": True,
        "status": "ok" if excerpts else "empty",
        "method": "catalog_label_sections_keyword",
        "query": query,
        "excerpts": excerpts,
        "evidence_sufficiency": "sufficient" if excerpts else "insufficient",
        "evidence_message": None if excerpts else INSUFFICIENT_EVIDENCE_MESSAGE,
        "faiss_note": (
            "Academic Spec used FAISS IndexFlatL2; this build retrieves the same "
            "SPL/catalog sections with deterministic keyword ranking (FAISS optional later)."
        ),
        "disclaimer": DISCLAIMER if excerpts else INSUFFICIENT_EVIDENCE_MESSAGE,
    }


def maybe_groq_summarise(excerpts: list[dict[str, Any]], *, medicine_name: str) -> dict[str, Any]:
    """Optional Groq LLM summary grounded only on retrieved excerpts (Spec O4)."""
    from app.core.config import settings

    if not getattr(settings, "ENABLE_SPEC_GROQ", False):
        return {
            "enabled": False,
            "status": "disabled",
            "summary": None,
            "note": "Set ENABLE_SPEC_GROQ=true and GROQ_API_KEY to enable.",
        }
    api_key = (getattr(settings, "GROQ_API_KEY", None) or "").strip()
    if not api_key:
        return {"enabled": True, "status": "missing_api_key", "summary": None, "note": "GROQ_API_KEY empty"}
    if not excerpts:
        return {
            "enabled": True,
            "status": "no_excerpts",
            "summary": None,
            "note": INSUFFICIENT_EVIDENCE_MESSAGE,
            "evidence_message": INSUFFICIENT_EVIDENCE_MESSAGE,
        }

    joined = "\n\n".join(
        f"[{e.get('source')}/{e.get('section_key')}]\n{e.get('excerpt')}" for e in excerpts[:5]
    )
    prompt = (
        f"You are assisting a pharmacist research prototype. Summarise ONLY the following "
        f"label excerpts for '{medicine_name}'. Do not invent doses, diagnoses, or advice "
        f"beyond the excerpts. If insufficient, say so.\n\n{joined}"
    )
    try:
        import json
        import urllib.request

        body = json.dumps(
            {
                "model": getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
                "temperature": 0.0,
                "messages": [
                    {"role": "system", "content": "Grounded summariser. No clinical prescribing."},
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
        summary = data["choices"][0]["message"]["content"]
        return {
            "enabled": True,
            "status": "ok",
            "summary": summary,
            "model": getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile"),
            "temperature": 0.0,
            "disclaimer": DISCLAIMER,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq summarise failed: %s", exc)
        return {"enabled": True, "status": "error", "summary": None, "note": str(exc)}
