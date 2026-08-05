"""PII exclusion + OCR Rx parse quality tests."""

from app.services.ocr.privacy import (
    filter_clinical_transcript_lines,
    find_rx_clinical_start,
    is_pii_or_admin_line,
    looks_like_pii_drug_name,
    redact_ocr_text,
    strip_trailing_strength_digits,
)
from app.services.pipeline import LineCandidate, MedicalParserAdapter, MergedLine


def _merged(lines: list[str]) -> list[MergedLine]:
    out: list[MergedLine] = []
    for i, text in enumerate(lines):
        cand = LineCandidate(
            line_id=f"l{i}",
            text=text,
            confidence=0.9,
            engine="test",
            is_mock=True,
        )
        out.append(
            MergedLine(
                line_id=f"l{i}",
                selected_text=text,
                selected_engine="test",
                selected_confidence=0.9,
                candidates=[cand],
                conflict=False,
                used_trocr_retry=False,
            )
        )
    return out


def test_pii_lines_detected():
    assert is_pii_or_admin_line("City Care Clinic")
    assert is_pii_or_admin_line("Patient Name :")
    assert is_pii_or_admin_line("Demo Patient")
    assert is_pii_or_admin_line("OPD No .: 38142")
    assert is_pii_or_admin_line("28 Y / Male")
    assert is_pii_or_admin_line("Dr. S. Ahmed")
    assert is_pii_or_admin_line("Reg . No. 55421 - P")
    assert is_pii_or_admin_line("23 Riverdale Ave , Riverdale , VIC 3121 Ph : 03 9876 5432")
    assert is_pii_or_admin_line("No repeats")
    assert is_pii_or_admin_line("Dr. Smith , FRACGP")
    assert is_pii_or_admin_line("Provider No. 246810K")
    assert is_pii_or_admin_line("Advice: Low sugar diet, monitor fasting glucose")
    assert is_pii_or_admin_line("Clinical note: Type 2 Diabetes Mellitus")
    assert is_pii_or_admin_line("Diabetes Mellitus")
    assert is_pii_or_admin_line("Type 2 Diabetes Mellitus")
    assert looks_like_pii_drug_name("Diabetes Mellitus")
    assert looks_like_pii_drug_name("Advice")
    assert not is_pii_or_admin_line("1. Amoxicillin 500 mg Capsule")
    assert not is_pii_or_admin_line("Ibuprofen 400 mg")
    assert not is_pii_or_admin_line("1. Amoxcillin 500 mg capsules")
    assert not is_pii_or_admin_line("Metformin 500 mg Tablet")


def test_redact_drops_header_keeps_medicines():
    raw = "\n".join(
        [
            "R",
            "Riverdale Family Clinic",
            "23 Riverdale Ave , Riverdale , VIC 3121 Ph : 03 9876 5432",
            "No repeats",
            "Dr. Jane Smith , FRACGP",
            "Provider No. 246810K",
            "1. Amoxcillin 500 mg capsules",
            "Take ONE capsule THREE times daily",
            "2. Ibrufen 400 mg tablets",
            "Take ONE tablet THREE times daily",
            "3. Salbutamol inhaler",
            "TWO puffs when required",
        ]
    )
    out = redact_ocr_text(raw)
    assert "Riverdale Ave" not in out
    assert "9876" not in out
    assert "FRACGP" not in out
    assert "Provider" not in out
    assert "No repeats" not in out
    assert "Amoxcillin" in out
    assert "Ibrufen" in out
    assert "Salbutamol" in out
    # Bare R glyph should not dominate transcript
    assert out.strip().splitlines()[0].startswith("1.")


def test_find_rx_clinical_start_skips_r_glyph_and_header():
    lines = [
        "R",
        "[REDACTED]",
        "23 Riverdale Ave , Riverdale , VIC 3121 Ph : 03 9876 5432",
        "No repeats",
        "Dr. [REDACTED] , FRACGP",
        "Provider No. 246810K",
        "1. Amoxcillin 500 mg capsules",
        "Take ONE capsule THREE times daily",
    ]
    assert find_rx_clinical_start(lines) == 6
    clinical = filter_clinical_transcript_lines(lines)
    assert clinical[0].startswith("1.")
    assert all("Riverdale" not in ln for ln in clinical)


def test_strip_trailing_strength_digits():
    assert strip_trailing_strength_digits("Amoxicillin 500") == "Amoxicillin"
    assert strip_trailing_strength_digits("Pantoprazole 40") == "Pantoprazole"
    assert strip_trailing_strength_digits("Cetirizine") == "Cetirizine"


