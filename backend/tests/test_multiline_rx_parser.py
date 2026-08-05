"""Multi-line OCR Rx block parser tests (Vision-style fragmented lines)."""

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


def test_multiline_vision_style_rx_block_parse():
    lines = [
        "Health Care Clinic",
        "Patient Name : Test Patient",
        "Age / Gender :",
        "32 Y / Female",
        "Rx",
        "1 ) Amoxicillin",
        "Take",
        "500",
        "mg",
        "Capsule",
        "1 capsule orally 8 howdy",
        "for 5 days .",
        "Paracetamol",
        "500 mg",
        "Tablet",
        "Take",
        "1 tablet orally 6 hourly if fever or pain",
        "3 )",
        "Cetirizine",
        "10",
        "Tablet",
        "mg",
        "Take",
        "1 tablet orally once daily at night for 7 days",
        "4 )",
        "Pantoprazole",
        "40 mg",
        "Tablet",
        "Take",
        "1 tablet orally once daily before breakfast for 7 days .",
        "Drink plenty of water .",
        "Avoid oily & spicy food .",
        "Dr. A. Khan",
    ]
    _, meds, _ = MedicalParserAdapter().parse(_merged(lines))
    names = [m.medicine_name for m in meds]
    assert names == ["Amoxicillin", "Paracetamol", "Cetirizine", "Pantoprazole"]
    assert meds[0].strength == "500 mg"
    assert meds[0].form == "capsule"
    assert meds[0].dose == "ONE capsule"
    assert meds[0].frequency == "8 hourly"
    assert meds[2].strength == "10 mg"
    assert meds[2].frequency == "ONCE daily"
    assert meds[3].strength == "40 mg"
    assert "Tablet" not in names
