"""Assemble the MediScan PGD Final Project Report as a formatted .docx.

Follows NED University CMPP PGD Final Report template (Annexure E) and
guidelines: Times New Roman 12, double-spaced body, one-sided, APA 7th.
"""
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.shared import Pt, Inches, Cm
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = Path(__file__).parent
OUT = HERE / "MediScan_Final_Project_Report.docx"
RESEARCH_DOCS_TS = HERE.parent.parent / "frontend" / "src" / "content" / "researchDocuments.ts"


def load_research_documents():
    """Pull the real Participant Information Sheet and consent statements
    straight from the shipped frontend source (frontend/src/content/
    researchDocuments.ts), so Appendix A/B quote the actual text the live
    application shows, not a paraphrase of it."""
    src = RESEARCH_DOCS_TS.read_text(encoding="utf-8")

    version_match = re.search(r"export const DOCUMENT_VERSION = '([^']*)'", src)
    date_match = re.search(r"export const DOCUMENT_DATE = '([^']*)'", src)
    document_version = version_match.group(1) if version_match else ""
    document_date = date_match.group(1) if date_match else ""

    pis_match = re.search(r"export const pisText = `(.*?)`\n", src, re.DOTALL)
    pis_text = pis_match.group(1).strip("\n") if pis_match else None
    if pis_text:
        pis_text = pis_text.replace("${DOCUMENT_VERSION}", document_version)
        pis_text = pis_text.replace("${DOCUMENT_DATE}", document_date)

    consent_match = re.search(r"export const consentStatements = \[(.*?)\]\n", src, re.DOTALL)
    consent_statements = []
    if consent_match:
        for line in consent_match.group(1).splitlines():
            line = line.strip()
            if not line or not (line.startswith("'") or line.startswith('"')):
                continue
            quote = line[0]
            end = line.rfind(quote)
            if end > 0:
                consent_statements.append(line[1:end])

    return pis_text, consent_statements

STUDENT = "Muhammad Usama Alam"
ENROLLMENT = "PGD/GAI/JUN-25/212418"
SUPERVISOR = "Sajid Majeed"
SUPERVISOR_DESIGNATION = "Project Supervisor, NED University of Engineering and Technology, Karachi"
SUBMISSION_DATE = "15 November 2026"
BATCH = "Batch 5, FALL I 2025"
PROGRAMME = "Postgraduate Diploma in Generative AI"
TITLE = ("MediScan: A Human-in-the-Loop, Explainable AI Decision-Support System for "
          "Prescription Reading and Therapeutically-Equivalent Medicine Substitution")

doc = Document()

# ---------- base style: Times New Roman 12, double space ----------
style = doc.styles["Normal"]
style.font.name = "Times New Roman"
style.font.size = Pt(12)
rpr = style.element.get_or_add_rPr()
rFonts = rpr.find(qn("w:rFonts"))
if rFonts is None:
    rFonts = OxmlElement("w:rFonts")
    rpr.append(rFonts)
rFonts.set(qn("w:eastAsia"), "Times New Roman")
pf = style.paragraph_format
pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE
pf.space_after = Pt(0)
pf.space_before = Pt(0)

for sec in doc.sections:
    sec.left_margin = Inches(1.25)
    sec.right_margin = Inches(1.0)
    sec.top_margin = Inches(1.0)
    sec.bottom_margin = Inches(1.0)


def para(text="", bold=False, italic=False, size=12, align=None, space_after=0,
         style_name=None, line_single=False):
    p = doc.add_paragraph(style=style_name) if style_name else doc.add_paragraph()
    if align is not None:
        p.alignment = align
    if line_single:
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    if text:
        r = p.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
        r.font.name = "Times New Roman"
    p.paragraph_format.space_after = Pt(space_after)
    return p


