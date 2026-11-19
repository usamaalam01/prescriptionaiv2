"""Generate a formatted PDF of the pharmacist-confirmed prescription for download.

Built from the confirmed/resolved fields only (pharmacist_* columns) — never the raw
OCR output — since this is meant to be the finalized, verified record, not a copy of
what the AI first read off the image. Decision-support only; not a clinical record.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.auth import User
from app.models.prescription import PrescriptionMedicine, ReviewSession

STATUS_LABELS = {
    "confirmed": "Confirmed",
    "excluded": "Excluded by pharmacist",
    "unidentified": "Unable to verify",
}


def _field(medicine: PrescriptionMedicine, name: str) -> str:
    """Pharmacist-confirmed value if present, else the dash placeholder —
    never fall back to the AI-extracted value in this document."""
    value = getattr(medicine, f"pharmacist_{name}", None)
    return value if value else "—"


def build_prescription_pdf(
    session: ReviewSession,
    pharmacist: User,
    medicines: list[PrescriptionMedicine],
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        title=f"Prescription {session.id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Heading1"], fontSize=16, spaceAfter=2
    )
    subtitle_style = ParagraphStyle(
        "SubtitleStyle", parent=styles["Normal"], fontSize=9, textColor=colors.grey
    )
    section_style = ParagraphStyle(
        "SectionStyle", parent=styles["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4
    )
    disclaimer_style = ParagraphStyle(
        "DisclaimerStyle",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
        spaceBefore=12,
    )

    story = []
    story.append(Paragraph("MediScan — Pharmacist-Verified Prescription Record", title_style))
    story.append(
        Paragraph(
            "Decision-support output. Not a clinical prescription or a substitute for "
            "the original document.",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta_rows = [
        ["Session ID", session.id],
        ["Verified by (pharmacist account)", pharmacist.username],
        ["Original file", session.original_filename],
        ["Session status", session.status],
        ["Generated at", generated_at],
    ]
    meta_table = Table(meta_rows, colWidths=[55 * mm, 110 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(meta_table)

    story.append(Paragraph("Confirmed medicines", section_style))

    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=8, leading=10)
    cell_center_style = ParagraphStyle("CellCenterStyle", parent=cell_style, alignment=1)  # TA_CENTER
    header_style = ParagraphStyle(
        "CellHeaderStyle",
        parent=cell_center_style,
        textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    def cell(text: str, style: ParagraphStyle = cell_style) -> Paragraph:
        return Paragraph(text, style)

    header = ["#", "Drug", "Strength", "Form", "Dose", "Route", "Frequency", "Duration", "Status"]
    data = [[cell(h, header_style) for h in header]]
    for med in medicines:
        status = STATUS_LABELS.get(med.pharmacist_status, med.pharmacist_status)
        data.append(
            [
                cell(str(med.item_number), cell_center_style),
                cell(_field(med, "medicine_name")),
                cell(_field(med, "strength")),
                cell(_field(med, "form")),
                cell(_field(med, "dose")),
                cell(_field(med, "route")),
                cell(_field(med, "frequency")),
                cell(_field(med, "duration")),
                cell(status),
            ]
        )

    # Widths sum to the full usable page width (A4 minus 18mm margins each side = 174mm).
    table = Table(
        data,
        colWidths=[7 * mm, 26 * mm, 16 * mm, 14 * mm, 16 * mm, 14 * mm, 24 * mm, 15 * mm, 42 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D47A1")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)

    excluded_with_reason = [
        m for m in medicines if m.pharmacist_status in {"excluded", "unidentified"} and m.pharmacist_reason
    ]
    if excluded_with_reason:
        story.append(Paragraph("Notes on excluded / unverifiable items", section_style))
        for med in excluded_with_reason:
            story.append(
                Paragraph(
                    f"#{med.item_number} {_field(med, 'medicine_name')}: {med.pharmacist_reason}",
                    styles["Normal"],
                )
            )

    story.append(
        Paragraph(
            "Pharmacist decision-support only. Not clinical care; this record reflects "
            "fields a licensed pharmacist confirmed, corrected, or marked unable to verify "
            "against a trusted drug catalog (FDA NDC / DrugBank / FDA SPL). It is not a "
            "substitute for the original prescription or for independent clinical judgment.",
            disclaimer_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
