"""Deterministic field normalization for analytics (not clinical equivalence)."""

from __future__ import annotations

import re

NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}

ROUTE_MAP = {
    "po": "oral",
    "oral": "oral",
    "p.o.": "oral",
    "p.o": "oral",
    "iv": "intravenous",
    "im": "intramuscular",
    "sc": "subcutaneous",
    "inhalation": "inhalation",
    "inh": "inhalation",
}

FREQ_MAP = {
    "tid": "three times daily",
    "t.i.d.": "three times daily",
    "t.i.d": "three times daily",
    "bd": "twice daily",
    "bid": "twice daily",
    "b.i.d.": "twice daily",
    "od": "once daily",
    "qd": "once daily",
    "qds": "four times daily",
    "qid": "four times daily",
    "prn": "as required",
}

UNIT_MAP = {
    "milligram": "mg",
    "milligrams": "mg",
    "microgram": "mcg",
    "micrograms": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "ml": "ml",
    "millilitre": "ml",
    "milliliter": "ml",
}

# Known OCR / synonym corrections already confirmed by pharmacists in DEMO seed
DRUG_SYNONYMS = {
    "ibrufen": "ibuprofen",
    "brufen": "ibuprofen",
    "amoxycillin": "amoxicillin",
    "amoxil": "amoxicillin",
    "acetaminophen": "paracetamol",
    "apap": "paracetamol",
    "albuterol": "salbutamol",
    "ventolin": "salbutamol",
}


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("-", " ")
    return text.strip()


def normalize_field(field: str, value: str | None) -> str:
    text = normalize_text(value)
    if not text:
        return ""

    if field in {"drug", "drug_name"}:
        return DRUG_SYNONYMS.get(text, text)

    if field == "route":
        return ROUTE_MAP.get(text.replace(".", ""), text)

    if field == "frequency":
        compact = text.replace(" ", "")
        if compact in FREQ_MAP:
            return FREQ_MAP[compact]
        # expand number words in frequency phrases
        parts = []
        for tok in text.split():
            parts.append(NUMBER_WORDS.get(tok, tok))
        return " ".join(parts)

    if field in {"dose", "dosage"}:
        parts = []
        for tok in text.split():
            parts.append(NUMBER_WORDS.get(tok, tok))
        return " ".join(parts)

    if field == "strength":
        text = text.replace("milligrams", "mg").replace("milligram", "mg")
        for k, v in UNIT_MAP.items():
            text = re.sub(rf"\b{re.escape(k)}\b", v, text)
        # "400mg" / "40mg/1" → "400 mg" / "40 mg" (format-equivalent, not clinical change)
        text = re.sub(r"(\d+(?:\.\d+)?)\s*/\s*1\b", r"\1", text)
        text = re.sub(r"(\d+(?:\.\d+)?)(mg|mcg|g|ml|%)\b", r"\1 \2", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    return text


def classify_error(
    field: str,
    ocr_value: str | None,
    confirmed_value: str | None,
    *,
    exact: bool,
    normalized: bool,
) -> str:
    if exact:
        return "none"
    ocr = (ocr_value or "").strip()
    conf = (confirmed_value or "").strip()
    if not ocr and conf:
        return "missing value"
    if ocr and not conf:
        return "extra value"
    if normalized:
        return "normalization correction"

    ocr_n = normalize_text(ocr)
    conf_n = normalize_text(conf)

    if field in {"drug", "drug_name"}:
        # close spelling / OCR character issues
        if abs(len(ocr_n) - len(conf_n)) <= 2 and ocr_n and conf_n:
            return "spelling"
        return "spelling"

    if field == "strength":
        ocr_num = re.findall(r"\d+(?:\.\d+)?", ocr_n)
        conf_num = re.findall(r"\d+(?:\.\d+)?", conf_n)
        if ocr_num and conf_num and ocr_num[0] != conf_num[0]:
            return "numeric error"
        if ocr_num == conf_num and ocr_n != conf_n:
            return "unit error"
        return "unsupported value"

    if field in {"dose", "dosage", "frequency"}:
        ocr_num = re.findall(r"\d+(?:\.\d+)?", normalize_field(field, ocr))
        conf_num = re.findall(r"\d+(?:\.\d+)?", normalize_field(field, conf))
        if ocr_num and conf_num and ocr_num != conf_num:
            return "numeric error"

    # character-level OCR suspicion
    if ocr_n and conf_n and abs(len(ocr_n) - len(conf_n)) <= 3:
        return "OCR character error"
    return "unsupported value"