def heading(text, level=1, upper=True, space_before=18, space_after=12, size=14):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    r = p.add_run(text.upper() if upper else text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.name = "Times New Roman"
    return p


def subheading(text, size=12):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.name = "Times New Roman"
    return p


def body_paragraph(text):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    p.paragraph_format.first_line_indent = Inches(0.0)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"
    return p


FIGURE_IMAGES = {
    "FIGURE 1.1": ("figures/fig_1_1_data_flow.png", Inches(6.3)),
    "FIGURE 3.1": ("figures/fig_3_1_dsr_cycle.png", Inches(4.8)),
    "FIGURE 3.2": ("figures/fig_3_2_architecture.png", Inches(6.3)),
    "FIGURE 3.3": ("figures/fig_3_3_workflow_gate.png", Inches(6.3)),
    "FIGURE 3.4": ("figures/fig_3_4_db_domains.png", Inches(5.5)),
    "FIGURE 3.5": ("figures/fig_3_5_timeline.png", Inches(6.3)),
    "FIGURE 4.1": ("figures/fig_4_1_scoring_breakdown.png", Inches(6.3)),
    "FIGURE 4.2": ("figures/fig_4_2_verification_gate.png", Inches(4.9)),
    "FIGURE 4.3": ("figures/fig_4_3_recommendation_panel.png", Inches(4.2)),
}


def figure_placeholder(caption):
    key = caption.split(":")[0].strip().upper()
    image = FIGURE_IMAGES.get(key)
    if image:
        path, width = image
        img_p = doc.add_paragraph()
        img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        img_p.paragraph_format.space_before = Pt(12)
        img_p.paragraph_format.space_after = Pt(4)
        run = img_p.add_run()
        run.add_picture(str(HERE / path), width=width)
    else:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(f"[ {caption} — insert as a native Word diagram/chart/screenshot ]")
        r.italic = True
        r.font.size = Pt(11)
        r.font.name = "Times New Roman"
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(12)
    r2 = cap.add_run(caption)
    r2.bold = True
    r2.font.size = Pt(11)
    r2.font.name = "Times New Roman"


REAL_TABLES = {
    "TABLE 3.1": [
        ["Source", "Role in the system"],
        ["FDA National Drug Code (NDC) directory", "Marketed product listings: names, strengths, dosage forms, routes, labellers"],
        ["DrugBank", "Drug-level reference data: active ingredients, salt forms, chemical identifiers"],
        ["FDA Structured Product Labeling (SPL)", "Approved label text used as the retrieval corpus for evidence grounding"],
        ["FDA Orange Book", "Therapeutic equivalence codes and reference listed products"],
    ],
    "TABLE 3.2": [
        ["RQ", "Focus", "Metric", "Acceptance threshold"],
        ["RQ1", "Extraction accuracy", "Word error rate; character error rate; field-level exact match", "WER < 0.15; CER < 0.10"],
        ["RQ2", "Recommendation quality", "Precision@3; Recall@3; structural-similarity coverage", "P@3 ≥ 0.70; R@3 ≥ 0.60"],
        ["RQ3", "Evidence grounding", "Citation coverage; unsupported-claim rate; semantic similarity", "Semantic similarity F1 ≥ 0.80"],
        ["RQ4", "Explainability and trust", "Likert ratings by explanation condition", "Descriptive; no threshold"],
    ],
    "TABLE 4.1": [
        ["Metric", "Value"],
        ["Completed prescription review sessions", "2"],
        ["OCR jobs run", "1"],
        ["Medicines extracted", "3"],
        ["Medicines matched to formulary", "2 (66.7%)"],
        ["Average OCR field confidence", "0.93"],
        ["Average parser confidence", "0.97"],
        ["Pharmacist-reviewed sessions", "1"],
    ],
    "TABLE 4.2": [
        ["Catalogue component", "Count"],
        ["Marketed medicines", "41,020"],
        ["Individual product records", "929,832"],
        ["Name aliases (fuzzy lookup)", "373,959"],
        ["Label sections (evidence-retrieval corpus)", "136,167"],
        ["FDA NDC rows ingested", "132,824"],
        ["DrugBank rows ingested", "4,953"],
        ["FDA SPL rows ingested", "255,904"],
    ],
    "TABLE 4.3": [
        ["Component", "Weight", "Awarded", "Status"],
        ["Indication relationship", "35", "35", "Matched"],
        ["ATC / therapeutic class", "15", "15", "Matched"],
        ["Mechanism relationship", "10", "10", "Matched"],
        ["Route compatibility", "10", "10", "Matched"],
        ["Patient-population compatibility", "10", "10", "Matched"],
        ["Target or pathway", "5", "5", "Matched"],
        ["Dosage-form compatibility", "5", "5", "Matched"],
        ["Contraindication / warning assessment", "5", "5", "Matched"],
        ["Interaction-assessment coverage", "5", "5", "Matched"],
        ["Total", "100", "100", "—"],
    ],
}


def table_placeholder(caption, note=""):
    key = caption.split(":")[0].strip().upper()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    r = p.add_run(caption)
    r.bold = True
    r.font.size = Pt(11)
    r.font.name = "Times New Roman"
    if key in REAL_TABLES:
        add_real_table(REAL_TABLES[key])
    else:
        if note:
            p2 = doc.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r2 = p2.add_run(note)
            r2.italic = True
            r2.font.size = Pt(10)
            r2.font.name = "Times New Roman"
        p3 = doc.add_paragraph()
        p3.paragraph_format.space_after = Pt(12)


def page_break():
    doc.add_page_break()


def add_real_table(rows, col_widths=None, header=True, font_size=10):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    for ridx, row in enumerate(rows):
        for cidx, val in enumerate(row):
            cell = t.cell(ridx, cidx)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            r = p.add_run(str(val))
            r.font.size = Pt(font_size)
            r.font.name = "Times New Roman"
            r.bold = header and ridx == 0
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return t


def load_chapter_text(filename):
    text = (HERE / filename).read_text(encoding="utf-8")
    return text


def render_chapter_body(text, skip_first_heading_lines=1):
    """Parse a plain-text chapter file into headed paragraphs.

    Convention used in the drafted .txt files:
      - First line: CHAPTER heading (ALL CAPS) -> level-1 heading, new page already added by caller
      - Lines like 'N.N Title' or 'N.N.N Title' (title case, short) -> subheading
      - '[FIGURE ...]' / '[TABLE ...]' lines -> placeholders
      - blank lines separate paragraphs
    """
    lines = text.split("\n")
    # First non-empty line is the chapter title; already rendered by caller before calling this.
    buf = []

    def flush():
        if buf:
            paragraph_text = " ".join(buf).strip()
            if paragraph_text:
                body_paragraph(paragraph_text)
            buf.clear()

    section_re = re.compile(r"^\d+(\.\d+){1,2}\s+[A-Z].{0,80}$")

    started = False
    for raw in lines:
        line = raw.rstrip()
        if not started:
            started = True
            continue  # skip chapter title line, handled by caller
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith("[FIGURE") or stripped.startswith("[TABLE"):
            flush()
            caption = stripped.strip("[]")
            if caption.upper().startswith("FIGURE"):
                figure_placeholder(caption)
            else:
                table_placeholder(caption)
            continue
        if section_re.match(stripped) and len(stripped) < 90:
            flush()
            subheading(stripped)
            continue
        buf.append(stripped)
    flush()


# =========================================================================
# FRONT MATTER
# =========================================================================

# ---- Title page ----
for _ in range(2):
    doc.add_paragraph()
para("NED UNIVERSITY OF ENGINEERING AND TECHNOLOGY", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=14)
para("Centre of Multidisciplinary Postgraduate Programmes (CMPP)", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
para("Postgraduate Diploma (PGD) Programmes", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=12)
for _ in range(3):
    doc.add_paragraph()
para("FINAL PROJECT REPORT", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=18)
for _ in range(3):
    doc.add_paragraph()
para(f"A Project Report submitted in partial fulfilment of the requirements for", align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"the Postgraduate Diploma in {PROGRAMME.replace('Postgraduate Diploma in ', '')}", align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(2):
    doc.add_paragraph()
para(f"Name of Student: {STUDENT}", align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"Enrolment No.: {ENROLLMENT}", align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"Batch: {BATCH}", align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"Project Title: {TITLE}", align=WD_ALIGN_PARAGRAPH.CENTER)
para(f"Name of Supervisor: {SUPERVISOR}", align=WD_ALIGN_PARAGRAPH.CENTER)
for _ in range(4):
    doc.add_paragraph()
para("_______________________________", align=WD_ALIGN_PARAGRAPH.CENTER)
para("Signature of Supervisor", align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)
para(f"Date: {SUBMISSION_DATE}", align=WD_ALIGN_PARAGRAPH.CENTER)

page_break()

# ---- Certificate ----
heading("Certificate", level=1)
body_paragraph(
    f"This is to certify that Mr. {STUDENT} of {BATCH} has successfully completed the PGD project "
    f"in partial fulfilment of requirements for a PGD in {PROGRAMME.replace('Postgraduate Diploma in ', '')} "
    f"from NED Academy, NED University of Engineering and Technology, Karachi, Pakistan."
)
for _ in range(3):
    doc.add_paragraph()
para("Project Supervisor", bold=False)
para("_______________________________")
para(f"{SUPERVISOR}")
para(f"Designation, Organization: {SUPERVISOR_DESIGNATION}")

page_break()

# ---- Declarations ----
heading("Declarations", level=1)
body_paragraph(
    f'I hereby state that this Project titled, "{TITLE}", is my own work and has not been submitted '
    f"previously by me for taking any degree or diploma from anywhere else in the world."
)
body_paragraph(
    "At any time if my statement is found incorrect, NED University of Engineering and Technology has "
    "the right to withdraw this PGD."
)
for _ in range(3):
    doc.add_paragraph()
para("Signature: _______________________________")
para(f"Student Name: {STUDENT}")
para(f"Date: {SUBMISSION_DATE}")

page_break()

# ---- Plagiarism Undertaking ----
heading("Plagiarism Undertaking", level=1)
body_paragraph(
    f'I solemnly declare that the research work presented in this PGD Project titled "{TITLE}" is '
    f"solely my own research work except where the acknowledgement of the sources is made."
)
for _ in range(3):
    doc.add_paragraph()
para("Signature: _______________________________")
para(f"Student Name: {STUDENT}")
para(f"Date: {SUBMISSION_DATE}")

page_break()

# ---- Final Project Report Submission Sheet ----
heading("Final Project Report Submission Sheet", level=1)
submission_rows = [
    ["S. No.", "Final Report Component", "Included (Yes)"],
    ["1.", "The cover page / Table of Contents", "Yes"],
    ["2.", "Abstract", "Yes"],
    ["3.", "Introduction / Background (2,000-3,000 words)", "Yes"],
    ["4.", "Literature Review (3,000-4,000 words)", "Yes"],
    ["5.", "Methodology / Study Design (2,500-4,500 words)", "Yes"],
    ["6.", "Main body of the report / Findings (4,000-5,000 words)", "Yes"],
    ["7.", "Conclusions and Recommendations (1,000-2,000 words)", "Yes"],
    ["8.", "References (not bibliography), APA 7th Edition (minimum 15)", "Yes"],
    ["9.", "Citations, APA 7th Edition (minimum 15)", "Yes"],
    ["10.", "Appendices", "Yes"],
    ["11.", "Turnitin Report (similarity < 19%; < 5% from any single source)", "[TO ATTACH]"],
]
add_real_table(submission_rows)
for _ in range(2):
    doc.add_paragraph()
para("_______________________________")
para("Name & Signature, Supervisor", italic=True)

page_break()

# ---- Table of Contents (static placeholder list; Word's own TOC field can replace this) ----
heading("Table of Contents", level=1)
toc_entries = [
    ("Title Page", "i"),
    ("Certificate", "ii"),
    ("Declarations", "iii"),
    ("Plagiarism Undertaking", "iv"),
    ("Final Project Report Submission Sheet", "v"),
    ("Table of Contents", "vi"),
    ("List of Tables", "vii"),
    ("List of Figures", "viii"),
    ("List of Abbreviations", "ix"),
    ("Acknowledgement", "x"),
    ("Abstract", "xi"),
    ("Dedication", "xii"),
    ("Chapter 1: Introduction", "1"),
    ("Chapter 2: Literature Review", "..."),
    ("Chapter 3: Methodology and Study Design", "..."),
    ("Chapter 4: Results and Discussion", "..."),
    ("Chapter 5: Conclusion and Recommendations", "..."),
    ("References", "..."),
    ("Appendices", "..."),
]
for title, pg in toc_entries:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_after = Pt(4)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(6.0))
    r = p.add_run(f"{title}\t{pg}")
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"

page_break()

# ---- List of Tables ----
heading("List of Tables", level=1)
lot = [
    ("Table 3.1", "Drug knowledge sources and their role in the system", "..."),
    ("Table 3.2", "Research questions, metrics, and acceptance thresholds", "..."),
    ("Table 4.1", "Operational snapshot from the live deployment", "..."),
    ("Table 4.2", "Drug-knowledge catalogue scale", "..."),
    ("Table 4.3", "Full nine-component score breakdown for the worked example", "..."),
]
for num, title, pg in lot:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"{num}: {title}")
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"

page_break()

# ---- List of Figures ----
heading("List of Figures", level=1)
lof = [
    ("Figure 1.1", "End-to-end data flow: image to confirmed fields to ranked alternatives to evidence to explanation"),
    ("Figure 3.1", "Design Science Research cycle applied to this project"),
    ("Figure 3.2", "System architecture, layered view"),
    ("Figure 3.3", "Four-step pharmacist workflow with the verification gate"),
    ("Figure 3.4", "Application database domains"),
    ("Figure 3.5", "Research process timeline"),
    ("Figure 4.1", "Worked example: scoring breakdown for the top-ranked candidate"),
    ("Figure 4.2", "Application screenshot: the verification gate"),
    ("Figure 4.3", "Application screenshot: recommendation and evidence panel"),
]
for num, title in lof:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(f"{num}: {title}")
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"

page_break()

# ---- List of Abbreviations ----
heading("List of Abbreviations", level=1)
abbrevs = [
    ("API", "Application Programming Interface"),
    ("ATC", "Anatomical Therapeutic Chemical (classification)"),
    ("CER", "Character Error Rate"),
    ("CMPP", "Centre of Multidisciplinary Postgraduate Programmes"),
    ("DSR", "Design Science Research"),
    ("FDA", "Food and Drug Administration (United States)"),
    ("HITL", "Human-in-the-Loop"),
    ("LIME", "Local Interpretable Model-agnostic Explanations"),
    ("MCS", "Maximum Common Substructure"),
    ("NDC", "National Drug Code"),
    ("OCR", "Optical Character Recognition"),
    ("P@K", "Precision at K"),
    ("PGD", "Postgraduate Diploma"),
    ("R@K", "Recall at K"),
    ("RAG", "Retrieval-Augmented Generation"),
    ("RQ", "Research Question"),
    ("SHAP", "SHapley Additive exPlanations"),
    ("SPL", "Structured Product Labeling"),
    ("TE", "Therapeutic Equivalence"),
    ("WER", "Word Error Rate"),
    ("XAI", "Explainable Artificial Intelligence"),
]
for term, expansion in abbrevs:
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    p.paragraph_format.space_after = Pt(4)
    tabs = p.paragraph_format.tab_stops
    tabs.add_tab_stop(Inches(1.2))
    r = p.add_run(f"{term}\t{expansion}")
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"

page_break()

# ---- Acknowledgement ----
heading("Acknowledgement", level=1)
body_paragraph(
    "First praise is to Allah, the Almighty, on whom ultimately I depend for sustenance and guidance. "
    "Acknowledgement is due to NED University of Engineering & Technology, Karachi, for the support it "
    "has provided for the completion of this project."
)
body_paragraph(
    f"I would like to express my gratitude to my project supervisor, {SUPERVISOR}, for his advice, "
    f"guidance, and patience throughout the development of this work."
)
body_paragraph(
    "I would also like to express my gratitude to my family and friends who gave their encouragement "
    "throughout the duration of this project."
)

page_break()

# ---- Abstract ----
heading("Abstract", level=1)
body_paragraph(
    "Handwritten prescriptions remain common in routine pharmacy practice, and illegible or "
    "look-alike, sound-alike drug names are a recognised, recurring source of medication error. "
    "Pharmacists also routinely face a second, related problem: when a prescribed medicine cannot be "
    "supplied, identifying a therapeutically appropriate alternative requires reasoning about active "
    "ingredient, strength, dosage form, route, and regulatory equivalence, which is a judgement most "
    "pharmacists currently make without any formal decision-support tool. This project presents "
    "MediScan, a human-in-the-loop, explainable AI decision-support prototype that reads a "
    "prescription image, requires a pharmacist to verify and confirm every extracted field before any "
    "further processing occurs, and then proposes therapeutically relevant alternative medicines, each "
    "carrying a transparent nine-component relevance score, FDA Orange Book regulatory "
    "equivalence evidence, retrieved drug-label evidence, and an exact, analytically computed "
    "explanation of how its score was built."
)
body_paragraph(
    "The project followed a Design Science Research methodology. The build phase was substantially "
    "completed: a working application, deployed publicly on a managed cloud platform, runs the full "
    "pharmacist workflow end to end against a real drug-knowledge catalogue of over nine hundred "
    "thousand product records assembled from FDA and DrugBank sources. The server-side verification "
    "gate, the nine-component scoring model, and the passive regulatory-equivalence annotation layer "
    "were all confirmed, by direct inspection of the running system, to operate exactly as designed. "
    "A worked example against the live catalogue is reported in full, showing every layer of the "
    "design operating coherently on a real query."
)
body_paragraph(
    "The evaluation phase, by contrast, could not be completed to the scale the original study design "
    "required within the time available. Of four pre-registered research questions covering "
    "extraction accuracy, recommendation quality, evidence grounding, and pharmacist trust, none "
    "could be reported against its threshold, because the evaluation dataset stood at a single "
    "confirmed case against a target of twenty-five to thirty, and institutional ethics approval for "
    "the planned pharmacist panel had not been obtained. Consistent with the project's own integrity "
    "commitment, that no metric is reported unless real data backs it, these gaps are reported "
    "plainly as data collection pending rather than filled with estimated or simulated figures. Seven "
    "specific implementation limitations are also recorded candidly, including a chemical-similarity "
    "ranking bonus that does not yet fully respect the project's own stated safety principle, and an "
    "audit trail that is append-only by application convention rather than by database-enforced "
    "constraint."
)
body_paragraph(
    "This project's conclusion is therefore a disciplined one: the proposed integration of OCR, "
    "regulatory equivalence, evidence-grounded explanation, and a structurally enforced "
    "human-in-the-loop gate is shown to be buildable and internally coherent, but is not yet shown, "
    "on the evidence collected so far, to perform well against real prescriptions at the scale a "
    "deployed clinical tool would need. Completing the evaluation dataset, redirecting two "
    "evaluation metrics identified during this project as measurement-design problems, and obtaining "
    "ethics approval for pharmacist panel recruitment are recommended as the immediate next steps."
)

page_break()

# ---- Dedication ----
heading("Dedication", level=1)
body_paragraph(
    "This project is dedicated to my parents and to my supervisor, for their support and guidance "
    "throughout its completion."
)

page_break()

# =========================================================================
# CHAPTER 1
# =========================================================================
ch1_text = load_chapter_text("ch1_introduction.txt")
heading("Chapter 1: Introduction", level=1)
render_chapter_body(ch1_text)
page_break()

# =========================================================================
# CHAPTER 2
# =========================================================================
ch2_text = load_chapter_text("ch2_literature_review.txt")
heading("Chapter 2: Literature Review", level=1)
render_chapter_body(ch2_text)
page_break()

# =========================================================================
# CHAPTER 3
# =========================================================================
ch3_text = load_chapter_text("ch3_methodology.txt")
heading("Chapter 3: Methodology and Study Design", level=1)
render_chapter_body(ch3_text)
page_break()

# =========================================================================
# CHAPTER 4
# =========================================================================
ch4_text = load_chapter_text("ch4_results.txt")
heading("Chapter 4: Results and Discussion", level=1)
render_chapter_body(ch4_text)
page_break()

# =========================================================================
# CHAPTER 5
# =========================================================================
ch5_text = load_chapter_text("ch5_conclusion.txt")
heading("Chapter 5: Conclusion and Recommendations", level=1)
render_chapter_body(ch5_text)
page_break()

# =========================================================================
# REFERENCES
# =========================================================================
heading("References", level=1)
refs_text = load_chapter_text("references.txt")
for line in refs_text.strip().split("\n\n"):
    line = line.strip()
    if not line:
        continue
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(-0.5)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(line)
    r.font.size = Pt(12)
    r.font.name = "Times New Roman"

page_break()

# =========================================================================
# APPENDICES
# =========================================================================
heading("Appendices", level=1)

PIS_TEXT, CONSENT_STATEMENTS = load_research_documents()

heading("Appendix A: Participant Information Sheet", level=2, size=13, upper=False)
if PIS_TEXT:
    for block in PIS_TEXT.split("\n\n"):
        block = block.strip("\n")
        if block.strip():
            body_paragraph(block.replace("\n", " "))
else:
    body_paragraph("[Insert the re-authored Participant Information Sheet from frontend/src/content/researchDocuments.ts, "
                    "updated to this project's attribution, once the RQ4 panel is planned.]")
page_break()

heading("Appendix B: Consent Form", level=2, size=13, upper=False)
if CONSENT_STATEMENTS:
    body_paragraph(
        "Each participant confirms the following statements individually before taking part "
        "(electronic affirmation, consistent with Section 3.7):"
    )
    for i, statement in enumerate(CONSENT_STATEMENTS, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        p.paragraph_format.left_indent = Inches(0.4)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(f"{i}. {statement}")
        r.font.size = Pt(12)
        r.font.name = "Times New Roman"
else:
    body_paragraph("[Insert the re-authored consent statements from frontend/src/content/researchDocuments.ts.]")
page_break()

heading("Appendix C: RQ4 Survey Instrument", level=2, size=13, upper=False)
body_paragraph("[Insert the structured Likert-scale questionnaire covering usability, clinical relevance, "
                "transparency, trust, and perceived value of explanations, administered externally per Section 3.5.2.]")
page_break()

heading("Appendix D: Turnitin Similarity Report", level=2, size=13, upper=False)
body_paragraph("[Attach the Turnitin similarity report for this submission once generated.]")

doc.save(OUT)
print(f"WROTE {OUT}")
