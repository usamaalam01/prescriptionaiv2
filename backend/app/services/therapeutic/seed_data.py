"""DEMO DATA seed: DrugBank / FDA SPL / FDA NDC style records for therapeutic alternatives.

Not a live DrugBank or openFDA integration. Every record is labelled DEMO DATA.
"""

from __future__ import annotations

from copy import deepcopy

DATASET_VERSION = "demo-seed-2026.07"
RULES_ENGINE_VERSION = "ta-rules-v1"
DEMO_LABEL = "DEMO DATA"


def _claim(
    claim_id: str,
    claim: str,
    claim_type: str,
    source_dataset: str,
    source_record_id: str,
    source_field_or_section: str,
    raw_evidence: str,
    *,
    source_reference_ids: list[str] | None = None,
    normalized_evidence: str | None = None,
    demo_data: bool = True,
) -> dict:
    return {
        "claim_id": claim_id,
        "claim": claim,
        "claim_type": claim_type,
        "source_dataset": source_dataset,
        "source_record_id": source_record_id,
        "source_field_or_section": source_field_or_section,
        "source_reference_ids": source_reference_ids or [],
        "raw_evidence": raw_evidence,
        "normalized_evidence": normalized_evidence or raw_evidence,
        "dataset_version": DATASET_VERSION,
        "effective_date": "2026-04-13",
        "retrieved_at": None,
        "demo_data": demo_data,
    }


