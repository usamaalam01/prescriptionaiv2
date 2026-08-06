"""Metric availability states for research evaluation dashboards."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class MetricAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_CALCULATED = "NOT_CALCULATED"
    INSUFFICIENT_GROUND_TRUTH = "INSUFFICIENT_GROUND_TRUTH"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class DqReadiness(StrEnum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    IMPLEMENTED_NOT_EVALUATED = "IMPLEMENTED_NOT_EVALUATED"
    EVALUATION_IN_PROGRESS = "EVALUATION_IN_PROGRESS"
    EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"


# U12 — approved B3 quantitative acceptance targets (Spec Design Report, B3 / B4 p.2).
# direction "max" = value must be >= target; "min" = value must be <= target (error rates).
ACCEPTANCE_TARGETS: dict[str, dict[str, Any]] = {
    "wer": {"target": 0.15, "direction": "min", "label": "WER < 15%"},
    "cer": {"target": 0.10, "direction": "min", "label": "CER < 10%"},
    "precision_at_3": {"target": 0.70, "direction": "max", "label": "Precision@3 >= 0.70"},
    "recall_at_3": {"target": 0.60, "direction": "max", "label": "Recall@3 >= 0.60"},
    "bertscore_f1": {"target": 0.80, "direction": "max", "label": "BERTScore F1 >= 0.80"},
}


def evaluate_target(metric_key: str, value: Any) -> dict[str, Any] | None:
    """Return {target, direction, label, pass} for a B3-tracked metric, or None.

    ``pass`` is True/False only when a numeric value is supplied; None otherwise
    (metric not yet available). Unknown metric keys return None (no target).
    """
    spec = ACCEPTANCE_TARGETS.get(metric_key)
    if spec is None:
        return None
    passed: bool | None = None
    if isinstance(value, (int, float)):
        passed = value <= spec["target"] if spec["direction"] == "min" else value >= spec["target"]
    return {
        "target": spec["target"],
        "direction": spec["direction"],
        "label": spec["label"],
        "pass": passed,
    }


def metric_envelope(
    *,
    name: str,
    value: Any = None,
    availability: MetricAvailability | str = MetricAvailability.NOT_CALCULATED,
    note: str | None = None,
    target_key: str | None = None,
) -> dict[str, Any]:
    avail = availability.value if isinstance(availability, MetricAvailability) else str(availability)
    surfaced = value if avail == MetricAvailability.AVAILABLE.value else None
    env = {
        "metric": name,
        "value": surfaced,
        "availability": avail,
        "note": note,
    }
    # U12: attach the B3 acceptance target + pass/fail when this metric is tracked.
    # Pass/fail is evaluated only on a surfaced (AVAILABLE) numeric value.
    tgt = evaluate_target(target_key or name, surfaced)
    if tgt is not None:
        env["acceptance"] = tgt
    return env


def claim_143_or_10_status(*, prescription_count: int, pharmacist_count: int) -> dict[str, Any]:
    """Spec proposes 25–30 Rx and n=5 pharmacists. 143/10 only if evidence complete."""
    ok_143 = prescription_count >= 143
    ok_10 = pharmacist_count >= 10
    if ok_143 and ok_10:
        return {
            "claim_143_prescriptions": MetricAvailability.AVAILABLE.value,
            "claim_10_pharmacists": MetricAvailability.AVAILABLE.value,
            "note": "Counts derived from stored evaluation cases / survey responses.",
            "prescription_count": prescription_count,
            "pharmacist_count": pharmacist_count,
        }
    return {
        "claim_143_prescriptions": MetricAvailability.NOT_VERIFIABLE.value,
        "claim_10_pharmacists": MetricAvailability.NOT_VERIFIABLE.value,
        "display": "Not verifiable — evaluation evidence incomplete",
        "prescription_count": prescription_count,
        "pharmacist_count": pharmacist_count,
        "spec_planned": {"prescriptions": "25-30", "pharmacists": 5},
    }
