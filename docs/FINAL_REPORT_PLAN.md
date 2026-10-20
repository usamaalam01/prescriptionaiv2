# MediScan Final Project Report — Plan (v2, audited)

Student: Muhammad Usama Alam · Supervisor: Sajid Majeed
PGD in Generative AI, Batch 5 FALL I 2025 · NED University of Engineering & Technology (CMPP)

Project title (as submitted): *MediScan: A Human-in-the-Loop, Explainable AI Decision-Support System
for Prescription Reading and Therapeutically-Equivalent Medicine Substitution*

> **v2 note.** Version 1 of this plan was audited by seven independent reviewers against the primary
> sources. It contained two blocking errors, several false claims about how much writing remains, and
> three incorrect assumptions about what the codebase can actually measure. Everything below is the
> corrected version. Items marked **[VERIFIED]** were checked directly against the source or the code.

---

## 0. Governing constraints

### 0.1 A genuine conflict between two university documents **[VERIFIED]**

The university states per-section word counts in two places, and **they do not agree**:

| Section | Guidelines p.10 (components a–k) | Submission Sheet p.26 (supervisor signs this) |
|---|---|---|
| Introduction | 1,500–2,500 | 2,000–3,000 |
| Literature Review | 3,000–4,000 | 3,000–4,000 |
| Methodology | 1,500–2,500 | 2,500–4,500 (merged with Study Design) |
| Study Design | 1,000–2,000 | *(merged above)* |
| Main body / Findings | 4,000–5,000 | 4,000–5,000 |
| Conclusions & Recommendations | 1,000–2,000 | 1,000–2,000 |

Notes that follow from this:
- The p.10 bands sum to exactly **12,000–18,000**, matching the overall total stated on p.9.
  The Submission Sheet bands sum to 12,500–18,500 — so you **cannot** write to the top of every
  Submission Sheet band without breaching the 18,000 cap.
- **Introduction is the only real conflict.** Target **2,000–2,500** (the overlap) and it passes both.
- Methodology + Study Design is 2,500–4,500 under either reading (1,500–2,500 + 1,000–2,000), so
  Chapter 3 is unaffected by the conflict.
- Where they conflict and you must pick one, prefer the **Submission Sheet** — it is the checklist your
  supervisor physically signs, row by row.

### 0.2 Hard requirements

- **Total:** 12,000–18,000 words across the five chapters (excludes references, appendices, prefatory pages).
- **Font/spacing:** Times New Roman 12, double-spaced body. Font 10 single-spacing is *permitted* (not
  required) for references and appendices. One-sided printing.
- **APA 7th edition** for citations, references, tables and figures. Annexure G is the reference guide.
  **References need a ½-inch hanging indent** on every entry longer than one line (Annexure G) — this is
  not optional. Safest: keep references double-spaced *with* hanging indent, since p.9 only permits
  single spacing, it doesn't mandate it.
- **Two separate checklist rows, not one** **[VERIFIED]**: (a) ≥15 reference-list entries, and
  (b) ≥15 in-text citations. Fifteen references each cited once is the bare minimum for both — plan for
  comfortably more in-text citations.
- **Where citations must appear** **[VERIFIED — this was a blocking error in v1]**: guidelines p.10
  component (i) requires references to "have been cited in the **introduction, body, and conclusions**".
  That means **Ch.1, Ch.2–4 (the body, including Results/Discussion), and Ch.5**.
  v1 said "Ch.1–3", which would have left Chapter 4 and Chapter 5 uncited and failed the checklist.
  The "Chapters 1–3" phrasing was inherited from the interim report's own note — correct for a
  three-chapter interim, wrong for a five-chapter final report. **Do not carry it forward.**
- **Similarity is a cap, not a floor** **[VERIFIED]**: guidelines p.9 says "less than 20%"; the
  Submission Sheet tightens it to **less than 19% overall and less than 5% from any single source**.
  The binding number is 19%. **This project targets 15%** for margin. The 5% single-source cap is
  measured **across the whole report**, not per chapter — a source at 3% in each of three chapters
  breaches it while no individual chapter does.
