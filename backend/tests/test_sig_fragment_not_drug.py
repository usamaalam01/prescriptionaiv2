"""Regression: Vision-split SIG fragments must not become HITL drug rows."""

from app.services.pipeline import MedicalParserAdapter, MergedLine, LineCandidate


def _merged(texts: list[str]) -> list[MergedLine]:
    out: list[MergedLine] = []
    for i, text in enumerate(texts):
        cand = LineCandidate(
            line_id=f"t-{i}",
            text=text,
            confidence=0.9,
            engine="test",
            is_mock=True,
        )
        out.append(
            MergedLine(
                line_id=f"m-{i}",
                selected_text=text,
                selected_confidence=0.9,
                selected_engine="test",
                candidates=[cand],
                conflict=False,
                used_trocr_retry=False,
            )
        )
    return out


def test_sig_fragments_not_treated_as_drugs():
    parser = MedicalParserAdapter()
    for frag in (
        "ONE",
        "ONE tablet",
        "TWO tablets",
        "THREE times daily",
        "ONCE daily",
        "twice daily",
        "every 6 hours",
        "every 6 hours as required",
        "with meals",
        "Ind:",
        "Ind",
        "Indication:",
        "Every",
        "Pains",
        "Pain",
        "Uses",
        "Fever",
    ):
        assert parser._looks_like_drug_name(frag) is False, frag


def test_vision_split_sig_does_not_create_extra_rows():
    """Real Vision often emits drug, then 'ONE', then 'THREE times daily' as separate lines."""
    parser = MedicalParserAdapter()
    lines = _merged(
        [
            "1. Arcabose 50 mg tablets",
            "ONE",
            "THREE times daily",
            "2. Pantoprazole 40 mg tablets",
            "ONE tablet",
            "ONCE daily",
            "3. Cetirizine 10 mg tablets",
            "Take ONE tablet ONCE daily",
            "4. Acetaminophen 500 mg tablets",
            "TWO tablets",
            "every 6 hours as required",
        ]
    )
    _, meds, _ = parser.parse(lines)
    names = [m.medicine_name for m in meds]
    assert "ONE" not in names
    assert "THREE times daily" not in names
    assert "ONCE daily" not in names
    assert "TWO tablets" not in names
    assert any("Arcabose" in n or "acarbose" in n.lower() for n in names)
    assert any("Pantoprazole" in n for n in names)
    assert any("Cetirizine" in n for n in names)
    assert any("Acetaminophen" in n for n in names)
    # SIG fragments enrich the prior drug
    arco = next(m for m in meds if "rcabose" in m.medicine_name.lower())
    assert arco.frequency == "THREE times daily" or arco.dose == "ONE tablet"
    panto = next(m for m in meds if "Pantoprazole" in m.medicine_name)
    assert panto.dose == "ONE tablet"
    assert panto.frequency == "ONCE daily"
