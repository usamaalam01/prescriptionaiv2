"""DQ4 controlled explanation conditions and additive SHAP/LIME for scoring functions."""

from __future__ import annotations

import random
from typing import Any


CONDITION_A = "A"  # Minimal — score only
CONDITION_B = "B"  # XAI
CONDITION_C = "C"  # XAI + provenance


def explain_additive_score(
    *,
    feature_values: dict[str, float],
    weights: dict[str, float],
    baseline: float = 0.0,
) -> dict[str, Any]:
    """
    Model-consistent SHAP for a linear/additive score:
      score = baseline + sum(w_i * x_i)
    SHAP value for feature i is w_i * x_i (baseline attribution separate).
    LIME: local linear fit via random perturbations of the same scoring function.
    """
    contrib = {k: float(weights.get(k, 0.0)) * float(feature_values.get(k, 0.0)) for k in weights}
    score = baseline + sum(contrib.values())
    shap = {
        "baseline": baseline,
        "feature_contributions": contrib,
        "reconciled_score": score,
        "method": "analytical_additive_shap",
        "limitation": (
            "SHAP values are exact for the additive weighted scoring function used in research; "
            "they do not explain clinical correctness."
        ),
    }
    lime = _lime_perturb(feature_values, weights, baseline)
    return {
        "score": score,
        "shap": shap,
        "lime": lime,
        "component_breakdown": contrib,
        "explanation_version": "1.0.0",
    }


def _lime_perturb(
    feature_values: dict[str, float],
    weights: dict[str, float],
    baseline: float,
    n: int = 40,
    seed: int = 42,
) -> dict[str, Any]:
    rng = random.Random(seed)
    keys = list(weights.keys())
    X: list[list[float]] = []
    y: list[float] = []
    for _ in range(n):
        row = []
        for k in keys:
            v = float(feature_values.get(k, 0.0))
            row.append(v + rng.uniform(-0.15, 0.15))
        X.append(row)
        y.append(baseline + sum(weights[k] * row[i] for i, k in enumerate(keys)))
    # Closed-form least squares for linear model without intercept (approx local weights)
    # Use simple correlation of each feature with y as LIME-style importance.
    importances: dict[str, float] = {}
    for i, k in enumerate(keys):
        xs = [r[i] for r in X]
        mean_x = sum(xs) / len(xs)
        mean_y = sum(y) / len(y)
        num = sum((xs[j] - mean_x) * (y[j] - mean_y) for j in range(len(y)))
        den = sum((xs[j] - mean_x) ** 2 for j in range(len(xs))) or 1.0
        importances[k] = num / den
    return {
        "local_feature_weights": importances,
        "n_perturbations": n,
        "seed": seed,
        "method": "perturbation_lime_on_scoring_fn",
        "limitation": (
            "LIME approximates the scoring function locally; not a substitute for clinical judgement."
        ),
    }


def build_condition_payload(
    *,
    condition: str,
    candidate: dict[str, Any],
    score: float,
    xai: dict[str, Any] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = {
        "condition": condition,
        "candidate": {
            "name": candidate.get("name"),
            "candidate_type": candidate.get("candidate_type"),
        },
        "disclaimer": (
            "PharmaAssist is decision support only. The pharmacist remains the final decision-maker."
        ),
    }
    if condition == CONDITION_A:
        return {**base, "final_score": score}
    if condition == CONDITION_B:
        return {
            **base,
            "final_score": score,
            "shap": (xai or {}).get("shap"),
            "lime": (xai or {}).get("lime"),
            "component_score_breakdown": (xai or {}).get("component_breakdown"),
        }
    # Condition C
    return {
        **base,
        "final_score": score,
        "shap": (xai or {}).get("shap"),
        "lime": (xai or {}).get("lime"),
        "component_score_breakdown": (xai or {}).get("component_breakdown"),
        "provenance": provenance or {},
        "evidence_limitations": (
            "Source attribution does not establish therapeutic equivalence. "
            "Structural similarity is supporting evidence only."
        ),
    }


def counterbalance_order(participant_seed: str) -> list[str]:
    order = [CONDITION_A, CONDITION_B, CONDITION_C]
    rng = random.Random(hash(participant_seed) & 0xFFFFFFFF)
    rng.shuffle(order)
    return order