- **Appendices:** each starts a new page, lettered A, B, … with a specific title. Turnitin report goes in
  an appendix.
- **Figures/tables:** combined ≤25% of the paper; each ≤ half a page.

### 0.3 Front matter order (per the template) **[VERIFIED]**

Title page → Certificate → Declarations → Plagiarism Undertaking → Final Report Submission Sheet →
Table of Contents → List of Tables → List of Figures → Notations/Abbreviations → Acknowledgement →
Abstract → Dedication → Chapter 1.

The template's own sample ToC omits Declarations, the Plagiarism Undertaking and the Submission Sheet
(which is why its page numbering skips iv). Bind all three in physical order **and** list them in the
ToC with roman numerals.

### 0.4 Chapter titles

1. Introduction
2. Literature Review
3. **Methodology and Study Design** — titled to match Submission Sheet item 5 and to make component (f)
   visibly satisfied (see §2.4)
4. Results and Discussion
5. Conclusion and Recommendations
REFERENCES

The template's sample chapters are cement-themed; the guidelines explicitly say headings are "sample
only, include your project topic related headings."

---

## 1. What actually exists — measured, not estimated **[VERIFIED]**

v1 claimed the interim report's Chapters 1–3 were "~6,500 words" and "within band already." **Both were
wrong.** Measured prose word counts:

| Chapter | Interim actual | Final target | Gap |
|---|---|---|---|
| Ch.1 Introduction | **1,298** | 2,400 | **+1,100** (below the minimum of *both* bands) |
| Ch.2 Literature Review | **1,482** | 3,400 | **+1,900 — must roughly double** |
| Ch.3 Methodology | **1,912** | 3,000 | **+1,100** (below the 2,500 floor — needs *expansion*) |
| Ch.4 Progress of Work | 1,653 | *(replaced entirely)* | — |
| **Ch.1–3 combined** | **4,692** | 8,800 | **+4,100** |

**v1 said Chapter 3 "will need trimming, not expansion." That was backwards** — it is ~600 words *below*
the floor. Following v1 as written would have pushed it further out of band.

Total genuinely new writing across the report: **roughly 9,700 words** (Ch.1–3 expansion +4,100, Ch.4
4,200, Ch.5 1,400) — not the modest "adapt and trim" job v1 implied. Chapter 2 is the single largest
writing task outside Chapter 4, and it also needs **new sources**, since the 15-reference minimum is not
met by the interim's placeholder list.

