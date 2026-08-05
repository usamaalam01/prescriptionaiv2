"""PII detection and redaction for prescription OCR (privacy-by-design).

Permanent, layout-agnostic rules for any prescription pad:
  - Detect clinic / patient / prescriber / address / phone / provider admin lines
  - Prefer the clinical Rx region (numbered medicines or strength/form/SIG cues)
  - Never promote identity text into medicine rows or the user-facing transcript

Decision-support prototype only — not clinical care.
"""

from __future__ import annotations

import re

# Lines / phrases that are demographic, clinic, or administrative — not medicines.
_PII_LINE_RE = re.compile(
    r"""^(?:
        (?:city|health|life|care|medical|family|community|riverdale|premier|united)?\s*
            (?:care\s+)?(?:clinic|medical\s+centre|medical\s+center|surgery)\b|
        (?:general|consultant)\s+physician\b|
        (?:hospital|pharmacy|dispensary|medical\s+centre|medical\s+center)\b|
        patient\s*(?:name|id|ref)?\s*:?|
        (?:name|age|gender|sex|wt|weight|address|phone|mobile|email|tel|fax)\s*:|
        age\s*/?\s*gender|
        opd\s*(?:no\.?|number|\#)?\s*:?|
        (?:mrn|nhs|cnic|nic)\s*(?:no\.?|\#)?\s*:?|
        date\s*:|
        dr\.?\s+[a-z]|
        doctor\s*:|
        (?:mbbs|fcps|md|frcs|fracgp|fracp|mrcp|frcp)\b|
        reg(?:istration)?\s*\.?\s*no\.?\b|
        provider\s*(?:no\.?|number|\#)\b|
        ahpra\b|
        drink\s+plenty|
        follow\s+up|
        avoid\s+(?:oily|spicy)|
        take\s+medicines\s+regularly|
        no\s+repeats?\b|
        repeats?\s*:?\s*(?:nil|none|0)\b|
        advice\s*:|
        clinical\s+note\s*:|
        diagnosis\s*:|
        dx\s*:|
        low\s+sugar|
        monitor\s+fasting|
        (?:type\s*[12]\s+)?diabetes(?:\s+mellitus)?\b|
        (?:essential\s+)?hypertension\b|
        hyperlipid(?:a)?emia\b|
        rx$|
        [•·▪]
    )""",
    re.I | re.VERBOSE,
)

# Full-line patterns for common PII / address / contact values
_PII_VALUE_RE = re.compile(
    r"""^(?:
        \d{1,2}/\d{1,2}/\d{2,4}$|
        \d+\s*y(?:ears?)?\s*/\s*(?:male|female|m|f)\b|
        demo\s+patient\b|
        test\s+patient\b|
        reg\s*\.?\s*no\.?\s*[:\-]?\s*[\w.-]+|
        opd\s*(?:no\.?)?\s*[:\-]?\s*\d+|
        provider\s*(?:no\.?|number)?\s*[:\-]?\s*[\w/-]+|
        # Street address + phone (AU/UK/US-ish)
        \d+\s+[A-Za-z].*\b(?:ave|avenue|st|street|rd|road|dr|drive|blvd|lane|ln|way|cres|close|ct|court)\b|
        .*\b(?:ph|tel|phone|fax|mob|mobile)\s*[:.]?\s*\(?\d|
        # State + postcode (AU / generic)
        .*\b(?:NSW|VIC|QLD|SA|WA|TAS|ACT|NT|VIC)\b.*\b\d{4}\b|
        .*\b(?:AL|AK|AZ|CA|CO|FL|GA|IL|NY|TX|WA)\b.*\b\d{5}(?:-\d{4})?\b|
        # Email / URL
        [A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$|
        https?://\S+$
    )""",
    re.I | re.VERBOSE,
)

