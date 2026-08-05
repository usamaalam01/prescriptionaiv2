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


def metric_envelope(
    *,
    name: str,
    value: Any = None,
    availability: MetricAvailability | str = MetricAvailability.NOT_CALCULATED,
    note: str | None = None,
) -> dict[str, Any]:
    avail = availability.value if isinstance(availability, MetricAvailability) else str(availability)
    return {
        "metric": name,
        "value": value if avail == MetricAvailability.AVAILABLE.value else None,
        "availability": avail,
        "note": note,
    }


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
