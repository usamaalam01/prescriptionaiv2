"""OCR adapters: Spec O1/B1 sequential TrOCR → Google Vision → Tesseract.

PaddleOCR may assist detection for TrOCR crops. Decision-support only — not clinical care.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrToken:
    text: str
    confidence: float
    bbox: list[float] | None = None  # [x0,y0,x1,y1] normalized or pixel
    engine: str = ""
    is_mock: bool = False


@dataclass
class OcrLine:
    text: str
    confidence: float
    bbox: list[float] | None = None
    engine: str = ""
    tokens: list[OcrToken] = field(default_factory=list)
    is_mock: bool = False


@dataclass
class OcrDocumentResult:
    full_text: str
    lines: list[OcrLine]
    engine_primary: str
    is_mock: bool
    warnings: list[str] = field(default_factory=list)
    engine_attempts: list[dict] = field(default_factory=list)
    selected_engine: str | None = None
    requires_human_review: bool = False
    consensus_status: str | None = None
    consensus_candidates: list[dict] = field(default_factory=list)


def _mock_document(reason: str) -> OcrDocumentResult:
    # Labelled academic fallback — four-drug HITL demo (one intentional misspelling).
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
    lines = [
        OcrLine(text=text, confidence=conf, engine="mock", is_mock=True, bbox=None)
        for text, conf in samples
    ]
    return OcrDocumentResult(
        full_text="\n".join(t for t, _ in samples),
        lines=lines,
        engine_primary="mock",
        is_mock=True,
        warnings=[reason, "MOCK OCR active - install/configure real engines for production path."],
    )


def paddle_detect_lines(image_bytes: bytes) -> list[dict]:
    """Use PaddleOCR for line detection / preprocessing. Returns crop metadata."""
    if not settings.ENABLE_PADDLE_DETECT:
        return []
    try:
        from paddleocr import PaddleOCR  # type: ignore
        from PIL import Image
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(arr, cls=True) or []
        lines: list[dict] = []
        for block in result:
            for item in block or []:
                box, (txt, conf) = item[0], item[1]
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                lines.append(
                    {
                        "text": txt,
                        "confidence": float(conf),
                        "bbox": [min(xs), min(ys), max(xs), max(ys)],
                        "engine": "paddleocr",
                    }
                )
        return lines
    except Exception as exc:  # noqa: BLE001
        logger.warning("PaddleOCR detect unavailable: %s", exc)
        return []


def _vision_lines_from_full_text_annotation(annotation: dict) -> list[OcrLine]:
    lines: list[OcrLine] = []
    for page in annotation.get("pages") or []:
        for block in page.get("blocks") or []:
            for paragraph in block.get("paragraphs") or []:
                texts: list[str] = []
                confs: list[float] = []
                for word in paragraph.get("words") or []:
                    symbols = word.get("symbols") or []
                    w = "".join(s.get("text", "") for s in symbols)
                    texts.append(w)
                    confs.append(float(word.get("confidence") or 0.0))
                line_text = " ".join(texts).strip()
                if not line_text:
                    continue
                conf = sum(confs) / len(confs) if confs else 0.0
                verts = (paragraph.get("boundingBox") or {}).get("vertices") or []
                xs = [int(v.get("x") or 0) for v in verts] or [0]
                ys = [int(v.get("y") or 0) for v in verts] or [0]
                lines.append(
                    OcrLine(
                        text=line_text,
                        confidence=conf,
                        bbox=[min(xs), min(ys), max(xs), max(ys)],
                        engine="google_vision",
                        is_mock=False,
                    )
                )
    return lines


def _google_vision_via_rest(image_bytes: bytes) -> OcrDocumentResult | None:
    """DOCUMENT_TEXT_DETECTION over HTTPS (avoids gRPC, often blocked on Windows)."""
    import base64

    import httpx

    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }

    api_key = (settings.GOOGLE_VISION_API_KEY or "").strip()
    cred_path = (settings.GOOGLE_APPLICATION_CREDENTIALS or "").strip()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    url = "https://vision.googleapis.com/v1/images:annotate"

    if api_key:
        url = f"{url}?key={api_key}"
    elif cred_path:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        creds = service_account.Credentials.from_service_account_file(
            cred_path,
            scopes=["https://www.googleapis.com/auth/cloud-vision"],
        )
        creds.refresh(google.auth.transport.requests.Request())
        headers["Authorization"] = f"Bearer {creds.token}"
    else:
        logger.warning(
            "Google Vision REST skipped: set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_VISION_API_KEY"
        )
        return None

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    responses = data.get("responses") or []
    if not responses:
        return None
    first = responses[0]
    if first.get("error"):
        raise RuntimeError(first["error"].get("message") or str(first["error"]))
    annotation = first.get("fullTextAnnotation") or {}
    full_text = (annotation.get("text") or "").strip()
    if not full_text:
        return None
    lines = _vision_lines_from_full_text_annotation(annotation)
    if not lines:
        lines = [
            OcrLine(text=ln, confidence=0.85, engine="google_vision", is_mock=False)
            for ln in full_text.splitlines()
            if ln.strip()
        ]
    return OcrDocumentResult(
        full_text=full_text,
        lines=lines,
        engine_primary="google_vision",
        is_mock=False,
        warnings=["Google Vision via REST DOCUMENT_TEXT_DETECTION"],
    )


def google_vision_document_text(image_bytes: bytes) -> OcrDocumentResult | None:
    """Primary OCR via Google Cloud Vision DOCUMENT_TEXT_DETECTION.

    Uses REST by default (gRPC client is often blocked by Windows Application Control).
    """
    try:
        return _google_vision_via_rest(image_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Vision OCR failed: %s", exc)
        return None


def trocr_recognize_crop(image_bytes: bytes, bbox: list[float] | None) -> OcrLine | None:
    """Secondary recognizer on a cropped medicine line.

    Prefer TrOCR Large Handwritten when torch/transformers are installed.
    Otherwise re-run Google Vision on an aggressively preprocessed crop (best-practice
    fallback so low-confidence lines still get a second pass without MOCK spelling hacks).
    """
    if not settings.ENABLE_TROCR_RETRY:
        return None

    real = _trocr_transformers_crop(image_bytes, bbox)
    if real is not None:
        return real
    return _vision_retry_crop(image_bytes, bbox)


def _trocr_transformers_crop(image_bytes: bytes, bbox: list[float] | None) -> OcrLine | None:
    try:
        from PIL import Image
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if bbox and len(bbox) == 4:
            x0, y0, x1, y1 = [int(v) for v in bbox]
            # Pad crop slightly for handwriting stems
            pad = 6
            x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
            x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
            if x1 <= x0 or y1 <= y0:
                return None
            img = img.crop((x0, y0, x1, y1))
        processor = TrOCRProcessor.from_pretrained("microsoft/trocr-large-handwritten")
        model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-large-handwritten")
        pixel_values = processor(images=img, return_tensors="pt").pixel_values
        with torch.no_grad():
            generated = model.generate(pixel_values)
        text = processor.batch_decode(generated, skip_special_tokens=True)[0].strip()
        if not text:
            return None
        return OcrLine(
            text=text,
            confidence=0.8,
            bbox=bbox,
            engine="trocr-large-handwritten",
            is_mock=False,
        )
    except Exception as excel:  # noqa: BLE001
        logger.warning("TrOCR crop failed: %s", excel)
        return None


def _vision_retry_crop(image_bytes: bytes, bbox: list[float] | None) -> OcrLine | None:
    """Second-pass Vision on a deskewed/ink-isolated crop when TrOCR weights are unavailable."""
    if not bbox or len(bbox) != 4:
        return None
    try:
        from PIL import Image

        from app.services.ocr.preprocess import preprocess_prescription_image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        x0, y0, x1, y1 = [int(v) for v in bbox]
        pad = 8
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
        if x1 <= x0 or y1 <= y0:
            return None
        crop = img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        enhanced = preprocess_prescription_image(
            buf.getvalue(),
            deskew=True,
            ink_isolate=True,
            adaptive_binarize=True,
            sharpen=True,
            max_side=1200,
        )
        doc = _google_vision_via_rest(enhanced)
        if not doc or not doc.full_text.strip():
            return None
        text = " ".join(doc.full_text.split())
        if not text:
            return None
        conf = sum(l.confidence for l in doc.lines) / max(len(doc.lines), 1)
        return OcrLine(
            text=text,
            confidence=float(conf or 0.82),
            bbox=bbox,
            engine="google_vision_crop_retry",
            is_mock=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Vision crop retry failed: %s", exc)
        return None


def _attempt_from_document(engine_id: str, doc: OcrDocumentResult | None, *, ms: float) -> "EngineAttempt":
    from app.services.ocr.contract import EngineAttempt

    if doc is None:
        return EngineAttempt(
            engine_id=engine_id,
            status="unavailable",
            processing_ms=ms,
            error_code="no_result",
        )
    text = (doc.full_text or "").strip()
    if not text:
        return EngineAttempt(
            engine_id=engine_id,
            status="empty",
            raw_text="",
            confidence=0.0,
            processing_ms=ms,
            is_mock=doc.is_mock,
            lines=[{"text": l.text, "confidence": l.confidence, "engine": l.engine, "bbox": l.bbox} for l in doc.lines],
        )
    conf = sum(l.confidence for l in doc.lines) / max(len(doc.lines), 1) if doc.lines else 0.0
    return EngineAttempt(
        engine_id=engine_id,
        status="success",
        raw_text=text,
        confidence=float(conf),
        processing_ms=ms,
        is_mock=doc.is_mock,
        lines=[{"text": l.text, "confidence": l.confidence, "engine": l.engine, "bbox": l.bbox} for l in doc.lines],
    )


def _run_trocr_document(image_bytes: bytes) -> OcrDocumentResult | None:
    """TrOCR as Spec primary recognition engine (full page or detected crops)."""
    import time

    t0 = time.perf_counter()
    paddle_lines = paddle_detect_lines(image_bytes)
    lines: list[OcrLine] = []
    if paddle_lines:
        for pl in paddle_lines:
            retry = _trocr_transformers_crop(image_bytes, pl.get("bbox"))
            if retry and retry.text:
                lines.append(retry)
            else:
                # Keep detector text only as weak provisional line — not a silent Vision overwrite
                lines.append(
                    OcrLine(
                        text=str(pl.get("text") or ""),
                        confidence=float(pl.get("confidence") or 0.4),
                        bbox=pl.get("bbox"),
                        engine="paddleocr_detect",
                        is_mock=False,
                    )
                )
    else:
        # Full-page TrOCR when no detector regions
        one = _trocr_transformers_crop(image_bytes, None)
        if one and one.text:
            lines = [one]
    ms = (time.perf_counter() - t0) * 1000.0
    if not lines or not any((l.text or "").strip() for l in lines):
        logger.info("ocr_engine=trocr status=empty_or_unavailable ms=%.1f", ms)
        return None
    # If only detector provisional lines (no real TrOCR), treat as unavailable for Spec primary
    if all(l.engine == "paddleocr_detect" for l in lines):
        logger.info("ocr_engine=trocr status=unavailable ms=%.1f", ms)
        return None
    trocr_lines = [l for l in lines if l.engine.startswith("trocr")]
    use = trocr_lines or lines
    return OcrDocumentResult(
        full_text="\n".join(l.text for l in use if l.text),
        lines=use,
        engine_primary="trocr",
        is_mock=False,
        warnings=[f"TrOCR primary recognition ({len(use)} line(s))."],
    )


def _document_from_attempt(attempt: "EngineAttempt") -> OcrDocumentResult:
    lines = [
        OcrLine(
            text=str(row.get("text") or ""),
            confidence=float(row.get("confidence") or attempt.confidence or 0.0),
            bbox=row.get("bbox"),
            engine=str(row.get("engine") or attempt.engine_id),
            is_mock=attempt.is_mock,
        )
        for row in (attempt.lines or [])
        if str(row.get("text") or "").strip()
    ]
    if not lines and attempt.raw_text:
        lines = [
            OcrLine(
                text=ln,
                confidence=float(attempt.confidence or 0.0),
                engine=attempt.engine_id,
                is_mock=attempt.is_mock,
            )
            for ln in str(attempt.raw_text).splitlines()
            if ln.strip()
        ]
    return OcrDocumentResult(
        full_text=attempt.raw_text or "",
        lines=lines,
        engine_primary=attempt.engine_id,
        is_mock=attempt.is_mock,
        warnings=[],
        selected_engine=attempt.engine_id,
    )


def run_ocr_stack(image_bytes: bytes) -> OcrDocumentResult:
    """Spec O1/B1 sequential OCR: TrOCR primary → Google Vision → Tesseract.

    Optional hybrid consensus retains all engine candidates without silent overwrite.
    Logs never include raw OCR text (engine_id / status / latency only).
    """
    import time

    from app.services.ocr.consensus import page_consensus
    from app.services.ocr.contract import is_acceptable, parse_engine_order
    from app.services.ocr.preprocess import preprocess_prescription_image, preprocess_status
    from app.services.ocr.privacy import redact_ocr_text
    from app.services.ocr.tesseract_adapter import run_tesseract

    warnings: list[str] = []
    prepared = preprocess_prescription_image(
        image_bytes,
        deskew=bool(settings.OCR_PREPROCESS_DESKEW),
        ink_isolate=bool(settings.OCR_PREPROCESS_INK_ISOLATE),
        adaptive_binarize=bool(settings.OCR_PREPROCESS_BINARIZE),
        sharpen=bool(settings.OCR_PREPROCESS_SHARPEN),
        max_side=int(settings.OCR_PREPROCESS_MAX_SIDE or 2400),
    )
    if prepared != image_bytes:
        accel = preprocess_status()
        warnings.append(
            "OCR image preprocessed (deskew/ink-isolate/soft-binarize/sharpen/resize) before recognition."
        )
        warnings.append(
            "Preprocess accel: "
            + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in accel.items())
        )

    order = parse_engine_order(settings.OCR_PRIMARY, settings.OCR_FALLBACK_ORDER)
    profile = (getattr(settings, "OCR_PROFILE", "production") or "production").strip().lower()
    if profile == "spec":
        # Spec O1 research profile: TrOCR primary → Vision → Tesseract
        order = parse_engine_order(
            getattr(settings, "OCR_SPEC_PRIMARY", "trocr"),
            getattr(settings, "OCR_SPEC_FALLBACK_ORDER", "google_vision,tesseract"),
        )
        warnings.append(
            "OCR_PROFILE=spec active (TrOCR→Vision→Tesseract). "
            "Production HITL should use OCR_PROFILE=production with Google Vision primary."
        )
    min_conf = float(settings.OCR_MIN_CONFIDENCE)
    preserve = bool(settings.OCR_PRESERVE_ENGINE_OUTPUTS)
    hybrid = bool(settings.OCR_HYBRID_CONSENSUS_ENABLED)
    strategy = (settings.OCR_STRATEGY or "sequential").strip().lower()

    attempts = []
    selected_doc: OcrDocumentResult | None = None
    selected_attempt = None

    def _run_one(engine_id: str):
        nonlocal selected_doc, selected_attempt
        t0 = time.perf_counter()
        if engine_id == "trocr":
            doc = _run_trocr_document(prepared)
            # Optional crop retry assist remains available when Vision is primary legacy path
            attempt = _attempt_from_document("trocr", doc, ms=(time.perf_counter() - t0) * 1000.0)
            if attempt.status == "success" and attempt.confidence is not None and attempt.confidence < min_conf:
                attempt.status = "low_confidence"
                attempt.warning = "TrOCR below OCR_MIN_CONFIDENCE"
        elif engine_id in {"google_vision"}:
            doc = google_vision_document_text(prepared)
            attempt = _attempt_from_document("google_vision", doc, ms=(time.perf_counter() - t0) * 1000.0)
            if attempt.status == "success" and attempt.confidence is not None and attempt.confidence < min_conf:
                attempt.status = "low_confidence"
                attempt.warning = "Google Vision below OCR_MIN_CONFIDENCE"
            # Legacy: when Vision is selected, still allow TrOCR crop retry on low-conf lines
            if (
                doc is not None
                and attempt.status == "success"
                and settings.ENABLE_TROCR_RETRY
                and engine_id == "google_vision"
            ):
                thr = float(settings.TROCR_CONFIDENCE_THRESHOLD)
                refined: list[OcrLine] = []
                for line in doc.lines:
                    if line.confidence < thr:
                        retry = trocr_recognize_crop(prepared, line.bbox)
                        if retry and retry.text:
                            refined.append(retry)
                            warnings.append(
                                f"Secondary crop retry ({retry.engine}) on low-confidence Vision line "
                                f"({line.confidence:.2f})."
                            )
                            continue
                    refined.append(line)
                doc.lines = refined
                doc.full_text = "\n".join(l.text for l in refined)
                attempt = _attempt_from_document("google_vision", doc, ms=(time.perf_counter() - t0) * 1000.0)
        elif engine_id in {"tesseract"}:
            attempt = run_tesseract(prepared)
            if attempt.status == "success" and attempt.confidence is not None and attempt.confidence < min_conf:
                attempt.status = "low_confidence"
                attempt.warning = "Tesseract below OCR_MIN_CONFIDENCE"
            doc = _document_from_attempt(attempt) if attempt.status == "success" else None
        elif engine_id == "paddle":
            paddle_lines = paddle_detect_lines(prepared)
            if not paddle_lines:
                attempt = _attempt_from_document("paddle", None, ms=(time.perf_counter() - t0) * 1000.0)
                doc = None
            else:
                doc = OcrDocumentResult(
                    full_text="\n".join(l["text"] for l in paddle_lines),
                    lines=[
                        OcrLine(
                            text=l["text"],
                            confidence=float(l["confidence"]),
                            bbox=l.get("bbox"),
                            engine="paddleocr",
                            is_mock=False,
                        )
                        for l in paddle_lines
                    ],
                    engine_primary="paddleocr",
                    is_mock=False,
                    warnings=[],
                )
                attempt = _attempt_from_document("paddle", doc, ms=(time.perf_counter() - t0) * 1000.0)
        else:
            attempt = _attempt_from_document(engine_id, None, ms=(time.perf_counter() - t0) * 1000.0)
            doc = None

        logger.info(
            "ocr_engine=%s status=%s ms=%s",
            attempt.engine_id,
            attempt.status,
            f"{attempt.processing_ms:.1f}" if attempt.processing_ms is not None else "n/a",
        )
        if preserve or hybrid or strategy == "sequential":
            attempts.append(attempt)

        if selected_doc is None and is_acceptable(attempt, min_confidence=min_conf):
            selected_attempt = attempt
            selected_doc = doc if doc is not None else _document_from_attempt(attempt)
            selected_doc.selected_engine = attempt.engine_id
            selected_doc.engine_primary = attempt.engine_id

        return attempt

    if strategy in {"sequential", "hybrid"}:
        for engine_id in order:
            _run_one(engine_id)
            # Spec fallback chain: stop after first acceptable unless preserving all outputs
            # or hybrid consensus needs every engine.
            if selected_doc is not None and not preserve and not hybrid:
                break
    else:
        # Legacy single-primary behaviour
        primary = order[0] if order else "google_vision"
        _run_one(primary)

    if selected_doc is None:
        if settings.OCR_ALLOW_MOCK_FALLBACK or settings.APP_ENV == "development":
            mock = _mock_document(
                f"All configured OCR engines unavailable/unacceptable ({','.join(order)}); "
                "using labelled MOCK fallback."
            )
            mock.engine_attempts = [a.to_dict() for a in attempts]
            mock.requires_human_review = True
            mock.warnings.extend(warnings)
            return mock
        raise RuntimeError(
            f"OCR engines unavailable ({','.join(order)}) and OCR_ALLOW_MOCK_FALLBACK=false"
        )

    if hybrid:
        cons = page_consensus(attempts)
        warnings.append(
            f"Hybrid consensus status={cons.consensus_status}; "
            f"requires_human_review={cons.requires_human_review}."
        )
        selected_doc.consensus_status = cons.consensus_status
        selected_doc.consensus_candidates = cons.candidates
        selected_doc.requires_human_review = cons.requires_human_review
        if cons.selected_value and cons.selected_engine:
            # Rebuild selected text from consensus winner without inventing values
            winner = next((a for a in attempts if a.engine_id == cons.selected_engine), None)
            if winner and winner.raw_text:
                selected_doc = _document_from_attempt(winner)
                selected_doc.consensus_status = cons.consensus_status
                selected_doc.consensus_candidates = cons.candidates
                selected_doc.requires_human_review = cons.requires_human_review
    elif selected_attempt and selected_attempt.confidence is not None and selected_attempt.confidence < min_conf:
        selected_doc.requires_human_review = True

    # Privacy-safe transcript
    raw_joined = "\n".join(l.text for l in selected_doc.lines) or selected_doc.full_text
    redacted = redact_ocr_text(raw_joined)
    if redacted != raw_joined:
        warnings.append("PII/admin lines redacted from OCR transcript (privacy-by-design).")
    selected_doc.full_text = redacted
    selected_doc.engine_attempts = [a.to_dict() for a in attempts]
    selected_doc.warnings.extend(warnings)
    if not selected_doc.selected_engine:
        selected_doc.selected_engine = selected_doc.engine_primary
    return selected_doc
