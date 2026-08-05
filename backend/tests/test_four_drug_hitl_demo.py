"""Validate the four-drug HITL demo set: Arcabose, Pantoprazole, Cetirizine, Acetaminophen."""

from app.services.datasets.match import normalize_query, suggest_medicines
from app.services.pipeline import PrescriptionPipeline


def test_normalize_maps_ocr_misspellings_and_acetaminophen():
    assert normalize_query("arcabose") == "acarbose"
    assert normalize_query("Arcabose") == "acarbose"
    assert normalize_query("Acetaminophen") == "acetaminophen"
    assert normalize_query("paracetamol") == "acetaminophen"
    assert normalize_query("Pantoprazole") == "pantoprazole"
    assert normalize_query("Cetirizine") == "cetirizine"


def test_suggest_top_hit_for_four_demo_drugs():
    cases = {
        "arcabose": "acarbose",
        "Pantoprazole": "pantoprazole",
        "Cetirizine": "cetirizine",
        "Acetaminophen": "acetaminophen",
    }
    for query, expected_canon in cases.items():
        hits = suggest_medicines(query, top_k=3)
        assert hits, f"no catalog hits for {query!r}"
        top = hits[0].canonical_name.strip().lower()
        assert top == expected_canon, f"{query!r} top={hits[0].canonical_name!r}"


def test_mock_pipeline_emits_four_target_drugs():
    result = PrescriptionPipeline().run(b"synthetic-four-drug-demo" + b"0" * 32)
    names = [m.medicine_name for m in result.parsed_medicines]
    assert "Arcabose" in names
    assert "Pantoprazole" in names
    assert "Cetirizine" in names
    assert "Acetaminophen" in names
    assert "Amoxicillin" not in names
    assert "Ibrufen" not in names

    by_name = {m.medicine_name: m for m in result.parsed_medicines}
    assert by_name["Pantoprazole"].route == "Oral"
    assert by_name["Pantoprazole"].strength == "40 mg"
    assert by_name["Acetaminophen"].dose == "TWO tablets"

    checks = {c.medicine_name: c for c in result.formulary_checks}
    assert checks["Arcabose"].matched is False
    assert checks["Pantoprazole"].matched is True
    assert checks["Cetirizine"].matched is True
    assert checks["Acetaminophen"].matched is True
