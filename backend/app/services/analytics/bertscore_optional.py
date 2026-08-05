"""Optional BERTScore for free-text analytics (feature-flagged)."""

from __future__ import annotations

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL_CACHE: dict = {"scorer": None, "failed": False}


def bertscore_status() -> str:
    """Human-readable status for analytics UI."""
    if not settings.ENABLE_BERTSCORE:
        return "disabled"
    if _MODEL_CACHE["failed"]:
        return "failed"
    try:
        import bert_score  # noqa: F401

        return "ready"
    except Exception:  # noqa: BLE001
        return "package_missing"


def bertscore_available() -> bool:
    return bertscore_status() == "ready"


@lru_cache(maxsize=1)
def _get_scorer():
    from bert_score import BERTScorer

    # DistilBERT keeps first-load and CPU inference lighter than roberta-large.
    # Baseline rescale is not available for this model_type — raw BertScore is fine.
    return BERTScorer(
        model_type="distilbert-base-uncased",
        lang="en",
        rescale_with_baseline=False,
        device="cpu",
    )


def score_pairs(hypotheses: list[str], references: list[str]) -> list[dict] | None:
    """Return list of {precision, recall, f1} or None if unavailable."""
    if not settings.ENABLE_BERTSCORE:
        return None
    if not hypotheses or not references or len(hypotheses) != len(references):
        return None
    if any(not (h or "").strip() or not (r or "").strip() for h, r in zip(hypotheses, references)):
        # Skip empty pairs — caller should filter
        pass
    try:
        scorer = _get_scorer()
        P, R, F1 = scorer.score(hypotheses, references)
        out = []
        for i in range(len(hypotheses)):
            out.append(
                {
                    "precision": round(float(P[i].item()), 4),
                    "recall": round(float(R[i].item()), 4),
                    "f1": round(float(F1[i].item()), 4),
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("BERTScore unavailable: %s", exc)
        _MODEL_CACHE["failed"] = True
        return None