### What must change, not merely be copied forward
- **Tense and factual reconciliation.** Interim Ch.2–3 are written in future tense ("will be") and state
  design intentions that the built system does not fully honour (the append-only audit trail; "structural
  similarity is subordinate"). Convert to as-built past tense and restate those claims to match reality,
  with forward references to the Ch.4 limitations. Otherwise the report asserts in Ch.2/Ch.3 what it
  retracts in Ch.4.
- **Chapter 1 needs a new "Methodology in Brief" subsection** (~200–300 words: DSR build–demonstrate–
  evaluate, the synthetic case set, the four evaluation strands). Component (c) names it explicitly and
  the interim Ch.1 does not contain it. Also make the "significance of this topic" framing explicit.
- **Use RQ1–RQ4 everywhere** **[VERIFIED]**. The university-facing chain (proposal → interim → final) is
  RQ-labelled. The codebase uses DQ1–DQ4 internally. Introducing DQ into the report breaks traceability
  to the already-submitted Table 3.2. If DQ must appear, confine it to an appendix note.
- **It is seven issues, not six** **[VERIFIED]**. Interim §4.3 is headed "Six substantive challenges" but
  lists seven: chemical similarity in ranking; evidence-retrieval refusal state; audit trail
  append-only by convention; scoring model vs specification; RQ3 circularity; jurisdictional scope;
  OCR platform sensitivity. Correct the count in the final report and make sure all seven reach Ch.4
  Limitations / Ch.5 Future Work — otherwise one silently drops out.
- **Name the document when discussing the scoring-model divergence** **[VERIFIED]**. The nine-component
  score diverges from the internal *PharmaAssist Complete Specification*, **not** from the approved PGD
  proposal — the proposal requires only "a transparent, weighted relevance score" and fixes no component
  count. Left ambiguous, an examiner reading "divergence from the approved specification" will read it as
  a deviation from approved scope. Also: obtain **written supervisory sign-off** treating the
  nine-component model as an approved amendment, since the interim report promised exactly that.
- **Chemical-similarity bonus: document it, don't defer it.** The interim offered two options —
  remove it from the sort key, or document and justify it. Deferring it to "future work" reads as walking
  back what the interim called the project's central safety claim. Take option two: document it in
  Ch.3/Ch.4 as a deliberate, justified ranking contribution on the same-moiety path (with Figure 11
  showing its magnitude), and state that it is suppressed on the different-ingredient path.

---

## 2. The blocking work: producing real RQ1–RQ4 results

**This section changed substantially in v2.** Three assumptions in v1 were wrong, and two of them mean
certain results **cannot** be produced by the existing code at all.

### 2.1 What the evaluation harness can and cannot measure **[VERIFIED against the code]**

| | Status | Consequence |
|---|---|---|
| **RQ1 (OCR WER/CER)** | ❌ **Simulated, not real** | `simulate_engine_outputs()` takes the ground-truth text and injects **hard-coded character noise per engine** (`trocr 0.05, google_vision 0.02, hybrid 0.03, paddleocr 0.08, tesseract 0.12`). No image is ever opened; no OCR engine runs. The code knows: it passes `suppress_acceptance=True` so no PASS/FAIL verdict is emitted, with the comment *"do NOT attach a B3 PASS/FAIL verdict (it would certify fabricated numbers)."* |
| **RQ2 (P@3 / R@3)** | ❌ **Measures the gold list against itself** | `build_per_case` ranks the pharmacist gold-standard rows themselves; the live recommendation pipeline is never invoked. The code states the condition comparison is vacuous: *"re-ordering valids among themselves by MCS coverage does NOT change P@K/R@K."* A rules-only vs rules+MCS chart would plot **two provably identical bar series**. |
| **RQ3 (RAG)** | ⚠️ Gated behind flags | Requires `ENABLE_SEMANTIC_RAG=true` (else it runs on a two-row demo stub, not the ~10k FDA-SPL corpus) and `ENABLE_BERTSCORE=true` with `bert-score` installed from `backend/requirements-bertscore.txt`. Until BERTScore is enabled the ≥0.80 threshold cannot be reported at all. |
| **RQ4 (Likert)** | ✅ Works, but gated on ethics | Import path is real. Blocked on ethics approval + a real panel. |

**Decisions this forces — pick one per RQ, with the supervisor:**

- **RQ1.** Either (a) add a real multi-engine OCR path as an explicit coding task on the critical path, or
  (b) **narrow RQ1** to a single-engine accuracy claim using the production analytics path, which *does*
  compare AI-extracted against pharmacist-confirmed values per session
  (`backend/app/services/analytics/compute.py`, keys `cer`/`wer`). Option (b) is far cheaper and still
  honest; it changes RQ1 from "how do the engines compare" to "how accurate is the production pipeline."
  **Under no circumstances report the simulated numbers as measured OCR accuracy.**
- **RQ2.** Either feed the real pipeline's ranked candidates into `retrieved_ranked` (a coding task), or
  drop the rules-only/rules+MCS framing and report `mean_mcs_atom_coverage` — the one metric that
  genuinely differs between conditions. Either way Ch.4 must disclose how P@3/R@3 were computed.
  Note also the ablation was **not pre-registered** in the interim's Table 3.2; if you keep it, say so
  and explain why, rather than presenting it as the submitted design.
- **RQ3.** Report the number with the circularity constraint attached **to the number itself**, and
  withhold or explicitly annotate the PASS/FAIL verdict. Issuing a PASS on a knowingly inflated metric
  would breach the integrity objective the interim report set in §1.3.

### 2.2 Dataset to construct (`data/research_evaluation/`) **[schema VERIFIED]**

Confirmed absent from the repo. Required shapes:

```
cases_v1.json = {
  "dataset_version": "...",
  "cases": [{
     "case_code": "...", "synthetic_prescription_ref": "...",
     "pharmacist_confirmed": true,          // ← omitting this silently yields no RQ1/RQ2 numbers
     "instruction_text": "...",
     "fields": { medicine_name, strength, dosage_form, route, dose, frequency, duration },
     "inclusion_status": "included", "exclusion_reason": null
  }]
}
gold_standards_v1.json  = { "records":  [...] }   // case_codes must already exist
survey_responses_v1.json= { "responses":[...] }   // participant_pseudonym + condition + likert
```

**There is no exporter from confirmed analyzer sessions to `cases_v1.json`.** Running a prescription
through the pharmacist UI does **not** create an `EvaluationCase` or `GroundTruthRecord`. Ground truth
reaches the research DB only via this JSON, or via the reviewer-only `POST
/api/v1/research/eval/ground-truth`. So: hand-author the JSON, or write an exporter — either way it is a
task on the critical path, not a side effect of using the app.

### 2.3 Source images — one hard exclusion

Reusable synthetic images: the **four WhatsApp-named JPEGs** in the old project's `test-prescriptions/`.
None exist in the new repo.

> ⚠️ **`1.png` and `2.png` in that folder were flagged by the audit as real prescriptions containing
> patient names, addresses and prescriber licence numbers.** I have not opened them to confirm, and you
> should check before doing anything with them. If that is right they **must not** enter the evaluation
> set, an appendix, or any figure — your Participant Information Sheet and consent text both promise
> synthetic-only data. (Note: `1.png` was used earlier in this project purely as an upload smoke-test.)

Also: `backend/scripts/create_asad_showcase_rx.py` renders a prescription with PIL, but it produces
*typed* text engineered for perfect OCR — a demo asset, not a handwriting case.

### 2.4 Ethics — a hard, dated gate **[blocking]**

The interim report already told your supervisor that approval precedes collection. Running the panel
without it would make §3.6 of the final report a false statement about your own conduct.

> ⚠️ **The participant-facing ethics documents in the app are attributed to a different person.**
> `frontend/src/content/researchDocuments.ts` names *"Student Researcher: Muhammad Zohaib"*,
> *"Principal Investigator / Dissertation Advisor: Dr. Nazmul Hussain"*, and refers to results appearing
> in an *"MSc dissertation"*. `docs/approved-specification/specification_manifest.json` carries
> `"author": "Muhammad Zohaib"`, `"student_number": "200052400"`,
> `"programme": "MSc Information Systems Management"`, `"ethics_application": "18274"`.
>
> Treat these as a **template only**. They must be re-authored under your own name, your supervisor
> (Sajid Majeed), your programme (PGD in Generative AI, CMPP/NED) and your project title before being
> shown to any participant or placed in an appendix. **Do not carry forward ethics application 18274 or
> any "MSc dissertation" wording** — presenting another student's ethics approval in a submitted report
> is an integrity problem, not a formatting one.

### 2.5 Execution sequence

0. **Obtain institutional research ethics approval (CMPP/NED)** — before recruitment, before any RQ4 data.
   If approval doesn't arrive in time, RQ4 and Figure 10 cannot be reported and Ch.4 must say so.
1. Re-author the PIS / consent / survey instrument under your own identity (§2.4).
2. Decide the RQ1 and RQ2 routes with your supervisor (§2.1) — this determines whether coding work joins
   the critical path.
3. Produce 25–30 synthetic prescription cases, varied by legibility, medicine class, dosage form, and
   including look-alike/sound-alike pairs.
4. Establish ground truth and hand-author `cases_v1.json` with `pharmacist_confirmed: true` (§2.2).
5. Establish the RQ2 pharmacist-judged gold standard.
6. Enable `ENABLE_SEMANTIC_RAG` and `ENABLE_BERTSCORE`; confirm the chunk corpus loads.
7. Run the evaluation strands. Re-enable the reviewer panel by flipping
   `SHOW_RESEARCH_EVALUATION_PANEL` in `frontend/src/pages/ReviewerDashboardPage.tsx`.
8. Recruit and run the 5-pharmacist panel for RQ4.
9. Freeze a snapshot. **But note** **[VERIFIED]**: the frozen snapshot carries **RQ2 and RQ4 only**, and
   the CSV export carries counts plus RQ4 Likert means only. **RQ1 and RQ3 numbers must be captured from
   the live `POST /dq1/run/{case_id}` and `POST /dq3/run` responses, or read out of the
   `ocr_evaluation_runs` / `rag_evaluation_runs` tables, and transcribed by hand.** RQ1 also runs one
   case at a time with no cross-case aggregation, so any averaged figure must be computed manually.

### 2.6 What Chapter 4 reports

- Pass/fail verdicts against the interim's pre-registered Table 3.2 thresholds (WER<0.15, CER<0.10,
  P@3≥0.70, R@3≥0.60, semantic F1≥0.80; RQ4 descriptive, no threshold) — reported as measured.
