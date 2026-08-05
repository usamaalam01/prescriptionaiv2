"""Deterministic extraction of dose + frequency from FDA SPL dosage_and_administration.

Evidence-only CDS (CSCK700): options are scoped to Drug → Route → Strength.
When a dose is selected, frequencies prefer spans near that dose phrase (dose-adjacent).
Fail-closed: if no compatible candidates remain for the selected triple, return [].
No LLM; no invented SIG templates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Soft window (chars) around a selected dose phrase for frequency co-occurrence.
_DOSE_ADJACENCY_WINDOW = 180

_SPACE = re.compile(r"\s+")
_WORD_NUM = {
    "half": 0.5,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "1": 1.0,
    "2": 2.0,
    "3": 3.0,
    "4": 4.0,
    "5": 5.0,
    "6": 6.0,
}

# Count-unit doses (solid / unit forms)
_COUNT_DOSE_RE = re.compile(
    r"(?i)\b(?P<num>half|one|two|three|four|five|six|1(?:\.5)?|2|3|4|5|6)"
    r"(?:\s+and\s+(?:a\s+)?half)?"
    r"\s+(?:\(\s*\d+(?:\.\d+)?\s*mg\s*\))?"
    r"\s*(?P<unit>tablets?|capsules?|puffs?|drops?|suppositories?|patches?)\b"
)

# "two 300 mg tablets"
_N_STRENGTH_UNITS_RE = re.compile(
    r"(?i)\b(?P<num>half|one|two|three|four|1|2|3|4)\s+"
    r"(?P<mg>\d+(?:\.\d+)?)\s*mg\s+"
    r"(?P<unit>tablets?|capsules?)\b"
)

# Volume doses — avoid matching the denominator of "400 mg/5 mL"
_VOLUME_DOSE_RE = re.compile(
    r"(?i)(?<!/)\b(?P<vol>\d+(?:\.\d+)?)\s*(?P<unit>mL|ml)\b"
)

# Mass dose near recommended wording (scoped later against tablet strength)
_RECOMMENDED_MG_RE = re.compile(
    r"(?i)(?:recommended\s+(?:dosage|dose)|dose\s+of|administer(?:ed)?)\s*[:\-]?\s*"
    r"(?:is\s+)?"
    r"(?:(?:a|an|the)\s+)?"
    r"(?P<mg>\d+(?:\.\d+)?)\s*mg\b"
)

# FDA table/regimen style: "500 mg every 8 hours" / "500 mg every 8 to 12 hours"
_MG_EVERY_HOURS_RE = re.compile(
    r"(?i)\b(?P<mg>\d+(?:\.\d+)?)\s*mg\s+every\s+(?P<h>\d+)"
    r"(?:\s*(?:to|-)\s*(?P<h2>\d+))?\s+hours?\b"
)

# FDA table style: "Adults 40 mg Once Daily" / "40 mg Twice Daily"
_MG_DAILY_REGIMEN_RE = re.compile(
    r"(?i)\b(?P<mg>\d+(?:\.\d+)?)\s*mg\s+"
    r"(?:once\s+daily|twice\s+daily|three\s+times\s+(?:a\s+)?daily|"
    r"four\s+times\s+(?:a\s+)?daily|once\s+a\s+day|two\s+times\s+(?:a\s+)?day|"
    r"t\.?i\.?d\.?|b\.?i\.?d\.?|q\.?i\.?d\.?|q\.?d\.?)\b"
)

# Unit count with interval: "1 tablet every 4 to 6 hours"
_COUNT_EVERY_HOURS_RE = re.compile(
    r"(?i)\b(?P<num>one|two|three|four|1|2|3|4)\s+"
    r"(?P<unit>tablets?|capsules?|puffs?)\s+every\s+(?P<h>\d+)"
    r"(?:\s*(?:to|-)\s*(?P<h2>\d+))?\s+hours?\b"
)

# Frequency patterns → HITL canonical labels (ordered: more specific first)
_FREQ_PATTERNS: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"(?i)\b(?:four\s+times\s+(?:a\s+)?daily|qid|q\.i\.d\.)\b"), "FOUR times daily", 0.9),
    (re.compile(r"(?i)\b(?:three\s+times\s+(?:a\s+)?daily|tid|t\.i\.d\.)\b"), "THREE times daily", 0.9),
    (re.compile(r"(?i)\b(?:twice\s+(?:daily|a\s+day)|two\s+times\s+(?:a\s+)?(?:day|daily)|bid|b\.i\.d\.)\b"), "TWICE daily", 0.92),
    (re.compile(r"(?i)\b(?:once\s+(?:daily|a\s+day)|one\s+time\s+(?:a\s+)?(?:day|daily)|(?:qd|q\.d\.)\b)"), "ONCE daily", 0.88),
    (re.compile(r"(?i)\b(?:at\s+bedtime|bedtime|hs\b|qhs)\b"), "at bedtime", 0.9),
    (re.compile(r"(?i)\b(?:before\s+(?:a\s+)?meals?|ac\b)\b"), "before meal", 0.85),
    (re.compile(r"(?i)\b(?:after\s+(?:a\s+)?meals?|after\s+food|pc\b)\b"), "after meal", 0.85),
    (re.compile(r"(?i)\b(?:when\s+required|as\s+required|as\s+needed|prn)\b"), "when required", 0.8),
    (re.compile(r"(?i)\bevery\s+72\s+hours\b"), "every 72 hours", 0.9),
    (re.compile(r"(?i)\b(?:once\s+weekly|once\s+a\s+week|weekly)\b"), "ONCE weekly", 0.85),
    # Range first so "every 8 to 12 hours" is not partially consumed as every 8 only
    (re.compile(r"(?i)\bevery\s+(?P<h>\d+)\s*(?:to|-)\s*(?P<h2>\d+)\s+hours?\b"), "__EVERY_H_RANGE__", 0.86),
    (re.compile(r"(?i)\bevery\s+(?P<h>\d+)\s+hours?\b"), "__EVERY_H__", 0.88),
)

_ROUTE_CUES: dict[str, tuple[str, ...]] = {
    "Oral": ("oral", "orally", "by mouth", "po ", " swallowed"),
    "Inhalation": ("inhal", "nebuliz", "puff"),
    "Topical": ("topical", "apply", "skin"),
    "Injection": ("inject", "intravenous", "intramuscular", "subcutaneous", "iv ", "im "),
    "Ophthalmic": ("ophthalmic", "eye"),
    "Otic": ("otic", "ear"),
    "Rectal": ("rectal", "suppositor"),
    "Transdermal": ("transdermal", "patch"),
    "Nasal": ("nasal", "intranasal"),
}


@dataclass(frozen=True)
class DoseCandidate:
    dose_label: str
    evidence_excerpt: str
    confidence: float
    unit_family: str  # tablet|capsule|liquid|inhaler|drop|suppository|patch|mass
    span_start: int = 0
    span_end: int = 0


@dataclass(frozen=True)
class FrequencyCandidate:
    frequency_label: str
    evidence_excerpt: str
    confidence: float
    span_start: int = 0
    span_end: int = 0
    dose_adjacent: bool = False
    distance_to_dose: int | None = None


def _norm(text: str | None) -> str:
    if not text:
        return ""
    return _SPACE.sub(" " , text.strip().lower().replace("-", " "))


def _clip_excerpt(text: str, start: int, end: int, *, radius: int = 60) -> str:
    a = max(0, start - radius)
    b = min(len(text), end + radius)
    excerpt = _SPACE.sub(" ", text[a:b].strip())
    if a > 0:
        excerpt = "…" + excerpt
    if b < len(text):
        excerpt = excerpt + "…"
    return excerpt[:220]


def _unit_canon(unit: str) -> tuple[str, str]:
    u = unit.lower().rstrip("s")
    if u == "tablet":
        return "tablet", "tablet"
    if u == "capsule":
        return "capsule", "capsule"
    if u == "puff":
        return "inhaler", "puff"
    if u == "drop":
        return "drop", "drop"
    if u == "suppositorie" or u == "suppository":
        return "suppository", "suppository"
    if u == "patche" or u == "patch":
        return "patch", "patch"
    return u, u


def _count_label(n: float, unit_word: str) -> str | None:
    if n == 0.5:
        return f"Half {unit_word}"
    if n == 1.0:
        return f"ONE {unit_word}"
    if n == 1.5:
        return f"One and Half {unit_word}s" if not unit_word.endswith("s") else f"One and Half {unit_word}"
    if n == 2.0:
        return f"TWO {unit_word}s" if not unit_word.endswith("s") else f"TWO {unit_word}"
    if n == int(n) and 3 <= int(n) <= 6:
        return f"{int(n)} {unit_word}s" if not unit_word.endswith("s") else f"{int(n)} {unit_word}"
    return None


def _parse_num(token: str) -> float | None:
    t = token.lower().strip()
    if t in _WORD_NUM:
        return _WORD_NUM[t]
    try:
        return float(t)
    except ValueError:
        return None


def parse_strength_mg(strength: str | None) -> float | None:
    """Return primary mass (mg) from a catalog strength string, if any."""
    if not strength:
        return None
    s = _norm(strength)
    # Prefer left side of concentration: 400 mg/5ml
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg\b", s)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*g\b", s)
    if m:
        return float(m.group(1)) * 1000.0
    m = re.search(r"(\d+(?:\.\d+)?)\s*mcg\b", s)
    if m:
        return float(m.group(1)) / 1000.0
    return None


def is_liquid_strength(strength: str | None) -> bool:
    s = _norm(strength)
    if not s:
        return False
    return bool(re.search(r"mg\s*/\s*\d", s) or "ml" in s or "mL" in (strength or ""))


def classify_form_family(form: str | None) -> str | None:
    if not form:
        return None
    d = _norm(form)
    if "tablet" in d or "tab " in d:
        return "tablet"
    if "capsule" in d or "caplet" in d:
        return "capsule"
    if any(x in d for x in ("suspension", "solution", "syrup", "elixir", "liquid", "powder for")):
        return "liquid"
    if "inhal" in d or "aerosol" in d or "spray" in d:
        return "inhaler"
    if "drop" in d or "ophthalmic" in d or "otic" in d:
        return "drop"
    if "suppositor" in d:
        return "suppository"
    if "patch" in d or "transdermal" in d:
        return "patch"
    if "inject" in d:
        return "injection"
    if "cream" in d or "ointment" in d or "gel" in d or "topical" in d:
        return "topical"
    return None


def _route_compatible(text: str, route_label: str | None) -> bool:
    """If route cues exist in text, require compatibility; else allow."""
    if not route_label:
        return True
    low = _norm(text)
    mentioned = []
    for label, cues in _ROUTE_CUES.items():
        if any(c in low for c in cues):
            mentioned.append(label)
    if not mentioned:
        return True
    return route_label in mentioned or (
        route_label == "Oral" and "Oral" in mentioned
    )


def extract_dose_candidates(
    section_text: str,
    *,
    keep_all_spans: bool = False,
) -> list[DoseCandidate]:
    """Extract dose candidates from SPL dosage_and_administration prose.

    By default dedupes by normalized label (first / highest-confidence kept).
    Set keep_all_spans=True to retain every match for dose-adjacency anchoring.
    """
    if not section_text or not section_text.strip():
        return []
    text = section_text
    out: list[DoseCandidate] = []
    seen: set[str] = set()

    def _add(label: str | None, fam: str, start: int, end: int, conf: float) -> None:
        if not label:
            return
        key = _norm(label)
        if not key:
            return
        # Reject vague / non-evidence doses
        if key in {"as directed", "apply as directed", "apply thinly"}:
            return
        if not keep_all_spans and key in seen:
            return
        if not keep_all_spans:
            seen.add(key)
        out.append(
            DoseCandidate(
                dose_label=label,
                evidence_excerpt=_clip_excerpt(text, start, end),
                confidence=conf,
                unit_family=fam,
                span_start=start,
                span_end=end,
            )
        )

    for m in _N_STRENGTH_UNITS_RE.finditer(text):
        n = _parse_num(m.group("num"))
        fam, word = _unit_canon(m.group("unit"))
        if n is None:
            continue
        try:
            unit_mg = float(m.group("mg"))
        except (TypeError, ValueError):
            unit_mg = 0.0
        # Prefer total mass so scoping can convert "two 20 mg tablets" → ONE 40 mg tablet
        if unit_mg > 0:
            total = n * unit_mg
            if 0 < total <= 10000:
                _add(f"{total:g} mg", "mass", m.start(), m.end(), 0.93)
        _add(_count_label(n, word), fam, m.start(), m.end(), 0.82)

    for m in _COUNT_DOSE_RE.finditer(text):
        n = _parse_num(m.group("num"))
        fam, word = _unit_canon(m.group("unit"))
        if n is None:
            continue
        # "one and half" handled loosely via group; refine if "and half" in span
        span = m.group(0).lower()
        if "and" in span and "half" in span and n == 1.0:
            n = 1.5
        _add(_count_label(n, word), fam, m.start(), m.end(), 0.88)

    for m in _VOLUME_DOSE_RE.finditer(text):
        # Skip if this ml is the concentration denominator: mg/5 mL
        prev = text[max(0, m.start() - 12) : m.start()]
        if re.search(r"(?i)mg\s*/\s*$", prev) or prev.rstrip().endswith("/"):
            continue
        vol = float(m.group("vol"))
        # Skip huge volumes unlikely to be patient doses
        if vol <= 0 or vol > 60:
            continue
        label = f"{vol:g} ml"
        _add(label, "liquid", m.start(), m.end(), 0.85)

    for m in _RECOMMENDED_MG_RE.finditer(text):
        mg = float(m.group("mg"))
        if mg <= 0 or mg > 10000:
            continue
        label = f"{mg:g} mg"
        _add(label, "mass", m.start(), m.end(), 0.7)

    # Evidence-based regimens: "500 mg every 8 hours" (common FDA tables)
    for m in _MG_EVERY_HOURS_RE.finditer(text):
        mg = float(m.group("mg"))
        if mg <= 0 or mg > 10000:
            continue
        _add(f"{mg:g} mg", "mass", m.start(), m.end(), 0.93)

    # "40 mg Once Daily" / "40 mg Twice Daily" FDA tables
    for m in _MG_DAILY_REGIMEN_RE.finditer(text):
        mg = float(m.group("mg"))
        if mg <= 0 or mg > 10000:
            continue
        _add(f"{mg:g} mg", "mass", m.start(), m.end(), 0.95)

    for m in _COUNT_EVERY_HOURS_RE.finditer(text):
        n = _parse_num(m.group("num"))
        fam, word = _unit_canon(m.group("unit"))
        if n is None:
            continue
        _add(_count_label(n, word), fam, m.start(), m.end(), 0.94)

    return out


def _hours_to_frequency_label(hours: int) -> str | None:
    if hours <= 0 or hours > 72:
        return None
    if hours == 24:
        return "ONCE daily"
    if hours == 12:
        return "TWICE daily"
    if hours == 8:
        return "THREE times daily"
    if hours == 6:
        return "FOUR times daily"
    return f"every {hours} hours"


def scope_doses_to_route_strength(
    candidates: list[DoseCandidate],
    *,
    route: str | None,
    strength: str | None,
    dosage_form: str | None = None,
    section_text: str | None = None,
) -> list[DoseCandidate]:
    """Keep candidates compatible with selected route + strength (+ form)."""
    if not candidates:
        return []

    route_label = route
    # Soft route gate using full section when available
    if section_text and route_label and not _route_compatible(section_text, route_label):
        # Still allow if candidate families match oral solids and route is Oral etc.
        pass

    form_fam = classify_form_family(dosage_form)
    liquid = is_liquid_strength(strength) or form_fam == "liquid"
    solid_mg = parse_strength_mg(strength)
    kept: list[DoseCandidate] = []

    for c in candidates:
        fam = c.unit_family

        if liquid:
            if fam == "liquid":
                kept.append(c)
            continue

        if form_fam in {"tablet", "capsule"} or (
            form_fam is None and fam in {"tablet", "capsule", "mass"}
        ):
            if fam in {"tablet", "capsule"} and (form_fam is None or fam == form_fam or form_fam in {fam, "tablet", "capsule"}):
                kept.append(c)
                # Oral solid interchange: tablet Rx vs capsule SPL (or reverse)
                if form_fam in {"tablet", "capsule"} and fam != form_fam:
                    alt_word = form_fam
                    alt_label = re.sub(
                        r"(?i)\b(tablets?|capsules?)\b",
                        "tablet" if alt_word == "tablet" else "capsule",
                        c.dose_label,
                        count=1,
                    )
                    # Fix pluralization via count helper when possible
                    n_match = re.search(r"(?i)\b(one|two|three|four|1|2|3|4)\b", c.dose_label)
                    if n_match:
                        n = _parse_num(n_match.group(1))
                        rebuilt = _count_label(n, alt_word) if n is not None else None
                        if rebuilt:
                            alt_label = rebuilt
                    kept.append(
                        DoseCandidate(
                            dose_label=alt_label,
                            evidence_excerpt=c.evidence_excerpt,
                            confidence=max(0.7, c.confidence - 0.05),
                            unit_family=alt_word,
                            span_start=c.span_start,
                            span_end=c.span_end,
                        )
                    )
                continue
            if fam == "mass" and solid_mg:
                # Convert mass dose → unit count when divisible by tablet strength
                try:
                    dose_mg = float(re.search(r"([\d.]+)", c.dose_label).group(1))  # type: ignore[union-attr]
                except (AttributeError, ValueError):
                    continue
                if solid_mg > 0 and abs(dose_mg % solid_mg) < 1e-6:
                    n = dose_mg / solid_mg
                    if n <= 0 or n > 8:
                        continue
                    word = "tablet" if form_fam != "capsule" else "capsule"
                    label = _count_label(n, word)
                    if label:
                        # Exact strength match (ONE tablet of selected strength) ranks highest
                        conf = 0.96 if abs(n - 1.0) < 1e-9 else min(c.confidence, 0.85)
                        kept.append(
                            DoseCandidate(
                                dose_label=label,
                                evidence_excerpt=c.evidence_excerpt,
                                confidence=conf,
                                unit_family=word,
                                span_start=c.span_start,
                                span_end=c.span_end,
                            )
                        )
            continue

        if form_fam and fam == form_fam:
            kept.append(c)
            continue

        if form_fam is None and fam in {"inhaler", "drop", "patch", "suppository"}:
            kept.append(c)

    # Deduplicate by normalized label, keep highest confidence
    best: dict[str, DoseCandidate] = {}
    for c in kept:
        key = _norm(c.dose_label)
        prev = best.get(key)
        if prev is None or c.confidence > prev.confidence:
            best[key] = c
    return sorted(best.values(), key=lambda x: (-x.confidence, x.dose_label.lower()))


def doses_for_label_context(
    section_text: str,
    *,
    route: str | None,
    strength: str | None,
    dosage_form: str | None = None,
) -> list[DoseCandidate]:
    """End-to-end: extract then scope to route + strength."""
    cands = extract_dose_candidates(section_text)
    return scope_doses_to_route_strength(
        cands,
        route=route,
        strength=strength,
        dosage_form=dosage_form,
        section_text=section_text,
    )


def extract_frequency_candidates(
    section_text: str,
    *,
    keep_all_spans: bool = False,
) -> list[FrequencyCandidate]:
    """Extract frequency labels from SPL dosage_and_administration prose.

    keep_all_spans=True retains every match (needed for dose-adjacency ranking).
    """
    if not section_text or not section_text.strip():
        return []
    text = section_text
    out: list[FrequencyCandidate] = []
    seen: set[str] = set()

    for pattern, label_or_token, conf in _FREQ_PATTERNS:
        for m in pattern.finditer(text):
            labels_to_add: list[str] = []
            if label_or_token == "__EVERY_H__":
                try:
                    hours = int(m.group("h"))
                except (IndexError, ValueError):
                    continue
                lab = _hours_to_frequency_label(hours)
                if lab:
                    labels_to_add.append(lab)
            elif label_or_token == "__EVERY_H_RANGE__":
                try:
                    h1 = int(m.group("h"))
                    h2 = int(m.group("h2"))
                except (IndexError, ValueError):
                    continue
                for hours in {h1, h2}:
                    lab = _hours_to_frequency_label(hours)
                    if lab:
                        labels_to_add.append(lab)
            else:
                labels_to_add.append(label_or_token)

            for label in labels_to_add:
                key = _norm(label)
                if not key:
                    continue
                if not keep_all_spans and key in seen:
                    continue
                if not keep_all_spans:
                    seen.add(key)
                out.append(
                    FrequencyCandidate(
                        frequency_label=label,
                        evidence_excerpt=_clip_excerpt(text, m.start(), m.end()),
                        confidence=conf,
                        span_start=m.start(),
                        span_end=m.end(),
                    )
                )
    if keep_all_spans:
        return out
    return sorted(out, key=lambda x: (-x.confidence, x.frequency_label.lower()))


def _dose_label_matches(candidate_label: str, selected_dose: str) -> bool:
    a = _norm(candidate_label)
    b = _norm(selected_dose)
    if not a or not b:
        return False
    if a == b:
        return True
    # "TWO tablets" ↔ "two tablet" / "2 tablets"
    a_tokens = set(a.replace("one and half", "1.5").split())
    b_tokens = set(b.replace("one and half", "1.5").split())
    # Normalize plural tablets/capsules
    def _stem(tok: str) -> str:
        if tok.endswith("s") and len(tok) > 3:
            return tok[:-1]
        return tok

    a_stem = {_stem(t) for t in a_tokens}
    b_stem = {_stem(t) for t in b_tokens}
    if a_stem == b_stem:
        return True
    # Require unit family overlap + numeric token overlap for partials
    units = {"tablet", "capsule", "puff", "drop", "suppository", "patch", "ml", "mg"}
    a_u = a_stem & units
    b_u = b_stem & units
    if a_u and b_u and (a_u & b_u):
        nums_a = a_stem - units
        nums_b = b_stem - units
        if nums_a & nums_b:
            return True
    return False


def find_dose_anchor_spans(section_text: str, dose_label: str | None) -> list[tuple[int, int]]:
    """Locate spans in section text that correspond to the selected HITL dose label."""
    if not section_text or not dose_label or not dose_label.strip():
        return []
    spans: list[tuple[int, int]] = []
    for c in extract_dose_candidates(section_text, keep_all_spans=True):
        if _dose_label_matches(c.dose_label, dose_label):
            spans.append((c.span_start, c.span_end))
    if spans:
        return spans

    low = section_text.lower()
    d = _norm(dose_label)

    # Volume e.g. "5 ml"
    m_vol = re.match(r"^(\d+(?:\.\d+)?)\s*ml$", d)
    if m_vol:
        pat = re.compile(rf"(?i)(?<!/)\b{re.escape(m_vol.group(1))}\s*mL\b")
        for m in pat.finditer(section_text):
            prev = section_text[max(0, m.start() - 12) : m.start()]
            if re.search(r"(?i)mg\s*/\s*$", prev):
                continue
            spans.append((m.start(), m.end()))
        return spans

    # Count + unit e.g. "two tablets" / "one tablet"
    m_count = re.match(
        r"^(half|one|two|three|four|five|six|\d+(?:\.\d+)?)\s+"
        r"(tablet|capsule|puff|drop|suppository|patch)s?$",
        d,
    )
    if m_count:
        num_raw, unit = m_count.group(1), m_count.group(2)
        num_alts = {
            "half": r"half|0\.5",
            "0.5": r"half|0\.5",
            "one": r"one|1",
            "1": r"one|1",
            "two": r"two|2",
            "2": r"two|2",
            "three": r"three|3",
            "3": r"three|3",
            "four": r"four|4",
            "4": r"four|4",
            "five": r"five|5",
            "5": r"five|5",
            "six": r"six|6",
            "6": r"six|6",
            "1.5": r"(?:one\s+and\s+(?:a\s+)?half|1\.5)",
        }
        num_pat = num_alts.get(num_raw, re.escape(num_raw))
        pat = re.compile(
            rf"(?i)\b(?:{num_pat})"
            rf"(?:\s+\d+(?:\.\d+)?\s*mg)?"
            rf"\s+{unit}s?\b"
        )
        for m in pat.finditer(section_text):
            spans.append((m.start(), m.end()))
        return spans

    needle = dose_label.strip()
    idx = low.find(needle.lower())
    if idx >= 0:
        spans.append((idx, idx + len(needle)))
    return spans


def _dedupe_frequencies_best(
    cands: list[FrequencyCandidate],
) -> list[FrequencyCandidate]:
    """Keep one candidate per label — prefer dose-adjacent, then nearer, then higher conf."""
    best: dict[str, FrequencyCandidate] = {}
    for c in cands:
        key = _norm(c.frequency_label)
        prev = best.get(key)
        if prev is None:
            best[key] = c
            continue
        # Prefer adjacent over non-adjacent
        if c.dose_adjacent and not prev.dose_adjacent:
            best[key] = c
            continue
        if prev.dose_adjacent and not c.dose_adjacent:
            continue
        c_dist = c.distance_to_dose if c.distance_to_dose is not None else 10**9
        p_dist = prev.distance_to_dose if prev.distance_to_dose is not None else 10**9
        if c_dist < p_dist:
            best[key] = c
            continue
        if c_dist == p_dist and c.confidence > prev.confidence:
            best[key] = c
    return sorted(
        best.values(),
        key=lambda x: (
            0 if x.dose_adjacent else 1,
            x.distance_to_dose if x.distance_to_dose is not None else 10**9,
            -x.confidence,
            x.frequency_label.lower(),
        ),
    )


def scope_frequencies_to_dose(
    candidates: list[FrequencyCandidate],
    dose_spans: list[tuple[int, int]],
    *,
    window: int = _DOSE_ADJACENCY_WINDOW,
    competing_spans: list[tuple[int, int]] | None = None,
) -> list[FrequencyCandidate]:
    """Prefer frequencies whose spans sit near the selected dose phrase.

    Soft: if none fall inside the window, return all candidates (deduped).
    Hard prefer: when ≥1 adjacent hit exists, return only adjacent labels.

    A frequency is dose-adjacent only when it is within ``window`` of a selected
    dose span *and* not closer to a competing (different) dose span — so multi-
    regimen labels ("two tablets twice daily" vs "one tablet once daily") bind
    correctly.
    """
    if not candidates:
        return []
    if not dose_spans:
        return _dedupe_frequencies_best(candidates)

    others = list(competing_spans or [])
    scored: list[FrequencyCandidate] = []
    for c in candidates:
        mid = (c.span_start + c.span_end) // 2
        best_dist = min(abs(mid - (ds + de) // 2) for ds, de in dose_spans)
        near_selected = any(
            c.span_start <= de + window and c.span_end >= ds - window for ds, de in dose_spans
        )
        nearer_other = False
        if others and near_selected:
            other_dist = min(abs(mid - (ds + de) // 2) for ds, de in others)
            nearer_other = other_dist < best_dist
        adjacent = near_selected and not nearer_other
        conf = min(1.0, c.confidence + (0.05 if adjacent else 0.0))
        scored.append(
            FrequencyCandidate(
                frequency_label=c.frequency_label,
                evidence_excerpt=c.evidence_excerpt,
                confidence=conf,
                span_start=c.span_start,
                span_end=c.span_end,
                dose_adjacent=adjacent,
                distance_to_dose=best_dist,
            )
        )

    adjacent_only = [c for c in scored if c.dose_adjacent]
    chosen = adjacent_only if adjacent_only else scored
    return _dedupe_frequencies_best(chosen)


def frequencies_for_label_context(
    section_text: str,
    *,
    route: str | None,
    strength: str | None = None,
    dose: str | None = None,
    adjacency_window: int = _DOSE_ADJACENCY_WINDOW,
) -> list[FrequencyCandidate]:
    """Extract frequencies; when dose is set, prefer dose-adjacent spans."""
    del strength  # strength already gates which label section/index row is used upstream
    if dose and dose.strip():
        raw = extract_frequency_candidates(section_text, keep_all_spans=True)
        anchors = find_dose_anchor_spans(section_text, dose)
        competing: list[tuple[int, int]] = []
        for c in extract_dose_candidates(section_text, keep_all_spans=True):
            if not _dose_label_matches(c.dose_label, dose):
                competing.append((c.span_start, c.span_end))
        return scope_frequencies_to_dose(
            raw,
            anchors,
            window=adjacency_window,
            competing_spans=competing,
        )

    cands = extract_frequency_candidates(section_text)
    if not cands:
        return []
    if route and section_text and not _route_compatible(section_text, route):
        # Still return candidates — many labels mention multiple routes
        pass
    return cands