def test_curated_pad_ocr_excludes_pii_and_parses_drugs():
    """Vision-style fragmented lines from curated_hitl_test_rx.png."""
    lines = [
        "City Care Clinic",
        "General Physician",
        "Date : 22/03/2025",
        "Patient Name :",
        "Demo Patient",
        "OPD No .: 38142",
        "Age / Gender :",
        "R",
        "28 Y / Male",
        "1. Amoxicillin 500",
        "mg Capsule",
        "Take 1 capsule orally three times daily for 7 days .",
        "2. Ibuprofen 400",
        "mg",
        "Tablet",
        "Take 1 tablet orally three times daily after food .",
        "mg",  # orphan unit (Vision sometimes mis-attaches)
        "3. Cetirizine 10",
        "Tablet",
        "Take 1 tablet orally once daily at night for 5 days .",
        "4. Pantoprazole 40",
        "Tablet",
        "mg",
        "once daily before breakfast for 7 days .",
        "Take 1 tablet orally",
        "Drink plenty of water .",
        "Follow up after 7 days .",
        "Dr. S. Ahmed",
        "MBBS",
        "Reg . No. 55421 - P",
    ]
    raw, meds, warnings = MedicalParserAdapter().parse(_merged(lines))
    names = [m.medicine_name for m in meds]
    assert "City Care Clinic" not in names
    assert "Demo Patient" not in names
    assert not any("Reg" in n for n in names)
    assert names == ["Amoxicillin", "Ibuprofen", "Cetirizine", "Pantoprazole"]
    assert meds[0].strength == "500 mg"
    assert meds[1].strength == "400 mg"
    assert meds[2].strength == "10 mg"
    assert meds[3].strength == "40 mg"
    assert meds[0].dose == "ONE capsule"
    assert meds[3].frequency == "ONCE daily"
    assert "Demo Patient" not in raw
    assert "Riverdale" not in raw
    assert any("PII" in w or "privacy" in w.lower() or "excluded" in w.lower() for w in warnings)


def test_au_pad_header_does_not_become_medicines():
    """Australian-style header after Rx glyph must not leak into medicines or transcript."""
    lines = [
        "R",
        "23 Riverdale Ave , Riverdale , VIC 3121 Ph : 03 9876 5432",
        "No repeats",
        "Dr. Jane Smith , FRACGP",
        "Provider No. 246810K",
        "1. Amoxcillin 500 mg capsules",
        "Take ONE capsule THREE times daily",
        "2. Ibrufen 400 mg tablets",
        "Take ONE tablet THREE times daily",
        "3. Salbutamol inhaler",
        "TWO puffs when required",
    ]
    raw, meds, _warnings = MedicalParserAdapter().parse(_merged(lines))
    names = [m.medicine_name for m in meds]
    assert "Amoxcillin" in names or "Amoxicillin" in names
    assert "Ibrufen" in names or "Ibuprofen" in names
    assert any("Salbutamol" in n or "albuterol" in n.lower() for n in names) or "Salbutamol" in names
    assert not any("Riverdale" in n or "Provider" in n or "FRACGP" in n for n in names)
    assert "9876" not in raw
    assert "Provider" not in raw
    assert "Amoxcillin" in raw or "Amoxicillin" in raw


def test_diabetic_pad_excludes_advice_and_diagnosis():
    """Clinical notes / advice must not become HITL medicine rows."""
    lines = [
        "City Care Clinic",
        "Patient Name : Test",
        "R",
        "52 Y / Male",
        "Clinical note: Type 2 Diabetes Mellitus",
        "1. Metformin 500 mg Tablet",
        "Take ONE tablet TWICE daily",
        "2. Empagliflozin 10 mg Tablet",
        "Take ONE tablet ONCE daily",
        "Advice: Low sugar diet, monitor fasting glucose",
        "Diabetes Mellitus",
        "Dr. S. Ahmed",
    ]
    _raw, meds, _warnings = MedicalParserAdapter().parse(_merged(lines))
    names = [m.medicine_name for m in meds]
    assert "Metformin" in names
    assert any("Empagliflozin" in n for n in names)
    assert not any("Diabetes" in n for n in names)
    assert not any("Advice" in n or "Low sugar" in n for n in names)
    assert not any("Clinical" in n for n in names)


def test_looks_like_pii_drug_name():
    assert looks_like_pii_drug_name("City Care Clinic")
    assert looks_like_pii_drug_name("Demo Patient")
    assert looks_like_pii_drug_name("Diabetes Mellitus")
    assert not looks_like_pii_drug_name("Amoxicillin")
    assert not looks_like_pii_drug_name("Metformin")
