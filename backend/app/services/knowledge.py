"""Synthetic academic knowledge base (DrugBank / FDA-style seed).

This is NOT a live DrugBank or openFDA integration. Records are curated for the
CSCK700 prototype so alternatives and citations remain available offline.
Replace adapters later with licensed DrugBank / openFDA clients behind the same
interfaces — never treat LLM prose as clinical source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceCitation:
    source: str  # DrugBank | FDA_NDC | FDA_SPL | BNF_STYLE | SYNTHETIC_FORMULARY
    source_id: str
    title: str
    url: str
    excerpt: str


@dataclass(frozen=True)
class AlternativeCandidate:
    medicine_name: str
    strength: str | None
    form: str | None
    route: str | None
    relationship: str  # same_class | therapeutic_substitute | dose_form_variant
    rationale: str
    contraindications_note: str
    confidence: float
    citations: list[EvidenceCitation] = field(default_factory=list)


@dataclass(frozen=True)
class DrugKnowledge:
    name: str
    formulary_id: str
    drugbank_id: str
    fda_ndc_example: str
    therapeutic_class: str
    indications_summary: str
    why_used: str
    limitations: str
    citations: list[EvidenceCitation]
    alternatives: list[AlternativeCandidate]


# Curated synthetic subset aligned with pipeline seed formulary medicines.
KNOWLEDGE: dict[str, DrugKnowledge] = {
    "amoxicillin": DrugKnowledge(
        name="Amoxicillin",
        formulary_id="FORM-AMOX-001",
        drugbank_id="DB-SYN-AMOX",
        fda_ndc_example="0000-0001-01",
        therapeutic_class="Penicillin antibiotic",
        indications_summary="Broad-spectrum penicillin for susceptible bacterial infections (academic summary).",
        why_used=(
            "Used as a beta-lactam antibiotic for susceptible bacterial infections when a penicillin is appropriate."
        ),
        limitations=(
            "Not for penicillin-allergic patients; complete the full course only under clinical direction; "
            "local resistance patterns and indication must be confirmed by the pharmacist/prescriber."
        ),
        citations=[
            EvidenceCitation(
                source="DrugBank",
                source_id="DB-SYN-AMOX",
                title="Amoxicillin — synthetic DrugBank-style monograph",
                url="https://go.drugbank.com/drugs/DB01060",
                excerpt="Beta-lactam antibiotic; pharmacist must confirm indication, allergy status, and local guidance.",
            ),
            EvidenceCitation(
                source="FDA_SPL",
                source_id="SPL-SYN-AMOX",
                title="Amoxicillin capsules — synthetic label reference",
                url="https://www.accessdata.fda.gov/",
                excerpt="Label-style dosing and allergy warnings are illustrative only in this prototype.",
            ),
        ],
        alternatives=[
            AlternativeCandidate(
                medicine_name="Phenoxymethylpenicillin",
                strength="250 mg",
                form="tablets",
                route="Oral",
                relationship="same_class",
                rationale="Same beta-lactam class; may be considered for narrower-spectrum oral streptococcal indications per local protocol.",
                contraindications_note="Do not suggest if penicillin allergy. Not interchangeable without clinical review.",
                confidence=0.72,
                citations=[
                    EvidenceCitation(
                        source="DrugBank",
                        source_id="DB-SYN-PEN-V",
                        title="Phenoxymethylpenicillin — synthetic monograph",
                        url="https://go.drugbank.com/",
                        excerpt="Narrower-spectrum penicillin; decision-support suggestion only.",
                    ),
                ],
            ),
            AlternativeCandidate(
                medicine_name="Doxycycline",
                strength="100 mg",
                form="capsules",
                route="Oral",
                relationship="therapeutic_substitute",
                rationale="Non-penicillin option sometimes considered when penicillin allergy is documented — only under pharmacist/prescriber judgement.",
                contraindications_note="Pregnancy, children under 12, and photosensitivity considerations apply. Not auto-selected.",
                confidence=0.61,
                citations=[
                    EvidenceCitation(
                        source="FDA_SPL",
                        source_id="SPL-SYN-DOXY",
                        title="Doxycycline — synthetic label reference",
                        url="https://www.accessdata.fda.gov/",
                        excerpt="Tetracycline-class warnings; evidence link for academic prototype.",
                    ),
                ],
            ),
        ],
    ),
    "ibuprofen": DrugKnowledge(
        name="Ibuprofen",
        formulary_id="FORM-IBU-001",
        drugbank_id="DB-SYN-IBU",
        fda_ndc_example="0000-0002-01",
        therapeutic_class="NSAID",
        indications_summary="Analgesic / anti-inflammatory (academic summary).",
        why_used=(
            "Used for mild-to-moderate pain and inflammation where an NSAID is clinically appropriate."
        ),
        limitations=(
            "Avoid or use with caution in peptic ulcer disease, renal impairment, heart failure, "
            "or with interacting medicines; take after food when advised; pharmacist must review risks."
        ),
        citations=[
            EvidenceCitation(
                source="DrugBank",
                source_id="DB-SYN-IBU",
                title="Ibuprofen — synthetic DrugBank-style monograph",
                url="https://go.drugbank.com/drugs/DB01050",
                excerpt="NSAID; GI, renal, and CV risk considerations require pharmacist review.",
            ),
            EvidenceCitation(
                source="FDA_NDC",
                source_id="NDC-SYN-IBU",
                title="Ibuprofen tablets — synthetic NDC-style reference",
                url="https://www.accessdata.fda.gov/scripts/cder/ndc/",
                excerpt="NDC-style identifier is synthetic for offline prototype use.",
            ),
            EvidenceCitation(
                source="FDA_SPL",
                source_id="SPL-SYN-IBU",
                title="Ibuprofen oral — synthetic label reference",
                url="https://www.accessdata.fda.gov/",
                excerpt="NSAID class warnings (GI bleed, CV risk) require pharmacist judgement.",
            ),
        ],
        alternatives=[
            AlternativeCandidate(
                medicine_name="Paracetamol",
                strength="500 mg",
                form="tablets",
                route="Oral",
                relationship="therapeutic_substitute",
                rationale="Non-NSAID analgesic alternative when NSAID risks outweigh benefits.",
                contraindications_note="Check hepatotoxicity risk and total daily dose across products.",
                confidence=0.78,
                citations=[
                    EvidenceCitation(
                        source="DrugBank",
                        source_id="DB-SYN-PARA",
                        title="Paracetamol — synthetic monograph",
                        url="https://go.drugbank.com/",
                        excerpt="Analgesic/antipyretic alternative suggestion with source link.",
                    ),
                ],
            ),
            AlternativeCandidate(
                medicine_name="Naproxen",
                strength="250 mg",
                form="tablets",
                route="Oral",
                relationship="same_class",
                rationale="Same NSAID class; longer-acting option sometimes considered — not interchangeable automatically.",
                contraindications_note="Same class risks as other NSAIDs; pharmacist confirmation mandatory.",
                confidence=0.66,
                citations=[
                    EvidenceCitation(
                        source="FDA_SPL",
                        source_id="SPL-SYN-NAP",
                        title="Naproxen — synthetic label reference",
                        url="https://www.accessdata.fda.gov/",
                        excerpt="NSAID boxed-warning style caution for academic demonstration.",
                    ),
                ],
            ),
        ],
    ),
    "salbutamol": DrugKnowledge(
        name="Salbutamol",
        formulary_id="FORM-SAL-001",
        drugbank_id="DB-SYN-SAL",
        fda_ndc_example="0000-0003-01",
        therapeutic_class="Short-acting beta-2 agonist",
        indications_summary="Reliever bronchodilator for reversible airways obstruction (academic summary).",
        why_used=(
            "Used as a short-acting reliever bronchodilator for reversible airways obstruction (e.g. asthma symptoms)."
        ),
        limitations=(
            "Not a preventer/controller; over-use may indicate poor control; check inhaler technique and "
            "device type; seek urgent care for severe/worsening breathlessness."
        ),
        citations=[
            EvidenceCitation(
                source="DrugBank",
                source_id="DB-SYN-SAL",
                title="Salbutamol (Albuterol) — synthetic monograph",
                url="https://go.drugbank.com/drugs/DB01001",
                excerpt="SABA reliever; technique and over-use monitoring are clinical responsibilities.",
            ),
            EvidenceCitation(
                source="FDA_SPL",
                source_id="SPL-SYN-ALB",
                title="Albuterol inhalation aerosol — synthetic label reference",
                url="https://www.accessdata.fda.gov/",
                excerpt="USAN albuterol / BAN salbutamol naming difference noted for prototype.",
            ),
        ],
        alternatives=[
            AlternativeCandidate(
                medicine_name="Terbutaline",
                strength="500 micrograms",
                form="inhaler",
                route="Inhalation",
                relationship="same_class",
                rationale="Alternative SABA inhaler in some formularies; device and dosing differ.",
                contraindications_note="Not a 1:1 device swap. Pharmacist must confirm local availability and technique.",
                confidence=0.64,
                citations=[
                    EvidenceCitation(
                        source="BNF_STYLE",
                        source_id="BNF-SYN-TERB",
                        title="Terbutaline — synthetic formulary-style note",
                        url="https://bnf.nice.org.uk/",
                        excerpt="Formulary-style alternative note for academic prototype only.",
                    ),
                ],
            ),
        ],
    ),
}


def normalize_medicine_name(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def lookup_drug(medicine_name: str) -> DrugKnowledge | None:
    key = normalize_medicine_name(medicine_name)
    # Handle common BAN/USAN aliases used in mock OCR
    aliases = {
        "albuterol": "salbutamol",
        "amoxycillin": "amoxicillin",
        "acetaminophen": "paracetamol",
    }
    key = aliases.get(key, key)
    return KNOWLEDGE.get(key)
