"""PII sanitization for analytics (synthetic prescription metrics only)."""

from __future__ import annotations

import re

PII_PATTERNS = [
    re.compile(r"(?i)\b(patient|pt\.?)\s*name\s*[:\-].*"),
    re.compile(r"(?i)\b(prescriber|doctor|dr\.?)\s*name\s*[:\-].*"),
    re.compile(r"(?i)\b(mrn|nhs|hospital\s*number|medical\s*record)\s*[:\-]?\s*\S+"),
    re.compile(r"(?i)\b(national\s*identifier|ni\s*number)\s*[:\-]?\s*\S+"),
    re.compile(r"(?i)\b(phone|tel|mobile)\s*[:\-]?\s*[\d\s\+\-()]{7,}"),
    re.compile(r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?i)\b(address)\s*[:\-].*"),
    re.compile(r"(?i)\b(registration\s*(no|number)|gmc)\s*[:\-]?\s*\S+"),
]

FORBIDDEN_KEYS = {
    "patient_name",
    "patient_reference",
    "prescriber_name",
    "prescriber_registration_number",
    "phone_number",
    "email",
    "email_address",
    "address",
    "national_identifier",
    "hospital_number",
    "medical_record_number",
}


def sanitize_prescription_text(text: str | None) -> str:
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        cleaned = line
        for pattern in PII_PATTERNS:
            cleaned = pattern.sub("[REDACTED]", cleaned)
        lines.append(cleaned)
    return "\n".join(lines)


def assert_no_pii_keys(payload: dict) -> None:
    flat = _flatten_keys(payload)
    bad = sorted(FORBIDDEN_KEYS.intersection(flat))
    if bad:
        raise ValueError(f"PII keys must not appear in analytics payload: {bad}")


def _flatten_keys(obj, prefix="") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            keys.add(key)
            keys |= _flatten_keys(v, key)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _flatten_keys(item, prefix)
    return keys