# Inline scrubbers for free-text transcripts
_PII_INLINE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(patient\s*name\s*:?\s*)([^\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(opd\s*(?:no\.?|number|\#)?\s*:?\s*)([^\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(reg(?:istration)?\s*\.?\s*no\.?\s*:?\s*)([^\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(provider\s*(?:no\.?|number|\#)?\s*:?\s*)([^\n]+)"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(date\s*:?\s*)(\d{1,2}/\d{1,2}/\d{2,4})"), r"\1[REDACTED]"),
    (
        re.compile(
            r"(?i)(dr\.?\s+)([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,4})"
            r"(?:\s*,?\s*(?:FRACGP|FRACP|MBBS|FCPS|MD|FRCS|MRCP|FRCP))?"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"(?i)\b\d+\s*y(?:ears?)?\s*/\s*(?:male|female|m|f)\b"), "[REDACTED AGE/SEX]"),
    (
        re.compile(
            r"(?i)\b\d+\s+[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,4}\s+"
            r"(?:Ave|Avenue|St|Street|Rd|Road|Dr|Drive|Blvd|Lane|Ln|Way|Cres|Close|Ct|Court)\b"
            r"[^\n]*"
        ),
        "[REDACTED ADDRESS]",
    ),
    (
        re.compile(
            r"(?i)\b(?:Ph|Tel|Phone|Fax|Mob|Mobile)\s*[:.]?\s*\(?\d[\d\s().-]{6,}\d\b"
        ),
        "[REDACTED PHONE]",
    ),
    (
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        "[REDACTED EMAIL]",
    ),
]

_BAD_AS_DRUG_RE = re.compile(
    r"""^(?:
        city\s+care|care\s+clinic|general\s+physician|demo\s+patient|test\s+patient|
        patient|clinic|physician|hospital|mbbs|fcps|fracgp|fracp|reg\.?\s*no|opd|
        provider|riverdale|drink|follow|avoid|plenty|water|no\s+repeats?|
        advice|clinical\s+note|diagnosis|dx|
        (?:type\s*[12]\s+)?diabetes(?:\s+mellitus)?|
        (?:essential\s+)?hypertension|hyperlipid(?:a)?emia|
        low\s+sugar|monitor\s+fasting|
        one|two|three|four|five|six|half|once|twice|thrice|times|every|
        ind|indication|indications|uses?|symptoms?|directions?|pains?|fever|headache|
        one\s+tablet|two\s+tablets|three\s+times\s+daily|once\s+daily|twice\s+daily
    )""",
    re.I | re.VERBOSE,
)

_CLINICAL_CUE_RE = re.compile(
    r"""
    \b(?:mg|mcg|g|ml|%|tablet|capsule|cap(?:sule)?s?|tab(?:let)?s?|
       inhale|inhaler|puff|puffs|drop|drops|cream|ointment|syrup|
       suspension|injection|patch|suppositor|
       take|apply|swallow|chew|
       daily|hourly|orally|bd|tds|tid|qid|od|hs|prn|
       amoxicillin|ibuprofen|paracetamol|cetirizine|pantoprazole|
       salbutamol|albuterol|metformin|atorvastatin)\b
    |
    \d+\s*(?:mg|mcg|g|ml|%)\b
    |
    ^\d+\s*[.)]\s*[A-Za-z]
    """,
    re.I | re.VERBOSE,
)

_ITEM_START_RE = re.compile(
    # "1. Drug" / "1) Drug" / Vision often drops punctuation: "1 Amoxicillin …"
    r"^\s*(?P<item>\d{1,2})\s*(?:[.)\-–—:]\s*|\s+)(?P<body>[A-Za-z].*)$"
)


def has_clinical_cue(text: str) -> bool:
    """True if the line looks like medicine / SIG content (keep for Rx focus)."""
    t = " ".join((text or "").split()).strip()
    if not t:
        return False
    return bool(_CLINICAL_CUE_RE.search(t))


def is_pii_or_admin_line(text: str) -> bool:
    """True if the OCR line is identity/admin/advice — must not become a medicine row."""
    t = " ".join((text or "").split()).strip()
    if not t:
        return True
    low = t.lower()
    if low in {"r", "rx", "•", "·", "▪", "-", "–", "—", ":", "no repeats", "no repeat"}:
        return True
    # Advice / clinical notes / diagnosis — even when OCR appends stray strength tokens
    if re.match(
        r"(?i)^(?:advice|clinical\s+note|diagnosis|dx|note)\s*:",
        t,
    ):
        return True
    if _PII_LINE_RE.match(low):
        return True
    if _PII_VALUE_RE.match(t):
        return True
    # Diagnosis / counseling alone (no medicine SIG) — never promote to drug rows
    if re.fullmatch(
        r"(?i)(?:type\s*[12]\s+)?diabetes(?:\s+mellitus)?|"
        r"(?:essential\s+)?hypertension|hyperlipid(?:a)?emia|"
        r"low\s+sugar(?:\s+diet)?|monitor\s+fasting(?:\s+glucose)?|"
        r"clinical\s+note|advice",
        t,
    ):
        return True
    # Address / phone cues anywhere on a non-clinical line
    if not has_clinical_cue(t) and re.search(
        r"(?i)\b(?:ave|avenue|street|st\.|road|rd\.|ph\s*:|tel\s*:|phone|provider\s*no|"
        r"fracgp|fracp|ahpra|postcode|zip\s*code)\b",
        t,
    ):
        return True
    # Clinic-style titles: 2–5 Title Case words, no strength/dose cues
    if (
        not re.search(r"\d", t)
        and not has_clinical_cue(t)
        and re.fullmatch(r"(?:[A-Z][a-zA-Z.'-]+\s+){0,4}[A-Z][a-zA-Z.'-]+", t)
        and any(
            w in low
            for w in (
                "clinic",
                "hospital",
                "physician",
                "care",
                "pharmacy",
                "medical",
                "surgery",
                "centre",
                "center",
            )
        )
    ):
        return True
    # Short slogan / non-clinical phrase without digits or drug cues
    if (
        not has_clinical_cue(t)
        and not re.search(r"\d", t)
        and len(t.split()) <= 4
        and any(w in low for w in ("repeat", "repeats", "confidential", "bulk bill", "medicare"))
    ):
        return True
    return False


def looks_like_pii_drug_name(name: str) -> bool:
    """Reject extracted medicine names that are clearly PII/admin."""
    n = " ".join((name or "").split()).strip()
    if not n:
        return True
    if _BAD_AS_DRUG_RE.match(n):
        return True
    if is_pii_or_admin_line(n):
        return True
    if re.fullmatch(r"[A-Z][a-z]+\s+[A-Z][a-z]+", n) and n.lower() in {
        "demo patient",
        "test patient",
    }:
        return True
    return False


def find_rx_clinical_start(lines: list[str]) -> int:
    """Index of first clinical Rx content for any pad layout.

    Prefers the first numbered medicine item with clinical body; falls back to first
    clinical-cue line. A lone 'R'/'Rx' glyph alone is NOT enough (headers often sit after it).
    """
    # Pass 1: numbered clinical items
    for idx, raw in enumerate(lines):
        text = " ".join((raw or "").split()).strip()
        m = _ITEM_START_RE.match(text)
        if not m:
            continue
        body = (m.group("body") or "").strip()
        if not body:
            # Empty "1." — look ahead one line
            if idx + 1 < len(lines):
                nxt = " ".join((lines[idx + 1] or "").split()).strip()
                if nxt and not is_pii_or_admin_line(nxt) and (
                    has_clinical_cue(nxt) or looks_like_drug_token(nxt)
                ):
                    return idx
            continue
        if is_pii_or_admin_line(body):
            continue
        if has_clinical_cue(body) or looks_like_drug_token(body):
            return idx

    # Pass 2: first clinical cue that is not PII
    for idx, raw in enumerate(lines):
        text = " ".join((raw or "").split()).strip()
        if not text or is_pii_or_admin_line(text):
            continue
        if has_clinical_cue(text) or looks_like_drug_token(text):
            return idx

    return 0


def looks_like_drug_token(text: str) -> bool:
    """Loose drug-name heuristic for focusing (not final catalog match)."""
    t = " ".join((text or "").split()).strip()
    if len(t) < 4 or is_pii_or_admin_line(t):
        return False
    low = t.lower()
    if re.fullmatch(
        r"(?:one|two|three|four|five|six|1|2|3|4)(?:\s+(?:tablet|tablets|capsule|capsules))?|"
        r"(?:once|twice|(?:one|two|three|four)\s+times)\s+daily|"
        r"three\s+times\s+daily|every\s+\d+\s+hours?",
        low,
    ):
        return False
    if has_clinical_cue(t) and not re.search(r"[A-Za-z]{5,}", t):
        # Pure SIG cue without a longer drug-like token
        if re.search(r"(?i)\b(?:tablet|capsule|daily|times|take|mg)\b", t):
            return False
    if has_clinical_cue(t):
        return True
    # Capitalized word / misspelling candidates (Amoxcillin, Ibrufen)
    if re.fullmatch(r"[A-Za-z][A-Za-z-]{3,}(?:\s+[A-Za-z][A-Za-z-]{2,}){0,2}", t):
        low = t.lower()
        if any(
            w in low
            for w in (
                "patient",
                "clinic",
                "doctor",
                "street",
                "avenue",
                "riverdale",
                "provider",
            )
        ):
            return False
        if low in {"one", "two", "three", "four", "five", "six", "once", "twice", "daily", "times"}:
            return False
        return True
    return False


def filter_clinical_transcript_lines(lines: list[str]) -> list[str]:
    """Keep only Rx clinical lines for the user-facing OCR transcript."""
    if not lines:
        return []
    start = find_rx_clinical_start(lines)
    focused = lines[start:]
    kept: list[str] = []
    for line in focused:
        t = " ".join((line or "").split()).strip()
        if not t:
            continue
        if is_pii_or_admin_line(t):
            continue
        # Drop residual address/phone even if clinical cue regex missed
        if re.search(r"(?i)\b(?:ph\s*:|tel\s*:|provider\s*no|fracgp|@[a-z0-9.-]+\.)", t):
            continue
        if has_clinical_cue(t) or looks_like_drug_token(t) or _ITEM_START_RE.match(t):
            kept.append(t)
            continue
        # Keep short SIG continuations after we already have clinical content
        if kept and re.search(
            r"(?i)\b(?:daily|times|tablet|capsule|puff|orally|before|after|food|night)\b",
            t,
        ):
            kept.append(t)
    return kept


def redact_ocr_text(text: str) -> str:
    """Return a privacy-safe OCR transcript focused on medicines (any pad layout)."""
    out = text or ""
    for pattern, repl in _PII_INLINE_PATTERNS:
        out = pattern.sub(repl, out)

    raw_lines = [ln for ln in out.splitlines()]
    clinical = filter_clinical_transcript_lines(raw_lines)
    if clinical:
        return "\n".join(clinical)

    # Fallback: line-wise redaction when no clinical region detected
    lines: list[str] = []
    for line in raw_lines:
        if is_pii_or_admin_line(line) and not has_clinical_cue(line):
            low = line.lower().strip()
            if low in {"rx", "r"} or re.match(r"^\d+\s*[.)]", line.strip()):
                continue  # drop bare Rx glyph / empty numbers from transcript
            lines.append("[REDACTED]")
        elif has_clinical_cue(line) or looks_like_drug_token(line):
            lines.append(line)
        elif not is_pii_or_admin_line(line) and re.search(r"\d", line or ""):
            # Keep ambiguous numeric clinical fragments; drop pure admin
            lines.append(line)
        else:
            if line.strip():
                lines.append("[REDACTED]")
    # Collapse runs of [REDACTED]
    collapsed: list[str] = []
    for ln in lines:
        if ln == "[REDACTED]" and collapsed and collapsed[-1] == "[REDACTED]":
            continue
        collapsed.append(ln)
    # Prefer empty clinical transcript over a wall of redactions
    if collapsed and all(x == "[REDACTED]" for x in collapsed):
        return ""
    return "\n".join(collapsed)


def strip_trailing_strength_digits(name: str) -> str:
    """OCR often yields 'Amoxicillin 500' — keep the drug token only."""
    n = " ".join((name or "").split()).strip()
    n = re.sub(r"\s+\d+(?:\.\d+)?\s*$", "", n).strip(" -,\t.")
    return n
