"""Unit tests for Summary Analytics metrics (no PII)."""

from app.services.analytics.edit_distance import character_error_rate, word_error_rate
from app.services.analytics.normalization import classify_error, normalize_field
from app.services.analytics.pii import assert_no_pii_keys, sanitize_prescription_text


def test_cer_wer_basic():
    assert character_error_rate("abc", "abc") == 0.0
    assert round(character_error_rate("abx", "abc") or 0, 4) == round(1 / 3, 4)
    assert word_error_rate("one two", "one two") == 0.0
    assert word_error_rate("one three", "one two") == 0.5


def test_empty_reference_cer_wer():
    assert character_error_rate("x", "") is None
    assert word_error_rate("x", "") is None
    assert character_error_rate("", "") == 0.0


def test_exact_and_normalized_match():
    assert normalize_field("drug", "Ibrufen") == "ibuprofen"
    assert normalize_field("route", "PO") == "oral"
    assert normalize_field("frequency", "TID") == "three times daily"
    assert normalize_field("strength", "250 mg") != normalize_field("strength", "200 mg")
    assert normalize_field("dose", "one capsule") != normalize_field("dose", "two capsules")


def test_numeric_mismatch_not_normalized_away():
    assert normalize_field("strength", "250 mg") == "250 mg"
    assert normalize_field("strength", "200 mg") == "200 mg"
    assert normalize_field("strength", "250 mg") != normalize_field("strength", "200 mg")


def test_error_category_spelling():
    cat = classify_error("drug", "Ibrufen", "Ibuprofen", exact=False, normalized=True)
    assert cat == "normalization correction"
    cat2 = classify_error("drug", "Ibrufen", "Ibuprofen", exact=False, normalized=False)
    assert cat2 in {"spelling", "OCR character error"}


def test_precision_recall_f1_helpers():
    from app.services.analytics.compute import _f1, _safe_div

    assert _safe_div(1, 0) is None
    assert _f1(1.0, 1.0) == 1.0
    assert _f1(0.0, 0.0) == 0.0
    assert round(_f1(0.5, 0.5) or 0, 4) == 0.5


def test_pii_sanitized_and_forbidden_keys():
    text = sanitize_prescription_text("Patient name: Alice\nAmoxicillin 500 mg")
    assert "Alice" not in text or "[REDACTED]" in text
    assert "Amoxicillin" in text
    payload = {"summary": {"medicines_confirmed": 1}, "anonymous_evaluation_id": "x"}
    assert_no_pii_keys(payload)
    try:
        assert_no_pii_keys({"patient_name": "x"})
        assert False
    except ValueError:
        pass


def test_bertscore_unavailable_returns_none():
    from app.services.analytics import bertscore_optional

    # Default ENABLE_BERTSCORE=false
    assert bertscore_optional.score_pairs(["a"], ["a"]) is None
