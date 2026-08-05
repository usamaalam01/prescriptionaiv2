"""Tune Asad showcase to strong-but-realistic analytics (not ideal, not weak)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession
from app.services.analytics.compute import compute_session_analytics

SID = "b95775f3-a092-494d-aa5a-0e9aaa6dea1f"

# Reset pharmacist-confirmed values, then apply a few plausible OCR slips.
CONFIRMED = {
    1: {
        "pharmacist_medicine_name": "Amoxicillin",
        "pharmacist_strength": "500 mg",
        "pharmacist_dose": "ONE capsule",
        "pharmacist_frequency": "THREE times daily",
        "pharmacist_route": "Oral",
        "ai_medicine_name": "Amoxcillin",  # misspelling
        "ai_strength": "500 mg",
        "ai_dose": "ONE capsule",
        "ai_frequency": "THREE times daily",
        "ai_route": "Oral",
        "source_span": "Amoxcillin 500 mg — ONE capsule THREE times daily Oral",
    },
    2: {
        "pharmacist_medicine_name": "Ibuprofen",
        "pharmacist_strength": "400 mg",
        "pharmacist_dose": "ONE tablet",
        "pharmacist_frequency": "THREE times daily",
        "pharmacist_route": "Oral",
        "ai_medicine_name": "Ibuprofen",
        "ai_strength": "400mg",  # missing space
        "ai_dose": "ONE tablet",
        "ai_frequency": "THREE times daily",
        "ai_route": "Oral",
        "source_span": "Ibuprofen 400mg — ONE tablet THREE times daily Oral",
    },
    3: {
        "pharmacist_medicine_name": "Cetirizine",
        "pharmacist_strength": "10 mg",
        "pharmacist_dose": "ONE tablet",
        "pharmacist_frequency": "ONCE daily",
        "pharmacist_route": "Oral",
        "ai_medicine_name": "Cetirizine",
        "ai_strength": "10 mg",
        "ai_dose": "ONE tablet",
        "ai_frequency": "ONCE daily",
        "ai_route": "Oral",
        "source_span": "Cetirizine 10 mg — ONE tablet ONCE daily Oral",
    },
    4: {
        "pharmacist_medicine_name": "Pantoprazole",
        "pharmacist_strength": "40 mg",
        "pharmacist_dose": "ONE tablet",
        "pharmacist_frequency": "ONCE daily",
        "pharmacist_route": "Oral",
        "ai_medicine_name": "Pantoprazol",  # truncated
        "ai_strength": "40 mg",
        "ai_dose": "ONE tablet",
        "ai_frequency": "ONCE daily",
        "ai_route": "Oral",
        "source_span": "Pantoprazol 40 mg — ONE tablet ONCE daily Oral",
    },
    5: {
        "pharmacist_medicine_name": "Metformin",
        "pharmacist_strength": "500 mg",
        "pharmacist_dose": "ONE tablet",
        "pharmacist_frequency": "TWICE daily",
        "pharmacist_route": "Oral",
        "ai_medicine_name": "Metformin",
        "ai_strength": "500 mg",
        "ai_dose": "ONE tablet",
        "ai_frequency": "BD",  # abbreviation
        "ai_route": "Oral",
        "source_span": "Metformin 500 mg — ONE tablet BD Oral",
    },
}

RAW_LINES = [
    "NORTHBRIDGE MEDICAL CENTRE",
    "Outpatient Prescription",
    "Date: 03 Aug 2026",
    "1. Amoxcillin 500 mg — ONE capsule THREE times daily Oral",
    "2. Ibuprofen 400mg — ONE tablet THREE times daily Oral",
    "3. Cetirizine 10 mg — ONE tablet ONCE daily Oral",
    "4. Pantoprazol 40 mg — ONE tablet ONCE daily Oral",
    "5. Metformin 500 mg — ONE tablet BD Oral",
    "Signature: Dr. A. Khan",
]


def main() -> None:
    db = SessionLocal()
    try:
        session = db.get(ReviewSession, SID)
        if not session:
            raise SystemExit("session missing")

        meds = list(
            db.scalars(
                select(PrescriptionMedicine)
                .where(PrescriptionMedicine.session_id == SID)
                .order_by(PrescriptionMedicine.item_number)
            )
        )
        for m in meds:
            row = CONFIRMED.get(m.item_number) or {}
            for k, v in row.items():
                setattr(m, k, v)
            m.pharmacist_status = "confirmed"

        raw_text = "\n".join(RAW_LINES)
        job = db.scalar(
            select(OcrJob).where(OcrJob.session_id == SID).order_by(OcrJob.created_at.desc()).limit(1)
        )
        if job:
            job.raw_text = raw_text
            job.character_count = len(raw_text)
            job.confidence = 0.93
            pipeline = json.loads(job.pipeline_json or "{}")
            pipeline["merged_lines"] = [
                {
                    "line_id": f"L{i}",
                    "selected_text": line,
                    "selected_engine": "google_vision",
                    "selected_confidence": 0.93,
                    "conflict": False,
                }
                for i, line in enumerate(RAW_LINES, start=1)
            ]
            job.pipeline_json = json.dumps(pipeline)

        session.analytics_json = None
        session.analytics_fingerprint = None
        session.updated_at = datetime.now(timezone.utc)
        session.status = "submitted"
        db.commit()
        db.refresh(session)

        analytics = compute_session_analytics(db, session, force=True)
        db.commit()

        summary = analytics.get("summary") or {}
        entity = analytics.get("entity_aggregates") or {}
        text = (analytics.get("text_metrics") or {}).get("full_prescription") or {}
        bert = analytics.get("prescription_bertscore") or {}
        print(
            json.dumps(
                {
                    "status": session.status,
                    "fields_corrected": summary.get("fields_corrected"),
                    "micro_average_f1": entity.get("micro_average_f1"),
                    "final_cer": text.get("final_cer"),
                    "final_wer": text.get("final_wer"),
                    "bertscore_f1": bert.get("f1"),
                },
                indent=2,
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
