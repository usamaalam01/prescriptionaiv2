"""Build HITL verified-indication options from the full medicine catalog.

Uses DrugBank / FDA_NDC / FDA_SPL indication text stored in medicine_catalog.sqlite3.
Decision-support only — pharmacist must confirm.
"""

from __future__ import annotations

import json
import re

from app.services.datasets.catalog_store import catalog_available
from app.services.formulary_catalog import normalize


_BULLET_SPLIT = re.compile(r"[\n•■▪◦●]+")
_HEADER_TRIM = re.compile(
    r"^(?:\d+\s+)?(?:indications?(?:\s*(?:&|and)\s*usage)?|uses?)\s*:?\s*",
    re.I,
)
# FDA SPL cross-refs: ( 14.1 ), [see Clinical Studies (14.1)]
_SPL_CROSSREF_RE = re.compile(
    r"""
    \[\s*see[^\]]*\]
    |
    \(\s*\d+(?:\.\d+)?\s*\)
    |
    \(\s*\d+(?:\.\d+)?\s*$
    |
    \[\s*see\s*$
    """,
    re.I | re.VERBOSE,
)
_GARBAGE_LABEL = re.compile(
    r"(?i)^(directions?|use\(s\)|uses?|adults?\s+and\s+children|do\s+not|"
    r"see\s+(?:overdose|warnings?|clinical)|clean\s+and\s+dry|apply\s+to|"
    r"temporarily|these\s+symptoms|due\s+to|short-term\s+use|"
    r"the\s+common\s+cold|aripiprazole\s+tablets|an?\s+atypical|"
    r"\d+\s+indications?|maintenance\s+of\s+healing\s+of|"
    r"schizophrenia\s*\(|acute\s+treatment\s+of\s*$)\b"
)
# Optional casing aliases only — labels are mined from catalog text, not this list.
_CASING_ALIASES: tuple[str, ...] = (
    "hay fever",
    "upper respiratory allergies",
    "allergic rhinitis",
    "urticaria",
    "GERD",
    "gastroesophageal reflux disease",
    "erosive esophagitis",
    "pathological hypersecretory conditions",
    "duodenal ulcer",
    "gastric ulcer",
    "bacterial infection",
    "type 2 diabetes mellitus",
    "type 2 diabetes",
    "diabetes mellitus",
    "pain",
    "inflammation",
    "headache",
    "toothache",
    "sore throat",
    "common cold",
    "flu",
    "backache",
    "menstrual cramps",
    "muscular aches",
    "minor aches and pains",
    "arthritis",
    "osteoarthritis",
    "schizophrenia",
    "bipolar i disorder",
    "bipolar disorder",
    "major depressive disorder",
    "autistic disorder",
    "tourette's disorder",
    "tourette disorder",
    "irritability associated with autistic disorder",
    "parkinsonism",
    "parkinson's disease",
    "parkinson disease",
    "extrapyramidal disorders",
    "extrapyramidal symptoms",
    "drug-induced extrapyramidal disorders",
    "drug-induced extrapyramidal symptoms",
)

# Clinical noun tails used to mine selectable labels from any catalog indication narrative
_CLINICAL_TAIL = (
    r"disease|disorder|syndrome|infection|ulcer|esophagitis|parkinsonism|"
    r"schizophrenia|diabetes(?:\s+mellitus)?|rhinitis|urticaria|arthritis|"
    r"osteoarthritis|depression|allergies|fever|headache|toothache|"
    r"sore\s+throat|common\s+cold|\bflu\b|backache|inflammation|"
    r"extrapyramidal\s+(?:disorders|symptoms)|reflux\s+disease|"
    r"hypersecretory\s+conditions|manic(?:\s+and\s+mixed)?\s+episodes|"
    r"bipolar\s+i?\s*disorder|autistic\s+disorder|tourette(?:'s)?\s+disorder|"
    r"\bGERD\b|\bpain\b"
)

_CLINICAL_ENTITY_RE = re.compile(
    rf"""
    \b(
      (?:[A-Za-z][A-Za-z0-9'/\-]*(?:\s+|$)){{0,6}}
      (?:{_CLINICAL_TAIL})
    )\b
    """,
    re.I | re.VERBOSE,
)

# Back-compat name used by older call sites / tests
_KNOWN_PHRASES = _CASING_ALIASES


