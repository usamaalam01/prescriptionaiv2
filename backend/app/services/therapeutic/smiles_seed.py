"""Seed SMILES for Spec O3 RDKit MCS (public DrugBank structures).

Used when RDKit is installed. Decision-support only — not clinical equivalence.
"""

from __future__ import annotations

# drugbank_id -> canonical SMILES (subset for demos + common NSAID/GI/allergy set)
BY_DRUGBANK_ID: dict[str, str] = {
    "DB01050": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # ibuprofen
    "DB00788": "COc1ccc2cc([C@H](C)C(=O)O)ccc2c1",  # naproxen
    "DB00586": "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl",  # diclofenac
    "DB00945": "CC(=O)Oc1ccccc1C(=O)O",  # aspirin
    "DB00316": "CC(=O)Nc1ccc(O)cc1",  # acetaminophen / paracetamol
    "DB01060": "CC1(C)S[C@@H]2[C@H](NC(=O)[C@H](N)c3ccc(O)cc3)C(=O)N2[C@H]1C(=O)O",  # amoxicillin
    "DB00341": "Clc1ccc(cc1)C(c2ccc(Cl)cc2)N3CCN(CC3)CCOCC(=O)O",  # cetirizine
    "DB00455": "COc1ccc2c(c1)C(=O)N(C)C(=Nc1ccc(Cl)cc1)c1ccccc12",  # loratadine
    "DB00338": "COc1ccc2[nH]c(nc2c1)S(=O)Cc1ncc(C)c(OC)c1C",  # omeprazole
    "DB00213": "COc1cc2[nH]c(nc2cc1OC)S(=O)Cc1ncc(F)c(OC)n1",  # pantoprazole
}

# normalized generic name -> drugbank id
BY_NAME: dict[str, str] = {
    "ibuprofen": "DB01050",
    "naproxen": "DB00788",
    "diclofenac": "DB00586",
    "aspirin": "DB00945",
    "acetylsalicylic acid": "DB00945",
    "acetaminophen": "DB00316",
    "paracetamol": "DB00316",
    "amoxicillin": "DB01060",
    "cetirizine": "DB00341",
    "loratadine": "DB00455",
    "omeprazole": "DB00338",
    "pantoprazole": "DB00213",
}


def normalize_key(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(name.lower().replace("-", " ").split())


def lookup_smiles(*, drugbank_id: str | None = None, name: str | None = None) -> str | None:
    if drugbank_id:
        sid = str(drugbank_id).strip().upper()
        if sid in BY_DRUGBANK_ID:
            return BY_DRUGBANK_ID[sid]
    key = normalize_key(name)
    if key and key in BY_NAME:
        return BY_DRUGBANK_ID.get(BY_NAME[key])
    return None
