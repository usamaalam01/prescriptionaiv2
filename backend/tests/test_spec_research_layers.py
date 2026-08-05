"""Tests for Spec O3–O5 research layers (MCS / RAG / XAI)."""

from __future__ import annotations

from app.services.therapeutic.feature_xai import explain_score_features
from app.services.therapeutic.mcs import compute_mcs_similarity, mcs_score_points, rdkit_available
from app.services.therapeutic.smiles_seed import lookup_smiles


def test_smiles_seed_ibuprofen():
    assert lookup_smiles(name="Ibuprofen")
    assert lookup_smiles(drugbank_id="DB01050")


def test_mcs_between_nsaids_or_graceful():
    mcs = compute_mcs_similarity(
        source_drugbank_id="DB01050",
        source_name="ibuprofen",
        candidate_drugbank_id="DB00788",
        candidate_name="naproxen",
    )
    assert mcs["method"] == "RDKit_MCS"
    if not rdkit_available():
        assert mcs["status"] == "unavailable"
        assert mcs_score_points(mcs) == 0
    else:
        assert mcs["status"] in {"ok", "no_mcs", "error"}
        if mcs["status"] == "ok":
            assert mcs["atom_coverage"] is not None
            assert 0 <= mcs_score_points(mcs) <= 15


def test_mcs_missing_smiles():
    mcs = compute_mcs_similarity(
        source_drugbank_id=None,
        source_name="unknown-molecule-xyz",
        candidate_drugbank_id=None,
        candidate_name="also-unknown",
    )
    assert mcs["status"] in {"no_smiles", "unavailable", "disabled"}


def test_feature_attribution_includes_mcs_bonus():
    evidence = {
        "components": [
            {
                "component": "indication_relationship",
                "weight": 35,
                "awarded": 35,
                "status": "matched",
                "explanation": "overlap",
            }
        ]
    }
    mcs = {"status": "ok", "atom_coverage": 0.5}
    out = explain_score_features(evidence_match=evidence, mcs=mcs, mcs_points=8)
    assert out["lime_style"] is True
    names = [f["feature"] for f in out["features"]]
    assert "indication_relationship" in names
    assert "molecular_similarity_mcs" in names
    assert out["disclaimer"]