def _strip_spl_noise(text: str) -> str:
    """Remove SPL section cross-references before label extraction."""
    cleaned = _SPL_CROSSREF_RE.sub(" ", text or "")
    cleaned = re.sub(r"[\[\(]\s*$", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _clean_label(text: str) -> str:
    cleaned = " ".join((text or "").replace("\xa0", " ").split())
    cleaned = _SPL_CROSSREF_RE.sub("", cleaned)
    cleaned = _HEADER_TRIM.sub("", cleaned)
    cleaned = re.sub(r"\s+[\[\(].*$", "", cleaned)  # truncate at dangling refs
    cleaned = cleaned.strip(" -:;,.")
    return cleaned


def _is_usable_label(label: str) -> bool:
    item = _clean_label(label)
    if not item or len(item) < 3 or len(item) > 110:
        return False
    if _GARBAGE_LABEL.match(item):
        return False
    if re.search(r"(?i)\bdue to\s*$", item):
        return False
    # Reject incomplete list fragments: "Adjunctive Treatment of", "Irritability Associated with"
    if re.search(r"(?i)\b(?:of|with|for|and|the|to|a|an)\s*$", item):
        return False
    if re.search(r"(?i)^(?:acute|adjunctive|irritability|treatment|maintenance)\b", item):
        # Require a completed clinical phrase, not a bare starter
        if not re.search(
            r"(?i)\b(?:disorder|disease|schizophrenia|depression|esophagitis|"
            r"ulcer|diabetes|episode|syndrome|parkinson|extrapyramidal)\b",
            item,
        ):
            return False
    # Reject incomplete or complete SPL section refs left in the label
    if re.search(r"[\(\[]", item) or re.search(r"(?i)\bsee\s+clinical\b", item):
        return False
    if re.search(r"(?i)\b(?:\d+\.\d+)\b", item) and len(item) < 40:
        return False
    if re.search(
        r"(?i)\b(?:tablet|capsule|every\s+\d+\s+hours|take\s+\d|mg\b|mL\b|"
        r"patch from the film|five days or less|days or less)\b",
        item,
    ) and (len(item) > 30 or "days" in item.lower()):
        return False
    if re.search(r"(?i)\b(?:relieves|reduces|temporarily)\b", item) and len(item.split()) > 3:
        return False
    if item.lower().startswith("indications"):
        return False
    if len(item) > 55:
        if not re.search(
            r"(?i)\b(?:disease|diabetes|ulcer|esophagitis|allergies|syndrome|"
            r"infection|mellitus|hypersecretory|gerd|disorder|depressive|"
            r"schizophrenia|bipolar|autistic|tourette|manic|parkinson|"
            r"extrapyramidal)\b",
            item,
        ):
            return False
    if len(item) > 90 and item.count(" ") > 12:
        return False
    return True


def _mine_clinical_entities(text: str) -> list[str]:
    """Mine short clinical condition labels from catalog narrative (any drug)."""
    out: list[str] = []
    for m in _CLINICAL_ENTITY_RE.finditer(text or ""):
        item = _clean_label(m.group(1))
        # Drop leading filler words from SPL prose
        item = re.sub(
            r"(?i)^(?:all\s+forms\s+of|forms\s+of|use\s+as\s+an\s+adjunct\s+in\s+|"
            r"an?\s+adjunct\s+in\s+|therapy\s+of|treatment\s+of|management\s+of|"
            r"control\s+of|for|the|and|or|with|due\s+to)\s+",
            "",
            item,
        ).strip()
        item = re.sub(
            r"(?i)^(?:all\s+forms\s+of|forms\s+of|therapy\s+of|treatment\s+of|"
            r"management\s+of|control\s+of)\s+",
            "",
            item,
        ).strip()
        if _is_usable_label(item):
            out.append(item)
    return out


def _split_treatment_list(blob: str) -> list[str]:
    """Split 'Schizophrenia Acute Treatment of Manic...' style lists."""
    text = _strip_spl_noise(blob)
    if not text:
        return []
    # Break before common indication list starters
    parts = re.split(
        r"(?=\b(?:Acute Treatment|Adjunctive Treatment|Irritability Associated|"
        r"Treatment of Tourette|Maintenance of|Schizophrenia|Bipolar|"
        r"Major Depressive|Autistic Disorder)\b)",
        text,
        flags=re.I,
    )
    out: list[str] = []
    for part in parts:
        item = _clean_label(part)
        if not item:
            continue
        # Prefer short disease name when phrase is a single clinical entity
        short = _mine_clinical_entities(item)
        if short and len(short[0]) <= 40 and len(item) > len(short[0]) + 10:
            out.extend(short[:3])
            continue
        if _is_usable_label(item):
            out.append(item)
    out.extend(_mine_clinical_entities(text))
    return out


def _extract_labels(indication: str | None) -> list[str]:
    """Derive short selectable indication labels from catalog narrative text.

    Catalog-first: mine FDA_SPL / DrugBank prose with clinical patterns.
    No per-drug hardcoding — works for any medicine with indication text.
    """
    if not indication:
        return []
    raw = (
        indication.replace("\u25a0", " ")
        .replace("■", "\n")
        .replace("•", "\n")
        .replace("●", "\n")
    )
    text = _strip_spl_noise(raw)
    labels: list[str] = []

    # OTC: "reduces fever" / "relieves minor aches and pains"
    for m in re.finditer(
        r"(?:temporarily\s+)?(?:relieves|reduces)\s+"
        r"((?:(?!\b(?:due\s+to|relieves|reduces|temporarily)\b)[^\n.•;]){3,60})",
        text,
        re.I,
    ):
        item = _clean_label(m.group(1))
        item = re.sub(r"\bdue to\s*:?\s*.*$", "", item, flags=re.I).strip(" -:;")
        if item.lower() not in {"temporarily"} and _is_usable_label(item):
            labels.append(item)

    due = re.search(
        r"(?:symptoms\s+)?due to\s+([^:\n]+):\s*(.+)$",
        text,
        re.I | re.S,
    )
    if due:
        condition = _clean_label(due.group(1))
        if _is_usable_label(condition):
            labels.append(condition)
        for part in _BULLET_SPLIT.split(due.group(2)):
            item = _clean_label(part)
            item = re.sub(r"^uses?\s+temporarily\s+", "", item, flags=re.I)
            if _is_usable_label(item):
                labels.append(item)

    for part in _BULLET_SPLIT.split(raw):
        item = _clean_label(_strip_spl_noise(part))
        item = re.sub(r"^(?:reduces|relieves|for)\s+", "", item, flags=re.I).strip()
        if _is_usable_label(item) and 3 <= len(item) <= 60:
            labels.append(item)

    # "indicated for …" / "indicated in the treatment of …" (any drug)
    for m in re.finditer(
        r"indicated(?:\s+(?:to\s+be\s+used|for\s+use|as\s+an\s+adjunct)[^.]*?)?\s+"
        r"(?:for(?:\s+the\s+(?:treatment|management|short-term[^.]{0,40}management)\s+of)?|"
        r"in\s+(?:the\s+)?(?:treatment|management|therapy)\s+of)\s*:?\s*(.+?)(?="
        r"(?:\.?\s*[A-Z][a-z]+\s+tablets?\s+are\s+an?\s+atypical)"
        r"|(?:\.?\s*\d+\s+[A-Z])"
        r"|(?:\Z))",
        text,
        re.I | re.S,
    ):
        chunk = _clean_label(m.group(1))
        chunk = re.sub(
            r"(?i)^(?:use\s+as\s+an\s+adjunct\s+in\s+the\s+therapy\s+of\s+"
            r"|an?\s+adjunct\s+in\s+the\s+therapy\s+of\s+|all\s+forms\s+of\s+)",
            "",
            chunk,
        ).strip()
        labels.extend(_split_treatment_list(chunk))
        if _is_usable_label(chunk) and len(chunk) <= 80:
            labels.append(chunk)

    # Generic adjunct / therapy / control phrasing from SPL
    for m in re.finditer(
        r"(?:adjunct(?:ive)?\s+)?(?:in\s+)?(?:the\s+)?therapy\s+of\s+"
        r"(?:all\s+forms\s+of\s+)?([^.;\n]{3,80})",
        text,
        re.I,
    ):
        item = _clean_label(m.group(1))
        item = re.sub(r"\b(?:useful|also|in\s+the\s+control).*$", "", item, flags=re.I).strip()
        if _is_usable_label(item):
            labels.append(item)

    for m in re.finditer(
        r"(?:control|management|treatment)\s+of\s+"
        r"([^.;\n(]{3,60}?)(?:\s*\(|\s+due\s+to|\s+except|\.|$)",
        text,
        re.I,
    ):
        item = _clean_label(m.group(1))
        if _is_usable_label(item):
            labels.append(item)

    # Mine clinical entities from full narrative (catalog-driven for any drug)
    labels.extend(_mine_clinical_entities(text))

    # Optional casing aliases when the phrase appears verbatim
    for phrase in _CASING_ALIASES:
        if re.search(rf"\b{re.escape(phrase)}\b", text, re.I):
            labels.append(phrase)
    if re.search(r"(?<!hay )\bfever\b", text, re.I):
        labels.append("fever")

    if not labels:
        clipped = _clean_label(text[:220])
        if _is_usable_label(clipped) and len(clipped) >= 12:
            labels.append(clipped[:110])

    by_key: dict[str, str] = {}
    for label in labels:
        if not _is_usable_label(label):
            continue
        key = normalize(label)
        if not key or len(key) < 3:
            continue
        preferred = next((p for p in _CASING_ALIASES if normalize(p) == key), None)
        if preferred:
            value = preferred[0].upper() + preferred[1:] if preferred[0].islower() else preferred
            if preferred.lower() == "gerd":
                value = "GERD"
            elif preferred.lower() == "schizophrenia":
                value = "Schizophrenia"
        else:
            # Title-case short mined entities
            value = label[0].upper() + label[1:] if label and label[0].islower() else label
        if key not in by_key or len(value) < len(by_key[key]):
            by_key[key] = value
    return sorted(by_key.values(), key=lambda s: (len(s) > 40, s.lower()))[:15]


def _combo_penalty(canonical_name: str) -> int:
    nm = (canonical_name or "").lower()
    if " and " in nm or "," in nm or "/" in nm:
        return 1
    return 0


def catalog_indication_options(drug_name: str | None) -> list[dict]:
    """Return indication options with FDA/DrugBank source tags from the SQLite catalog."""
    if not drug_name or not catalog_available():
        return []
    key = normalize(drug_name)
    if not key:
        return []

    from app.services.datasets.catalog_store import _connect, list_label_sections

    try:
        conn = _connect()
    except Exception:  # noqa: BLE001
        return []
    try:
        rows = conn.execute(
            """
            SELECT m.id, m.canonical_name, m.indication, m.sources, m.drugbank_id, m.product_ndc
            FROM medicines m
            JOIN aliases a ON a.medicine_id = m.id
            WHERE a.alias_key = ?
            ORDER BY
              CASE WHEN lower(m.canonical_name) = ? THEN 0 ELSE 1 END,
              CASE
                WHEN lower(m.canonical_name) LIKE '% and %' OR m.canonical_name LIKE '%,%' THEN 1
                ELSE 0
              END,
              length(m.canonical_name),
              CASE WHEN m.indication IS NOT NULL AND length(m.indication) > 0 THEN 0 ELSE 1 END
            LIMIT 12
            """,
            (key, key),
        ).fetchall()
    finally:
        conn.close()

    by_value: dict[str, dict] = {}

    def _add_from_text(
        indication: str | None,
        *,
        sources: list[str],
        record_ids: list[str],
        prefer: bool,
    ) -> None:
        if not indication:
            return
        for label in _extract_labels(indication):
            k = normalize(label)
            if not k:
                continue
            if k not in by_value:
                by_value[k] = {
                    "value": label,
                    "sources": list(dict.fromkeys(sources)),
                    "source_record_ids": list(dict.fromkeys(record_ids))[:4],
                    "_prefer": prefer,
                }
            else:
                for src in sources:
                    if src not in by_value[k]["sources"]:
                        by_value[k]["sources"].append(src)
                for rid in record_ids:
                    if rid not in by_value[k]["source_record_ids"]:
                        by_value[k]["source_record_ids"].append(rid)
                by_value[k]["source_record_ids"] = by_value[k]["source_record_ids"][:4]
                if prefer:
                    by_value[k]["_prefer"] = True
                    if len(label) < len(by_value[k]["value"]):
                        by_value[k]["value"] = label

    for row in rows:
        try:
            sources_raw = json.loads(row["sources"] or "[]")
        except json.JSONDecodeError:
            sources_raw = []
        mapped: list[str] = []
        for src in sources_raw:
            s = str(src).upper()
            if "DRUGBANK" in s:
                mapped.append("DrugBank")
            elif "SPL" in s:
                mapped.append("FDA_SPL")
            elif "NDC" in s:
                mapped.append("FDA_NDC")
        if not mapped:
            mapped = ["FDA_SPL"]
        record_ids = [
            x
            for x in (row["drugbank_id"], row["product_ndc"], row["canonical_name"])
            if x
        ]
        prefer = _combo_penalty(row["canonical_name"]) == 0
        _add_from_text(
            row["indication"],
            sources=mapped,
            record_ids=record_ids,
            prefer=prefer,
        )
        try:
            sections = list_label_sections(int(row["id"]))
        except Exception:  # noqa: BLE001
            sections = {}
        section_text = (sections.get("indications_and_usage") or "").strip()
        if section_text and section_text != (row["indication"] or "").strip():
            _add_from_text(
                section_text,
                sources=list(dict.fromkeys(mapped + ["FDA_SPL"])),
                record_ids=record_ids,
                prefer=prefer,
            )

    items = list(by_value.values())
    items.sort(
        key=lambda item: (
            0 if item.get("_prefer") else 1,
            len(item["value"]) > 50,
            item["value"].lower(),
        )
    )
    out: list[dict] = []
    for item in items[:15]:
        item.pop("_prefer", None)
        out.append(item)
    return out