- Where a threshold is missed, say so plainly and discuss why. The guidelines require
  "Findings/Observations… Limitations of Study."
- Full disclosure of the measurement limitations in §2.1 — how P@3/R@3 were actually computed, and
  whether RQ1 is a single-engine or multi-engine claim.
- All **seven** interim §4.3 issues, reframed as limitations of the build. The chemical-similarity one
  belongs inside the RQ2 discussion, not as a standalone caveat.

---

## 3. Writing in human language, not AI language

- **No AI tells:** avoid rule-of-three stacking ("not just X, but Y, and ultimately Z"), em-dash pivots
  used as a crutch, and "it is important to note," "this underscores," "robust," "seamless," "delve,"
  "furthermore" as a default transition. The interim report already avoids these — it reads like someone
  who thought the argument through. Keep that register; don't polish it toward typical LLM prose.
- **Sentence rhythm:** vary length. Let some sentences be short and flat. Avoid uniformly balanced
  structures across a whole paragraph. Failure mode: "This ensures consistency, promotes transparency,
  and enables reproducibility." Better: one plain, specific claim, stated once.
- **Voice:** follow the interim report's own established mix of "the project," "this report," and
  occasional first person for decisions made (e.g. *"This boundary is drawn for safety, not for
  convenience"*).
- **Read every drafted paragraph aloud before accepting it.** If it doesn't sound like something you'd
  actually say, rewrite it. Do not accept generated text verbatim.
- **Concrete over abstract:** real numbers, real table values, real observed behaviour. The interim does
  this well (the catalogue-scale table; the candid audit-trail and scoring-model admissions). Hold the new
  chapters to that standard.
- **Paraphrase discipline for the 15% target:** rewrite carried-forward interim text substantively —
  restructure the argument, don't swap synonyms. Check similarity **after each chapter**, not once at the
  end. (Note: whether your own prior interim submission is in the comparison corpus depends on the
  university's Turnitin configuration — no source document states this either way. Confirm with your
  supervisor rather than assuming.)

---

## 3a. Figures and tables

### 3a.1 What the production rule actually says **[VERIFIED — v1 overstated this]**

The guideline is: *"Diagrams / Graphs / Tables must be drawn in word – not images from E-views or SPSS
and must be formatted according to the APA guidelines."* That targets **statistical-package exports**, not
all external images — the university's own sample report contains photographs.

Practically: insert charts as **native Word chart objects** and schematic diagrams as **Word
shapes/SmartArt**. **Screenshots of the running application are not forbidden by any source** and are the
strongest available evidence of a working prototype — include them (conservatively, in an appendix).

**The interim report's four figures are externally-rendered PNGs pasted into Word**, and the supervisor
accepted them at interim. Decide explicitly: either refresh their content as-is, or rebuild them as
native Word objects and budget that work. Don't leave it dangling.

### 3a.2 Caption convention **[VERIFIED — v1 misattributed this to APA]**

APA 7 numbers figures consecutively ("Figure 1", bold, own line, italic title beneath, no colon).
Chapter-based double numeration is a **thesis convention APA permits, not an APA rule**, and the
guidelines give no figure-caption rule at all (Annexure G is referencing-only). The two university
samples disagree on the colon.

**Decision: use "Figure X.Y: Title"** for continuity with the already-submitted interim report — and flag
to your supervisor that the Annexure E template omits the colon, in case they prefer that.

### 3a.3 Figure inventory

Numbering is chapter-sequential. **The interim's Figure 4.1 (timeline) and Tables 4.1–4.3 belonged to a
"Progress of Work" chapter that no longer exists** — they must be renumbered or relocated before
drafting, or they collide with the new Chapter 4 results figures.

| New # | Figure | Chapter | Type | Source |
|---|---|---|---|---|
| 3.1 | Design Science Research cycle | Ch.3 | Cycle diagram | Exists (interim Fig 3.1) — refresh |
| 3.2 | System architecture (layered) | Ch.3 | Layered boxes | Exists (interim Fig 3.2) — refresh; must include the verification module |
| 3.3 | Four-step pharmacist workflow with verification gate | Ch.3 | Flowchart | Exists (interim Fig 3.3) — refresh |
| 1.1 | End-to-end data flow (image → confirmed fields → ranked alternatives → evidence → explanation) | Ch.1 | Data-flow | New — anchors the Ch.1 problem/solution framing |
| 3.4 | Application database domains (auth, consent, administration, prescriptions, OCR, clinical, audit, research evaluation) | Ch.3 | ER-style boxes | New — supports the separated-data-stores safety argument |
| 3.5 | Research process timeline | Ch.3 *(or appendix)* | Gantt-style | From interim Fig 4.1, updated. **Not Chapter 4** — a project schedule is not a result |
| 4.1 | RQ1 — WER/CER (scope depends on the §2.1 RQ1 decision) | Ch.4 | Bar chart | Gated on §2 |
| 4.2 | RQ2 — P@3 / R@3, or MCS atom coverage | Ch.4 | Bar chart | Gated on §2; framing depends on §2.1 decision |
| 4.3 | RQ3 — citation coverage / unsupported-claim rate by retrieval strategy | Ch.4 | Bar chart | Gated on §2 |
| 4.4 | RQ4 — mean Likert by explanation condition (A/B/C) | Ch.4 | Grouped bars | Gated on ethics + panel |
| 4.5 | Worked scoring breakdown — one recommendation, per-component contributions | Ch.4 | Stacked bar | New — makes "transparent by construction" concrete and anchors the chemical-similarity discussion |

Chapters 2 and 5 carry no figure. That matches the university template (which concentrates figures in the
results chapter) and is fine — v1's claim that the template shows figures in every chapter was false.

### 3a.4 Table inventory — *v1 omitted this entirely*

Without it the List of Tables cannot be assembled, and half the "Quality of Tables, Figures, Graphs"
criterion is unplanned.

| New # | Table | Chapter | Source |
|---|---|---|---|
| 3.1 | Drug knowledge sources and their role | Ch.3 | Interim Table 3.1 |
| 3.2 | Research questions, metrics, acceptance thresholds | Ch.3 | Interim Table 3.2 |
| 4.1 | RQ1 per-engine (or per-session) WER/CER | Ch.4 | New |
| 4.2 | RQ2 P@3 / R@3 (or MCS coverage) | Ch.4 | New |
| 4.3 | RQ3 citation coverage / unsupported-claim rate | Ch.4 | New |
| 4.4 | RQ4 Likert means and SDs by condition | Ch.4 | New |
| 4.5 | Pass/fail verdicts against Table 3.2 thresholds | Ch.4 | New |
| 4.6 | Knowledge base scale achieved | Ch.3 or Ch.4 | Interim Table 4.2 — relocate |
| 5.1 | Limitations and future work (the seven issues) | Ch.5 | From interim Table 4.3, reframed |

Keep each chart's underlying numbers in a companion table nearby — not a stated requirement, but it reads
as more rigorous and helps fill the List of Tables.

---

## 4. Word budget (corrected)

| Chapter | Band used | Target | Interim actual | Work required |
|---|---|---|---|---|
| Abstract | not specified | ~300 | — | Write last |
| Ch.1 Introduction | **2,000–2,500** (overlap of both sources) | 2,400 | 1,298 | **+1,100**, plus new "Methodology in Brief" |
| Ch.2 Literature Review | 3,000–4,000 | 3,400 | 1,482 | **+1,900 — roughly double; needs new sources** |
| Ch.3 Methodology & Study Design | 2,500–4,500 | 3,000 | 1,912 | **+1,100 — expand** (v1 wrongly said trim) |
| Ch.4 Results and Discussion | 4,000–5,000 | **4,200** | — | **New — gated on §2** |
| Ch.5 Conclusion & Recommendations | 1,000–2,000 | 1,400 | — | New |
| **Total** | 12,000–18,000 | **14,400** | | |

v1 set Ch.4 at 3,800 — **below the 4,000 floor stated by both sources**, on a row the supervisor signs.
Corrected to 4,200.

---

## 5. Component coverage checklist

Tick each before submission — these map to the rows on the signed Submission Sheet:

| # | Component | Where it lives |
|---|---|---|
| 1 | Cover page / ToC | Front matter |
| 2 | Abstract | Front matter |
| 3 | Introduction / Background | Ch.1 (incl. significance, scope, objectives, **brief methodology**, organization) |
| 4 | Literature Review | Ch.2 |
| 5 | Methodology / **Study Design** | Ch.3 — needs explicit sub-headings for **research design + questionnaire instrument**, **data-collection methodology**, **data sources and survey target audience** (who the five pharmacists are, how selected), and a pointer to findings. **The questionnaire must be attached in an Appendix** |
| 6 | Main body / Findings | Ch.4 |
| 7 | Conclusions & Recommendations | Ch.5 |
| 8 | References ≥15, APA 7 | References |
| 9 | Citations ≥15, APA 7 | **Ch.1–Ch.5** |
| 10 | Appendices | See below |
| 11 | Turnitin report (<19% / <5% single source) | Appendix |

**Appendices:** Turnitin report · re-authored Participant Information Sheet · consent form · blank survey
instrument · frozen snapshot CSV/JSON exports · completed (scanned) RQ4 responses · pharmacist
gold-standard judgements · per-case ground-truth set · application screenshots.
The Week-16 draft submission explicitly demands "all supplementary material (Excel sheets, scans of
surveys, appendices/annexures)."

