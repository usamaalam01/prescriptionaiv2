"""OCR string metrics: WER, CER, field-level exact match (DQ1)."""

from __future__ import annotations

import re
from typing import Any


def normalise_for_error_rate(text: str | None) -> str:
    """
    Normalisation before WER/CER (documented in evaluation_protocol.md):
    - lowercase
    - collapse whitespace
    - strip leading/trailing space
    - remove punctuation except digits and letters and %
    """
    if text is None:
        return ""
    t = str(text).lower().strip()
    t = re.sub(r"[^\w\s%./-]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def character_error_rate(reference: str | None, hypothesis: str | None) -> float:
    ref = normalise_for_error_rate(reference)
    hyp = normalise_for_error_rate(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / max(len(ref), 1)


def word_error_rate(reference: str | None, hypothesis: str | None) -> float:
    ref_toks = normalise_for_error_rate(reference).split()
    hyp_toks = normalise_for_error_rate(hypothesis).split()
    if not ref_toks:
        return 0.0 if not hyp_toks else 1.0
    return _levenshtein_seq(ref_toks, hyp_toks) / max(len(ref_toks), 1)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins, delete, sub = cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def _levenshtein_seq(a: list[str], b: list[str]) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, xa in enumerate(a, 1):
        cur = [i]
        for j, xb in enumerate(b, 1):
            ins, delete, sub = cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (xa != xb)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def field_exact_match(ref: str | None, hyp: str | None) -> bool:
    return normalise_for_error_rate(ref) == normalise_for_error_rate(hyp) and bool(
        normalise_for_error_rate(ref)
    )


def entity_prf(
    gold_names: list[str],
    pred_names: list[str],
) -> dict[str, float]:
    g = {normalise_for_error_rate(x) for x in gold_names if normalise_for_error_rate(x)}
    p = {normalise_for_error_rate(x) for x in pred_names if normalise_for_error_rate(x)}
    if not g and not p:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    tp = len(g & p)
    precision = tp / len(p) if p else 0.0
    recall = tp / len(g) if g else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def score_ocr_against_gt(
    *,
    gt_text: str | None,
    hyp_text: str | None,
    gt_fields: dict[str, Any],
    hyp_fields: dict[str, Any],
) -> dict[str, Any]:
    cer = character_error_rate(gt_text, hyp_text)
    wer = word_error_rate(gt_text, hyp_text)
    fields = ("medicine_name", "strength", "route", "dosage_form", "dose", "frequency", "duration")
    field_acc: dict[str, Any] = {}
    for f in fields:
        field_acc[f] = {
            "exact_match": field_exact_match(gt_fields.get(f), hyp_fields.get(f)),
            "ref": gt_fields.get(f),
            "hyp": hyp_fields.get(f),
        }
    name_prf = entity_prf(
        [str(gt_fields.get("medicine_name") or "")],
        [str(hyp_fields.get("medicine_name") or "")],
    )
    return {
        "cer": cer,
        "wer": wer,
        "medicine_name_exact_match": field_acc["medicine_name"]["exact_match"],
        "medicine_name_precision": name_prf["precision"],
        "medicine_name_recall": name_prf["recall"],
        "medicine_name_f1": name_prf["f1"],
        "field_accuracy": field_acc,
    }
