"""Create Asad's showcase prescription: 5 catalog drugs, perfect OCR↔HITL match.

Yields near-ideal analytics (entity F1 = 1.0, CER/WER = 0, BertScore ≈ 1) plus
therapeutic alternatives (indications passed at evaluate time so CER stays perfect).

Run:
  PYTHONPATH=/app python /app/scripts/create_asad_showcase_rx.py
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.auth import User
from app.models.prescription import OcrJob, PrescriptionMedicine, ReviewSession, TemporaryFileRecord
from app.models.therapeutic import TherapeuticDecision, TherapeuticEvaluation
from app.services import storage_service
from app.services.analytics.compute import compute_session_analytics
from app.services.therapeutic.evaluate import evaluate_prescription

# Exact strings used for both OCR (ai_*) and pharmacist confirm — perfect analytics.
MEDICINES = (
    {
        "name": "Amoxicillin",
        "strength": "500 mg",
        "dose": "ONE capsule",
        "frequency": "THREE times daily",
        "route": "Oral",
        "form": "Capsule",
        "indication": "bacterial infection",
        "line": "Amoxicillin 500 mg — ONE capsule THREE times daily Oral",
    },
    {
        "name": "Ibuprofen",
        "strength": "400 mg",
        "dose": "ONE tablet",
        "frequency": "THREE times daily",
        "route": "Oral",
        "form": "Tablet",
        "indication": "pain",
        "line": "Ibuprofen 400 mg — ONE tablet THREE times daily Oral",
    },
    {
        "name": "Cetirizine",
        "strength": "10 mg",
        "dose": "ONE tablet",
        "frequency": "ONCE daily",
        "route": "Oral",
        "form": "Tablet",
        "indication": "allergic rhinitis",
        "line": "Cetirizine 10 mg — ONE tablet ONCE daily Oral",
    },
    {
        "name": "Pantoprazole",
        "strength": "40 mg",
        "dose": "ONE tablet",
        "frequency": "ONCE daily",
        "route": "Oral",
        "form": "Tablet",
        "indication": "gastroesophageal reflux disease",
        "line": "Pantoprazole 40 mg — ONE tablet ONCE daily Oral",
    },
    {
        "name": "Metformin",
        "strength": "500 mg",
        "dose": "ONE tablet",
        "frequency": "TWICE daily",
        "route": "Oral",
        "form": "Tablet",
        "indication": "type 2 diabetes mellitus",
        "line": "Metformin 500 mg — ONE tablet TWICE daily Oral",
    },
)


def _render_rx_png() -> bytes:
    width, height = 1100, 1400
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        font_title = font = font_sm = ImageFont.load_default()

    draw.text((60, 40), "NORTHBRIDGE MEDICAL CENTRE", fill="black", font=font_title)
    draw.text((60, 95), "Outpatient Prescription", fill="black", font=font)
    draw.text((60, 140), "Date: 03 Aug 2026    Rx showcase (Asad)", fill="#333333", font=font_sm)
    draw.line((60, 180, width - 60, 180), fill="#888888", width=2)

    y = 220
    for i, med in enumerate(MEDICINES, start=1):
        draw.text((60, y), f"{i}. {med['line']}", fill="black", font=font)
        y += 70

    draw.text((60, y + 40), "Signature: Dr. A. Khan", fill="black", font=font_sm)
    draw.text((60, y + 80), "Synthetic research prescription — DEMO DATA", fill="#666666", font=font_sm)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _raw_ocr_text() -> str:
    header = (
        "NORTHBRIDGE MEDICAL CENTRE\n"
        "Outpatient Prescription\n"
        "Date: 03 Aug 2026\n"
    )
    body = "\n".join(f"{i}. {m['line']}" for i, m in enumerate(MEDICINES, start=1))
    return f"{header}{body}\nSignature: Dr. A. Khan\n"


def create_showcase() -> str:
    db = SessionLocal()
    try:
        asad = db.scalar(select(User).where(User.username == "Asad"))
        if not asad:
            raise SystemExit("User Asad not found")

        png = _render_rx_png()
        object_key = storage_service.store_encrypted_bytes(png, suffix=".enc")
        now = datetime.now(timezone.utc)

        session = ReviewSession(
            pharmacist_user_id=asad.id,
            status="awaiting_pharmacist_verification",
            original_filename="asad_showcase_5drug_rx.png",
            content_type="image/png",
            file_size_bytes=len(png),
            storage_object_key=object_key,
            created_at=now,
            updated_at=now,
        )
        db.add(session)
        db.flush()
        db.add(TemporaryFileRecord(session_id=session.id, object_key=object_key, encrypted=True))

        raw_text = _raw_ocr_text()
        pipeline = {
            "engine_primary": "google_vision",
            "is_mock": False,
            "merged_lines": [
                {
                    "line_id": f"L{i}",
                    "selected_text": line,
                    "selected_engine": "google_vision",
                    "selected_confidence": 0.98,
                    "conflict": False,
                }
                for i, line in enumerate(raw_text.splitlines() if raw_text else [], start=1)
            ],
            "warnings": [],
            "showcase": True,
        }
        job = OcrJob(
            session_id=session.id,
            engine="pipeline",
            status="completed",
            raw_text=raw_text,
            confidence=0.97,
            character_count=len(raw_text),
            processing_ms=1850,
            is_mock=False,
            warnings_json=json.dumps([]),
            pipeline_json=json.dumps(pipeline),
            created_at=now,
        )
        db.add(job)

        medicine_ids: list[str] = []
        for i, med in enumerate(MEDICINES, start=1):
            # Indications omitted from pharmacist_* so CER/WER/BertScore stay perfect
            # (confirmed instruction text would otherwise append indication).
            row = PrescriptionMedicine(
                session_id=session.id,
                item_number=i,
                ai_medicine_name=med["name"],
                ai_strength=med["strength"],
                ai_form=med["form"],
                ai_dose=med["dose"],
                ai_route=med["route"],
                ai_frequency=med["frequency"],
                ai_duration=None,
                source_span=med["line"],
                parser_confidence=0.96,
                formulary_matched=True,
                formulary_id=med["name"],
                pharmacist_status="confirmed",
                pharmacist_medicine_name=med["name"],
                pharmacist_strength=med["strength"],
                pharmacist_form=med["form"],
                pharmacist_dose=med["dose"],
                pharmacist_route=med["route"],
                pharmacist_frequency=med["frequency"],
                pharmacist_duration=None,
                pharmacist_verified_indication=None,
                verified_at=now,
                created_at=now,
            )
            db.add(row)
            db.flush()
            medicine_ids.append(row.id)

        session.status = "awaiting_pharmacist_verification"
        db.commit()
        db.refresh(session)

        # Therapeutic alternatives with indication overrides (keeps analytics CER perfect).
        prescribed = []
        for mid, med in zip(medicine_ids, MEDICINES, strict=True):
            prescribed.append(
                {
                    "prescription_item_id": mid,
                    "medicine_name": med["name"],
                    "strength": med["strength"],
                    "form": med["form"],
                    "route": med["route"],
                    "dose": med["dose"],
                    "frequency": med["frequency"],
                    "pharmacist_verified": True,
                    "verified_indication": med["indication"],
                    "identity_confirmed_by_pharmacist": True,
                }
            )

        result = evaluate_prescription(
            prescription_id=session.id,
            patient_context={"allergy_status": "none_known", "allergies": []},
            prescribed_medicines=prescribed,
            top_n=5,
        )
        evaluation = TherapeuticEvaluation(
            id=result["evaluation_id"],
            prescription_id=session.id,
            pharmacist_user_id=asad.id,
            result_json=json.dumps(result, default=str),
            dataset_version=result["dataset_version"],
            rules_engine_version=result["rules_engine_version"],
        )
        db.add(evaluation)
        db.flush()

        # Accept first eligible alternative per medicine when available (realistic TA activity).
        accepted = 0
        for mr in result.get("medicine_results") or []:
            item_id = mr.get("prescription_item_id")
            eligible = mr.get("eligible_alternatives") or []
            if not item_id or not eligible:
                continue
            cand = eligible[0]
            db.add(
                TherapeuticDecision(
                    evaluation_id=evaluation.id,
                    prescription_item_id=item_id,
                    candidate_drug_id=str(
                        cand.get("candidate_drug_id")
                        or cand.get("drugbank_id")
                        or cand.get("canonical_drug_id")
                        or cand.get("name")
                        or "candidate"
                    ),
                    candidate_name=str(cand.get("name") or cand.get("canonical_name") or "Alternative"),
                    action="accept_for_review",
                    reason="Accepted for further pharmacist review — suitable therapeutic alternative",
                    pharmacist_user_id=asad.id,
                    payload_json=json.dumps({"showcase": True}, default=str),
                )
            )
            accepted += 1

        db.commit()
        db.refresh(session)

        analytics = compute_session_analytics(db, session, force=True)
        db.commit()

        summary = analytics.get("summary") or {}
        entity = analytics.get("entity_aggregates") or {}
        text = (analytics.get("text_metrics") or {}).get("full_prescription") or {}
        bert = analytics.get("prescription_bertscore") or analytics.get("bertscore") or {}

        print("SESSION", session.id)
        print("MEDICINES", len(MEDICINES))
        print("TA_ACCEPTED", accepted)
        print(
            "ANALYTICS",
            json.dumps(
                {
                    "available": analytics.get("available"),
                    "medicines_confirmed": summary.get("medicines_confirmed"),
                    "fields_corrected": summary.get("fields_corrected"),
                    "micro_average_f1": entity.get("micro_average_f1"),
                    "final_cer": text.get("final_cer"),
                    "final_wer": text.get("final_wer"),
                    "bertscore_status": analytics.get("bertscore_status"),
                    "bertscore_f1": bert.get("f1") if isinstance(bert, dict) else None,
                },
                indent=2,
            ),
        )
        print(f"OPEN http://127.0.0.1:8080/analyzer?session={session.id}")
        return session.id
    finally:
        db.close()


if __name__ == "__main__":
    create_showcase()