---

## 6. Submission logistics and dates — *v1 omitted these entirely*

**These are separate submissions, not one.**

| Week | Deliverable | Form |
|---|---|---|
| 16 | **Draft Project Report** | Three **spiral-bound** copies + all supplementary material, to the Focal Person via the Supervisor, after supervisor approval |
| 18 | **Final Project Presentation + Viva** | 20-minute presentation (Annexure F template, guidelines pp.35–45) + 20-minute viva. Committee must receive the draft **≥2 weeks before** |
| 20 | **Final Report** | Three **hard-bound** copies incorporating post-viva revisions |

Post-viva, you get **1–6 weeks** to incorporate required improvements before the final bound copies.

> **Task zero: get the actual calendar dates** for Weeks 16, 18 and 20 from the Focal Person, and
> back-schedule from them. This plan has no dates and cannot be sequenced realistically without them.
> Note the guidelines are internally inconsistent about whether the three spiral copies are due at
> Week 16 or Week 18 — plan to the earlier date and confirm with the Focal Person.

**Supervisor checkpoints to schedule:** chapter-by-chapter review as drafted; formal approval before the
Week-16 draft is printed; and lead time for the physical signatures required on the Title Page, the
Certificate and the Submission Sheet. Regularity of supervisor correspondence is itself a scored rubric
line.

