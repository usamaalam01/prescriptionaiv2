"""
MediScan — Final Project Presentation generator (data-driven, one layout per slide type).

Builds the 11-slide deck specified in MediScan_Presentation.md, following the official
NED University CMPP Annexure F template's slide order, with a visual design system reused
from D:\\Certifications\\OnlineCourses\\PMP\\generate_pptx.py (same palette, chrome, layout
approach — "EXAM TIP" renamed to "KEY POINT").

Usage:
    python generate_pptx.py
Writes MediScan_Final_Presentation.pptx next to this script.
"""
import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "MediScan_Final_Presentation.pptx")

LOGO_STANDARD = os.path.join(
    HERE, "..", "..", "uni-docs", "new", "_logo_standard.jpg"
)
LOGO_CENTENARY = os.path.join(
    HERE, "..", "..", "uni-docs", "new", "_logo_centenary.jpg"
)

# ── palette (reused exactly from the PMP reference deck) ────────────────────
SKY = RGBColor(0x00, 0x8B, 0xD4)
SKY_DARK = RGBColor(0x00, 0x5F, 0x99)
SKY_LIGHT = RGBColor(0xD6, 0xEE, 0xF8)
TEAL = RGBColor(0x00, 0xAD, 0x9F)
TEAL_LIGHT = RGBColor(0xCC, 0xF0, 0xEC)
ORANGE = RGBColor(0xFF, 0x6B, 0x00)
ORANGE_LIGHT = RGBColor(0xFF, 0xEB, 0xDB)
TIP_BG = RGBColor(0xFF, 0xF4, 0xCC)
TIP_BORDER = RGBColor(0xFF, 0xB4, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
OFF_WHITE = RGBColor(0xF5, 0xF9, 0xFF)
DARK = RGBColor(0x0D, 0x1C, 0x2E)
MID_GREY = RGBColor(0x55, 0x6B, 0x82)
LIGHT_GREY = RGBColor(0xB0, 0xC4, 0xD8)
ROW_ALT = RGBColor(0xEA, 0xF4, 0xFB)

SW, SH = Inches(13.333), Inches(7.5)
HEADER_H = Inches(0.95)
FOOTER_H = Inches(0.32)
MARGIN = Inches(0.45)
BODY_TOP = HEADER_H + Inches(0.22)
BODY_BOTTOM = SH - FOOTER_H - Inches(0.12)

FOOTER_TAG = "MediScan \u2014 PGD in Generative AI, Batch 5"
TOTAL_SLIDES = 11


# ─────────────────────────────────────────────────────────────────────────────
# drawing helpers
# ─────────────────────────────────────────────────────────────────────────────
def rect(slide, l, t, w, h, fill, line=None, line_w=1.0, rounded=False, radius=0.08):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        int(l), int(t), int(w), int(h),
    )
    if rounded:
        shp.adjustments[0] = radius
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    return shp


