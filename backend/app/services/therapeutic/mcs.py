"""RDKit Maximum Common Substructure (MCS) for Spec objective O3.

Runs only in the therapeutic-alternatives path (after HITL Confirm).
Never auto-substitutes medicines. Optional — disabled when RDKit/SMILES missing.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.therapeutic.smiles_catalog import resolve_smiles_catalog

logger = logging.getLogger(__name__)


def rdkit_available() -> bool:
    try:
        from rdkit import Chem  # noqa: F401

        return True
    except Exception:
        return False


def resolve_smiles(*, drugbank_id: str | None, name: str | None) -> str | None:
    # Catalogue-backed (DrugBank structures) with the curated seed as fallback.
    return resolve_smiles_catalog(drugbank_id=drugbank_id, name=name)


def compute_mcs_similarity(
    *,
    source_drugbank_id: str | None,
    source_name: str | None,
    candidate_drugbank_id: str | None,
    candidate_name: str | None,
) -> dict[str, Any]:
    """Return MCS atom-coverage style metrics for ranking support.

    Spec referenced ~90% atom coverage as a strong structural match threshold.
    """
    base = {
        "enabled": True,
        "status": "unavailable",
        "method": "RDKit_MCS",
        "source_smiles_found": False,
        "candidate_smiles_found": False,
        "atom_coverage": None,
        "bond_coverage": None,
        "mcs_smarts": None,
        "meets_spec_threshold_0_9": None,
        "note": "",
    }

    try:
        from app.core.config import settings

        if not getattr(settings, "ENABLE_SPEC_MCS", True):
            base["enabled"] = False
            base["status"] = "disabled"
            base["note"] = "ENABLE_SPEC_MCS=false"
            return base
    except Exception:
        pass

    if not rdkit_available():
        base["note"] = "RDKit not installed — MCS skipped (pip install rdkit)."
        return base

    from rdkit import Chem
    from rdkit.Chem import rdFMCS

    s_smiles = resolve_smiles(drugbank_id=source_drugbank_id, name=source_name)
    c_smiles = resolve_smiles(drugbank_id=candidate_drugbank_id, name=candidate_name)
    base["source_smiles_found"] = bool(s_smiles)
    base["candidate_smiles_found"] = bool(c_smiles)

    if not s_smiles or not c_smiles:
        base["status"] = "no_smiles"
        base["note"] = (
            "SMILES not in seed cache for source and/or candidate. "
            "MCS applies to the seeded DrugBank subset (Spec O3 demo path)."
        )
        return base

    mol_a = Chem.MolFromSmiles(s_smiles)
    mol_b = Chem.MolFromSmiles(c_smiles)
    if mol_a is None or mol_b is None:
        base["status"] = "invalid_smiles"
        base["note"] = "Could not parse SMILES with RDKit."
        return base

    try:
        res = rdFMCS.FindMCS(
            [mol_a, mol_b],
            timeout=8,
            matchValences=True,
            ringMatchesRingOnly=True,
            completeRingsOnly=False,
        )
        if res.canceled or res.numAtoms < 1:
            base["status"] = "no_mcs"
            base["note"] = "No meaningful MCS found."
            return base

        atom_cov = res.numAtoms / max(mol_a.GetNumAtoms(), mol_b.GetNumAtoms())
        bond_cov = res.numBonds / max(mol_a.GetNumBonds(), mol_b.GetNumBonds(), 1)
        base.update(
            {
                "status": "ok",
                "atom_coverage": round(float(atom_cov), 4),
                "bond_coverage": round(float(bond_cov), 4),
                "mcs_smarts": res.smartsString,
                "meets_spec_threshold_0_9": bool(atom_cov >= 0.9),
                "note": (
                    "Structural similarity only — not therapeutic interchangeability. "
                    "Pharmacist review required."
                ),
            }
        )
        return base
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCS failed: %s", exc)
        base["status"] = "error"
        base["note"] = f"MCS error: {exc}"
        return base


def mcs_score_points(mcs: dict[str, Any], *, max_points: int = 15) -> int:
    """Map atom coverage to Evidence Match bonus points (0..max_points)."""
    if mcs.get("status") != "ok" or mcs.get("atom_coverage") is None:
        return 0
    cov = float(mcs["atom_coverage"])
    return int(round(max(0.0, min(1.0, cov)) * max_points))