---

## 7. What is actually being marked (Annexure H) — *v1 ignored this*

| Component | Marks |
|---|---|
| Project Progress (supervisor: correspondence regularity, interim-report adequacy) | 10 |
| **Quality of Presentation** (completeness, design, clarity, Q&A) | **20** |
| Quality of Final Report (content adequacy, language, **layout/format/chapters**, write-up) | 20 |
| **Quality of Project Work** (Originality 10, Data Collection 5, Data Analysis 5, **Overall Effort 20**) | **40** |
| Director CMPP | 10 |

The written report is only **20 of 100**. The presentation — which v1 didn't mention at all — is another
20. The largest single block, 40, is *Quality of Project Work*, which is exactly what the §2 evaluation
run and the working deployed artefact demonstrate. Build the Week-18 deck from the same frozen snapshot
as Ch.4 rather than re-deriving it later.

**One reconciliation to raise with your supervisor:** the milestone table calls for "Data Collection from
the local industry." Your approved proposal rules out real patient data. The industry strand is satisfied
by the licensed-pharmacist panel (RQ4), the pharmacist-judged gold standards (RQ2), and real published
FDA/regulator datasets. Confirm that framing in writing so examiners don't read it as a missed milestone.

---

## 8. Sequencing

1. **Task zero:** obtain Week 16/18/20 dates from the Focal Person.
2. **Start ethics approval immediately** (§2.4) — longest lead time, gates RQ4 entirely.
3. Decide the RQ1 / RQ2 measurement routes with the supervisor (§2.1). This determines whether coding
   work is on the critical path.
