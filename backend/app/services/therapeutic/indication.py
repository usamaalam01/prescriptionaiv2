"""Indication and mechanism normalization helpers."""

from __future__ import annotations

from app.services.therapeutic.identity import normalize_name


CONDITION_ALIASES = {
    "bacterial infection": {"bacterial infection", "infection", "susceptible bacterial infection"},
    "pain": {"pain", "mild to moderate pain", "analgesia", "minor aches and pains", "aches and pains"},
    "inflammation": {"inflammation", "anti-inflammatory"},
    "fever": {"fever", "pyrexia"},
    "asthma": {"asthma", "bronchospasm", "reversible airways obstruction", "reversible obstructive airway disease"},
    "allergic rhinitis": {
        "allergic rhinitis",
        "hay fever",
        "upper respiratory allergies",
        "runny nose",
        "sneezing",
        "itchy watery eyes",
        "watery eyes",
        "itching of the nose or throat",
        "itching of the nose",
    },
    "urticaria": {"urticaria", "hives", "chronic idiopathic urticaria"},
    "gastroesophageal reflux disease": {
        "gastroesophageal reflux disease",
        "gerd",
        "acid reflux",
        "reflux",
        "heartburn",
        "erosive esophagitis",
        "reflux oesophagitis",
    },
    "duodenal ulcer": {"duodenal ulcer", "peptic ulcer"},
    "gastric ulcer": {"gastric ulcer", "stomach ulcer"},
    # Psych / neurology (HITL catalog indications)
    "schizophrenia": {"schizophrenia"},
    "bipolar disorder": {
        "bipolar disorder",
        "bipolar i disorder",
        "bipolar i",
        "manic and mixed episodes",
        "manic episodes",
    },
    "major depressive disorder": {
        "major depressive disorder",
        "depression",
        "adjunctive treatment of major depressive disorder",
    },
    "autistic disorder": {
        "autistic disorder",
        "autism",
        "irritability associated with autistic disorder",
    },
    "tourette disorder": {
        "tourette disorder",
        "tourette's disorder",
        "tourette",
    },
    "parkinsonism": {
        "parkinsonism",
        "parkinson's disease",
        "parkinson disease",
        "all forms of parkinsonism",
    },
    "extrapyramidal disorders": {
        "extrapyramidal disorders",
        "extrapyramidal symptoms",
        "drug-induced extrapyramidal disorders",
        "drug-induced extrapyramidal symptoms",
        "neuroleptic-induced extrapyramidal disorders",
    },
}


def normalize_indication_text(text: str | None, *, source_record_id: str = "", source_section: str = "") -> dict:
    raw = (text or "").strip()
    lowered = normalize_name(raw)
    condition = ""
    # Prefer longest alias match so "hay fever" does not collapse to "fever"
    best_len = -1
    for canonical, aliases in CONDITION_ALIASES.items():
        for alias in aliases | {canonical}:
            a = normalize_name(alias)
            if not a:
                continue
            hit = lowered == a or f" {a} " in f" {lowered} " or lowered.startswith(a + " ") or lowered.endswith(" " + a)
            if hit and len(a) > best_len:
                condition = canonical
                best_len = len(a)
    if not condition and lowered:
        condition = lowered

    intent = "treatment"
    if "prevent" in lowered:
        intent = "prevention"
    elif condition in {"pain", "fever", "inflammation", "allergic rhinitis", "urticaria"}:
        intent = "symptom_control"
    elif condition in {"asthma"}:
        intent = "symptom_control"

    return {
        "condition": condition,
        "intent": intent,
        "population": "adult",
        "disease_stage": "",
        "combination_requirement": "",
        "source_record_id": source_record_id,
        "source_section": source_section or "indications_and_usage",
        "raw_text": raw,
    }


def indications_overlap(source_condition: str, candidate_indications: list[str]) -> bool:
    src = normalize_name(source_condition)
    if not src:
        return False
    for group, aliases in CONDITION_ALIASES.items():
        if src == group or src in aliases:
            for cand in candidate_indications:
                c = normalize_name(cand)
                if c == group or c in aliases or group in c or c in aliases:
                    return True
    for cand in candidate_indications:
        if src and (src in normalize_name(cand) or normalize_name(cand) in src):
            return True
    return False


def normalize_mechanism(mech: dict | str | None, *, source_record_id: str = "", source_field: str = "") -> dict:
    if isinstance(mech, dict):
        return {
            "action": mech.get("action") or "",
            "target": mech.get("target") or "",
            "pathway": mech.get("pathway") or "",
            "physiological_effect": mech.get("physiological_effect") or "",
            "source_record_id": source_record_id,
            "source_field": source_field or "mechanism_of_action",
        }
    text = str(mech or "")
    return {
        "action": "",
        "target": "",
        "pathway": "",
        "physiological_effect": text,
        "source_record_id": source_record_id,
        "source_field": source_field or "mechanism_of_action",
    }


def mechanism_related(a: dict, b: dict) -> bool:
    for key in ("target", "pathway", "physiological_effect", "action"):
        av = normalize_name(a.get(key))
        bv = normalize_name(b.get(key))
        if av and bv and (av == bv or av in bv or bv in av):
            return True
    return False
