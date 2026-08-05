"""Spec O5 — interpretability for the alternatives Evidence Match scorer.

Uses local linear feature attribution (LIME-style). Optional SHAP if installed
and ENABLE_SPEC_SHAP=true. Explains ranking features — not clinical correctness.
"""

from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "Research interpretability only. Feature contributions explain the Evidence Match "
    "score components, not therapeutic correctness, safety, or interchangeability."
)


def explain_score_features(
    *,
    evidence_match: dict[str, Any] | None,
    mcs: dict[str, Any] | None = None,
    mcs_points: int = 0,
) -> dict[str, Any]:
    """Build a LIME-like attribution over scored components."""
    components = list((evidence_match or {}).get("components") or [])
    features: list[dict[str, Any]] = []
    for c in components:
        features.append(
            {
                "feature": c.get("component"),
                "weight": c.get("weight"),
                "awarded": c.get("awarded"),
                "status": c.get("status"),
                "contribution": float(c.get("awarded") or 0),
                "explanation": c.get("explanation"),
            }
        )

    if mcs and mcs.get("status") == "ok":
        features.append(
            {
                "feature": "molecular_similarity_mcs",
                "weight": 15,
                "awarded": mcs_points,
                "status": "matched" if mcs_points else "unmatched",
                "contribution": float(mcs_points),
                "explanation": (
                    f"RDKit MCS atom coverage={mcs.get('atom_coverage')} "
                    f"(Spec O3 structural similarity bonus)."
                ),
            }
        )

    features_sorted = sorted(features, key=lambda f: -abs(float(f["contribution"])))
    total = sum(float(f["contribution"]) for f in features_sorted)

    shap_block = _optional_shap(features_sorted)

    return {
        "method": "local_linear_feature_attribution",
        "lime_style": True,
        "shap": shap_block,
        "features": features_sorted,
        "total_explained": total,
        "top_positive": [f for f in features_sorted if f["contribution"] > 0][:5],
        "disclaimer": DISCLAIMER,
        "note": "Does not explain OCR models or patient-specific dosing.",
    }


def _optional_shap(features: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from app.core.config import settings

        if not getattr(settings, "ENABLE_SPEC_SHAP", False):
            return {
                "enabled": False,
                "status": "disabled",
                "note": "Set ENABLE_SPEC_SHAP=true to attempt SHAP (requires shap+sklearn).",
            }
    except Exception:
        return {"enabled": False, "status": "no_settings"}

    try:
        import numpy as np
        import shap
        from sklearn.linear_model import Ridge

        # Tiny surrogate: features -> sum(awarded); SHAP on one instance
        names = [str(f["feature"]) for f in features]
        x = np.array([[float(f["contribution"]) for f in features]], dtype=float)
        # Train on identity-like neighbourhood
        rng = np.random.default_rng(0)
        X = np.clip(x + rng.normal(0, 0.5, size=(64, x.shape[1])), 0, None)
        y = X.sum(axis=1)
        model = Ridge(alpha=1.0).fit(X, y)
        explainer = shap.Explainer(model.predict, X)
        sv = explainer(x)
        values = sv.values[0].tolist() if hasattr(sv, "values") else list(sv[0])
        return {
            "enabled": True,
            "status": "ok",
            "feature_names": names,
            "shap_values": [round(float(v), 4) for v in values],
            "note": "Surrogate Ridge+SHAP over Evidence Match component awards.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "status": "unavailable",
            "note": f"SHAP optional path failed ({exc}); LIME-style attribution still provided.",
        }