def set_bg(slide, color):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def textbox(slide, l, t, w, h, anchor=MSO_ANCHOR.TOP, margins=(0.05, 0.03)):
    tb = slide.shapes.add_textbox(int(l), int(t), int(w), int(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(margins[0])
    tf.margin_right = Inches(margins[0])
    tf.margin_top = Inches(margins[1])
    tf.margin_bottom = Inches(margins[1])
    return tb, tf


def runs(para, text, size, color=DARK, bold=False, align=None, italic=False, font="Calibri"):
    if align is not None:
        para.alignment = align
    r = para.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font
    r.font.color.rgb = color
    return r


def bullet_para(tf, first, text, size=16, color=DARK, level=0, bold_lead=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(8)
    p.level = level
    bullet_char = "\u2022  " if level == 0 else "\u2013  "
    r0 = p.add_run()
    r0.text = bullet_char
    r0.font.size = Pt(size)
    r0.font.color.rgb = TEAL
    r0.font.name = "Calibri"
    if bold_lead:
        r1 = p.add_run()
        r1.text = bold_lead
        r1.font.bold = True
        r1.font.size = Pt(size)
        r1.font.color.rgb = DARK
        r1.font.name = "Calibri"
    r2 = p.add_run()
    r2.text = text
    r2.font.size = Pt(size)
    r2.font.color.rgb = color
    r2.font.name = "Calibri"
    return p


def chrome(prs, title, pill_text, n, accent=SKY):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, OFF_WHITE)
    rect(slide, 0, 0, SW, HEADER_H, accent)
    rect(slide, 0, 0, Inches(0.14), HEADER_H, TEAL)
    _, tf = textbox(slide, Inches(0.38), Inches(0.08), Inches(9.6), HEADER_H - Inches(0.16),
                     anchor=MSO_ANCHOR.MIDDLE)
    size = 30 if len(title) <= 44 else (26 if len(title) <= 58 else 22)
    runs(tf.paragraphs[0], title, size, WHITE, bold=True)
    # topic pill (top-right) — the Annexure F conformance marker
    pill_w = Inches(0.35 + 0.11 * len(pill_text))
    pill_x = SW - Inches(0.35) - pill_w
    rect(slide, pill_x, Inches(0.27), pill_w, Inches(0.42), SKY_DARK, rounded=True, radius=0.5)
    _, ptf = textbox(slide, pill_x, Inches(0.27), pill_w, Inches(0.42), anchor=MSO_ANCHOR.MIDDLE)
    runs(ptf.paragraphs[0], pill_text, 13, WHITE, bold=True, align=PP_ALIGN.CENTER)
    # footer
    rect(slide, 0, SH - FOOTER_H, SW, FOOTER_H, SKY_DARK)
    _, ftf = textbox(slide, MARGIN, SH - FOOTER_H, Inches(8), FOOTER_H, anchor=MSO_ANCHOR.MIDDLE)
    runs(ftf.paragraphs[0], FOOTER_TAG, 11, WHITE)
    _, ntf = textbox(slide, SW - Inches(1.3), SH - FOOTER_H, Inches(0.85), FOOTER_H,
                      anchor=MSO_ANCHOR.MIDDLE)
    runs(ntf.paragraphs[0], f"{n} / {TOTAL_SLIDES}", 11, WHITE, align=PP_ALIGN.RIGHT)
    return slide


def body_card(slide, top, height, left=MARGIN, width=None):
    width = width if width is not None else (SW - 2 * MARGIN)
    rect(slide, left, top, width, height, WHITE, line=LIGHT_GREY, line_w=1.0, rounded=True, radius=0.03)
    rect(slide, left, top + Inches(0.12), Inches(0.09), height - Inches(0.24), TEAL)
    return left, top, width, height


def key_point(slide, text, top, width=None, left=None):
    left = left if left is not None else MARGIN
    width = width if width is not None else (SW - 2 * MARGIN)
    height = Inches(0.95) if len(text) > 140 else Inches(0.72)
    rect(slide, left, top, width, height, TIP_BG, line=TIP_BORDER, line_w=1.5, rounded=True, radius=0.12)
    rect(slide, left, top, Inches(0.1), height, TIP_BORDER)
    _, tf = textbox(slide, left + Inches(0.25), top, width - Inches(0.4), height,
                     anchor=MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "KEY POINT   "
    r.font.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = ORANGE
    r.font.name = "Calibri"
    r2 = p.add_run()
    r2.text = text
    r2.font.size = Pt(14) if len(text) < 150 else Pt(12.5)
    r2.font.color.rgb = DARK
    r2.font.name = "Calibri"
    return height


# ─────────────────────────────────────────────────────────────────────────────
# Slide 1 — Title (full-bleed, no standard chrome, matches official template "in spirit")
# ─────────────────────────────────────────────────────────────────────────────
def build_title_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, OFF_WHITE)
    band_h = Inches(2.3)
    rect(slide, 0, 0, SW, band_h, SKY)
    rect(slide, 0, band_h, SW, Inches(0.06), TEAL)

    _, itf = textbox(slide, Inches(1.0), Inches(0.14), SW - Inches(2.0), Inches(0.85),
                      anchor=MSO_ANCHOR.TOP)
    p1 = itf.paragraphs[0]
    runs(p1, "NED ACADEMY", 16, WHITE, bold=True, align=PP_ALIGN.CENTER)
    p2 = itf.add_paragraph()
    runs(p2, "Centre of Multidisciplinary Postgraduate Programmes", 13, WHITE, align=PP_ALIGN.CENTER)
    p3 = itf.add_paragraph()
    runs(p3, "NED UNIVERSITY OF ENGINEERING & TECHNOLOGY, KARACHI, PAKISTAN", 12, WHITE,
         align=PP_ALIGN.CENTER)

    # logo pair — centenary crest LEFT, standard crest RIGHT (matches official template order)
    logo_size = Inches(1.35)
    gap = Inches(0.9)
    cx = SW / 2
    left_x = cx - gap / 2 - logo_size
    right_x = cx + gap / 2
    logo_y = Inches(0.95)
    if os.path.exists(LOGO_CENTENARY):
        slide.shapes.add_picture(LOGO_CENTENARY, int(left_x), int(logo_y), height=int(logo_size))
    if os.path.exists(LOGO_STANDARD):
        slide.shapes.add_picture(LOGO_STANDARD, int(right_x), int(logo_y), height=int(logo_size))

    _, ttf = textbox(slide, Inches(0.8), Inches(2.65), SW - Inches(1.6), Inches(0.9),
                      anchor=MSO_ANCHOR.TOP)
    runs(ttf.paragraphs[0], "MediScan", 42, DARK, bold=True, align=PP_ALIGN.CENTER)

    _, stf = textbox(slide, Inches(1.2), Inches(3.45), SW - Inches(2.4), Inches(1.0),
                      anchor=MSO_ANCHOR.TOP)
    sp = stf.paragraphs[0]
    runs(sp, "A Human-in-the-Loop, Explainable AI Decision-Support System for Prescription "
             "Reading and Therapeutically-Equivalent Medicine Substitution",
         18, MID_GREY, align=PP_ALIGN.CENTER)

    _, btf = textbox(slide, Inches(1.0), Inches(4.55), SW - Inches(2.0), Inches(0.5),
                      anchor=MSO_ANCHOR.TOP)
    runs(btf.paragraphs[0], "Postgraduate Diploma in Generative AI \u2014 Batch 5, FALL I 2025",
         16, SKY_DARK, bold=True, align=PP_ALIGN.CENTER)

    _, ctf = textbox(slide, Inches(1.0), SH - Inches(0.75), SW - Inches(2.0), Inches(0.5),
                      anchor=MSO_ANCHOR.MIDDLE)
    runs(ctf.paragraphs[0], "Muhammad Usama Alam  \u00b7  Supervisor: Sajid Majeed", 14, MID_GREY,
         align=PP_ALIGN.CENTER)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 2 — Name / Batch / Roll No.
# ─────────────────────────────────────────────────────────────────────────────
def build_name_slide(prs):
    slide = chrome(prs, "Student Details", "Student Details", 2)
    left, top, width, height = body_card(slide, BODY_TOP, BODY_BOTTOM - BODY_TOP)
    fields = [
        ("NAME", "Muhammad Usama Alam"),
        ("ROLL NO. / ENROLMENT NO.", "PGD/GAI/JUN-25/212418"),
        ("BATCH", "5, FALL I 2025"),
        ("SUPERVISOR", "Sajid Majeed"),
    ]
    row_h = height / 4
    for i, (label, value) in enumerate(fields):
        y = top + row_h * i
        _, lf = textbox(slide, left + Inches(0.6), y, width - Inches(1.2), row_h * 0.45,
                         anchor=MSO_ANCHOR.BOTTOM)
        runs(lf.paragraphs[0], label, 14, SKY_DARK, bold=True)
        _, vf = textbox(slide, left + Inches(0.6), y + row_h * 0.45, width - Inches(1.2), row_h * 0.5,
                         anchor=MSO_ANCHOR.TOP)
        runs(vf.paragraphs[0], value, 26, DARK, bold=True)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 3/4/9/10 — plain bullets layout
# ─────────────────────────────────────────────────────────────────────────────
def build_bullets_slide(prs, title, pill, n, bullets, key_point_text=None, numbered=False):
    slide = chrome(prs, title, pill, n)
    kp_h = Inches(0)
    if key_point_text:
        kp_top = BODY_BOTTOM - (Inches(0.95) if len(key_point_text) > 140 else Inches(0.72))
        body_h = kp_top - BODY_TOP - Inches(0.12)
    else:
        body_h = BODY_BOTTOM - BODY_TOP
    left, top, width, height = body_card(slide, BODY_TOP, body_h)
    _, tf = textbox(slide, left + Inches(0.45), top + Inches(0.25), width - Inches(0.9),
                     height - Inches(0.5), anchor=MSO_ANCHOR.TOP)
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(12)
        lead = f"{i + 1}.  " if numbered else "\u2022  "
        r0 = p.add_run()
        r0.text = lead
        r0.font.size = Pt(17)
        r0.font.bold = True
        r0.font.color.rgb = TEAL
        r0.font.name = "Calibri"
        r1 = p.add_run()
        r1.text = b
        r1.font.size = Pt(17)
        r1.font.color.rgb = DARK
        r1.font.name = "Calibri"
    if key_point_text:
        key_point(slide, key_point_text, kp_top)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 5 — Scope of Work (cards: In Scope / Out of Scope)
# ─────────────────────────────────────────────────────────────────────────────
def build_scope_slide(prs):
    slide = chrome(prs, "Scope of Work", "Scope of work", 5)
    gap = Inches(0.3)
    card_w = (SW - 2 * MARGIN - gap) / 2
    card_h = BODY_BOTTOM - BODY_TOP
    cards = [
        ("IN SCOPE", TEAL, [
            "OCR extraction + mandatory pharmacist verification gate",
            "9-component recommendation scoring + FDA Orange Book evidence",
            "Evidence-grounded explanation + explainable-AI (XAI) attribution",
            "Role-based access: pharmacist / reviewer / administrator \u2014 "
            "self-registration with mandatory admin approval, full audit trail",
        ]),
        ("OUT OF SCOPE", MID_GREY, [
            "No autonomous prescribing, dispensing, or automatic substitution",
            "No real patient data or PII \u2014 synthetic prescriptions only",
            "Not a clinical source of truth; drug-drug interaction checking is future work",
            "Research-grade prototype, not a production clinical system",
        ]),
    ]
    for i, (label, accent, items) in enumerate(cards):
        left = MARGIN + i * (card_w + gap)
        rect(slide, left, BODY_TOP, card_w, card_h, WHITE, line=LIGHT_GREY, line_w=1.0,
             rounded=True, radius=0.04)
        rect(slide, left, BODY_TOP, card_w, Inches(0.5), accent, rounded=True, radius=0.1)
        rect(slide, left, BODY_TOP + Inches(0.25), card_w, Inches(0.25), accent)
        _, lf = textbox(slide, left, BODY_TOP, card_w, Inches(0.5), anchor=MSO_ANCHOR.MIDDLE)
        runs(lf.paragraphs[0], label, 16, WHITE, bold=True, align=PP_ALIGN.CENTER)
        _, bf = textbox(slide, left + Inches(0.3), BODY_TOP + Inches(0.65), card_w - Inches(0.6),
                         card_h - Inches(0.85), anchor=MSO_ANCHOR.TOP)
        for j, item in enumerate(items):
            p = bf.paragraphs[0] if j == 0 else bf.add_paragraph()
            p.space_after = Pt(10)
            r0 = p.add_run()
            r0.text = "\u2022  "
            r0.font.size = Pt(13.5)
            r0.font.color.rgb = accent
            r0.font.name = "Calibri"
            r1 = p.add_run()
            r1.text = item
            r1.font.size = Pt(13.5)
            r1.font.color.rgb = DARK
            r1.font.name = "Calibri"
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 6 — Literature Review (table)
# ─────────────────────────────────────────────────────────────────────────────
def build_literature_slide(prs):
    slide = chrome(prs, "Literature Review", "Literature Review", 6)
    rows_data = [
        ("Research strand", "What the literature establishes", "Where MediScan sits"),
        ("Prescription OCR",
         "Handwriting harder than print; look-alike/sound-alike names are a documented error class",
         "Joins OCR to a substitution decision, not just transcription"),
        ("Therapeutic equivalence",
         "A regulatory determination (FDA Orange Book), not inferred from chemical similarity alone",
         "Equivalence is the primary ranking signal"),
        ("Explainable AI",
         "Interpretable-by-design preferred over post-hoc black-box explanation for high-stakes "
         "use (Rudin, 2019)",
         "Score is additive \u2014 exact attribution, not an approximation"),
        ("Evidence grounding (RAG)",
         "Retrieval reduces unsupported claims vs. an unconstrained LLM (Lewis et al., 2020)",
         "Withholds narrative entirely when no evidence is found"),
        ("Human-in-the-loop",
         "Confirmation after a system acts invites automation bias (Parasuraman & Manzey, 2010)",
         "Gate enforced before any recommendation is generated"),
    ]
    top = BODY_TOP
    table_h = Inches(4.55)
    gfx = slide.shapes.add_table(len(rows_data), 3, int(MARGIN), int(top),
                                  int(SW - 2 * MARGIN), int(table_h))
    table = gfx.table
    table.columns[0].width = Inches(2.1)
    table.columns[1].width = Inches(6.73)
    table.columns[2].width = Inches(4.0)
    for r, row in enumerate(rows_data):
        for c, val in enumerate(row):
            cell = table.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.fill.solid()
            cell.fill.fore_color.rgb = SKY_DARK if r == 0 else (WHITE if r % 2 else ROW_ALT)
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            size = 13 if r == 0 else 11.5
            color = WHITE if r == 0 else DARK
            bold = r == 0 or c == 0
            runs(p, val, size, color, bold=bold)
    key_point(slide, "Each of these five properties is addressed separately in prior work \u2014 "
                      "no existing system integrates all five together. (Full review: report "
                      "Chapter 2.)", top + table_h + Inches(0.12))
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 7 — Methodology (native-shape chevron-flow diagram + caption strip)
# ─────────────────────────────────────────────────────────────────────────────
def build_methodology_slide(prs):
    slide = chrome(prs, "Methodology", "Methodology", 7)
    steps = [
        "Upload\nprescription image",
        "Multi-engine OCR\n(Vision/TrOCR/Tesseract)",
        "Verification\nGate",
        "Eligibility\nfilters (5)",
        "9-component\nweighted score",
        "Equivalence +\nevidence + XAI",
        "Pharmacist\ndecision",
    ]
    n = len(steps)
    diagram_top = BODY_TOP + Inches(0.3)
    chevron_h = Inches(1.15)
    gap = Inches(0.06)
    total_w = SW - 2 * MARGIN
    chevron_w = (total_w - gap * (n - 1)) / n
    notch = Inches(0.22)
    x = MARGIN
    for i, step in enumerate(steps):
        fill = ORANGE if i == 2 else SKY
        shp = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, int(x), int(diagram_top),
                                      int(chevron_w), int(chevron_h))
        shp.adjustments[0] = 0.35
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        shp.line.color.rgb = WHITE
        shp.line.width = Pt(1.5)
        shp.shadow.inherit = False
        tf = shp.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.05)
        tf.margin_right = Inches(0.18)
        lines = step.split("\n")
        for li, line in enumerate(lines):
            p = tf.paragraphs[0] if li == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = line
            r.font.size = Pt(12.5)
            r.font.bold = True
            r.font.color.rgb = WHITE
            r.font.name = "Calibri"
        x += chevron_w + gap

    cap_top = diagram_top + chevron_h + Inches(0.35)
    left, top, width, height = body_card(slide, cap_top, BODY_BOTTOM - cap_top)
    _, tf = textbox(slide, left + Inches(0.45), top + Inches(0.18), width - Inches(0.9),
                     height - Inches(0.36), anchor=MSO_ANCHOR.MIDDLE)
    caps = [
        "Design Science Research: build \u2192 demonstrate \u2192 evaluate, iterated "
        "(Hevner et al., 2004; Peffers et al., 2007)",
        "Verification gate enforced server-side \u2014 nothing proceeds without "
        "pharmacist confirmation",
        "Score is additive (sum = 100); FDA Orange Book equivalence is evidence "
        "only, never re-ranks",
    ]
    for i, c in enumerate(caps):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        r0 = p.add_run()
        r0.text = "\u2022  "
        r0.font.size = Pt(14.5)
        r0.font.color.rgb = TEAL
        r0.font.name = "Calibri"
        r1 = p.add_run()
        r1.text = c
        r1.font.size = Pt(14.5)
        r1.font.color.rgb = DARK
        r1.font.name = "Calibri"
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 8 — Findings (2x2 card grid)
# ─────────────────────────────────────────────────────────────────────────────
def build_findings_slide(prs):
    slide = chrome(prs, "Findings", "Findings", 8)
    kp_text = ("A system examined this closely, and reported on this honestly, is the point of "
               "Design Science Research \u2014 not a weakness to hide.")
    kp_top = BODY_BOTTOM - Inches(0.72)
    grid_h = kp_top - BODY_TOP - Inches(0.15)
    gap = Inches(0.25)
    card_w = (SW - 2 * MARGIN - gap) / 2
    card_h = (grid_h - gap) / 2

    cards = [
        ("Worked Example", SKY,
         "Ibuprofen 200mg \u2192 Naproxen scores 100/100 (9/9 components); real DrugBank "
         "evidence + real FDA Orange Book AB-rating (167 products). The same run also "
         "surfaced a real gap: 2 of 5 candidates were clinically implausible \u2014 the "
         "route/dosage-form filters did not gate as strictly as designed (see Limitations)."),
        ("Verified Working", TEAL,
         "Human verification gate (Sec. 3.3.2) is server-enforced, not UI-only \u00b7 score "
         "sums to exactly 100 \u00b7 equivalence layer confirmed passive \u00b7 evidence-"
         "withholding confirmed \u00b7 catalogue at production scale (900K+ records)"),
        ("Evaluation Status", SKY_DARK,
         "4 pre-registered RQs, thresholds fixed in advance. RQ1/RQ2 harnesses need "
         "redirecting (real single-engine signal; structural-similarity coverage) \u2014 not "
         "just more data. RQ3/RQ4: dataset + ethics approval/panel are next."),
        ("Known Limitations", ORANGE,
         "Chemical-similarity bonus on one path \u00b7 evidence layer not fully passive \u00b7 "
         "scoring model diverges from an internal spec \u00b7 audit trail append-only by "
         "convention \u00b7 filters under-enforced in the worked example \u00b7 equivalence is "
         "jurisdiction-specific. (6 of 9 report limitations shown; the first three need "
         "supervisor input.)"),
    ]
    for idx, (label, accent, body) in enumerate(cards):
        row, col = divmod(idx, 2)
        left = MARGIN + col * (card_w + gap)
        top = BODY_TOP + row * (card_h + gap)
        rect(slide, left, top, card_w, card_h, WHITE, line=LIGHT_GREY, line_w=1.0,
             rounded=True, radius=0.05)
        rect(slide, left, top, card_w, Inches(0.4), accent, rounded=True, radius=0.15)
        rect(slide, left, top + Inches(0.2), card_w, Inches(0.2), accent)
        _, lf = textbox(slide, left, top, card_w, Inches(0.4), anchor=MSO_ANCHOR.MIDDLE)
        runs(lf.paragraphs[0], label.upper(), 13, WHITE, bold=True, align=PP_ALIGN.CENTER)
        _, bf = textbox(slide, left + Inches(0.22), top + Inches(0.48), card_w - Inches(0.44),
                         card_h - Inches(0.6), anchor=MSO_ANCHOR.TOP)
        runs(bf.paragraphs[0], body, 11.5, DARK)
    key_point(slide, kp_text, kp_top)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# Slide 11 — Thank You (full-bleed, bookends Slide 1)