4. Re-author the PIS, consent and survey instrument under your own identity.
5. Execute §2.5: build the dataset, run the strands, recruit the panel, freeze the snapshot, and
   hand-capture the RQ1/RQ3 numbers the snapshot doesn't carry.
6. Draft Ch.4 + Figures 4.1–4.5 + Tables 4.1–4.5 together from the frozen data.
7. Draft Ch.5 (impacts, lessons learned, limitations — all **seven** issues — recommendations, future work).
8. Expand and rewrite Ch.1–3 (~+4,100 words), convert to as-built past tense, reconcile the stale design
   claims, add Ch.1's "Methodology in Brief", and draw Figures 1.1 / 3.1–3.5.
9. Compile References (≥15, APA 7, hanging indent) and ensure ≥15 in-text citations spanning Ch.1–Ch.5.
10. Assemble appendices (§5) and front matter (§0.3).
11. Turnitin → target ≤15%; fix any single source over 5% of the whole report.
12. Formatting pass: TNR 12 / double-spaced, figure and table placement, half-page sizing, ≤25% combined,
    one-sided.
13. Supervisor approval → **Week 16: three spiral-bound copies + supplementary material.**
14. Build the presentation deck from the frozen snapshot → **Week 18: presentation + viva.**
15. Incorporate post-viva revisions → **Week 20: three hard-bound copies.**

---

## Open questions for you

1. **Dates** — what are the actual Week 16 / 18 / 20 deadlines?
2. **Ethics** — has CMPP/NED approval been applied for, or does that start now?
3. **RQ1 and RQ2** — given §2.1, do you want to invest in real measurement paths, or narrow the claims to
   what the current code can honestly support?
4. **Pharmacist access** — can you recruit five licensed pharmacists for the RQ4 panel and the RQ2 gold
   standard, or does the design need to shrink to what you can resource?
