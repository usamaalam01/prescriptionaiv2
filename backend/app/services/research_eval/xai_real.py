"""U10 — real SHAP + LIME over the additive Evidence Match Score.

The therapeutic Evidence Match Score is a *linear/additive* model:
    score = baseline + sum_i (w_i * x_i)
For such a model the exact per-feature attribution is analytically `w_i * x_i`
(already computed by `xai_conditions.explain_additive_score`). U10 additionally
runs the **spec-named libraries** (`shap`, `lime`) over the same scoring function
and *reconciles* the library SHAP values against that exact attribution — turning
"spec named these libs but the app used a bespoke method" into "spec-named libs
used AND verified against the exact result".

Feature-gated (`ENABLE_SPEC_SHAP` / `ENABLE_SPEC_LIME`) with graceful fallback to
the analytical method, so the app runs identically when the libraries are absent.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from app.core.config import settings
from app.services.research_eval.xai_conditions import explain_additive_score

logger = logging.getLogger(__name__)


def _score_fn(weights: dict[str, float], keys: list[str], baseline: float) -> Callable:
    """Return f(X: ndarray[n, d]) -> ndarray[n] for the additive score (numpy-typed)."""
    import numpy as np

    w = np.array([float(weights[k]) for k in keys], dtype="float64")

    def f(X):
        X = np.asarray(X, dtype="float64").reshape(-1, len(keys))
        return baseline + X @ w

    return f


def _real_shap(
    feature_values: dict[str, float], weights: dict[str, float], baseline: float
) -> dict[str, Any] | None:
    """Library SHAP over the additive score. None if unavailable/failed."""
    if not settings.ENABLE_SPEC_SHAP:
        return None
    try:
        import numpy as np
        import shap

        keys = list(weights.keys())
        x = np.array([[float(feature_values.get(k, 0.0)) for k in keys]], dtype="float64")
        f = _score_fn(weights, keys, baseline)
        # Exact for a linear model: background = the zero vector (baseline reference).
        background = np.zeros((1, len(keys)), dtype="float64")
        explainer = shap.Explainer(f, background)
        sv = explainer(x)
        values = [float(v) for v in np.asarray(sv.values).reshape(-1)]
        base = float(np.asarray(sv.base_values).reshape(-1)[0])
        return {
            "library": f"shap=={getattr(shap, '__version__', '?')}",
            "base_value": base,
            "feature_values": {k: values[i] for i, k in enumerate(keys)},
            "method": "shap.Explainer(additive_score_fn)",
        }
    except Exception as exc:  # noqa: BLE001 - never fail a request on XAI
        logger.warning("Real SHAP unavailable (%s); analytical fallback used.", exc)
        return None


def _real_lime(
    feature_values: dict[str, float], weights: dict[str, float], baseline: float
) -> dict[str, Any] | None:
    """Library LIME (tabular) over the additive score. None if unavailable/failed."""
    if not settings.ENABLE_SPEC_LIME:
        return None
    try:
        import numpy as np
        from lime.lime_tabular import LimeTabularExplainer

        keys = list(weights.keys())
        x = np.array([float(feature_values.get(k, 0.0)) for k in keys], dtype="float64")
        f = _score_fn(weights, keys, baseline)
        # Deterministic training distribution around plausible [0,1] feature values.
        rng = np.random.RandomState(42)
        train = rng.uniform(0.0, 1.0, size=(200, len(keys)))
        explainer = LimeTabularExplainer(
            training_data=train,
            feature_names=keys,
            mode="regression",
            discretize_continuous=False,
            random_state=42,
        )
        exp = explainer.explain_instance(
            x, lambda X: f(X), num_features=len(keys), num_samples=500
        )
        local = dict(exp.as_list())
        # LIME keys back to feature names (discretize off → names are exact).
        weights_by_key = {k: float(local.get(k, 0.0)) for k in keys}
        return {
            "library": "lime==0.2.0.1",
            "local_feature_weights": weights_by_key,
            "intercept": float(exp.intercept[1] if isinstance(exp.intercept, dict) else exp.intercept),
            "method": "lime.lime_tabular over additive_score_fn (regression)",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Real LIME unavailable (%s); analytical fallback used.", exc)
        return None


def _reconcile(analytical: dict[str, float], shap_block: dict[str, Any] | None) -> dict[str, Any]:
    """Compare library SHAP against the exact analytical w_i*x_i attribution."""
    if not shap_block:
        return {"status": "not_computed", "note": "Real SHAP not enabled/available."}
    lib = shap_block["feature_values"]
    residuals = {k: abs(float(analytical.get(k, 0.0)) - float(lib.get(k, 0.0))) for k in analytical}
    max_res = max(residuals.values()) if residuals else 0.0
    tol = 1e-6
    return {
        "status": "reconciled" if max_res <= tol else "divergent",
        "max_abs_residual": max_res,
        "tolerance": tol,
        "note": (
            "Library SHAP values match the exact analytical additive attribution "
            "(w_i * x_i) within tolerance — as required for a linear score."
            if max_res <= tol
            else "Library SHAP diverges from the exact additive attribution; investigate."
        ),
    }


def explain_candidate_xai(
    *,
    feature_values: dict[str, float],
    weights: dict[str, float],
    baseline: float = 0.0,
) -> dict[str, Any]:
    """Full XAI payload: exact analytical attribution + (optional) real SHAP/LIME + reconciliation.

    Always returns the analytical block (so the dashboard has data even with the
    libraries off). ``real_shap`` / ``real_lime`` are populated only when their
    flags are on and the libraries import; ``reconciliation`` reports whether the
    library SHAP matches the exact attribution.
    """
    analytical = explain_additive_score(
        feature_values=feature_values, weights=weights, baseline=baseline
    )
    exact_contrib = analytical["shap"]["feature_contributions"]

    shap_block = _real_shap(feature_values, weights, baseline)
    lime_block = _real_lime(feature_values, weights, baseline)

    return {
        "score": analytical["score"],
        "baseline": baseline,
        # Exact additive attribution — always present, ground truth for the bars.
        "analytical_shap": exact_contrib,
        "analytical_lime": analytical["lime"]["local_feature_weights"],
        # Spec-named libraries (None when disabled/unavailable).
        "real_shap": shap_block,
        "real_lime": lime_block,
        "reconciliation": _reconcile(exact_contrib, shap_block),
        "flags": {
            "shap_enabled": settings.ENABLE_SPEC_SHAP,
            "lime_enabled": settings.ENABLE_SPEC_LIME,
            "shap_computed": shap_block is not None,
            "lime_computed": lime_block is not None,
        },
        "disclaimer": (
            "SHAP/LIME explain the rule-based Evidence Match Score, not clinical "
            "correctness or therapeutic equivalence. Pharmacist verification required."
        ),
        "explanation_version": "u10-1.0.0",
    }
