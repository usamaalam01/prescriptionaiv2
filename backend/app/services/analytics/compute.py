"""Session-scoped Summary Analytics (synthetic prescription metrics only)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession
from app.models.therapeutic import TherapeuticDecision, TherapeuticEvaluation
from app.services.analytics.bertscore_optional import bertscore_available, bertscore_status, score_pairs
from app.services.analytics.edit_distance import as_percent, character_error_rate, word_error_rate
from app.services.analytics.normalization import classify_error, normalize_field, normalize_text
from app.services.analytics.pii import assert_no_pii_keys, sanitize_prescription_text
from app.services.formulary_catalog import find_by_canonical

FIELD_DEFS = [
    ("drug_name", "drug", "ai_medicine_name", "pharmacist_medicine_name"),
    ("strength", "strength", "ai_strength", "pharmacist_strength"),
    ("dosage", "dose", "ai_dose", "pharmacist_dose"),
    ("frequency", "frequency", "ai_frequency", "pharmacist_frequency"),
    ("route", "route", "ai_route", "pharmacist_route"),
    ("duration", "duration", "ai_duration", "pharmacist_duration"),
    ("indication", "indication", None, "pharmacist_verified_indication"),
]

DEMO_LABEL = "DEMO DATA"


def _eff(medicine: PrescriptionMedicine, ai_attr: str | None, pharm_attr: str | None) -> tuple[str | None, str | None]:
    ocr = getattr(medicine, ai_attr) if ai_attr else None
    if pharm_attr == "pharmacist_medicine_name":
        confirmed = medicine.pharmacist_medicine_name or (
            medicine.ai_medicine_name if medicine.pharmacist_status == "confirmed" else None
        )
        if medicine.pharmacist_status == "confirmed":
            confirmed = medicine.pharmacist_medicine_name or medicine.ai_medicine_name
    elif pharm_attr:
        confirmed = getattr(medicine, pharm_attr)
        if medicine.pharmacist_status == "confirmed" and confirmed is None and ai_attr:
            # indication has no AI value; others may fall back only if pharmacist left null after confirm
            confirmed = getattr(medicine, ai_attr) if pharm_attr != "pharmacist_verified_indication" else confirmed
    else:
        confirmed = None
    return ocr, confirmed


def _medicine_instruction(medicine: PrescriptionMedicine, *, confirmed: bool) -> str:
    """Build the instruction string used for CER/WER / BertScore text metrics.

    Indication is excluded: OCR never extracts it, so appending pharmacist indication
    would inflate CER/WER without reflecting OCR quality. Clinical SIG changes
    (dose/frequency/form) remain in both sides and still raise CER/WER when they differ.
    """
    if confirmed:
        parts = [
            medicine.pharmacist_medicine_name or medicine.ai_medicine_name,
            medicine.pharmacist_strength or medicine.ai_strength,
            medicine.pharmacist_dose or medicine.ai_dose,
            medicine.pharmacist_frequency or medicine.ai_frequency,
            medicine.pharmacist_route or medicine.ai_route,
            medicine.pharmacist_duration or medicine.ai_duration,
        ]
    else:
        parts = [
            medicine.ai_medicine_name,
            medicine.ai_strength,
            medicine.ai_dose,
            medicine.ai_frequency,
            medicine.ai_route,
            medicine.ai_duration,
        ]
    return " ".join(p for p in parts if p)


def _safe_div(num: float, den: float) -> float | None:
    if den == 0:
        return None
    return num / den


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _entity_prf_bundle(
    comparison_rows: list[dict],
    *,
    mode: str,
) -> tuple[list[dict], dict]:
    """Compute per-entity TP/FP/FN and P/R/F1.

    Always compares:
      Prediction = Original Prescription OCR extracted
      Reference  = Pharmacist-in-the-loop verified / confirmed

    mode='exact'      — character-level string match (no cleanup)
    mode='normalized' — same comparison after spelling / unit / synonym cleanup

    Indication is excluded: OCR never predicts indication.
    """
    entity_metrics: list[dict] = []
    micro_tp = micro_fp = micro_fn = 0
    f1_list: list[float] = []

    for field_key, norm_key, *_ in FIELD_DEFS:
        if field_key == "indication":
            continue
        rows = [r for r in comparison_rows if r["field"] == field_key]
        if not rows:
            continue
        tp = fp = fn = 0
        for r in rows:
            if mode == "exact":
                pred = (r["ocr_value"] or "").strip()
                gold = (r["confirmed_value"] or "").strip()
            else:
                pred = normalize_field(norm_key, r["ocr_value"])
                gold = normalize_field(norm_key, r["confirmed_value"])
            if pred and gold and pred == gold:
                tp += 1
            elif pred and (not gold or pred != gold):
                fp += 1
                if gold and pred != gold:
                    fn += 1
            elif gold and not pred:
                fn += 1
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _f1(precision, recall)
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn
        if f1 is not None:
            f1_list.append(f1)
        entity_metrics.append(
            {
                "entity": field_key,
                "match_mode": mode,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": None if precision is None else round(precision, 4),
                "recall": None if recall is None else round(recall, 4),
                "f1": None if f1 is None else round(f1, 4),
            }
        )

    micro_p = _safe_div(micro_tp, micro_tp + micro_fp)
    micro_r = _safe_div(micro_tp, micro_tp + micro_fn)
    micro_f1 = _f1(micro_p, micro_r)
    macro_f1 = sum(f1_list) / len(f1_list) if f1_list else None
    aggregates = {
        "match_mode": mode,
        "micro_average_precision": None if micro_p is None else round(micro_p, 4),
        "micro_average_recall": None if micro_r is None else round(micro_r, 4),
        "micro_average_f1": None if micro_f1 is None else round(micro_f1, 4),
        "macro_average_f1": None if macro_f1 is None else round(macro_f1, 4),
        "indication_excluded": True,
        "indication_note": (
            "Indication is excluded from entity P/R/F1 because Original Prescription OCR "
            "does not extract indication; pharmacist-supplied indications are tracked separately."
        ),
        "comparison_frame": (
            "Original Prescription OCR extracted vs Pharmacist-in-the-loop verified/confirmed"
        ),
        "mode_label": (
            "Exact match (no cleanup)"
            if mode == "exact"
            else "Normalized match (spelling / units / synonyms)"
        ),
    }
    return entity_metrics, aggregates


def build_fingerprint(
    medicines: list[PrescriptionMedicine],
    ocr: OcrJob | None,
    evaluations: list[TherapeuticEvaluation],
    decisions: list[TherapeuticDecision],
) -> str:
    payload = {
        "schema": "analytics-v2-ocr-vs-pharmacist",
        "ocr_id": ocr.id if ocr else None,
        "ocr_conf": ocr.confidence if ocr else None,
        "meds": [
            {
                "id": m.id,
                "status": m.pharmacist_status,
                "ai": [
                    m.ai_medicine_name,
                    m.ai_strength,
                    m.ai_dose,
                    m.ai_frequency,
                    m.ai_route,
                    m.ai_duration,
                ],
                "ph": [
                    m.pharmacist_medicine_name,
                    m.pharmacist_strength,
                    m.pharmacist_dose,
                    m.pharmacist_frequency,
                    m.pharmacist_route,
                    m.pharmacist_duration,
                    m.pharmacist_verified_indication,
                ],
            }
            for m in medicines
        ],
        "evals": [(e.id, e.created_at.isoformat() if e.created_at else None) for e in evaluations],
        "decisions": [(d.id, d.action, d.created_at.isoformat() if d.created_at else None) for d in decisions],
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_session_analytics(
    db: Session,
    session: ReviewSession,
    *,
    force: bool = False,
) -> dict:
    medicines = list(
        db.scalars(
            select(PrescriptionMedicine)
            .where(PrescriptionMedicine.session_id == session.id)
            .order_by(PrescriptionMedicine.item_number)
        )
    )
    ocr = db.scalar(
        select(OcrJob).where(OcrJob.session_id == session.id).order_by(OcrJob.created_at.desc()).limit(1)
    )
    evaluations = list(
        db.scalars(
            select(TherapeuticEvaluation)
            .where(TherapeuticEvaluation.prescription_id == session.id)
            .order_by(TherapeuticEvaluation.created_at.desc())
        )
    )
    eval_ids = [e.id for e in evaluations]
    decisions: list[TherapeuticDecision] = []
    if eval_ids:
        decisions = list(
            db.scalars(select(TherapeuticDecision).where(TherapeuticDecision.evaluation_id.in_(eval_ids)))
        )

    fingerprint = build_fingerprint(medicines, ocr, evaluations, decisions)

    # Cache on session.pipeline_json companion fields via analytics columns if present
    cached = getattr(session, "analytics_json", None)
    cached_fp = getattr(session, "analytics_fingerprint", None)
    if cached and cached_fp == fingerprint and not force:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    confirmed = [m for m in medicines if m.pharmacist_status == "confirmed"]
    matched = [m for m in medicines if m.formulary_matched or find_by_canonical(m.pharmacist_medicine_name or m.ai_medicine_name)]

    if not medicines and not ocr:
        return {
            "available": False,
            "message": "Analytics will appear after the prescription pipeline is completed and at least one medicine is confirmed.",
            "demo_label": DEMO_LABEL,
            "anonymous_evaluation_id": session.id,
        }

    if not confirmed:
        return {
            "available": False,
            "message": "Analytics will appear after the prescription pipeline is completed and at least one medicine is confirmed.",
            "demo_label": DEMO_LABEL,
            "anonymous_evaluation_id": session.id,
            "summary": {
                "prescription_items_detected": len(medicines),
                "medicines_matched": len(matched),
                "medicines_confirmed": 0,
            },
        }

    comparison_rows = []
    for med in confirmed:
        display_name = med.pharmacist_medicine_name or med.ai_medicine_name
        for field_key, norm_key, ai_attr, ph_attr in FIELD_DEFS:
            ocr_val, conf_val = _eff(med, ai_attr, ph_attr)
            # Skip indication when pharmacist left it blank (optional)
            if field_key == "indication" and not conf_val:
                continue
            if field_key != "indication" and ocr_val is None and conf_val is None:
                continue
            # Indication is pharmacist-supplied context — not an OCR field to score
            if field_key == "indication":
                comparison_rows.append(
                    {
                        "medicine": display_name,
                        "medicine_id": med.id,
                        "field": field_key,
                        "ocr_value": None,
                        "confirmed_value": conf_val,
                        "exact_match": False,
                        "normalized_match": False,
                        "correction_required": False,
                        "error_category": "pharmacist_supplied",
                        "ocr_scorable": False,
                    }
                )
                continue
            exact = (ocr_val or "") == (conf_val or "") and bool(conf_val or ocr_val)
            norm_ocr = normalize_field(norm_key, ocr_val)
            norm_conf = normalize_field(norm_key, conf_val)
            normalized = bool(norm_conf) and norm_ocr == norm_conf
            correction = not exact
            error_cat = classify_error(
                norm_key, ocr_val, conf_val, exact=exact, normalized=normalized and not exact
            )
            comparison_rows.append(
                {
                    "medicine": display_name,
                    "medicine_id": med.id,
                    "field": field_key,
                    "ocr_value": ocr_val,
                    "confirmed_value": conf_val,
                    "exact_match": exact,
                    "normalized_match": normalized or exact,
                    "correction_required": correction,
                    "error_category": error_cat if correction else "none",
                    "ocr_scorable": True,
                }
            )

    # OCR-scorable rows only (exclude pharmacist-supplied indication from OCR KPIs)
    ocr_rows = [r for r in comparison_rows if r.get("ocr_scorable", True)]

    # Field-level accuracy (OCR fields only)
    field_metrics = []
    for field_key, *_ in FIELD_DEFS:
        if field_key == "indication":
            continue
        rows = [r for r in ocr_rows if r["field"] == field_key]
        if not rows:
            continue
        exact_n = sum(1 for r in rows if r["exact_match"])
        norm_n = sum(1 for r in rows if r["normalized_match"])
        corr_n = sum(1 for r in rows if r["correction_required"])
        total = len(rows)
        field_metrics.append(
            {
                "field": field_key,
                "total_evaluated": total,
                "exact_matches": exact_n,
                "normalized_matches": norm_n,
                "corrections": corr_n,
                "exact_match_accuracy": round(exact_n / total, 4) if total else None,
                "normalized_match_accuracy": round(norm_n / total, 4) if total else None,
            }
        )

    # Entity P/R/F1 — exact (primary) and normalized (relaxed); indication excluded
    entity_metrics_exact, entity_aggregates_exact = _entity_prf_bundle(ocr_rows, mode="exact")
    entity_metrics_normalized, entity_aggregates_normalized = _entity_prf_bundle(
        ocr_rows, mode="normalized"
    )
    # Backward-compatible defaults = exact (stricter HITL view)
    entity_metrics = entity_metrics_exact
    entity_aggregates = entity_aggregates_exact
    indication_confirmed = sum(
        1 for r in comparison_rows if r["field"] == "indication" and r.get("confirmed_value")
    )
    entity_aggregates["indication_confirmed_count"] = indication_confirmed
    entity_aggregates_exact["indication_confirmed_count"] = indication_confirmed
    entity_aggregates_normalized["indication_confirmed_count"] = indication_confirmed

    # HITL / OCR usability KPIs (OCR-scorable fields only)
    total_fields = len(ocr_rows)
    fields_corrected = sum(1 for r in ocr_rows if r["correction_required"])
    fields_accepted = total_fields - fields_corrected
    hitl_metrics = {
        "fields_accepted_without_change": fields_accepted,
        "fields_corrected": fields_corrected,
        "automatic_confirmation_rate": round(fields_accepted / total_fields, 4) if total_fields else None,
        "manual_correction_rate": round(fields_corrected / total_fields, 4) if total_fields else None,
        "average_corrections_per_medicine": round(fields_corrected / len(confirmed), 4) if confirmed else None,
        "indication_supplied_count": indication_confirmed,
        "corrections_by_type": {},
        "correction_table": [],
    }
    for r in ocr_rows:
        if not r["correction_required"]:
            continue
        key = f"{r['field']}_correction"
        hitl_metrics["corrections_by_type"][key] = hitl_metrics["corrections_by_type"].get(key, 0) + 1
        hitl_metrics["correction_table"].append(
            {
                "medicine": r["medicine"],
                "field": r["field"],
                "original_ocr_value": r["ocr_value"],
                "confirmed_value": r["confirmed_value"],
                "correction_category": r["error_category"],
            }
        )

    # Text metrics CER/WER
    raw_text = sanitize_prescription_text(ocr.raw_text if ocr else "")
    confirmed_full = sanitize_prescription_text(
        "\n".join(_medicine_instruction(m, confirmed=True) for m in confirmed)
    )
    ocr_full = sanitize_prescription_text(
        "\n".join(_medicine_instruction(m, confirmed=False) for m in confirmed)
    )
    # Raw OCR stage from job if present
    pipeline = {}
    if ocr and ocr.pipeline_json:
        try:
            pipeline = json.loads(ocr.pipeline_json)
        except json.JSONDecodeError:
            pipeline = {}
    paddle_text = None
    if pipeline.get("paddle_lines"):
        paddle_text = sanitize_prescription_text(
            "\n".join(line.get("text") or "" for line in pipeline["paddle_lines"])
        )

    text_metrics = {
        "full_prescription": {
            "raw_cer": as_percent(character_error_rate(paddle_text, confirmed_full)) if paddle_text is not None else None,
            "final_cer": as_percent(character_error_rate(ocr_full, confirmed_full)),
            "raw_wer": as_percent(word_error_rate(paddle_text, confirmed_full)) if paddle_text is not None else None,
            "final_wer": as_percent(word_error_rate(ocr_full, confirmed_full)),
            "raw_available": paddle_text is not None,
            "note": (
                "Hypothesis = Original Prescription OCR extracted. "
                "Reference = Pharmacist-in-the-loop verified/confirmed (not an OCR result)."
            ),
        },
        "medicine_metrics": [],
    }
    if paddle_text is None:
        text_metrics["full_prescription"]["raw_cer"] = None
        text_metrics["full_prescription"]["raw_wer"] = None
        text_metrics["full_prescription"]["raw_status"] = "Not available"

    # Latest therapeutic evaluation (aggregate across all stored evals for session — use newest per medicine)
    latest_eval = evaluations[0] if evaluations else None
    latest_result = json.loads(latest_eval.result_json) if latest_eval else None
    alt_by_item: dict[str, dict] = {}
    if latest_result:
        for mr in latest_result.get("medicine_results") or []:
            alt_by_item[mr.get("prescription_item_id")] = mr

    # BERTScore optional — prescription-level (full text) + per-medicine rows
    bert_rows = []
    prescription_bertscore = None
    status_code = bertscore_status()
    if status_code == "disabled":
        bert_status = "disabled (set ENABLE_BERTSCORE=true)"
    elif status_code == "package_missing":
        bert_status = "Not calculated (bert-score package missing)"
    elif status_code == "failed":
        bert_status = "Not calculated (model load failed)"
    else:
        bert_status = "Not calculated"
    if bertscore_available():
        # Prescription-level: entire OCR instruction block vs pharmacist-accepted block
        if ocr_full.strip() and confirmed_full.strip():
            rx_scores = score_pairs([ocr_full], [confirmed_full])
            if rx_scores:
                prescription_bertscore = {
                    "precision": rx_scores[0]["precision"],
                    "recall": rx_scores[0]["recall"],
                    "f1": rx_scores[0]["f1"],
                    "compared_text": "Full prescription OCR vs pharmacist-accepted instructions",
                }
                bert_status = "calculated"
        hyps, refs, meta = [], [], []
        for med in confirmed:
            hyp = _medicine_instruction(med, confirmed=False)
            ref = _medicine_instruction(med, confirmed=True)
            if hyp.strip() and ref.strip():
                hyps.append(hyp)
                refs.append(ref)
                meta.append(med.pharmacist_medicine_name or med.ai_medicine_name)
        scores = score_pairs(hyps, refs) if hyps else None
        if scores:
            bert_status = "calculated"
            for name, hyp, ref, sc in zip(meta, hyps, refs, scores):
                bert_rows.append(
                    {
                        "medicine": name,
                        "compared_text": "OCR medicine instruction vs pharmacist-confirmed instruction",
                        "hypothesis_preview": hyp[:120],
                        "reference_preview": ref[:120],
                        "bertscore_precision": sc["precision"],
                        "bertscore_recall": sc["recall"],
                        "bertscore_f1": sc["f1"],
                    }
                )
        elif bertscore_status() == "failed":
            bert_status = "Not calculated (model load failed)"
        elif not prescription_bertscore:
            bert_status = "Not calculated (no comparable instruction pairs)"

    medicine_performance = []
    for med in confirmed:
        name = med.pharmacist_medicine_name or med.ai_medicine_name
        rows = [r for r in ocr_rows if r["medicine_id"] == med.id]
        exact_f = sum(1 for r in rows if r["exact_match"])
        norm_f = sum(1 for r in rows if r["normalized_match"])
        corr_f = sum(1 for r in rows if r["correction_required"])
        ocr_instr = _medicine_instruction(med, confirmed=False)
        conf_instr = _medicine_instruction(med, confirmed=True)
        cer = character_error_rate(ocr_instr, conf_instr)
        wer = word_error_rate(ocr_instr, conf_instr)

        # drug match result
        ai_drug = med.ai_medicine_name or ""
        conf_drug = med.pharmacist_medicine_name or med.ai_medicine_name or ""
        if ai_drug == conf_drug:
            drug_match = "exact"
        elif normalize_field("drug", ai_drug) == normalize_field("drug", conf_drug):
            drug_match = "normalized"
        elif med.pharmacist_medicine_name and med.pharmacist_medicine_name != med.ai_medicine_name:
            drug_match = "corrected"
        elif find_by_canonical(conf_drug):
            drug_match = "normalized"
        else:
            drug_match = "unmatched"

        # per-medicine entity F1 — exact OCR vs pharmacist-accepted (indication excluded)
        m_tp = m_fp = m_fn = 0
        for r in rows:
            pred = (r["ocr_value"] or "").strip()
            gold = (r["confirmed_value"] or "").strip()
            if pred and gold and pred == gold:
                m_tp += 1
            elif pred and (not gold or pred != gold):
                m_fp += 1
                if gold and pred != gold:
                    m_fn += 1
            elif gold and not pred:
                m_fn += 1
        m_p = _safe_div(m_tp, m_tp + m_fp)
        m_r = _safe_div(m_tp, m_tp + m_fn)
        m_f1 = _f1(m_p, m_r)

        bert_f1 = None
        for br in bert_rows:
            if br["medicine"] == name:
                bert_f1 = br["bertscore_f1"]
                break

        alt = alt_by_item.get(med.id)
        item_decisions = [d for d in decisions if d.prescription_item_id == med.id]
        alt_status = (alt or {}).get("evaluation_status") or "not_evaluated"
        if any(d.action == "accept_for_review" for d in item_decisions):
            alt_status = "accepted_for_further_review"
        elif any(d.action == "reject" for d in item_decisions):
            alt_status = "rejected"
        elif item_decisions:
            alt_status = item_decisions[-1].action

        medicine_performance.append(
            {
                "medicine_name": name,
                "ocr_confidence": round(med.parser_confidence, 4),
                "drug_match_result": drug_match,
                "fields_evaluated": len(rows),
                "exact_fields": exact_f,
                "normalized_fields": norm_f,
                "corrected_fields": corr_f,
                "cer": None if cer is None else round(cer, 4),
                "wer": None if wer is None else round(wer, 4),
                "entity_f1": None if m_f1 is None else round(m_f1, 4),
                "bertscore_f1": bert_f1 if bert_f1 is not None else "Not calculated",
                "alternative_status": alt_status,
            }
        )
        text_metrics["medicine_metrics"].append(
            {
                "medicine": name,
                "final_cer": as_percent(cer),
                "final_wer": as_percent(wer),
                "raw_cer": "Not available",
                "raw_wer": "Not available",
            }
        )

    # Alternative metrics
    eligible = blocked = withdrawn = insufficient = 0
    scores = []
    coverages = []
    src_db = src_spl = src_ndc = 0
    per_med_alt = []
    candidates_total = 0
    if latest_result:
        for mr in latest_result.get("medicine_results") or []:
            el = mr.get("eligible_alternatives") or []
            bl = mr.get("blocked_candidates") or []
            wd = mr.get("withdrawn_candidates") or []
            ins = mr.get("insufficient_candidates") or []
            eligible += len(el)
            blocked += len(bl)
            withdrawn += len(wd)
            insufficient += len(ins)
            bag = el + bl + wd + ins
            candidates_total += len(bag)
            for c in el:
                if c.get("evidence_match_score") is not None:
                    scores.append(c["evidence_match_score"])
                cov = (c.get("evidence_coverage") or {}).get("coverage_percentage")
                if cov is not None:
                    coverages.append(cov)
            for c in bag:
                for claim in c.get("source_claims") or []:
                    ds = claim.get("source_dataset")
                    if ds == "DrugBank":
                        src_db += 1
                    elif ds == "FDA_SPL":
                        src_spl += 1
                    elif ds == "FDA_NDC":
                        src_ndc += 1
            top = max((c.get("evidence_match_score") or 0) for c in el) if el else None
            avg = (sum(c.get("evidence_match_score") or 0 for c in el) / len(el)) if el else None
            avg_cov = (
                sum((c.get("evidence_coverage") or {}).get("coverage_percentage") or 0 for c in el) / len(el)
                if el
                else None
            )
            item_decisions = [d for d in decisions if d.prescription_item_id == mr.get("prescription_item_id")]
            accepted_count = sum(1 for d in item_decisions if d.action == "accept_for_review")
            rejected_count = sum(1 for d in item_decisions if d.action == "reject")
            decision_status = "pending"
            if accepted_count and not rejected_count:
                decision_status = "accepted"
            elif rejected_count and not accepted_count:
                decision_status = "rejected"
            elif accepted_count or rejected_count:
                decision_status = "mixed"
            per_med_alt.append(
                {
                    "prescription_item_id": mr.get("prescription_item_id"),
                    "prescribed_medicine": (mr.get("source_medicine") or {}).get("medicine_name"),
                    "candidates_found": len(bag),
                    "eligible": len(el),
                    "excluded": len(bl) + len(wd) + len(ins),
                    "accepted": accepted_count,
                    "rejected": rejected_count,
                    "top_evidence_match_score": top,
                    "average_evidence_match_score": None if avg is None else round(avg, 2),
                    "evidence_coverage": None if avg_cov is None else round(avg_cov, 2),
                    "decision_status": decision_status,
                }
            )

    # Ensure every confirmed medicine appears in the alternatives chart
    seen_ids = {row.get("prescription_item_id") for row in per_med_alt}
    for med in confirmed:
        if med.id in seen_ids:
            continue
        item_decisions = [d for d in decisions if d.prescription_item_id == med.id]
        accepted_count = sum(1 for d in item_decisions if d.action == "accept_for_review")
        rejected_count = sum(1 for d in item_decisions if d.action == "reject")
        per_med_alt.append(
            {
                "prescription_item_id": med.id,
                "prescribed_medicine": med.pharmacist_medicine_name or med.ai_medicine_name,
                "candidates_found": 0,
                "eligible": 0,
                "excluded": 0,
                "accepted": accepted_count,
                "rejected": rejected_count,
                "top_evidence_match_score": None,
                "average_evidence_match_score": None,
                "evidence_coverage": None,
                "decision_status": "not_evaluated",
            }
        )
    # Stable order by confirmed medicine item_number
    order = {m.id: m.item_number for m in confirmed}
    per_med_alt.sort(key=lambda row: order.get(row.get("prescription_item_id") or "", 999))

    accept_n = sum(1 for d in decisions if d.action == "accept_for_review")
    reject_n = sum(1 for d in decisions if d.action == "reject")
    pending_n = max(0, eligible - accept_n - reject_n) if latest_result else 0

    alternative_metrics = {
        "medicines_evaluated": len(alt_by_item),
        "total_candidates_retrieved": candidates_total,
        "eligible_alternatives": eligible,
        "excluded_alternatives": blocked + withdrawn + insufficient,
        "withdrawn_alternatives": withdrawn,
        "insufficient_evidence_candidates": insufficient,
        "average_evidence_match_score": round(sum(scores) / len(scores), 2) if scores else None,
        "average_evidence_coverage": round(sum(coverages) / len(coverages), 2) if coverages else None,
        "candidates_supported_by_drugbank": src_db,
        "candidates_supported_by_fda_spl": src_spl,
        "candidates_supported_by_fda_ndc": src_ndc,
        "accepted_for_further_review": accept_n,
        "rejected": reject_n,
        "pending_pharmacist_decision": pending_n,
        "per_medicine": per_med_alt,
        "note": "Evidence Match Score is not clinical confidence.",
        "evaluation_id": latest_eval.id if latest_eval else None,
    }

    confidences = [m.parser_confidence for m in medicines if m.parser_confidence is not None]
    avg_ocr = round(sum(confidences) / len(confidences), 4) if confidences else None
    session_ocr_confidence = (
        round(float(ocr.confidence), 4) if ocr and ocr.confidence is not None else None
    )

    exact_rate = round(sum(1 for r in ocr_rows if r["exact_match"]) / total_fields, 4) if total_fields else None
    norm_rate = (
        round(sum(1 for r in ocr_rows if r["normalized_match"]) / total_fields, 4) if total_fields else None
    )

    # Provenance: catalog sessions are not DEMO seed analytics
    try:
        from app.services.datasets.catalog_store import catalog_available

        provenance = "FDA NDC + DrugBank catalog" if catalog_available() else DEMO_LABEL
    except Exception:  # noqa: BLE001
        provenance = DEMO_LABEL

    result = {
        "available": True,
        "demo_label": provenance,
        "provenance_label": provenance,
        "anonymous_evaluation_id": session.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "disclaimer": (
            "Application usability analytics: Original Prescription OCR vs pharmacist-accepted "
            "values (Precision, Recall, F1, CER/WER, BertScore when available). "
            "Indication is pharmacist-supplied and excluded from OCR correction/accuracy KPIs. "
            "These metrics measure OCR↔HITL agreement and workflow effort — not independent "
            "gold-label OCR accuracy, clinical correctness, therapeutic suitability, or patient safety."
        ),
        "summary": {
            "prescription_items_detected": len(medicines),
            "medicines_matched": len(matched),
            "medicines_confirmed": len(confirmed),
            "total_fields_evaluated": total_fields,
            "fields_accepted": fields_accepted,
            "fields_corrected": fields_corrected,
            "exact_match_rate": exact_rate,
            "normalized_match_rate": norm_rate,
            "average_ocr_confidence": avg_ocr,
            "session_ocr_confidence": session_ocr_confidence,
            "indication_supplied_count": indication_confirmed,
            "alternative_evaluations_completed": len(alt_by_item),
            # Engine candidates vs pharmacist TA decisions (no key collision)
            "eligible_alternatives": eligible,
            "excluded_alternatives": blocked + withdrawn + insufficient,
            "pharmacist_accepted_alternatives": accept_n,
            "pharmacist_rejected_alternatives": reject_n,
            "alternative_accepted": accept_n,
            "alternative_rejected": reject_n,
            "alternative_pending": pending_n,
            "candidate_alternatives_ranked": eligible,
        },
        "text_metrics": text_metrics,
        "field_metrics": field_metrics,
        "entity_metrics": entity_metrics,
        "entity_aggregates": entity_aggregates,
        "entity_metrics_exact": entity_metrics_exact,
        "entity_aggregates_exact": entity_aggregates_exact,
        "entity_metrics_normalized": entity_metrics_normalized,
        "entity_aggregates_normalized": entity_aggregates_normalized,
        "bertscore_metrics": bert_rows,
        "bertscore_status": bert_status,
        "prescription_bertscore": prescription_bertscore,
        "hitl_metrics": hitl_metrics,
        "alternative_metrics": alternative_metrics,
        "comparison_rows": comparison_rows,
        "medicine_performance": medicine_performance,
    }

    assert_no_pii_keys(result)

    # Persist cache if columns exist
    if hasattr(session, "analytics_json"):
        session.analytics_json = json.dumps(result, default=str)
        session.analytics_fingerprint = fingerprint
        session.analytics_updated_at = datetime.now(timezone.utc)
        db.commit()

    return result
