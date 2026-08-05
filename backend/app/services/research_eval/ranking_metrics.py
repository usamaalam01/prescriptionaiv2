"""DQ2 ranking metrics: Precision@K, Recall@K."""

from __future__ import annotations

from typing import Any, Iterable


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = [normalise(x) for x in retrieved[:k]]
    rel = {normalise(x) for x in relevant}
    if not top:
        return 0.0
    hits = sum(1 for x in top if x in rel)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Recall@K uses all valid gold candidates as denominator (not only retrieved)."""
    rel = {normalise(x) for x in relevant if normalise(x)}
    if not rel:
        return 0.0
    top = {normalise(x) for x in retrieved[:k]}
    return len(top & rel) / len(rel)


def normalise(s: str) -> str:
    return " ".join(str(s).lower().split())


def aggregate_recommendation_metrics(
    *,
    per_case: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    per_case items: {
      retrieved_ranked: [str],
      gold_valid: [str],
      gold_invalid_count: int,
      accepted_count: int,
      rejection_reasons: [str],
    }
    """
    if not per_case:
        return {
            "precision_at_1": None,
            "precision_at_3": None,
            "recall_at_3": None,
            "invalid_candidate_rate": None,
            "pharmacist_acceptance_rate": None,
            "n_cases": 0,
        }
    p1, p3, r3 = [], [], []
    invalid_flags = []
    accept_rates = []
    reason_counts: dict[str, int] = {}
    for row in per_case:
        gold = set(row.get("gold_valid") or [])
        retrieved = list(row.get("retrieved_ranked") or [])
        p1.append(precision_at_k(retrieved, gold, 1))
        p3.append(precision_at_k(retrieved, gold, 3))
        r3.append(recall_at_k(retrieved, gold, 3))
        inv = int(row.get("gold_invalid_count") or 0)
        tot = len(gold) + inv
        invalid_flags.append(inv / tot if tot else 0.0)
        acc = int(row.get("accepted_count") or 0)
        judged = int(row.get("judged_count") or tot)
        accept_rates.append(acc / judged if judged else 0.0)
        for reason in row.get("rejection_reasons") or []:
            reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1

    def mean(xs: Iterable[float]) -> float:
        xs = list(xs)
        return sum(xs) / len(xs) if xs else 0.0

    return {
        "precision_at_1": mean(p1),
        "precision_at_3": mean(p3),
        "recall_at_3": mean(r3),
        "invalid_candidate_rate": mean(invalid_flags),
        "pharmacist_acceptance_rate": mean(accept_rates),
        "rejection_reason_distribution": reason_counts,
        "n_cases": len(per_case),
    }
