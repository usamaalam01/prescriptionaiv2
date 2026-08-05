"""Indication options should come from catalog SPL/DrugBank text, not noise."""

from app.services.datasets.indication_options import _extract_labels, catalog_indication_options
from app.services.field_verification import _indication_options_catalog


def test_extract_labels_from_otc_acetaminophen_text():
    text = (
        "Uses temporarily: • reduces fever • relieves minor aches and pains due to: "
        "• the common cold • flu • headache • sore throat • toothache"
    )
    labels = [x.lower() for x in _extract_labels(text)]
    assert "fever" in labels
    assert any("pain" in x for x in labels)
    assert "headache" in labels
    assert not any(x.startswith("directions") for x in labels)


def test_catalog_indication_options_for_demo_drugs():
    for name in ("Acetaminophen", "Pantoprazole", "Cetirizine", "acarbose"):
        opts = catalog_indication_options(name)
        assert opts, f"no indications for {name}"
        values = [o["value"].lower() for o in opts]
        assert not any(v.startswith("directions") for v in values)
        assert all(len(o["value"]) <= 120 for o in opts)
        assert all(o.get("sources") for o in opts)


def test_aripiprazole_indications_clean():
    from app.services.datasets.indication_options import catalog_indication_options

    opts = catalog_indication_options("Aripiprazole")
    values = [o["value"] for o in opts]
    assert opts, "expected Aripiprazole indications from catalog"
    assert any(v.lower() == "schizophrenia" for v in values)
    assert not any("(" in v or "[" in v or "14" in v for v in values)
    assert not any("clinical studies" in v.lower() for v in values)


def test_benztropine_indications_from_catalog_text():
    from app.services.datasets.indication_options import _extract_labels, catalog_indication_options

    text = (
        "INDICATIONS AND USAGE Benztropine mesylate tablets USP are indicated for use "
        "as an adjunct in the therapy of all forms of parkinsonism. Useful also in the "
        "control of extrapyramidal disorders (except tardive dyskinesia) due to neuroleptic drugs."
    )
    labels = [x.lower() for x in _extract_labels(text)]
    assert any("parkinson" in x for x in labels)
    assert any("extrapyramidal" in x for x in labels)
    opts = catalog_indication_options("Benztropine")
    assert opts
    values = [o["value"].lower() for o in opts]
    assert any("parkinson" in v for v in values)
