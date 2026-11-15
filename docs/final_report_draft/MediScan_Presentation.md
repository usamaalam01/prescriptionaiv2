<!--
MediScan — Final Project Presentation (PMP-style visual design, condensed)
PGD in Generative AI, Batch 5 FALL I 2025 | NED University of Engineering & Technology (CMPP)
Student: Muhammad Usama Alam | Roll No./Enrolment No.: PGD/GAI/JUN-25/212418 | Supervisor: Sajid Majeed

STATUS: markdown build spec — not yet converted to .pptx. Convert next with a python-pptx
generator following the same data-driven approach as the reference deck at
D:\Certifications\OnlineCourses\PMP\generate_pptx.py (parse this file's [Layout:]/[Visual]/
[DIAGRAM] blocks, same way that script parses slides.md).

STRUCTURE: 12 slides. The first 11 are one per topic in the official university template
(PGD-Project-Presentation Template-Finalized.pptx, Annexure F), in the template's own order:
Title -> Name/Batch/Roll No. -> Introduction -> Objectives -> Scope of work -> Literature Review
-> Methodology -> Findings -> Conclusions -> Recommendations -> Thank you. A 12th slide, System
Architecture (the report's Figure 3.2 layered-view diagram), was added after Methodology with the
university's agreement that the template may be tailored slightly; its topic pill still reads
"Methodology" since it elaborates that same required topic rather than introducing a new one.
This supersedes the earlier 22-slide MediScan_Presentation.md draft (same 22-slide content is
still available at docs/final_report_draft/ as background reference) — the university's own
pptx template arrived after that draft and takes precedence; this version condenses that
richer content down to exactly one slide per required topic, as instructed.

====================================================================================
VISUAL DESIGN SYSTEM — reused from D:\Certifications\OnlineCourses\PMP\generate_pptx.py
====================================================================================
Canvas: 16:9 widescreen, 13.333 x 7.5 in.
Font: Calibri throughout.

Palette (same hex values as the PMP reference deck):
  SKY          #008BD4   primary header bar / accent
  SKY_DARK     #005F99   footer bar / dark accent / topic pill
  SKY_LIGHT    #D6EEF8   light tint (card headers, footer secondary text)
  TEAL         #00AD9F   left accent strip on body cards, bullet markers
  TEAL_LIGHT   #CCF0EC   light tint
  ORANGE       #FF6B00   "KEY POINT" callout label + accent border
  ORANGE_LIGHT #FFEBDB   light tint
  TIP_BG       #FFF4CC   "KEY POINT" callout fill
  TIP_BORDER   #FFB400   "KEY POINT" callout border
  WHITE        #FFFFFF
  OFF_WHITE    #F5F9FF   slide background
  DARK         #0D1C2E   body text
  MID_GREY     #556B82   secondary text
  LIGHT_GREY   #B0C4D8   card border
  ROW_ALT      #EAF4FB   table zebra-striping

Chrome (every content slide, built the same way as the PMP reference's chrome() function):
  - Header bar: full-width rectangle, height 0.95in, fill SKY. A 0.14in TEAL strip down the
    far left edge. Slide title in WHITE bold Calibri (32pt, drop to 28/24pt if the title text
    is long), vertically centered.
  - Topic pill (top-right of header): rounded pill, fill SKY_DARK, white bold 14pt text —
    holds the EXACT Annexure F topic name this slide satisfies (e.g. "Methodology",
    "Findings"). This doubles as a visible conformance marker for anyone checking the deck
    against the university template.
  - Footer bar: full-width rectangle, height 0.32in, fill SKY_DARK. Left: "MediScan — PGD in
    Generative AI, Batch 5" in WHITE 11pt. Right: "<slide n> / 11" in WHITE 11pt.
  - Body card: white rounded rectangle filling the space between header and footer, 1pt
    LIGHT_GREY border, with a 0.09in TEAL accent strip down its own left edge (inset).
  - "KEY POINT" callout (used sparingly, at most one per slide, same visual role as the PMP
    deck's "EXAM TIP" box): rounded rectangle, fill TIP_BG, 1.5pt TIP_BORDER border, 0.1in
    ORANGE/TIP_BORDER strip down its left edge. Label "KEY POINT" in ORANGE bold 14pt, body
    text in DARK 15-17pt.

Diagrams are NATIVE POWERPOINT SHAPES (boxes, arrows, pills), not images — built directly
with python-pptx shape primitives, matching the PMP reference's approach of drawing chevron
flows, layered stacks, etc. as real shapes rather than importing pictures. Each diagram below
is specified as a build spec (steps, shape, fill, which step if any is highlighted) rather
than Mermaid, since Mermaid cannot be converted into native PowerPoint shapes directly.

====================================================================================
SLIDE 1: TITLE
====================================================================================
**[Layout: title]**

Full-bleed title treatment (no header/footer chrome on this slide — matches the official
template's own title-slide treatment, which has no page-chrome either):
- Background: OFF_WHITE, with a SKY band across the top ~2.2in (full width) and a thin TEAL
  rule beneath it, echoing the header-bar accent used on every other slide.
- Institutional block, centered in the SKY band: "NED ACADEMY" / "Centre of Multidisciplinary
  Postgraduate Programmes" / "NED UNIVERSITY OF ENGINEERING & TECHNOLOGY, KARACHI, PAKISTAN" —
  white Calibri, bold for the first line, regular for the rest, sized to fit three stacked
  lines within the band.
- Logo pair, centered beneath the institutional text block, before the main title: reuse the
  two actual logo images embedded in the official template's own title slide — both are NED
  University crest variants, not a crest-plus-separate-"Academy badge" pair: `image5.jpg` is
  the 100th-anniversary/centenary crest ("100 Years of Excellence", banner "1921-2021") and
  `image4.jpg` is the standard NED crest (gear/sun-over-sea design). On the official template
  the centenary crest sits on the LEFT (~x=2.29in) and the standard crest on the RIGHT
  (~x=6.21in), each roughly square, ~2x2in on the 4:3 canvas; re-import both at build time in
  that same left/right order and scale/center proportionally for 16:9. The "NED ACADEMY /
  Centre for Multidisciplinary Postgraduate Programmes" line is a plain text box on the
  official slide, not a logo image — render it as text here too, not as a third graphic.
- Below the logos, on OFF_WHITE background:
  - **MediScan** — large (40-44pt) DARK bold Calibri
  - "A Human-in-the-Loop, Explainable AI Decision-Support System for Prescription Reading and
    Therapeutically-Equivalent Medicine Substitution" — 18pt MID_GREY, wrapped to 2 lines
  - "Postgraduate Diploma in Generative AI — Batch 5, FALL I 2025" — 16pt SKY_DARK, bold
- Footer-area text block (bottom of slide, OFF_WHITE, no bar — kept visually light since the
  full name/batch/roll-no detail has its own dedicated Slide 2):
  "Muhammad Usama Alam · Supervisor: Sajid Majeed" — 14pt MID_GREY, centered

---

====================================================================================
SLIDE 2: NAME / BATCH / ROLL NO.
====================================================================================
**[Layout: title]**
*(Topic pill: "Student Details" — the template's own 2nd slide has no named topic beyond the
three bare fields, so the pill names what the slide actually shows.)*

Centered content on OFF_WHITE. The official template's slide 2 literally shows only three bare
fields — NAME, Roll No., and BATCH: (confirmed by reading the actual embedded text/title image
on this exact slide) — the first three bullets below reproduce those three directly; the
fourth (Supervisor) is a deliberate addition beyond the literal template, not something drawn
from it, included because it's directly relevant context for the audience:
- "NAME" (SKY_DARK label, 16pt, letter-spaced) → "Muhammad Usama Alam" (DARK, 28pt bold)
- "ROLL NO. / ENROLMENT NO." (SKY_DARK label) → "PGD/GAI/JUN-25/212418" (DARK, 28pt bold)
- "BATCH" (SKY_DARK label) → "5, FALL I 2025" (DARK, 28pt bold)
- "SUPERVISOR" (SKY_DARK label, added beyond the template) → "Sajid Majeed" (DARK, 28pt bold)

Four fields laid out as a vertical stack or a simple 2x2 grid, generously spaced — this slide
is intentionally the lightest-density slide in the deck.

---

====================================================================================
SLIDE 3: INTRODUCTION
====================================================================================
**[Layout: bullets]**
*(Topic pill: "Introduction")*

**[Visual]**
- Two connected problems pharmacists face every day, with no formal tool support:
  - **Reading the prescription correctly** — handwritten prescriptions are common; a single
    misread character in a look-alike/sound-alike drug name selects a different medicine
  - **Finding a substitute when the prescribed medicine isn't available** — out of stock,
    discontinued, or unaffordable; the pharmacist must judge an appropriate alternative on
    the spot, with no formal decision-support tool today
- A third, cross-cutting problem: any automated tool here must **earn trust** — an answer
  without a reason is not safe to act on in a clinical setting

**[KEY POINT]** No existing tool joins prescription reading with regulated therapeutic-
equivalence reasoning in one system — this is the gap MediScan addresses.

---

====================================================================================
SLIDE 4: OBJECTIVES
====================================================================================
**[Layout: bullets]**
*(Topic pill: "Objectives")*

**[Visual]**
1. Multi-engine OCR pipeline — extract medicine name, strength, form, route
2. **Mandatory** pharmacist verification before anything downstream runs
3. Recommendation engine — trusted catalogue + eligibility filters + transparent score
4. Regulatory therapeutic-equivalence layer (FDA Orange Book)
5. Evidence-grounded explanations (FDA label text)
6. Explainable-AI attribution — show *why* a score was given

**[KEY POINT]** Cross-cutting commitment: no metric or claim is reported unless real data
backs it.

---

====================================================================================
SLIDE 5: SCOPE OF WORK
====================================================================================
**[Layout: cards]**
*(Topic pill: "Scope of work")*

Two cards, side by side:

**Card 1 — In Scope**
- OCR extraction + mandatory pharmacist verification gate
- 9-component recommendation scoring + FDA Orange Book evidence
- Evidence-grounded explanation + explainable-AI (XAI) attribution
- Role-based access: pharmacist / reviewer / administrator, self-registration with mandatory
  admin approval, full audit trail

**Card 2 — Out of Scope**
- No autonomous prescribing, dispensing, or automatic substitution
- No real patient data or PII — synthetic prescriptions only
- Not a clinical source of truth; drug-drug interaction checking is future work
- Research-grade prototype, not a production clinical system

---

====================================================================================
SLIDE 6: LITERATURE REVIEW
====================================================================================
**[Layout: table]**
*(Topic pill: "Literature Review")*

| Research strand | What the literature establishes | Where MediScan sits |
|---|---|---|
| Prescription OCR | Handwriting harder than print; look-alike/sound-alike names are a documented error class | Joins OCR to a *substitution decision*, not just transcription |
| Therapeutic equivalence | A regulatory determination (FDA Orange Book), not inferred from chemical similarity alone | Equivalence is the *primary* ranking signal |
| Explainable AI | Interpretable-by-design preferred over post-hoc black-box explanation for high-stakes use (Rudin, 2019) | Score is additive — exact attribution, not an approximation |
| Evidence grounding (RAG) | Retrieval reduces unsupported claims vs. an unconstrained LLM (Lewis et al., 2020) | Withholds narrative entirely when no evidence is found |
| Human-in-the-loop | Confirmation *after* a system acts invites automation bias (Parasuraman & Manzey, 2010) | Gate enforced *before* any recommendation is generated |

**[KEY POINT]** Each of these five properties is addressed separately in prior work — no
existing system integrates all five together. *(Full review: report Chapter 2.)*

---

====================================================================================
SLIDE 7: METHODOLOGY
====================================================================================
**[Layout: diagram]**
*(Topic pill: "Methodology")*

**[DIAGRAM: End-to-end pipeline]**
`type: chevron-flow · shape: native · fill: SKY, step 3 highlighted ORANGE`

Seven horizontal chevron steps, left to right, equal width, SKY fill / WHITE bold Calibri
text, connecting arrowheads between each:
1. Upload prescription image
2. Multi-engine OCR (Google Vision / TrOCR / Tesseract)
3. **Verification Gate** *(fill ORANGE instead of SKY — the one safety-critical step, visually
   distinct from the rest of the chevron chain)*
4. Eligibility filters (5 hard gates)
5. 9-component weighted score
6. Equivalence + evidence + XAI
7. Pharmacist decision

**[Visual]** *(compact caption strip beneath the diagram, 3 lines)*
- Design Science Research: build → demonstrate → evaluate, iterated (Hevner et al., 2004;
  Peffers et al., 2007)
- Verification gate enforced **server-side** — nothing proceeds without pharmacist confirmation
- Score is additive (sum = 100); FDA Orange Book equivalence is evidence only, never re-ranks

---

====================================================================================
SLIDE 8: SYSTEM ARCHITECTURE
====================================================================================
**[Layout: diagram]**
*(Topic pill: "Methodology" — this slide elaborates the Methodology topic required by the
template rather than introducing a new one; added with the university's agreement that the
template may be tailored slightly)*

**[DIAGRAM: System architecture, layered view]**
`type: image · source: docs/final_report_draft/figures/fig_3_2_architecture.png`
`(same image as report Figure 3.2, generated by scratchpad/figures/make_figures.py::fig_3_2)`

Full-width embedded PNG, five horizontal layers top to bottom: Client (React SPA) ->
Presentation/API (FastAPI backend) -> Application services (OCR stack / recommendation engine /
evidence layers) -> Data (Postgres application DB + read-only SQLite drug catalogue) ->
Deployment (single Docker container + externally hosted Postgres).

**[Visual]** *(compact caption strip beneath the diagram, 1-2 lines)*
- FastAPI backend + React SPA, single Docker container; a read-only SQLite drug catalogue is
  kept structurally separate from the Postgres application database.

---

====================================================================================
SLIDE 9: FINDINGS
====================================================================================
**[Layout: cards]**
*(Topic pill: "Findings")*

Four compact cards in a 2x2 grid:

**Card 1 — Worked Example**
Ibuprofen 200mg → Naproxen scores 100/100 (9/9 components); real DrugBank evidence + real FDA
Orange Book AB-rating (167 products) attached. The same run also surfaced a real gap: 2 of the
5 returned candidates (an injectable antiviral, a benzodiazepine) are clinically implausible —
the route/dosage-form eligibility filters did not gate as strictly as designed in this case
(see Card 4). Found by running a real query, not just by reading the code.

**Card 2 — Verified Working**
Human verification gate (Sec. 3.3.2) is server-enforced, not UI-only · score sums to exactly
100 · equivalence layer confirmed passive · evidence-withholding confirmed (no evidence -> no
fabricated narrative) · catalogue at production scale (900K+ product records) *(the separate
mandatory eligibility filters are not included in this "verified working" list — see Card 1)*

**Card 3 — Evaluation Status**
4 pre-registered RQs, thresholds fixed in advance. RQ1/RQ2 harnesses need redirecting (real
single-engine signal; structural-similarity coverage) — not just more data. RQ3/RQ4: dataset +
ethics approval/panel are the immediate next step.

**Card 4 — Known Limitations** *(6 of the report's 9 shown; full list in Ch.4 Sec. 4.9)*
Chemical-similarity bonus on one candidate path · evidence layer not fully passive · scoring
model diverges from an earlier internal spec · audit trail append-only by convention, not
DB-enforced · eligibility filters under-enforced in the worked example (route/dosage-form) ·
equivalence data is jurisdiction-specific. *(Not shown here, still in the report: RQ3's
semantic-similarity metric has a circularity risk; one OCR engine is platform-sensitive.)* The
first three are the ones the report itself flags as needing the supervisor's input.

**[KEY POINT]** A system examined this closely, and reported on this honestly, is the point of
Design Science Research — not a weakness to hide.

---

====================================================================================
SLIDE 10: CONCLUSIONS
====================================================================================
**[Layout: bullets]**
*(Topic pill: "Conclusions")*

**[Visual]**
- The design is buildable, internally coherent, and deployed
- Every layer was exercised end-to-end on a real query against the real catalogue
- This is a **disciplined demonstration** of integration — not yet a fully validated
  performance claim at scale
- What remains is evaluating the system at scale, which the infrastructure built for this
  project is already designed to support

---

====================================================================================
SLIDE 11: RECOMMENDATIONS
====================================================================================
**[Layout: bullets]**
*(Topic pill: "Recommendations")*

**[Visual]**
1. Complete the 25-30 case synthetic evaluation dataset (RQ3)
2. Redirect RQ1 to the real single-engine accuracy signal and RQ2 to structural-similarity
   coverage, then re-run both
3. Obtain ethics approval → recruit pharmacist panel → RQ4
4. Resolve the three supervisor-facing design questions the report itself flags (chemical-
   similarity bonus; evidence-layer passivity; scoring-model specification divergence), and fix
   the route/dosage-form filter gaps the worked example surfaced

---

====================================================================================
SLIDE 12: THANK YOU
====================================================================================
**[Layout: title]**
*(Topic pill: "Thank you!" — the official template's own title includes the exclamation mark;
reproduced exactly since this pill is meant as a literal conformance marker.)*

Centered, full-bleed closing treatment (SKY band top, as on the title slide, for visual
bookending):
- **Thank You**
- "Questions & Discussion" — 20pt MID_GREY
- "MediScan — live at: usamaalam-prescription-assistant.hf.space" — 14pt
- "Muhammad Usama Alam · Supervisor: Sajid Majeed" — 14pt MID_GREY

====================================================================================
NEXT STEP
====================================================================================
Convert this spec into an actual .pptx with python-pptx, following the same pattern as
D:\Certifications\OnlineCourses\PMP\generate_pptx.py: one function per [Layout: x] type
(title, bullets, cards, table, diagram), a shared chrome() for the header/footer/topic-pill,
and the chevron-flow diagram on Slide 7 built as native shapes (rounded rectangles connected by
arrow connectors, not an image).