# ─────────────────────────────────────────────────────────────────────────────
def build_thankyou_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_bg(slide, OFF_WHITE)
    band_h = Inches(2.3)
    rect(slide, 0, 0, SW, band_h, SKY)
    rect(slide, 0, band_h, SW, Inches(0.06), TEAL)
    _, ttf = textbox(slide, Inches(0.8), Inches(0.75), SW - Inches(1.6), Inches(1.0),
                      anchor=MSO_ANCHOR.MIDDLE)
    runs(ttf.paragraphs[0], "Thank You", 42, WHITE, bold=True, align=PP_ALIGN.CENTER)

    _, qtf = textbox(slide, Inches(1.0), Inches(3.0), SW - Inches(2.0), Inches(0.6),
                      anchor=MSO_ANCHOR.TOP)
    runs(qtf.paragraphs[0], "Questions & Discussion", 22, MID_GREY, align=PP_ALIGN.CENTER)

    _, utf = textbox(slide, Inches(1.0), Inches(3.9), SW - Inches(2.0), Inches(0.5),
                      anchor=MSO_ANCHOR.TOP)
    runs(utf.paragraphs[0], "MediScan \u2014 live at: usamaalam-prescription-assistant.hf.space",
         14, SKY_DARK, italic=True, align=PP_ALIGN.CENTER)

    _, ctf = textbox(slide, Inches(1.0), SH - Inches(0.9), SW - Inches(2.0), Inches(0.5),
                      anchor=MSO_ANCHOR.MIDDLE)
    runs(ctf.paragraphs[0], "Muhammad Usama Alam  \u00b7  Supervisor: Sajid Majeed", 14, MID_GREY,
         align=PP_ALIGN.CENTER)
    return slide