# Canonical DrugBank-style monographs (synthetic)
DRUGBANK_RECORDS: dict[str, dict] = {
    "DB-SYN-AMOX": {
        "drugbank_id": "DB-SYN-AMOX",
        "generic_name": "Amoxicillin",
        "synonyms": ["Amoxycillin", "Amoxil"],
        "drug_type": "small molecule",
        "description": "Broad-spectrum penicillin antibiotic.",
        "indications": ["bacterial infection", "susceptible respiratory tract infection"],
        "drug_class": "Penicillin antibiotic",
        "atc_classification": "J01CA04",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "penicillin-binding proteins",
            "pathway": "cell wall synthesis",
            "physiological_effect": "bactericidal",
        },
        "pharmacodynamics": "Inhibits bacterial cell wall synthesis.",
        "targets": ["PBP"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["methotrexate", "warfarin"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "26787-78-0",
        "unii": "9EM05410Q9",
        "linked_reference_ids": ["SPL-SYN-AMOX", "NDC-SYN-AMOX-500"],
    },
    "DB-SYN-PEN-V": {
        "drugbank_id": "DB-SYN-PEN-V",
        "generic_name": "Phenoxymethylpenicillin",
        "synonyms": ["Penicillin V", "Pen V"],
        "drug_type": "small molecule",
        "description": "Narrower-spectrum penicillin.",
        "indications": ["bacterial infection", "streptococcal infection"],
        "drug_class": "Penicillin antibiotic",
        "atc_classification": "J01CE02",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "penicillin-binding proteins",
            "pathway": "cell wall synthesis",
            "physiological_effect": "bactericidal",
        },
        "pharmacodynamics": "Inhibits bacterial cell wall synthesis.",
        "targets": ["PBP"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["methotrexate"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "87-08-1",
        "unii": "Z61I075U2W",
        "linked_reference_ids": ["SPL-SYN-PENV"],
    },
    "DB-SYN-DOXY": {
        "drugbank_id": "DB-SYN-DOXY",
        "generic_name": "Doxycycline",
        "synonyms": ["Vibramycin"],
        "drug_type": "small molecule",
        "description": "Tetracycline-class antibiotic.",
        "indications": ["bacterial infection", "respiratory tract infection"],
        "drug_class": "Tetracycline antibiotic",
        "atc_classification": "J01AA02",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "30S ribosomal subunit",
            "pathway": "protein synthesis",
            "physiological_effect": "bacteriostatic",
        },
        "pharmacodynamics": "Inhibits bacterial protein synthesis.",
        "targets": ["30S"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["isotretinoin", "warfarin"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "564-25-0",
        "unii": "33419IH98U",
        "linked_reference_ids": ["SPL-SYN-DOXY"],
        "population_restrictions": ["pregnancy", "children_under_12"],
    },
    "DB-SYN-IBU": {
        "drugbank_id": "DB-SYN-IBU",
        "generic_name": "Ibuprofen",
        "synonyms": ["Ibrufen", "Brufen", "Advil"],
        "drug_type": "small molecule",
        "description": "NSAID analgesic/anti-inflammatory.",
        "indications": ["pain", "inflammation", "fever"],
        "drug_class": "NSAID",
        "atc_classification": "M01AE01",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "COX-1/COX-2",
            "pathway": "prostaglandin synthesis",
            "physiological_effect": "analgesia_anti_inflammatory",
        },
        "pharmacodynamics": "Inhibits cyclooxygenase.",
        "targets": ["COX"],
        "enzymes": ["CYP2C9"],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["warfarin", "lithium", "methotrexate"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "15687-27-1",
        "unii": "WK2XYI10QM",
        "linked_reference_ids": ["SPL-SYN-IBU", "NDC-SYN-IBU-200"],
    },
    "DB-SYN-PARA": {
        "drugbank_id": "DB-SYN-PARA",
        "generic_name": "Paracetamol",
        "synonyms": ["Acetaminophen", "APAP"],
        "drug_type": "small molecule",
        "description": "Analgesic/antipyretic.",
        "indications": ["pain", "fever"],
        "drug_class": "Analgesic",
        "atc_classification": "N02BE01",
        "mechanism_of_action": {
            "action": "modulate",
            "target": "central COX pathways",
            "pathway": "prostaglandin synthesis",
            "physiological_effect": "analgesia_antipyresis",
        },
        "pharmacodynamics": "Central analgesic/antipyretic.",
        "targets": ["COX"],
        "enzymes": ["CYP2E1"],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["warfarin"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "103-90-2",
        "unii": "362O9ITL9D",
        "linked_reference_ids": ["SPL-SYN-PARA"],
        "hepatic_warning": True,
    },
    "DB-SYN-NAP": {
        "drugbank_id": "DB-SYN-NAP",
        "generic_name": "Naproxen",
        "synonyms": ["Naprosyn"],
        "drug_type": "small molecule",
        "description": "NSAID.",
        "indications": ["pain", "inflammation"],
        "drug_class": "NSAID",
        "atc_classification": "M01AE02",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "COX-1/COX-2",
            "pathway": "prostaglandin synthesis",
            "physiological_effect": "analgesia_anti_inflammatory",
        },
        "pharmacodynamics": "Inhibits cyclooxygenase.",
        "targets": ["COX"],
        "enzymes": ["CYP2C9"],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["warfarin", "lithium"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "22204-53-1",
        "unii": "57Y76R9ATQ",
        "linked_reference_ids": ["SPL-SYN-NAP"],
    },
    "DB-SYN-SAL": {
        "drugbank_id": "DB-SYN-SAL",
        "generic_name": "Salbutamol",
        "synonyms": ["Albuterol", "Ventolin"],
        "drug_type": "small molecule",
        "description": "Short-acting beta-2 agonist reliever.",
        "indications": ["asthma", "reversible airways obstruction", "bronchospasm"],
        "drug_class": "Short-acting beta-2 agonist",
        "atc_classification": "R03AC02",
        "mechanism_of_action": {
            "action": "agonize",
            "target": "beta-2 adrenergic receptor",
            "pathway": "bronchodilation",
            "physiological_effect": "bronchodilation",
        },
        "pharmacodynamics": "Relaxes bronchial smooth muscle.",
        "targets": ["ADRB2"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["beta blockers"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "18559-94-9",
        "unii": "QF8SVZ843E",
        "linked_reference_ids": ["SPL-SYN-ALB", "NDC-SYN-SAL-100"],
    },
    "DB-SYN-TERB": {
        "drugbank_id": "DB-SYN-TERB",
        "generic_name": "Terbutaline",
        "synonyms": ["Bricanyl"],
        "drug_type": "small molecule",
        "description": "Short-acting beta-2 agonist.",
        "indications": ["asthma", "bronchospasm", "reversible airways obstruction"],
        "drug_class": "Short-acting beta-2 agonist",
        "atc_classification": "R03AC03",
        "mechanism_of_action": {
            "action": "agonize",
            "target": "beta-2 adrenergic receptor",
            "pathway": "bronchodilation",
            "physiological_effect": "bronchodilation",
        },
        "pharmacodynamics": "Relaxes bronchial smooth muscle.",
        "targets": ["ADRB2"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": ["beta blockers"],
        "approval_status": ["approved"],
        "withdrawal_status": None,
        "market_status": "active",
        "cas_number": "23031-25-6",
        "unii": "N8ONU3L4PG",
        "linked_reference_ids": ["SPL-SYN-TERB"],
    },
    "DB-SYN-WITHDRAWN-X": {
        "drugbank_id": "DB-SYN-WITHDRAWN-X",
        "generic_name": "DemoWithdrawnNSAID",
        "synonyms": [],
        "drug_type": "small molecule",
        "description": "Withdrawn demo NSAID for exclusion tests.",
        "indications": ["pain", "inflammation"],
        "drug_class": "NSAID",
        "atc_classification": "M01AX99",
        "mechanism_of_action": {
            "action": "inhibit",
            "target": "COX-1/COX-2",
            "pathway": "prostaglandin synthesis",
            "physiological_effect": "analgesia_anti_inflammatory",
        },
        "pharmacodynamics": "Demo withdrawn agent.",
        "targets": ["COX"],
        "enzymes": [],
        "carriers": [],
        "transporters": [],
        "drug_interactions": [],
        "approval_status": ["approved"],
        "withdrawal_status": "withdrawn",
        "market_status": "withdrawn",
        "cas_number": "00000-00-0",
        "unii": "DEMOWITHDRAW1",
        "linked_reference_ids": [],
    },
}

FDA_SPL_RECORDS: dict[str, dict] = {
    "SPL-SYN-AMOX": {
        "spl_id": "SPL-SYN-AMOX",
        "generic_name": "Amoxicillin",
        "brand_name": "Amoxil Demo",
        "active_ingredient": "Amoxicillin",
        "product_ndc": "0000-0001-01",
        "route": "Oral",
        "dosage_form": "capsule",
        "indications_and_usage": "Treatment of infections due to susceptible strains of bacteria.",
        "contraindications": ["penicillin hypersensitivity"],
        "warnings_and_precautions": ["serious hypersensitivity reactions"],
        "drug_interactions": ["methotrexate"],
        "pregnancy": "Use only if clearly needed",
        "lactation": "Excreted in milk — caution",
        "pediatric_use": "Yes",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Dose adjustment may be required",
        "hepatic_impairment": "Not available in connected source",
        "mechanism_of_action": "Inhibits bacterial cell wall synthesis",
        "linked_drugbank_id": "DB-SYN-AMOX",
    },
    "SPL-SYN-PENV": {
        "spl_id": "SPL-SYN-PENV",
        "generic_name": "Phenoxymethylpenicillin",
        "brand_name": "Pen V Demo",
        "active_ingredient": "Phenoxymethylpenicillin",
        "product_ndc": "0000-0010-01",
        "route": "Oral",
        "dosage_form": "tablet",
        "indications_and_usage": "Treatment of mild to moderate infections due to penicillin-sensitive organisms.",
        "contraindications": ["penicillin hypersensitivity"],
        "warnings_and_precautions": ["allergy cross-reactivity"],
        "drug_interactions": ["methotrexate"],
        "pregnancy": "Use only if clearly needed",
        "lactation": "Caution",
        "pediatric_use": "Yes",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Dose adjustment may be required",
        "hepatic_impairment": "Not available in connected source",
        "mechanism_of_action": "Inhibits bacterial cell wall synthesis",
        "linked_drugbank_id": "DB-SYN-PEN-V",
    },
    "SPL-SYN-DOXY": {
        "spl_id": "SPL-SYN-DOXY",
        "generic_name": "Doxycycline",
        "brand_name": "Doxy Demo",
        "active_ingredient": "Doxycycline",
        "product_ndc": "0000-0011-01",
        "route": "Oral",
        "dosage_form": "capsule",
        "indications_and_usage": "Treatment of infections caused by susceptible organisms including respiratory tract infections.",
        "contraindications": ["tetracycline hypersensitivity"],
        "warnings_and_precautions": ["photosensitivity", "tooth discoloration in children"],
        "drug_interactions": ["isotretinoin"],
        "pregnancy": "Contraindicated in pregnancy",
        "lactation": "Avoid",
        "pediatric_use": "Not for children under 12",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Generally no adjustment for doxycycline",
        "hepatic_impairment": "Use with caution",
        "mechanism_of_action": "Inhibits 30S ribosomal subunit",
        "linked_drugbank_id": "DB-SYN-DOXY",
        "population_restrictions": ["pregnancy", "children_under_12"],
    },
    "SPL-SYN-IBU": {
        "spl_id": "SPL-SYN-IBU",
        "generic_name": "Ibuprofen",
        "brand_name": "Ibuprofen Demo",
        "active_ingredient": "Ibuprofen",
        "product_ndc": "0000-0002-01",
        "route": "Oral",
        "dosage_form": "tablet",
        "indications_and_usage": "Relief of mild to moderate pain and inflammation.",
        "contraindications": ["NSAID hypersensitivity", "active peptic ulcer"],
        "warnings_and_precautions": ["GI bleed", "CV risk", "renal impairment"],
        "drug_interactions": ["warfarin", "lithium"],
        "pregnancy": "Avoid in third trimester",
        "lactation": "Compatible with caution",
        "pediatric_use": "Age-appropriate formulations",
        "geriatric_use": "Increased risk of adverse effects",
        "renal_impairment": "Avoid in severe renal impairment",
        "hepatic_impairment": "Use with caution",
        "mechanism_of_action": "COX inhibition",
        "linked_drugbank_id": "DB-SYN-IBU",
    },
    "SPL-SYN-PARA": {
        "spl_id": "SPL-SYN-PARA",
        "generic_name": "Paracetamol",
        "brand_name": "Paracetamol Demo",
        "active_ingredient": "Paracetamol",
        "product_ndc": "0000-0020-01",
        "route": "Oral",
        "dosage_form": "tablet",
        "indications_and_usage": "Relief of mild to moderate pain and fever.",
        "contraindications": ["severe hepatic impairment"],
        "warnings_and_precautions": ["hepatotoxicity with overdose"],
        "drug_interactions": ["warfarin"],
        "pregnancy": "Widely used — confirm locally",
        "lactation": "Compatible",
        "pediatric_use": "Yes with weight-based dosing",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Use with caution",
        "hepatic_impairment": "Avoid in severe hepatic impairment",
        "mechanism_of_action": "Central prostaglandin modulation",
        "linked_drugbank_id": "DB-SYN-PARA",
        "hepatic_warning": True,
    },
    "SPL-SYN-NAP": {
        "spl_id": "SPL-SYN-NAP",
        "generic_name": "Naproxen",
        "brand_name": "Naproxen Demo",
        "active_ingredient": "Naproxen",
        "product_ndc": "0000-0021-01",
        "route": "Oral",
        "dosage_form": "tablet",
        "indications_and_usage": "Relief of pain and inflammation.",
        "contraindications": ["NSAID hypersensitivity", "active peptic ulcer"],
        "warnings_and_precautions": ["GI bleed", "CV risk"],
        "drug_interactions": ["warfarin"],
        "pregnancy": "Avoid in third trimester",
        "lactation": "Caution",
        "pediatric_use": "Selected indications",
        "geriatric_use": "Increased risk",
        "renal_impairment": "Avoid in severe renal impairment",
        "hepatic_impairment": "Use with caution",
        "mechanism_of_action": "COX inhibition",
        "linked_drugbank_id": "DB-SYN-NAP",
    },
    "SPL-SYN-ALB": {
        "spl_id": "SPL-SYN-ALB",
        "generic_name": "Albuterol",
        "brand_name": "Albuterol Demo",
        "active_ingredient": "Salbutamol",
        "product_ndc": "0000-0003-01",
        "route": "Inhalation",
        "dosage_form": "inhaler",
        "indications_and_usage": "Treatment or prevention of bronchospasm in patients with reversible obstructive airway disease.",
        "contraindications": ["hypersensitivity to albuterol"],
        "warnings_and_precautions": ["paradoxical bronchospasm", "overuse"],
        "drug_interactions": ["beta blockers"],
        "pregnancy": "Use if benefit outweighs risk",
        "lactation": "Caution",
        "pediatric_use": "Yes",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Not available in connected source",
        "hepatic_impairment": "Not available in connected source",
        "mechanism_of_action": "Beta-2 adrenergic agonism",
        "linked_drugbank_id": "DB-SYN-SAL",
    },
    "SPL-SYN-TERB": {
        "spl_id": "SPL-SYN-TERB",
        "generic_name": "Terbutaline",
        "brand_name": "Terbutaline Demo",
        "active_ingredient": "Terbutaline",
        "product_ndc": "0000-0030-01",
        "route": "Inhalation",
        "dosage_form": "inhaler",
        "indications_and_usage": "Relief of bronchospasm in reversible airways obstruction.",
        "contraindications": ["hypersensitivity to terbutaline"],
        "warnings_and_precautions": ["overuse", "device technique"],
        "drug_interactions": ["beta blockers"],
        "pregnancy": "Use if benefit outweighs risk",
        "lactation": "Caution",
        "pediatric_use": "Selected",
        "geriatric_use": "Use with caution",
        "renal_impairment": "Not available in connected source",
        "hepatic_impairment": "Not available in connected source",
        "mechanism_of_action": "Beta-2 adrenergic agonism",
        "linked_drugbank_id": "DB-SYN-TERB",
    },
}

FDA_NDC_RECORDS: dict[str, dict] = {
    "NDC-SYN-AMOX-500": {
        "product_ndc": "0000-0001-01",
        "generic_name": "Amoxicillin",
        "brand_name": "Amoxil Demo",
        "active_ingredient": "Amoxicillin",
        "strength": "500 mg",
        "dosage_form": "capsule",
        "route": "Oral",
        "product_type": "HUMAN PRESCRIPTION DRUG",
        "manufacturer": "Demo Labeler",
        "marketing_status": "active",
        "package_information": "20 capsules",
        "linked_drugbank_id": "DB-SYN-AMOX",
        "note": "Formulation/product support only — not therapeutic equivalence evidence.",
    },
    "NDC-SYN-IBU-200": {
        "product_ndc": "0000-0002-01",
        "generic_name": "Ibuprofen",
        "brand_name": "Ibuprofen Demo",
        "active_ingredient": "Ibuprofen",
        "strength": "200 mg",
        "dosage_form": "tablet",
        "route": "Oral",
        "product_type": "HUMAN OTC DRUG",
        "manufacturer": "Demo Labeler",
        "marketing_status": "active",
        "package_information": "24 tablets",
        "linked_drugbank_id": "DB-SYN-IBU",
        "note": "Formulation/product support only — not therapeutic equivalence evidence.",
    },
    "NDC-SYN-SAL-100": {
        "product_ndc": "0000-0003-01",
        "generic_name": "Albuterol",
        "brand_name": "Albuterol Demo",
        "active_ingredient": "Salbutamol",
        "strength": "100 mcg/actuation",
        "dosage_form": "inhaler",
        "route": "Inhalation",
        "product_type": "HUMAN PRESCRIPTION DRUG",
        "manufacturer": "Demo Labeler",
        "marketing_status": "active",
        "package_information": "200 actuations",
        "linked_drugbank_id": "DB-SYN-SAL",
        "note": "Formulation/product support only — not therapeutic equivalence evidence.",
    },
}


def all_drugbank() -> list[dict]:
    return [deepcopy(v) for v in DRUGBANK_RECORDS.values()]


def get_drugbank(drugbank_id: str) -> dict | None:
    row = DRUGBANK_RECORDS.get(drugbank_id)
    return deepcopy(row) if row else None


def get_spl(spl_id: str) -> dict | None:
    row = FDA_SPL_RECORDS.get(spl_id)
    return deepcopy(row) if row else None


def get_ndc(ndc_id: str) -> dict | None:
    row = FDA_NDC_RECORDS.get(ndc_id)
    return deepcopy(row) if row else None


def make_claim(**kwargs) -> dict:
    return _claim(**kwargs)


def _norm_ind(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def indication_options_for_drug(drug_name: str) -> list[dict]:
    """Unique indication labels from DrugBank / FDA SPL / FDA NDC.

    Prefer curated DEMO seed rows when present. Otherwise (and additionally)
    derive selectable labels from the full local catalog SQLite indication text
    (DrugBank + FDA_NDC + FDA_SPL ingest). Values are de-duplicated
    case-insensitively. Decision-support only — pharmacist must confirm.
    """
    from app.services.therapeutic.identity import resolve_identity

    identity = resolve_identity(drug_name)
    by_key: dict[str, dict] = {}

    def add(label: str, dataset: str, record_id: str) -> None:
        cleaned = " ".join((label or "").split())
        if not cleaned:
            return
        key = _norm_ind(cleaned)
        if key not in by_key:
            by_key[key] = {
                "value": cleaned,
                "sources": [dataset],
                "source_record_ids": [record_id],
            }
            return
        if dataset not in by_key[key]["sources"]:
            by_key[key]["sources"].append(dataset)
        if record_id not in by_key[key]["source_record_ids"]:
            by_key[key]["source_record_ids"].append(record_id)

    db_id = identity.get("drugbank_id")
    if db_id:
        row = DRUGBANK_RECORDS.get(db_id)
        if row:
            for ind in row.get("indications") or []:
                add(ind, "DrugBank", db_id)
            for ref in row.get("linked_reference_ids") or []:
                if ref in FDA_SPL_RECORDS:
                    spl = FDA_SPL_RECORDS[ref]
                    for ind in spl.get("indication_concepts") or row.get("indications") or []:
                        add(ind, "FDA_SPL", ref)
                    # Promote short DrugBank labels that appear in SPL narrative
                    narrative = _norm_ind(spl.get("indications_and_usage") or "")
                    for ind in row.get("indications") or []:
                        if _norm_ind(ind) in narrative or any(
                            tok in narrative for tok in _norm_ind(ind).split() if len(tok) > 5
                        ):
                            add(ind, "FDA_SPL", ref)
                if ref in FDA_NDC_RECORDS:
                    ndc = FDA_NDC_RECORDS[ref]
                    for ind in ndc.get("indication_concepts") or []:
                        add(ind, "FDA_NDC", ref)

    for spl_id in identity.get("matched_spl_ids") or []:
        spl = FDA_SPL_RECORDS.get(spl_id)
        if not spl:
            continue
        for ind in spl.get("indication_concepts") or []:
            add(ind, "FDA_SPL", spl_id)

    for ndc_id in identity.get("matched_product_ndcs") or []:
        ndc = FDA_NDC_RECORDS.get(ndc_id)
        if not ndc:
            continue
        for ind in ndc.get("indication_concepts") or []:
            add(ind, "FDA_NDC", ndc_id)

    # Full local catalog (FDA NDC + DrugBank + SPL) — fills gaps for drugs outside DEMO seed
    try:
        from app.services.datasets.indication_options import catalog_indication_options

        for opt in catalog_indication_options(drug_name):
            for src in opt.get("sources") or ["FDA_SPL"]:
                rid = (opt.get("source_record_ids") or [drug_name])[0]
                add(opt["value"], src, str(rid))
    except Exception:
        pass

    return sorted(by_key.values(), key=lambda item: item["value"].lower())

