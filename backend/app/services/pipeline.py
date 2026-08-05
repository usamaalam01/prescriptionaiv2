"""Multi-stage prescription interpretation pipeline (Milestone 3+).

Stages (in order):
1. OCR stack: Paddle detect → Google Vision primary → TrOCR on low-conf crops
2. Line merge / candidate view for HITL audit
3. Constrained medical parser (structured fields from OCR lines)
4. Catalog / seed formulary validation (top candidates; never silent auto-pick)
5. Pharmacist verification (Human-in-the-Loop)

Heavy ML runtimes are optional. When unavailable, adapters return clearly labelled MOCK
outputs so the academic prototype remains runnable on Windows without GPU stacks.
Decision-support prototype only — not clinical care.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field

from app.services.formulary_catalog import SEED_FORMULARY, normalize as _normalize, resolve_drug
from app.services.ocr.engines import run_ocr_stack
from app.services.ocr.privacy import (
    find_rx_clinical_start,
    has_clinical_cue,
    is_pii_or_admin_line,
    looks_like_pii_drug_name,
    redact_ocr_text,
    strip_trailing_strength_digits,
)

UNCERTAIN_THRESHOLD = 0.78


@dataclass
class LineCandidate:
    line_id: str
    text: str
    confidence: float
    engine: str
    bbox: list[float] | None = None
    is_mock: bool = True
    source_stage: str = "paddleocr"


@dataclass
class MergedLine:
    line_id: str
    selected_text: str
    selected_engine: str
    selected_confidence: float
    candidates: list[LineCandidate]
    conflict: bool
    used_trocr_retry: bool


@dataclass
class ParsedMedicine:
    item_number: int
    medicine_name: str
    strength: str | None
    form: str | None
    dose: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    source_span: str
    parser_confidence: float
    parser_name: str
    is_mock: bool


@dataclass
class FormularyCheck:
    medicine_name: str
    matched: bool
    formulary_id: str | None
    allowed_strengths: list[str]
    allowed_forms: list[str]
    allowed_routes: list[str]
    strength_ok: bool | None
    form_ok: bool | None
    route_ok: bool | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    pipeline_id: str
    raw_text: str
    overall_ocr_confidence: float
    processing_ms: int
    paddle_lines: list[LineCandidate]
    trocr_retries: list[LineCandidate]
    merged_lines: list[MergedLine]
    parsed_medicines: list[ParsedMedicine]
    formulary_checks: list[FormularyCheck]
    warnings: list[str]
    stages_used: list[str]
    is_mock: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


class PaddleOcrAdapter:
    """Detection + recognition. Uses real PaddleOCR when installed; otherwise MOCK."""

    name = "paddleocr"

    def detect_and_recognize(self, image_bytes: bytes) -> list[LineCandidate]:
        real = self._try_real(image_bytes)
        if real is not None:
            return real
        return self._mock(image_bytes)

    def _try_real(self, image_bytes: bytes) -> list[LineCandidate] | None:
        try:
            from paddleocr import PaddleOCR  # type: ignore
            import numpy as np
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            arr = np.array(image)
            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            raw = ocr.ocr(arr, cls=True)
            lines: list[LineCandidate] = []
            for block in raw or []:
                for item in block or []:
                    box, (text, conf) = item
                    flat = [float(x) for pt in box for x in pt]
                    lines.append(
                        LineCandidate(
                            line_id=str(uuid.uuid4()),
                            text=str(text),
                            confidence=float(conf),
                            engine=self.name,
                            bbox=flat,
                            is_mock=False,
                            source_stage="paddleocr",
                        )
                    )
            return lines or None
        except Exception:
            return None

    def _mock(self, image_bytes: bytes) -> list[LineCandidate]:
        # Demo Rx for HITL when Vision is unavailable — labelled MOCK (Confirm blocked by default).
        # Includes a handwritten-style misspelling (arcabose) for pharmacist correction.
        samples = [
            ("SYNTHETIC PRESCRIPTION — NO REAL PATIENT DATA", 0.96),
            ("Prescriber: Dr. A. Example  Reg: EX-0001", 0.91),
            ("Patient ref: ANON-1001  Age: 45  Sex: F", 0.89),
            ("1. Arcabose 50 mg tablets", 0.58),  # OCR misspelling of Acarbose
            ("Take ONE tablet THREE times daily with meals", 0.72),
            ("Route: Oral", 0.93),
            ("2. Pantoprazole 40 mg tablets", 0.86),
            ("Take ONE tablet ONCE daily before breakfast", 0.84),
            ("Route: Oral", 0.94),
            ("3. Cetirizine 10 mg tablets", 0.88),
            ("Take ONE tablet ONCE daily", 0.85),
            ("Route: Oral", 0.92),
            ("4. Acetaminophen 500 mg tablets", 0.80),
            ("Take TWO tablets every 6 hours as required", 0.78),
            ("Route: Oral", 0.93),
        ]
        noise = len(image_bytes) % 5
        lines: list[LineCandidate] = []
        for idx, (text, conf) in enumerate(samples):
            lines.append(
                LineCandidate(
                    line_id=f"paddle-{idx}",
                    text=text if idx != 3 else f"{text} [n={noise}]",
                    confidence=max(0.45, conf - (noise * 0.01)),
                    engine=self.name,
                    bbox=[10, 20 + idx * 28, 600, 44 + idx * 28],
                    is_mock=True,
                    source_stage="paddleocr",
                )
            )
        return lines


class TrocrRetryAdapter:
    """Retry uncertain lines with TrOCR. Real transformers model optional."""

    name = "trocr"

    def retry_line(self, image_bytes: bytes, line: LineCandidate) -> LineCandidate:
        real = self._try_real(image_bytes, line)
        if real is not None:
            return real
        corrected = line.text
        if "Amoxycillin" in corrected:
            corrected = corrected.replace("Amoxycillin", "Amoxicillin")
        # Strip mock noise markers — leave misspellings (e.g. Arcabose) for HITL catalog suggest
        if " [n=" in corrected:
            corrected = corrected.split(" [n=")[0]
        conf = min(0.93, line.confidence + 0.25) if "Amoxicillin" in corrected else min(0.90, line.confidence + 0.12)
        return LineCandidate(
            line_id=f"trocr-{line.line_id}",
            text=corrected,
            confidence=conf,
            engine=self.name,
            bbox=line.bbox,
            is_mock=True,
            source_stage="trocr_retry",
        )

    def _try_real(self, image_bytes: bytes, line: LineCandidate) -> LineCandidate | None:
        try:
            from app.core.config import settings
            from app.services.ocr.engines import trocr_recognize_crop
        except Exception:  # noqa: BLE001
            return None
        if not settings.ENABLE_TROCR_RETRY:
            return None
        result = trocr_recognize_crop(image_bytes, line.bbox)
        if result is None or not result.text:
            return None
        return LineCandidate(
            line_id=f"trocr-{line.line_id}",
            text=result.text,
            confidence=float(result.confidence),
            engine=self.name,
            bbox=result.bbox or line.bbox,
            is_mock=False,
            source_stage="trocr_retry",
        )


class CandidateMerger:
    """Merge Paddle + TrOCR candidates with confidence-weighted selection."""

    def merge(
        self,
        paddle_lines: list[LineCandidate],
        trocr_retries: dict[str, LineCandidate],
    ) -> list[MergedLine]:
        merged: list[MergedLine] = []
        for line in paddle_lines:
            candidates = [line]
            used_retry = False
            if line.line_id in trocr_retries:
                candidates.append(trocr_retries[line.line_id])
                used_retry = True
            best = max(candidates, key=lambda c: c.confidence)
            conflict = len({c.text.strip().lower() for c in candidates}) > 1
            merged.append(
                MergedLine(
                    line_id=line.line_id,
                    selected_text=best.text,
                    selected_engine=best.engine,
                    selected_confidence=best.confidence,
                    candidates=candidates,
                    conflict=conflict,
                    used_trocr_retry=used_retry,
                )
            )
        return merged


_STRENGTH_RE = re.compile(
    r"(?P<strength>\d+(?:\.\d+)?\s*(?:mg|g|mcg|micrograms?(?:\s*/\s*actuation)?|%))",
    re.I,
)
# OCR often truncates "625 mg" → "625 m" or splits "625" / "mg ."
_STRENGTH_TRUNC_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*m\b\.?", re.I)
_FORM_RE = re.compile(
    r"\b(?P<form>capsules?|tabs?\.?|tablets?|caps?\.?|inhaler|aerosol|suspension|syrup|cream|ointment)\b",
    re.I,
)
_FORM_ONLY_RE = re.compile(
    r"^\s*(?:capsules?|tabs?\.?|tablets?|caps?\.?|inhaler|aerosol|suspension|syrup|cream|ointment)\s*\.?\s*$",
    re.I,
)
_ITEM_RE = re.compile(
    # "1. Amoxicillin" / "1) Drug" / Vision often drops the dot: "1 Amoxicillin"
    r"^\s*(?P<item>\d{1,2})\s*(?:[.)]\s*|\s+)(?P<body>[A-Z][A-Za-z].*)$"
)
# Vision sometimes glues two Rx items onto one line:
# "... for 7 days 2. Ibuprofen 400mg ..."
_MERGED_ITEM_SPLIT_RE = re.compile(
    r"(?<=\S)\s+(?=\d{1,2}\s*(?:[.)]\s*|\s+)[A-Z][A-Za-z])"
)
_STRENGTH_ONLY_RE = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*(?:mg|g|mcg|%)?\s*$",
    re.I,
)
_CLINICAL_INTERRUPT_RE = re.compile(
    r"^(?:allerg(?:y|ies)\b|nkda\b|nka\b|name\s*:|age\b|wt\b|weight\b|date\s*:|opd\b|rx$)",
    re.I,
)
_HEADER_FOOTER_RE = re.compile(
    r"^(?:health\s*care|life\s*care|city\s+care|care\s+clinic|general\s*physician|consultant\s*physic|"
    r"patient\s*name|age\s*/?\s*gender|weight|address|phone|opd\s*no|date\s*:|rx$|"
    r"drink\s+plenty|avoid\s+|take\s+medicines\s+regularly|follow\s+up|dr\.?\s|mbbs|fcps|"
    r"reg\.?\s*no|test\s+patient|demo\s+patient|"
    r"\d+\s*y(?:ears?)?\s*/\s*(?:male|female|m|f)\b)",
    re.I,
)
_SIG_START_RE = re.compile(r"^(?:take|inhale|apply)\b", re.I)
_ROUTE_LINE_RE = re.compile(r"^route\s*:\s*", re.I)
# Vision often splits SIG onto its own line: "ONE", "ONE tablet", "THREE times daily"
_SIG_FRAGMENT_RE = re.compile(
    r"""(?ix)^
        (?:
            (?:one|two|three|four|five|six|1|2|3|4|5|6)
            (?:\s+or\s+(?:one|two|three|1|2|3))?
            \s+(?:tablet|tablets|capsule|capsules|puff|puffs|drop|drops)s?
          | (?:one|two|three|four|five|six|1|2|3|4|5|6)\s*$
          | (?:once|twice|thrice|
              (?:one|two|three|four)\s+times|
              \d+\s*times
            )\s+(?:a\s+)?daily
          | (?:three|four|two|one)\s+times\s+daily
          | every\s+\d+(?:\s*(?:to|-)\s*\d+)?\s+hours?
          | \d+\s+hours?
          | (?:before|after)\s+(?:food|meals?|breakfast)
          | (?:as|when)\s+required
          | with\s+meals?
        )
        (?:\s+(?:as|when)\s+required)?
        (?:\s+with\s+meals?)?
        (?:\s+after\s+(?:food|meals?))?
        \s*$
    """,
)
_COUNT_WORD_RE = re.compile(
    r"^(?:one|two|three|four|five|six|half|once|twice|thrice|times|every)$",
    re.I,
)
# Pad / Vision fragments: "Ind:", "Indication:", "Every", "Pains", "Uses"
_LABEL_FRAGMENT_RE = re.compile(
    r"""(?ix)^
        (?:
            ind(?:ication)?s?
          | uses?
          | symptoms?
          | directions?
          | every
          | pains?
          | headache
          | fever
          | allergy|allergies
          | notes?
          | sig
          | qty|quantity
          | refills?
          | diagnosis
          | dx
        )
        \s*:?\s*$
    """,
)
_BAD_DRUG_NAME_RE = re.compile(
    r"^(?:for|at|before|after|avoid|if|once|twice|thrice|take|with|and|&|oily|spicy|food|days?|night|"
    r"daily|hourly|orally|fever|pains?|plenty|water|follow|drink|regularly|medicines|"
    r"one|two|three|four|five|six|half|times|every|ind|indication|indications|uses?|symptoms?|"
    r"directions?|headache|notes?|sig|qty|quantity|refills?|diagnosis|dx|advice|clinical|"
    r"diabetes|mellitus|hypertension|hyperlipid(?:a)?emia|"
    r"male|female|patient|clinic|physician|hospital|allerg(?:y|ies)|nkda|nka|tab|tabs|cap|caps|"
    r"mg|po|bd|tds|od|hs|tid|qid|demo|test|care|city|general|opd|reg|route|oral|inhalation)\b",
    re.I,
)


class MedicalParserAdapter:
    """Structured medical parser.

    Preferred future backend: Qwen2.5-VL.
    Current default: multi-line Rx block extractor (Vision often splits name/strength/form/sig).
    Never uses free-form LLM as clinical source of truth.
    """

    name = "constrained-ocr-line-parser"

    def parse(self, merged_lines: list[MergedLine]) -> tuple[str, list[ParsedMedicine], list[str]]:
        raw_text = "\n".join(line.selected_text for line in merged_lines)
        warnings = [
            "Parser stage uses a constrained multi-line Rx extractor over OCR lines. "
            "Output is decision-support only — not clinical truth.",
            "PII/admin lines (patient, clinic, OPD, prescriber) are excluded from medicine extraction.",
        ]
        # Pre-merge Vision fragments: "500"+"mg" -> "500 mg"; "40"+"Tablet"+"mg" -> "40 mg" + form
        tokens: list[tuple[str, float, bool]] = []
        for line in merged_lines:
            text = " ".join((line.selected_text or "").split()).strip()
            if not text:
                continue
            tokens.append(
                (
                    text,
                    line.selected_confidence,
                    all(c.is_mock for c in line.candidates) if line.candidates else True,
                )
            )
        lines = self._premerge_fragments(tokens)
        # Vision may merge "1. Amox… 2. Ibu…" onto one line — explode before focus/parse
        lines = self._explode_merged_item_lines(lines)
        # Best practice: focus after Rx marker / first numbered item when present
        lines = self._focus_rx_region(lines)

        medicines: list[ParsedMedicine] = []
        i = 0
        while i < len(lines):
            text, conf, is_mock = lines[i]
            if self._is_noise_line(text) or is_pii_or_admin_line(text):
                i += 1
                continue

            m_item = _ITEM_RE.match(text)
            starts_item = m_item is not None
            starts_drug = (not starts_item) and self._looks_like_drug_name(text)

            if not starts_item and not starts_drug:
                # Orphan sig / strength for previous medicine (including after Allergies interrupt)
                if medicines:
                    if (
                        _SIG_START_RE.match(text)
                        or _SIG_FRAGMENT_RE.match(text)
                        or _LABEL_FRAGMENT_RE.match(text.strip(" .:;-–—"))
                        or "hourly" in text.lower()
                        or "orally" in text.lower()
                        or re.search(r"\b(?:po|bd|tds|od|hs|tid|qid)\b", text, re.I)
                        or re.search(r"\b(?:times\s+daily|once\s+daily|twice\s+daily)\b", text, re.I)
                    ):
                        # Label headers (Ind:) are skipped; SIG fragments enrich prior row
                        if not _LABEL_FRAGMENT_RE.match(text.strip(" .:;-–—")):
                            self._enrich_sig(medicines[-1], text)
                    elif (
                        _STRENGTH_RE.search(text)
                        or _STRENGTH_TRUNC_RE.search(text)
                        or _FORM_ONLY_RE.match(text)
                        or _STRENGTH_ONLY_RE.match(text)
                        or re.fullmatch(r"mg\.?", text, re.I)
                    ):
                        repaired = _STRENGTH_TRUNC_RE.sub(r"\g<num> mg", text)
                        self._enrich_strength_form(medicines[-1], repaired)
                i += 1
                continue

            # Numbered SIG-only / label-only lines — look ahead for the real drug name
            if starts_item:
                body_chk = (m_item.group("body") or "").strip() if m_item else ""
                if body_chk and (
                    _SIG_FRAGMENT_RE.match(body_chk)
                    or _SIG_START_RE.match(body_chk)
                    or _ROUTE_LINE_RE.match(body_chk)
                    or _LABEL_FRAGMENT_RE.match(body_chk.strip(" .:;-–—"))
                    or _COUNT_WORD_RE.match(body_chk.strip(" .:;-–—"))
                ):
                    # Vision often emits "4. Ind:" then "Acetaminophen 500 mg" on later lines
                    looked_ahead = False
                    for k in range(i + 1, min(i + 6, len(lines))):
                        nxt, nconf, nmock = lines[k]
                        if _ITEM_RE.match(nxt):
                            break
                        if self._looks_like_drug_name(nxt) and not _LABEL_FRAGMENT_RE.match(
                            nxt.strip(" .:;-–—")
                        ):
                            # Re-parse this item starting at the drug line
                            item_no = int(m_item.group("item"))
                            block = [nxt]
                            j = k + 1
                            while j < len(lines):
                                nxt2, _, _ = lines[j]
                                if _ITEM_RE.match(nxt2):
                                    break
                                if (
                                    self._is_advice_or_footer(nxt2)
                                    or _CLINICAL_INTERRUPT_RE.match(nxt2)
                                    or is_pii_or_admin_line(nxt2)
                                ):
                                    break
                                if self._looks_like_drug_name(nxt2) and not _STRENGTH_RE.search(nxt2):
                                    break
                                block.append(nxt2)
                                j += 1
                            med = self._parse_rx_block(item_no, block, nconf, nmock)
                            if med is not None:
                                medicines.append(med)
                            looked_ahead = True
                            i = j
                            break
                    if looked_ahead:
                        continue
                    if medicines and not _LABEL_FRAGMENT_RE.match(body_chk.strip(" .:;-–—")):
                        self._enrich_sig(medicines[-1], body_chk)
                    i += 1
                    continue

            item_no = int(m_item.group("item")) if m_item else (len(medicines) + 1)
            body = (m_item.group("body") or "").strip() if m_item else text
            body = body.lstrip(".-–— \t")
            # Numbered empty body (e.g. "3 )") — wait for following drug line
            if starts_item and not body:
                i += 1
                continue
            if starts_item and body and (
                is_pii_or_admin_line(body) or looks_like_pii_drug_name(body)
            ):
                i += 1
                continue

            block: list[str] = [body] if body else ([] if starts_item else [text])
            if starts_drug and not starts_item:
                block = [text]

            j = i + 1
            while j < len(lines):
                nxt, _, _ = lines[j]
                if _ITEM_RE.match(nxt):
                    break
                if (
                    self._is_advice_or_footer(nxt)
                    or _CLINICAL_INTERRUPT_RE.match(nxt)
                    or is_pii_or_admin_line(nxt)
                ):
                    # Do not absorb Allergies / NKDA / demographics / PII into the drug block
                    break
                if self._is_noise_line(nxt) and not (
                    _STRENGTH_RE.search(nxt)
                    or _STRENGTH_TRUNC_RE.search(nxt)
                    or _FORM_ONLY_RE.match(nxt)
                    or _STRENGTH_ONLY_RE.match(nxt)
                ):
                    j += 1
                    continue
                # Next unnumbered drug name (e.g. Paracetamol after item 1 block)
                if (
                    block
                    and self._block_has_drug_name(block)
                    and self._looks_like_drug_name(nxt)
                    and not _STRENGTH_RE.search(nxt)
                    and not _STRENGTH_TRUNC_RE.search(nxt)
                ):
                    break
                block.append(nxt)
                j += 1

            med = self._parse_rx_block(item_no, block, conf, is_mock)
            if med is not None:
                medicines.append(med)
            elif starts_item and body:
                # Itemised drug with delayed/broken strength (e.g. Augmentin … 625 m) — still emit HITL row
                rescue = self._rescue_item_drug(item_no, body, block, conf, is_mock)
                if rescue is not None:
                    medicines.append(rescue)
            # Pull strength/sig that appear after clinical interrupts (Allergies/NKDA) before next item
            if medicines and j < len(lines):
                k = j
                while k < len(lines):
                    nxt, _, _ = lines[k]
                    if _ITEM_RE.match(nxt):
                        break
                    if self._is_advice_or_footer(nxt) or is_pii_or_admin_line(nxt):
                        break
                    if _CLINICAL_INTERRUPT_RE.match(nxt) or self._is_noise_line(nxt):
                        k += 1
                        continue
                    if self._looks_like_drug_name(nxt) and not (
                        _STRENGTH_RE.search(nxt) or _STRENGTH_TRUNC_RE.search(nxt) or _FORM_ONLY_RE.match(nxt)
                    ):
                        break
                    repaired = _STRENGTH_TRUNC_RE.sub(r"\g<num> mg", nxt)
                    if (
                        _STRENGTH_RE.search(repaired)
                        or _FORM_ONLY_RE.match(nxt)
                        or _STRENGTH_ONLY_RE.match(nxt)
                        or re.fullmatch(r"mg\.?", nxt, re.I)
                        or re.search(r"\b(?:po|bd|tds|od|hs|tab)\b", nxt, re.I)
                    ):
                        self._enrich_strength_form(medicines[-1], repaired)
                        self._enrich_sig(medicines[-1], repaired)
                        k += 1
                        continue
                    break
                j = max(j, k)
            i = j

        # Final privacy gate: never emit PII/admin or SIG fragments as medicines
        before = len(medicines)
        medicines = [
            m
            for m in medicines
            if not looks_like_pii_drug_name(m.medicine_name)
            and not _SIG_FRAGMENT_RE.match(m.medicine_name or "")
            and not _LABEL_FRAGMENT_RE.match((m.medicine_name or "").strip(" .:;-–—"))
            and not _COUNT_WORD_RE.match(m.medicine_name or "")
            and not _BAD_DRUG_NAME_RE.match(m.medicine_name or "")
        ]
        if before and len(medicines) < before:
            warnings.append(
                f"Dropped {before - len(medicines)} non-medicine row(s) (PII/admin/SIG filter)."
            )

        # Recover drugs present in OCR text but missed when Vision split Ind:/SIG first
        recovered = self._recover_missed_catalog_drugs(lines, medicines)
        if recovered:
            medicines.extend(recovered)
            warnings.append(
                f"Recovered {len(recovered)} medicine name(s) from OCR lines after SIG/label fragments."
            )

        if not medicines:
            warnings.append("No medicine lines extracted from OCR text; pharmacist manual entry required.")
        else:
            # Re-number sequentially for HITL readability when OCR item markers were sparse
            for idx, med in enumerate(medicines, start=1):
                med.item_number = idx

        # Privacy-safe transcript for persistence / HITL audit panels
        return redact_ocr_text(raw_text), medicines, warnings

    def _recover_missed_catalog_drugs(
        self,
        lines: list[tuple[str, float, bool]],
        medicines: list[ParsedMedicine],
    ) -> list[ParsedMedicine]:
        """If OCR still contains a catalog drug not yet parsed, emit a HITL row.

        Production path: catalog fuzzy/abbrev suggest per clinical line (not exact
        substring only), so Amoxcillin/Amoxycillin/Cetrizine still recover.
        """
        have = {_normalize(m.medicine_name) for m in medicines}
        recovered: list[ParsedMedicine] = []
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.match import suggest_medicines
        except Exception:  # noqa: BLE001
            catalog_available = lambda: False  # type: ignore
            suggest_medicines = None  # type: ignore

        # OCR misspellings → canonical (exact-substring fallback when catalog DB cold)
        ocr_alias_targets = (
            ("amoxicillin", ("amoxicillin", "amoxycillin", "amoxcillin", "amoxcilin")),
            ("ibuprofen", ("ibuprofen", "ibrufen", "brufen")),
            ("cetirizine", ("cetirizine", "cetrizine", "ceterizine", "cetirizin")),
            ("pantoprazole", ("pantoprazole", "pantoprazol", "pantoprozole")),
            ("metformin", ("metformin", "metformine")),
            ("acetaminophen", ("acetaminophen", "paracetamol", "acetaminophe")),
            ("acarbose", ("acarbose", "arcabose", "acarbos")),
        )

        for text, conf, is_mock in lines:
            low = text.lower()
            if _LABEL_FRAGMENT_RE.match(text.strip(" .:;-–—")):
                continue
            if _SIG_FRAGMENT_RE.match(text) or _SIG_START_RE.match(text):
                continue
            # Skip patient / letterhead / advice / diagnosis — never invent drug rows
            if is_pii_or_admin_line(text) or self._is_advice_or_footer(text):
                continue
            if re.match(
                r"^(?:patient\s*name|age\s*/?\s*gender|opd\s*no|date\s*:|city care|general physician|advice\s*:|dr\.?\s)",
                low,
            ):
                continue

            body = text
            m_item = _ITEM_RE.match(text)
            if m_item:
                body = (m_item.group("body") or text).strip()
            if is_pii_or_admin_line(body) or looks_like_pii_drug_name(body):
                continue

            display: str | None = None
            # 1) Catalog suggest on the drug-leading phrase
            hint = re.split(r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml)\b", body, maxsplit=1, flags=re.I)[0]
            hint = re.sub(r"^[\d]+[.)]\s*", "", hint).strip(" -–—:")
            if (
                not hint
                or len(hint) < 4
                or _BAD_DRUG_NAME_RE.match(hint)
                or looks_like_pii_drug_name(hint)
                or _SIG_START_RE.match(hint)
                or _SIG_FRAGMENT_RE.match(hint)
            ):
                hint = ""
            if suggest_medicines is not None and catalog_available() and hint:
                hits = suggest_medicines(hint, top_k=5, min_score=85.0)
                hint_key = _normalize(hint)
                for h in hits:
                    cand = h.canonical_name
                    if self._recovery_already_covered(have, cand, hint_key):
                        continue
                    if _BAD_DRUG_NAME_RE.match(cand) or looks_like_pii_drug_name(cand):
                        continue
                    # Prefer exact/near-exact over combo expansions (Amoxicillin ≠ amox+clav)
                    if _normalize(cand) == hint_key or hint_key == _normalize(cand).split()[0]:
                        display = cand
                        break
                    first = hint_key.split()[0] if hint_key else ""
                    ck = _normalize(cand)
                    if first and (ck == first or ck.startswith(first + " ") or ck.startswith(first + "/")):
                        # Only accept combo if hint itself mentions the combo partner
                        if " " in ck or "/" in ck:
                            if not any(tok in hint_key for tok in ("clav", "potassium", "hctz", "combo")):
                                continue
                        display = cand
                        break

            # 2) Exact OCR-alias substring fallback
            if display is None:
                for canonical, aliases in ocr_alias_targets:
                    if self._recovery_already_covered(have, canonical, ""):
                        continue
                    if not any(re.search(rf"\b{re.escape(a)}\b", low) for a in aliases):
                        continue
                    if re.search(r"\b(?:allergy|allergic|avoid|contraindicat)\b", low):
                        continue
                    display = canonical.title() if canonical != "acarbose" else "Acarbose"
                    if canonical == "acetaminophen":
                        display = "Acetaminophen"
                    break

            if display is None:
                continue
            if self._recovery_already_covered(have, display, ""):
                continue

            med = self._parse_rx_block(len(medicines) + len(recovered) + 1, [body], conf, is_mock)
            if med is None:
                strength_m = _STRENGTH_RE.search(text)
                med = ParsedMedicine(
                    item_number=len(medicines) + len(recovered) + 1,
                    medicine_name=display,
                    strength=strength_m.group("strength").strip() if strength_m else None,
                    form=None,
                    dose=None,
                    route="Oral" if re.search(r"\b(?:tablet|capsule|oral)\b", low) else None,
                    frequency=None,
                    duration=None,
                    source_span=text[:180],
                    parser_confidence=conf,
                    parser_name=self.name + "+ocr-name-recovery",
                    is_mock=is_mock,
                )
            else:
                # Prefer catalog canonical when recovery was alias/fuzzy driven
                med.medicine_name = display
            self._enrich_sig(med, body)
            key = _normalize(med.medicine_name)
            if key in have:
                continue
            have.add(key)
            recovered.append(med)
        return recovered

    @staticmethod
    def _recovery_norm_keys(name: str) -> set[str]:
        """Normalized keys including OCR abbrev expansion (arcabose → acarbose)."""
        keys = {_normalize(name)}
        try:
            from app.services.datasets.match import normalize_query

            mapped = normalize_query(name)
            if mapped:
                keys.add(_normalize(mapped))
        except Exception:  # noqa: BLE001
            pass
        return {k for k in keys if k}

    @staticmethod
    def _recovery_already_covered(have: set[str], candidate: str, hint_key: str = "") -> bool:
        """True if candidate is already parsed or is a combo expansion of an existing drug."""
        cand_keys = MedicalParserAdapter._recovery_norm_keys(candidate)
        if not cand_keys:
            return True
        have_expanded: set[str] = set()
        for existing in have:
            have_expanded |= MedicalParserAdapter._recovery_norm_keys(existing)
        if hint_key:
            have_expanded |= MedicalParserAdapter._recovery_norm_keys(hint_key)
        if cand_keys & have_expanded:
            return True
        ck = _normalize(candidate)
        for existing in have_expanded:
            if not existing:
                continue
            # Amoxicillin already present → skip "amoxicillin and clavulanate …"
            if ck.startswith(existing + " ") or ck.startswith(existing + "/"):
                return True
            if existing.startswith(ck + " ") or existing.startswith(ck + "/"):
                return True
            if f" {existing} " in f" {ck} " or f" {ck} " in f" {existing} ":
                return True
        return False

    @staticmethod
    def _explode_merged_item_lines(
        lines: list[tuple[str, float, bool]],
    ) -> list[tuple[str, float, bool]]:
        """Split OCR lines that contain multiple numbered Rx items."""
        out: list[tuple[str, float, bool]] = []
        for text, conf, is_mock in lines:
            parts = _MERGED_ITEM_SPLIT_RE.split(text)
            if len(parts) <= 1:
                out.append((text, conf, is_mock))
                continue
            for part in parts:
                chunk = part.strip(" -–—\t")
                if chunk:
                    out.append((chunk, conf, is_mock))
        return out

    @staticmethod
    def _premerge_fragments(
        tokens: list[tuple[str, float, bool]],
    ) -> list[tuple[str, float, bool]]:
        out: list[tuple[str, float, bool]] = []
        i = 0
        while i < len(tokens):
            text, conf, is_mock = tokens[i]
            # "500" + "mg" / "10" + "mg"
            if (
                re.fullmatch(r"\d+(?:\.\d+)?", text)
                and i + 1 < len(tokens)
                and re.fullmatch(r"mg|g|mcg|%", tokens[i + 1][0], re.I)
            ):
                unit = tokens[i + 1][0]
                out.append((f"{text} {unit}", conf, is_mock))
                i += 2
                continue
            # "40" + "Tablet" + "mg"  (Vision often interleaves form between number and unit)
            if (
                re.fullmatch(r"\d+(?:\.\d+)?", text)
                and i + 2 < len(tokens)
                and _FORM_ONLY_RE.match(tokens[i + 1][0])
                and re.fullmatch(r"mg|g|mcg|%|m\.?", tokens[i + 2][0], re.I)
            ):
                form = tokens[i + 1][0]
                unit = tokens[i + 2][0]
                unit = "mg" if unit.lower().startswith("m") else unit
                out.append((f"{text} {unit}", conf, is_mock))
                out.append((form, tokens[i + 1][1], tokens[i + 1][2]))
                i += 3
                continue
            # "500 mg" already, or "mg" alone after a number already consumed
            if re.fullmatch(r"mg|g|mcg|%", text, re.I) and out and re.search(r"\d\s*$", out[-1][0]):
                prev, pconf, pmock = out[-1]
                if not re.search(r"\b(?:mg|g|mcg|%)\b", prev, re.I):
                    out[-1] = (f"{prev} {text}", pconf, pmock)
                    i += 1
                    continue
            # "Pantoprazole 40" + "Tablet" + "mg" → attach unit past an intervening form
            if (
                re.fullmatch(r"mg|g|mcg|%|m\.?", text, re.I)
                and len(out) >= 2
                and _FORM_ONLY_RE.match(out[-1][0])
                and re.search(r"\d\s*$", out[-2][0])
                and not re.search(r"\b(?:mg|g|mcg|%)\b", out[-2][0], re.I)
            ):
                unit = "mg" if text.lower().startswith("m") else text
                prev2, p2conf, p2mock = out[-2]
                out[-2] = (f"{prev2} {unit}", p2conf, p2mock)
                i += 1
                continue
            out.append((text, conf, is_mock))
            i += 1
        return out

    @classmethod
    def _focus_rx_region(
        cls, lines: list[tuple[str, float, bool]]
    ) -> list[tuple[str, float, bool]]:
        """Drop pre-Rx header/PII for any pad layout.

        Do NOT treat a lone 'R'/'Rx' glyph as the clinical start — many pads print
        clinic address / doctor details after that glyph. Prefer the first numbered
        medicine item (or first clinical-cue line).
        """
        texts = [t for t, _, _ in lines]
        start = find_rx_clinical_start(texts)
        if start <= 0:
            # Still strip leading pure PII/admin even without a clear numbered block
            while start < len(lines) and (
                is_pii_or_admin_line(lines[start][0])
                and not has_clinical_cue(lines[start][0])
            ):
                start += 1
            return lines[start:] if start else lines
        return lines[start:]

    @staticmethod
    def _is_noise_line(text: str) -> bool:
        low = text.lower().strip()
        if len(low) < 1:
            return True
        if low in {":", "-", "–", "—", "rx", "r", "•", "·"}:
            return True
        if is_pii_or_admin_line(text):
            return True
        if re.fullmatch(r"[\d\s/.-]+", low) and "mg" not in low:  # bare OPD numbers / dates alone
            if re.search(r"\d{2}/\d{2}/\d{4}", low):
                return True
            if len(low) <= 8 and not _STRENGTH_RE.search(low):
                return True
        return bool(_HEADER_FOOTER_RE.match(low))

    @staticmethod
    def _is_advice_or_footer(text: str) -> bool:
        low = text.lower()
        return bool(
            re.match(
                r"^(drink\s+plenty|avoid\s+|take\s+medicines\s+regularly|follow\s+up|"
                r"advice\s*:|clinical\s+note|diagnosis\s*:|dx\s*:|low\s+sugar|monitor\s+fasting|"
                r"(?:type\s*[12]\s+)?diabetes(?:\s+mellitus)?\b|"
                r"dr\.?\s|mbbs|fcps|fracgp|fracp|reg\.?\s*no|provider\s*no|no\s+repeats?)",
                low,
            )
        )

    @classmethod
    def _looks_like_drug_name(cls, text: str) -> bool:
        low = text.lower().strip()
        if len(low) < 4:
            return False
        if _ROUTE_LINE_RE.match(low):
            return False
        if _LABEL_FRAGMENT_RE.match(low):
            return False
        if _SIG_FRAGMENT_RE.match(low) or _SIG_START_RE.match(low):
            return False
        if is_pii_or_admin_line(text) or looks_like_pii_drug_name(text):
            return False
        # Strip trailing punctuation for fragment checks ("Ind:")
        stripped_low = low.strip(" .:;-–—")
        if _LABEL_FRAGMENT_RE.match(stripped_low) or _COUNT_WORD_RE.match(stripped_low):
            return False
        if _FORM_ONLY_RE.match(low) or _STRENGTH_ONLY_RE.match(low):
            return False
        if "orally" in low or "hourly" in low:
            return False
        if re.search(r"\b(?:times\s+daily|once\s+daily|twice\s+daily|every\s+\d+\s+hours?)\b", low):
            return False
        if _BAD_DRUG_NAME_RE.match(low) or _BAD_DRUG_NAME_RE.match(stripped_low):
            return False
        if re.search(r"\b(?:days?|hourly|orally|breakfast|fever|pain|daily)\b", low) and not _STRENGTH_RE.search(
            low
        ):
            # Sig / advice fragments, not drug names
            if not re.match(r"^[A-Za-z][A-Za-z-]{2,}$", text.strip()):
                return False
        fillers = {
            "take",
            "tablet",
            "tablets",
            "capsule",
            "capsules",
            "orally",
            "daily",
            "night",
            "before",
            "breakfast",
            "hourly",
            "fever",
            "pain",
            "days",
            "once",
            "twice",
            "thrice",
            "times",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "half",
            "every",
            "ind",
            "indication",
            "indications",
            "uses",
            "use",
            "symptoms",
            "symptom",
            "directions",
            "direction",
            "pains",
            "pain",
            "fever",
            "headache",
            "after",
            "with",
            "food",
            "water",
            "avoid",
            "oily",
            "spicy",
            "plenty",
            "drink",
            "follow",
            "female",
            "male",
            "clinic",
            "patient",
            "physician",
            "hospital",
            "care",
            "city",
            "general",
            "route",
            "oral",
            "inhalation",
            "mg",
            "mcg",
            "required",
            "meals",
            "meal",
        }
        # Pure "500 mg tablets" (no drug token) — not a drug name line.
        # Keep "Arcabose 50 mg tablets" as a drug line.
        if _STRENGTH_RE.search(low) and _FORM_RE.search(low):
            stripped = _STRENGTH_RE.sub(" ", low)
            stripped = _FORM_RE.sub(" ", stripped)
            stripped = re.sub(r"[^\w\s-]", " ", stripped)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            tokens = [w for w in stripped.split() if w not in fillers and len(w) > 2]
            if not tokens:
                return False
        if _STRENGTH_RE.fullmatch(low) or re.fullmatch(r"\d+(?:\.\d+)?\s*mg", low, re.I):
            return False
        if re.search(r"\d+\s*y\s*/\s*(?:male|female)", low):
            return False
        words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text)
        drug_words = [w for w in words if w.lower() not in fillers]
        if not drug_words:
            return False
        if all(_COUNT_WORD_RE.match(w) for w in drug_words):
            return False
        if looks_like_pii_drug_name(" ".join(drug_words)):
            return False
        return not _BAD_DRUG_NAME_RE.match(drug_words[0])

    @classmethod
    def _block_has_drug_name(cls, block: list[str]) -> bool:
        return any(cls._looks_like_drug_name(x) for x in block if x.strip())

    def _parse_rx_block(
        self,
        item_no: int,
        block: list[str],
        conf: float,
        is_mock: bool,
    ) -> ParsedMedicine | None:
        parts = [b.strip() for b in block if b and b.strip()]
        if not parts:
            return None
        joined = " ".join(parts)
        # Repair OCR truncations: "625 m" / "625" + "mg ." → "625 mg"
        joined = _STRENGTH_TRUNC_RE.sub(r"\g<num> mg", joined)
        joined = re.sub(r"\b(\d+(?:\.\d+)?)\s+mg\s*\.", r"\1 mg", joined, flags=re.I)
        strength_m = _STRENGTH_RE.search(joined)
        form_m = _FORM_RE.search(joined)
        strength = strength_m.group("strength").strip() if strength_m else None
        # Vision sometimes emits: "10" / "Tablet" / "mg"  or  "Pantoprazole 40" / "Tablet" / "mg"
        if strength is None:
            for idx, part in enumerate(parts):
                if re.fullmatch(r"\d+(?:\.\d+)?", part):
                    for nxt in parts[idx + 1 : idx + 4]:
                        if re.fullmatch(r"mg|g|mcg|%|m\.?", nxt, re.I):
                            unit = "mg" if nxt.lower().startswith("m") else nxt
                            strength = f"{part} {unit}"
                            break
                    if strength:
                        break
                # Trailing digits on a drug line with unit nearby
                trail = re.search(r"^(?P<head>.+?)\s+(?P<num>\d+(?:\.\d+)?)$", part)
                if trail and not strength:
                    for nxt in parts[idx + 1 : idx + 4]:
                        if re.fullmatch(r"mg|g|mcg|%|m\.?", nxt, re.I):
                            unit = "mg" if nxt.lower().startswith("m") else nxt
                            strength = f"{trail.group('num')} {unit}"
                            break
                        if _FORM_ONLY_RE.match(nxt):
                            continue
                        break
            if strength is None:
                trunc = _STRENGTH_TRUNC_RE.search(joined)
                if trunc:
                    strength = f"{trunc.group('num')} mg"
            # Last resort: "Name 40 ... mg" anywhere in joined (form may sit between)
            if strength is None:
                loose = re.search(
                    r"(\d+(?:\.\d+)?)\s+(?:(?:capsules?|tabs?\.?|tablets?|caps?\.?)\s+)?(mg|g|mcg|%)\b",
                    joined,
                    re.I,
                )
                if loose:
                    strength = f"{loose.group(1)} {loose.group(2)}"

        name = None
        pending_trail_num: str | None = None
        for part in parts:
            if _CLINICAL_INTERRUPT_RE.match(part) or is_pii_or_admin_line(part):
                continue
            if _ROUTE_LINE_RE.match(part):
                continue
            if self._looks_like_drug_name(part):
                candidate = part
                sm = _STRENGTH_RE.search(candidate)
                fm = _FORM_RE.search(candidate)
                if sm:
                    candidate = candidate[: sm.start()]
                elif fm:
                    candidate = candidate[: fm.start()]
                trail_num = re.search(r"^(?P<head>.+?)\s+(?P<num>\d+(?:\.\d+)?)$", candidate.strip())
                if trail_num:
                    pending_trail_num = trail_num.group("num")
                    candidate = trail_num.group("head")
                candidate = strip_trailing_strength_digits(candidate)
                candidate = re.sub(r"\s+", " ", candidate).strip(" -,\t.")
                if (
                    candidate
                    and not _FORM_ONLY_RE.match(candidate)
                    and not _BAD_DRUG_NAME_RE.match(candidate)
                    and not looks_like_pii_drug_name(candidate)
                ):
                    name = candidate
                    break
        if not name:
            if strength_m:
                name = joined[: strength_m.start()].strip(" -,\t.")
                name = strip_trailing_strength_digits(name)
            else:
                return None
        name = re.sub(r"\s+", " ", name).strip()
        name = re.sub(r"^(?:take\s+)+", "", name, flags=re.I).strip()
        name = strip_trailing_strength_digits(name)
        if (
            not name
            or _FORM_ONLY_RE.match(name)
            or _BAD_DRUG_NAME_RE.match(name)
            or _SIG_FRAGMENT_RE.match(name)
            or _COUNT_WORD_RE.match(name)
            or looks_like_pii_drug_name(name)
            or len(name) < 3
        ):
            return None
        form = form_m.group("form").lower() if form_m else None
        if form:
            form = form.rstrip(".")
            if form in {"tab", "tabs"}:
                form = "tablet"
            elif form in {"cap", "caps"}:
                form = "capsule"
        # Orphan unit OCR (mg attached to prior item): recover from "Cetirizine 10" + Tablet
        if strength is None and pending_trail_num and form:
            strength = f"{pending_trail_num} mg"
        # Allow catalog-known drug names even when strength/form OCR is broken
        catalog_known = self._catalog_known_name(name)
        if strength is None and form is None and not catalog_known:
            return None

        med = ParsedMedicine(
            item_number=item_no,
            medicine_name=name.title() if name.islower() else name,
            strength=strength,
            form=form,
            dose=None,
            route=None,
            frequency=None,
            duration=None,
            source_span=joined[:180],
            parser_confidence=conf,
            parser_name=self.name,
            is_mock=is_mock,
        )
        for part in parts:
            pl = part.lower()
            if (
                _SIG_START_RE.match(part)
                or _SIG_FRAGMENT_RE.match(part)
                or "orally" in pl
                or "hourly" in pl
            ):
                self._enrich_sig(med, part)
            elif "for " in pl and "day" in pl:
                self._enrich_sig(med, part)
            elif "once" in pl and "daily" in pl:
                self._enrich_sig(med, part)
            elif "before breakfast" in pl or "at night" in pl:
                self._enrich_sig(med, part)
            elif "if fever" in pl or "or pain" in pl:
                self._enrich_sig(med, part)
        self._enrich_sig(med, joined)
        return med

    @staticmethod
    def _catalog_known_name(name: str) -> bool:
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.match import suggest_medicines

            if not catalog_available():
                return False
            hits = suggest_medicines(name, top_k=1, min_score=85.0)
            return bool(hits and hits[0].score >= 85.0)
        except Exception:  # noqa: BLE001
            return False

    def _rescue_item_drug(
        self,
        item_no: int,
        body: str,
        block: list[str],
        conf: float,
        is_mock: bool,
    ) -> ParsedMedicine | None:
        """Create a HITL row for numbered items when strength OCR is truncated/split."""
        name = body.lstrip(".-–— \t").strip()
        if not name or len(name) < 3:
            return None
        if (
            _CLINICAL_INTERRUPT_RE.match(name)
            or _BAD_DRUG_NAME_RE.match(name)
            or _SIG_FRAGMENT_RE.match(name)
            or _SIG_START_RE.match(name)
            or _COUNT_WORD_RE.match(name)
            or _ROUTE_LINE_RE.match(name)
            or is_pii_or_admin_line(name)
            or looks_like_pii_drug_name(name)
        ):
            return None
        name = strip_trailing_strength_digits(name)
        if _SIG_FRAGMENT_RE.match(name) or _COUNT_WORD_RE.match(name) or _BAD_DRUG_NAME_RE.match(name):
            return None
        # Prefer catalog canonical when brand OCR is clear (Augmentin, etc.)
        canonical = name
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.match import suggest_medicines

            if catalog_available():
                hits = suggest_medicines(name, top_k=1, min_score=85.0)
                if hits and hits[0].score >= 90.0:
                    canonical = hits[0].canonical_name
        except Exception:  # noqa: BLE001
            pass
        joined = " ".join([b for b in block if b and not _CLINICAL_INTERRUPT_RE.match(b)])
        joined = _STRENGTH_TRUNC_RE.sub(r"\g<num> mg", joined)
        strength_m = _STRENGTH_RE.search(joined)
        form_m = _FORM_RE.search(joined)
        strength = strength_m.group("strength").strip() if strength_m else None
        if strength is None:
            trunc = _STRENGTH_TRUNC_RE.search(joined)
            if trunc:
                strength = f"{trunc.group('num')} mg"
        form = form_m.group("form").lower().rstrip(".") if form_m else None
        if form in {"tab", "tabs"}:
            form = "tablet"
        elif form in {"cap", "caps"}:
            form = "capsule"
        return ParsedMedicine(
            item_number=item_no,
            medicine_name=canonical,
            strength=strength,
            form=form,
            dose=None,
            route=None,
            frequency=None,
            duration=None,
            source_span=(joined or name)[:180],
            parser_confidence=conf,
            parser_name=self.name + "+item-rescue",
            is_mock=is_mock,
        )

    @staticmethod
    def _enrich_strength_form(med: ParsedMedicine, text: str) -> None:
        if med.strength is None:
            sm = _STRENGTH_RE.search(text)
            if sm:
                med.strength = sm.group("strength").strip()
        if med.form is None:
            fm = _FORM_RE.search(text)
            if fm:
                med.form = fm.group("form").lower()

    @staticmethod
    def _enrich_sig(med: ParsedMedicine, text: str) -> None:
        low = text.lower()
        # Common Vision misreads for "hourly"
        low = re.sub(r"\bhowdy\b", "hourly", low)
        low = re.sub(r"\bhouldy\b", "hourly", low)
        low = re.sub(r"\bhrly\b", "hourly", low)
        if med.dose is None:
            # Prefer a single discrete count for HITL catalog match; "one or two" stays red until selected
            dose_m = re.search(
                r"\b(one|two|three|four|\d+)(?:\s+or\s+(one|two|three|\d+))?\s+(capsule|tablet|puff)s?\b",
                low,
            )
            if dose_m:
                qty_raw = dose_m.group(1)
                qty = qty_raw.upper() if qty_raw.isalpha() else qty_raw
                word = {"1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR"}.get(qty, qty)
                unit = dose_m.group(3)
                if dose_m.group(2):
                    # Ambiguous OCR range — leave dose unset so pharmacist picks catalog evidence
                    med.dose = None
                else:
                    plural = "" if word == "ONE" else "s"
                    med.dose = f"{word} {unit}{plural}"
            elif re.fullmatch(r"(?:one|1|two|2|three|3|four|4)", low.strip()):
                # Vision-split count alone — assume tablet when form known or default oral solid
                qty_raw = low.strip()
                word = {"1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "one": "ONE", "two": "TWO", "three": "THREE", "four": "FOUR"}.get(qty_raw, qty_raw.upper())
                unit = "tablet"
                if med.form and "capsule" in med.form.lower():
                    unit = "capsule"
                plural = "" if word == "ONE" else "s"
                med.dose = f"{word} {unit}{plural}"
        if med.frequency is None:
            if (
                "up to three times" in low
                or "three times daily" in low
                or re.search(r"\b3\s*(?:x|times)\s*(?:a\s+day|daily)\b", low)
                or re.search(r"\b(?:tid|tds)\b", low)
                or re.search(r"\bthrice\b", low)
            ):
                med.frequency = "THREE times daily"
            elif "twice daily" in low or re.search(r"\b(?:bd|bid)\b", low):
                med.frequency = "TWICE daily"
            elif "four times daily" in low or re.search(r"\b(?:qid|qds)\b", low):
                med.frequency = "FOUR times daily"
            elif re.search(r"\b8\s*hourly\b", low) or re.search(r"\bevery\s+8\s+hours\b", low):
                med.frequency = "THREE times daily"
            elif re.search(r"\b6\s*hourly\b", low) or re.search(r"\bevery\s+6\s+hours\b", low):
                med.frequency = "FOUR times daily"
            elif re.search(r"\b12\s*hourly\b", low) or re.search(r"\bevery\s+12\s+hours\b", low):
                med.frequency = "TWICE daily"
            elif re.search(r"\b4\s*hourly\b", low) or re.search(
                r"\bevery\s+4\s*(?:to|-)\s*6\s+hours\b", low
            ):
                med.frequency = "every 4 hours"
            elif "once daily" in low or re.search(r"\bonce\b.*\bdaily\b", low) or re.search(
                r"\b(?:od|qd)\b", low
            ):
                med.frequency = "ONCE daily"
            elif any(x in low for x in ("as required", "when required", "as needed", "if fever")):
                med.frequency = "when required"
            elif "after food" in low or "after meal" in low:
                med.frequency = "after meal"
            elif "before food" in low or "before meal" in low:
                med.frequency = "before meal"
        if med.duration is None:
            dur = re.search(r"\bfor\s+(\d+\s+days?)\b", low)
            if dur:
                med.duration = dur.group(1)
        if med.route is None:
            if _ROUTE_LINE_RE.match(low) or re.search(r"\broute\s*:\s*oral\b", low):
                med.route = "Oral"
            elif re.search(r"\broute\s*:\s*inhal", low):
                med.route = "Inhalation"
            elif "inhal" in low:
                med.route = "Inhalation"
            elif any(x in low for x in ("oral", "capsule", "tablet", "before breakfast", "at night")):
                med.route = "Oral"


class FormularyValidator:
    """Validate parsed medicines against real catalog when available, else seed formulary.

    `matched` is True only when OCR/parser name equals canonical spelling.
    Fuzzy / alias hits stay unmatched and surface as HITL warnings + top candidates.
    """

    def validate(self, medicines: list[ParsedMedicine]) -> list[FormularyCheck]:
        checks: list[FormularyCheck] = []
        catalog_ready = False
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.match import suggest_medicines

            catalog_ready = catalog_available()
        except Exception:  # noqa: BLE001
            suggest_medicines = None  # type: ignore[assignment]

        for med in medicines:
            if catalog_ready and suggest_medicines is not None:
                try:
                    hits = suggest_medicines(med.medicine_name, top_k=3)
                except Exception:  # noqa: BLE001
                    hits = []
                if hits:
                    best = hits[0]
                    raw_norm = _normalize(med.medicine_name)
                    canon_norm = _normalize(best.canonical_name)
                    alias_norm = _normalize(best.matched_alias)
                    # Exact spelling OR real catalog synonym (alias string equals OCR text).
                    # OCR misspellings remapped via abbrev table stay unmatched for HITL.
                    exact = raw_norm == canon_norm or (
                        best.score >= 100.0 and bool(alias_norm) and alias_norm == raw_norm
                    )
                    strengths = list(best.strengths or [])
                    forms = list(best.dosage_forms or [])
                    routes = list(best.routes or [])
                    warnings: list[str] = [
                        "Decision-support catalog match only — pharmacist must confirm. "
                        f"Top candidates: {', '.join(h.canonical_name for h in hits)}."
                    ]
                    if not exact:
                        warnings.append(
                            f"OCR/parser name '{med.medicine_name}' fuzzy-matched "
                            f"'{best.canonical_name}' (score={best.score:.0f}) — confirm in HITL."
                        )
                    strength_ok = (
                        any(_normalize(med.strength or "") == _normalize(s) for s in strengths)
                        if med.strength and strengths
                        else None
                    )
                    form_ok = (
                        any(_normalize(med.form or "") == _normalize(f) for f in forms)
                        if med.form and forms
                        else None
                    )
                    route_ok = (
                        any(_normalize(med.route or "") == _normalize(r) for r in routes)
                        if med.route and routes
                        else None
                    )
                    if strength_ok is False:
                        warnings.append("Strength not listed for top catalog candidate.")
                    if form_ok is False:
                        warnings.append("Dosage form not listed for top catalog candidate.")
                    checks.append(
                        FormularyCheck(
                            medicine_name=med.medicine_name,
                            matched=exact,
                            formulary_id=(best.drugbank_id or best.product_ndc or best.canonical_name)
                            if exact
                            else None,
                            allowed_strengths=strengths,
                            allowed_forms=forms,
                            allowed_routes=routes,
                            strength_ok=strength_ok if exact else None,
                            form_ok=form_ok if exact else None,
                            route_ok=route_ok if exact else None,
                            warnings=warnings,
                        )
                    )
                    continue

            entry_obj = resolve_drug(med.medicine_name)
            if not entry_obj:
                checks.append(
                    FormularyCheck(
                        medicine_name=med.medicine_name,
                        matched=False,
                        formulary_id=None,
                        allowed_strengths=[],
                        allowed_forms=[],
                        allowed_routes=[],
                        strength_ok=None,
                        form_ok=None,
                        route_ok=None,
                        warnings=["Unsupported / Manual Review Required - no formulary match."],
                    )
                )
                continue

            entry = SEED_FORMULARY[_normalize(entry_obj.canonical_name)]
            strength_ok = (
                any(_normalize(med.strength or "") == _normalize(s) for s in entry["strengths"])
                if med.strength
                else None
            )
            form_ok = (
                any(_normalize(med.form or "") == _normalize(f) for f in entry["forms"]) if med.form else None
            )
            route_ok = (
                any(_normalize(med.route or "") == _normalize(r) for r in entry["routes"]) if med.route else None
            )
            warnings = []
            if strength_ok is False:
                warnings.append("Strength not listed for matched formulary medicine.")
            if form_ok is False:
                warnings.append("Dosage form not listed for matched formulary medicine.")
            if route_ok is False:
                warnings.append("Route not listed for matched formulary medicine.")
            if _normalize(med.medicine_name) != _normalize(entry_obj.canonical_name):
                warnings.append(
                    f"OCR/parser name '{med.medicine_name}' matched alias for "
                    f"'{entry_obj.canonical_name}' - pharmacist should confirm canonical name."
                )
            exact = _normalize(med.medicine_name) == _normalize(entry_obj.canonical_name)
            checks.append(
                FormularyCheck(
                    medicine_name=med.medicine_name,
                    matched=exact,
                    formulary_id=entry["formulary_id"] if exact else None,
                    allowed_strengths=entry["strengths"],
                    allowed_forms=entry["forms"],
                    allowed_routes=entry["routes"],
                    strength_ok=strength_ok if exact else None,
                    form_ok=form_ok if exact else None,
                    route_ok=route_ok if exact else None,
                    warnings=warnings,
                )
            )
        return checks


class PrescriptionPipeline:
    def __init__(self) -> None:
        self.paddle = PaddleOcrAdapter()
        self.trocr = TrocrRetryAdapter()
        self.merger = CandidateMerger()
        self.parser = MedicalParserAdapter()
        self.formulary = FormularyValidator()

    def run(self, image_bytes: bytes) -> PipelineResult:
        """Run OCR stack → parse → catalog/seed formulary validation."""
        started = time.perf_counter()
        warnings: list[str] = []
        stages = [
            "ocr_stack_spec_sequential",
            "candidate_line_view",
            "medical_parser",
            "catalog_formulary_validation",
            "awaiting_pharmacist_verification",
        ]

        ocr = run_ocr_stack(image_bytes)
        warnings.extend(ocr.warnings)
        if ocr.is_mock:
            warnings.append(
                f"OCR stack primary='{ocr.engine_primary}' running in labelled MOCK mode "
                "(configure Google Vision credentials for real DOCUMENT_TEXT_DETECTION)."
            )

        paddle_lines: list[LineCandidate] = []
        trocr_list: list[LineCandidate] = []
        trocr_map: dict[str, LineCandidate] = {}
        for idx, line in enumerate(ocr.lines):
            line_id = f"ocr-{idx}"
            primary = LineCandidate(
                line_id=line_id,
                text=line.text,
                confidence=line.confidence,
                engine=line.engine or ocr.engine_primary,
                bbox=line.bbox,
                is_mock=line.is_mock or ocr.is_mock,
                source_stage="ocr_stack",
            )
            paddle_lines.append(primary)
            if line.engine == "trocr":
                retry = LineCandidate(
                    line_id=f"trocr-{line_id}",
                    text=line.text,
                    confidence=line.confidence,
                    engine="trocr",
                    bbox=line.bbox,
                    is_mock=line.is_mock,
                    source_stage="trocr_retry",
                )
                trocr_map[line_id] = retry
                trocr_list.append(retry)
            elif line.confidence < UNCERTAIN_THRESHOLD:
                # Real TrOCR when available; labelled mock spelling assist otherwise
                retry = self.trocr.retry_line(image_bytes, primary)
                trocr_map[line_id] = retry
                trocr_list.append(retry)

        merged = self.merger.merge(paddle_lines, trocr_map)
        raw_text, medicines, parser_warnings = self.parser.parse(merged)
        warnings.extend(parser_warnings)
        if not medicines:
            fallback = self._fallback_medicines_from_ocr(merged, ocr.is_mock)
            if fallback:
                medicines = fallback
                warnings.append(
                    "Line parser found no structured medicines — used catalog-assisted OCR line fallback for HITL."
                )
        checks = self.formulary.validate(medicines)
        for check in checks:
            warnings.extend(check.warnings)

        overall = sum(line.selected_confidence for line in merged) / max(len(merged), 1)
        elapsed = int((time.perf_counter() - started) * 1000)
        is_mock = ocr.is_mock and (not medicines or all(m.is_mock for m in medicines))

        return PipelineResult(
            pipeline_id=str(uuid.uuid4()),
            raw_text=raw_text or ocr.full_text,
            overall_ocr_confidence=overall,
            processing_ms=max(elapsed, 1),
            paddle_lines=paddle_lines,
            trocr_retries=trocr_list,
            merged_lines=merged,
            parsed_medicines=medicines,
            formulary_checks=checks,
            warnings=warnings,
            stages_used=stages,
            is_mock=is_mock,
        )

    def _fallback_medicines_from_ocr(
        self, merged: list[MergedLine], is_mock: bool
    ) -> list[ParsedMedicine]:
        """When structured parse fails, still create HITL rows from OCR lines + catalog hints."""
        medicines: list[ParsedMedicine] = []
        try:
            from app.services.datasets.catalog_store import catalog_available
            from app.services.datasets.match import suggest_medicines
        except Exception:  # noqa: BLE001
            catalog_available = lambda: False  # type: ignore
            suggest_medicines = None  # type: ignore

        item_no = 0
        for line in merged:
            text = line.selected_text.strip()
            if len(text) < 4:
                continue
            if is_pii_or_admin_line(text):
                continue
            low = text.lower()
            if low.startswith(
                (
                    "patient",
                    "age",
                    "date",
                    "dr ",
                    "doctor",
                    "rx",
                    "prescriber",
                    "take ",
                    "inhale ",
                    "route:",
                    "clinic",
                    "opd",
                    "reg",
                    "mbbs",
                    "follow",
                    "drink",
                    "provider",
                    "fracgp",
                    "no repeats",
                )
            ):
                continue
            body = text
            m_item = _ITEM_RE.match(text)
            if m_item:
                item_no = int(m_item.group("item"))
                body = m_item.group("body").strip()
            if is_pii_or_admin_line(body) or looks_like_pii_drug_name(body):
                continue
            strength_m = _STRENGTH_RE.search(body)
            form_m = _FORM_RE.search(body)
            # Need a medicine cue: strength/form or a strong catalog hit
            catalog_hit = None
            if catalog_available() and suggest_medicines is not None:
                hits = suggest_medicines(body, top_k=1)
                if hits and hits[0].score >= 70:
                    catalog_hit = hits[0]
            if not strength_m and not form_m and catalog_hit is None:
                continue
            if not m_item:
                item_no += 1
            name = body
            if strength_m:
                name = body[: strength_m.start()].strip(" -,\t")
            if form_m and (not strength_m or form_m.start() < strength_m.start()):
                name = body[: form_m.start()].strip(" -,\t") or name
            name = strip_trailing_strength_digits(re.sub(r"\s+", " ", name).strip(" ."))
            if looks_like_pii_drug_name(name):
                continue
            if (
                _SIG_FRAGMENT_RE.match(name)
                or _COUNT_WORD_RE.match(name)
                or _BAD_DRUG_NAME_RE.match(name)
                or _SIG_START_RE.match(name)
            ):
                continue
            if len(name) < 3 and catalog_hit is not None:
                name = catalog_hit.canonical_name
            if len(name) < 3 or looks_like_pii_drug_name(name):
                continue
            if _SIG_FRAGMENT_RE.match(name) or _COUNT_WORD_RE.match(name):
                continue
            medicines.append(
                ParsedMedicine(
                    item_number=item_no or (len(medicines) + 1),
                    medicine_name=name,
                    strength=strength_m.group("strength").strip() if strength_m else None,
                    form=form_m.group("form").lower() if form_m else None,
                    dose=None,
                    route=None,
                    frequency=None,
                    duration=None,
                    source_span=text,
                    parser_confidence=line.selected_confidence,
                    parser_name="catalog-assisted-ocr-fallback",
                    is_mock=is_mock,
                )
            )
        return medicines