# ─────────────────────────────────────────────────────────────────────────────
# build
# ─────────────────────────────────────────────────────────────────────────────
def main():
    prs = Presentation()
    prs.slide_width = SW
    prs.slide_height = SH

    build_title_slide(prs)
    build_name_slide(prs)
    build_bullets_slide(
        prs, "Introduction", "Introduction", 3,
        [
            "Reading the prescription correctly \u2014 handwritten prescriptions are common; a "
            "single misread character in a look-alike/sound-alike drug name selects a "
            "different medicine",
            "Finding a substitute when the prescribed medicine isn't available \u2014 out of "
            "stock, discontinued, or unaffordable; the pharmacist must judge an appropriate "
            "alternative on the spot, with no formal decision-support tool today",
            "A third, cross-cutting problem: any automated tool here must earn trust \u2014 an "
            "answer without a reason is not safe to act on in a clinical setting",
        ],
        key_point_text="No existing tool joins prescription reading with regulated "
                        "therapeutic-equivalence reasoning in one system \u2014 this is the "
                        "gap MediScan addresses.",
    )
    build_bullets_slide(
        prs, "Objectives", "Objectives", 4,
        [
            "Multi-engine OCR pipeline \u2014 extract medicine name, strength, form, route",
            "Mandatory pharmacist verification before anything downstream runs",
            "Recommendation engine \u2014 trusted catalogue + eligibility filters + "
            "transparent score",
            "Regulatory therapeutic-equivalence layer (FDA Orange Book)",
            "Evidence-grounded explanations (FDA label text)",
            "Explainable-AI attribution \u2014 show why a score was given",
        ],
        key_point_text="Cross-cutting commitment: no metric or claim is reported unless real "
                        "data backs it.",
        numbered=True,
    )
    build_scope_slide(prs)
    build_literature_slide(prs)
    build_methodology_slide(prs)
    build_findings_slide(prs)
    build_bullets_slide(
        prs, "Conclusions", "Conclusions", 9,
        [
            "The design is buildable, internally coherent, and deployed",
            "Every layer was exercised end-to-end on a real query against the real catalogue",
            "This is a disciplined demonstration of integration \u2014 not yet a fully "
            "validated performance claim at scale",
            "What remains is evaluating the system at scale, which the infrastructure built "
            "for this project is already designed to support",
        ],
    )
    build_bullets_slide(
        prs, "Recommendations", "Recommendations", 10,
        [
            "Complete the 25-30 case synthetic evaluation dataset (RQ3)",
            "Redirect RQ1 to the real single-engine accuracy signal and RQ2 to "
            "structural-similarity coverage, then re-run both",
            "Obtain ethics approval \u2192 recruit pharmacist panel \u2192 RQ4",
            "Resolve the three supervisor-facing design questions the report itself flags "
            "(chemical-similarity bonus; evidence-layer passivity; scoring-model "
            "specification divergence), and fix the route/dosage-form filter gaps the "
            "worked example surfaced",
        ],
        numbered=True,
    )
    build_thankyou_slide(prs)

    prs.save(OUT)
    print(f"WROTE {OUT}")
    print(f"slides: {len(prs.slides.__iter__.__self__._sldIdLst)}" if False else f"slides written: 11")


if __name__ == "__main__":
    main()
