"""Optional hybrid consensus over independent OCR engine attempts (R01).

Spec O1/B1 require a sequential TrOCR → Vision → Tesseract fallback chain.
Consensus is optional configuration — not mandated by the signed Spec (no 'consensus' wording).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.ocr.contract import EngineAttempt


def _norm(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[^\w\s%./-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Collapse "500 mg" ↔ "500mg" so Spec/engine formatting noise is not a conflict
    t = re.sub(r"(\d)\s+(mg|mcg|µg|g|ml|iu|units)\b", r"\1\2", t)
    return t


@dataclass
class ConsensusResult:
    selected_value: str
    selected_engine: str
    confidence: float
    consensus_status: str  # agreement | majority | conflict | single | empty
    requires_human_review: bool
    candidates: list[dict[str, Any]]


def page_consensus(attempts: list[EngineAttempt]) -> ConsensusResult:
    """Deterministic page-level consensus from successful engine texts only."""
    candidates = [
        {
            "engine_id": a.engine_id,
            "value": a.raw_text or "",
            "confidence": a.confidence,
            "status": a.status,
        }
        for a in attempts
    ]
    successes = [a for a in attempts if a.status == "success" and (a.raw_text or "").strip()]
    if not successes:
        return ConsensusResult(
            selected_value="",
            selected_engine="",
            confidence=0.0,
            consensus_status="empty",
            requires_human_review=True,
            candidates=candidates,
        )
    if len(successes) == 1:
        a = successes[0]
        return ConsensusResult(
            selected_value=a.raw_text or "",
            selected_engine=a.engine_id,
            confidence=float(a.confidence or 0.0),
            consensus_status="single",
            requires_human_review=float(a.confidence or 0.0) < 0.6,
            candidates=candidates,
        )

    norms = {_norm(a.raw_text or ""): a for a in successes}
    # Group by normalised text
    buckets: dict[str, list[EngineAttempt]] = {}
    for a in successes:
        buckets.setdefault(_norm(a.raw_text or ""), []).append(a)

    best_key = max(buckets.keys(), key=lambda k: (len(buckets[k]), max(float(x.confidence or 0) for x in buckets[k])))
    group = buckets[best_key]
    winner = max(group, key=lambda x: float(x.confidence or 0.0))

    if len(buckets) == 1:
        status = "agreement"
        review = False
    elif len(group) >= 2 and len(group) > len(successes) / 2:
        status = "majority"
        # Material disagreement if other buckets look like different drug/strength tokens
        review = _material_disagreement(list(buckets.keys()))
    else:
        status = "conflict"
        review = True

    return ConsensusResult(
        selected_value=winner.raw_text or "",
        selected_engine=winner.engine_id,
        confidence=float(winner.confidence or 0.0),
        consensus_status=status,
        requires_human_review=review,
        candidates=candidates,
    )


def _material_disagreement(norm_texts: list[str]) -> bool:
    """Flag when normalised page texts diverge on tokens that may be clinically material."""
    if len(norm_texts) < 2:
        return False
    token_sets = [set(t.split()) for t in norm_texts if t]
    if len(token_sets) < 2:
        return False
    base = token_sets[0]
    for other in token_sets[1:]:
        if not base or not other:
            return True
        # Jaccard low → disagreement
        inter = len(base & other)
        union = len(base | other) or 1
        if inter / union < 0.75:
            return True
        # Digit/unit tokens differ
        dig_a = {t for t in base if any(c.isdigit() for c in t)}
        dig_b = {t for t in other if any(c.isdigit() for c in t)}
        if dig_a != dig_b:
            return True
    return False
