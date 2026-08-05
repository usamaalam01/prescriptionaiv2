# Answering the Spec research questionnaire (best practice only)

**Purpose:** Keep Spec Design Report relevancy for DQ1–DQ4 and Likert Q1–Q5 while using the **built** PharmaAssist app and honest clinical-safety language.  
**Do not** invent metrics, claim therapeutic equivalence from MCS, or re-platform to Streamlit.

**Spec instrument (v1.2):** 5-point Likert (1 Very Poor … 5 Very Good) + optional free text · planned **n = 5** pharmacists · ethics **18274**.

---

## 1. Principle: Spec questions, application evidence

| Spec named technology | What pharmacists actually use | How you stay relevant |
| --------------------- | ---------------------------- | --------------------- |
| TrOCR | Google Vision (+ optional Paddle/TrOCR retry) | DQ1 = “OCR pipeline accuracy”, not “TrOCR-only” |
| Streamlit HITL | React red/green Confirm cascade | O2 / Q1 fulfilled by stronger HITL |
| RDKit MCS “equivalents” | Candidate alternatives + optional MCS structural score | DQ2 / Q3 = **candidates for review**, not TE |
| FAISS + Groq RAG | SPL/catalog label excerpts (+ optional Groq) | DQ3 = grounded explanations from FDA SPL |
| SHAP/LIME | Rule-based score breakdown + provenance (+ optional SHAP) | DQ4 / Q4 = transparency of **reasons and sources** |

**Best-practice wording for sessions and thesis:**  
*“Candidate alternative for pharmacist review”* — never “therapeutically equivalent” unless an authoritative source states it.

---

## 2. Session script (what each pharmacist does)

1. PIS + consent (as ethics 18274).  
2. Open PharmaAssist (pharmacist role) — synthetic Rx only.  
3. Upload / select synthetic handwritten prescription.  
4. Review OCR text beside image; correct fields in HITL (Drug → Route → Strength → Dose → Frequency).  
5. Confirm row (system must not allow Confirm until greens).  
6. Open **Alternatives**: review candidates, evidence/provenance, score components, MCS note (structural only), RAG excerpts or *Insufficient evidence — pharmacist review required.*  
7. Accept-for-review or Reject with reason (optional for survey).  
8. Glance analytics CER/WER if shown (optional).  
9. Complete **Microsoft Forms v1.2** (Q1–Q5 + free text).

Keep each session ~20–30 minutes. Do not coach Likert scores.

---

## 3. How to answer / interpret each Likert item

### Q1 — Usability and Interface  
*“The system interface is easy to navigate and use.”*

**Show:** Login → Analyzer → upload → HITL table → Confirm → Alternatives.  
**Thesis note:** Maps to Spec O2 (HITL), implemented as React cascade (improvement over Streamlit forms).  
**Best practice:** Fail-closed Confirm; catalog dropdowns only.

### Q2 — OCR Performance  
*“The system accurately extracts medication names and dosages from handwritten prescription images.”*

**Show:** Image vs extracted lines; pharmacist corrections.  
**Thesis note:** Maps to DQ1 / O1. Report **CER/WER vs pharmacist-confirmed** values from sessions — do not invent &lt;15%/&lt;10% unless measured.  
**Best practice:** OCR suggestions are not silent corrections; pharmacist value is source of truth.

### Q3 — Clinical Relevance  
*“The recommended generic alternatives are clinically appropriate and relevant…”*

**Critical reframe for best practice (say this in the session intro):**  
Candidates are **possible alternatives for pharmacist review** based on catalog indication overlap and/or structural similarity aids — **not** automatic generic substitution or proven therapeutic equivalence.

**Show:** Different-ingredient banner (if present); provenance FDA NDC / DrugBank / SPL; Reject path.  
**Thesis note:** Maps to DQ2 / O3 **intent** (support finding related options). If Spec wording says “equivalent generics”, discuss as Spec language refined for safety in the built artefact.  
**Do not:** Ask them to rate MCS as proving equivalence.

### Q4 — Explainability and Transparency  
*“How clear and trustworthy are the system explanations and reasons provided?”*

**Show:** Why identified; score components (rule-based); provenance chips; RAG excerpts; insufficient-evidence message when empty; MCS labelled structural only.  
**Thesis note:** Maps to DQ4 / O5. Primary explanation = **rules + sources**; SHAP/LIME only if you enable a real model — otherwise say “rule-based transparency aligned with Spec explainability goals.”  
**Best practice:** Never call a deterministic formula “SHAP” in the UI.

### Q5 — Decision Support Perception  
*“The system provides meaningful support for clinical decision-making…”*

**Show:** HITL gate before alternatives; pharmacist final Accept/Reject; disclaimer decision-support only.  
**Thesis note:** Maps to O2 + O6 usability / decision-support aim.  
**Best practice:** Emphasise final decision remains with the pharmacist.

### Free text  
Invite comments on trust, missing evidence, confusing scores, OCR difficulty — use for thematic analysis (Spec Weeks 34–35 plan).

---

## 4. Mapping dissertation questions (honest answers)

### DQ1 — OCR accuracy (WER/CER)
- **Method:** Instruction string from pharmacist-confirmed fields vs OCR/AI extract (as in `analytics`).  
- **Report:** Mean CER/WER on your synthetic set (up to 25–30).  
- **If below Spec targets:** Discuss honestly; targets were aspirational.  
- **Engine naming:** “Multi-engine OCR (Vision primary; TrOCR/Paddle optional)” — Spec-relevant, app-accurate.

### DQ2 — Recommendation effectiveness (P@K / R@K)
- **Gold set:** Pharmacist marks each top-3 candidate as relevant / not for review (not “clinically interchangeable”).  
- **Compute:** Precision@3, Recall@3 against that gold.  
- **MCS:** Report as optional structural feature — **not** TE proof.  
- **If no gold yet:** Mark metrics Not verifiable; questionnaire Q3 is perceptual only.

### DQ3 — RAG / explanation reliability (BERTScore + grounding)
- **Grounding:** Explanations must cite retrieved SPL/catalog excerpts.  
- **Insufficient evidence** when retrieval empty.  
- **BERTScore:** Optional semantic similarity vs reference label text — **not** factual proof.  
- **FAISS:** Spec technology; built system uses catalog section retrieval — state as modification with same clinical sources (OpenFDA/SPL).

### DQ4 — Trust / transparency (Likert Q1–Q5)
- Primary evidence = **n=5** Forms results (mean ± SD per Q).  
- Link free-text themes to provenance, HITL, score clarity.  
- Do not claim SHAP drove trust unless pharmacists saw SHAP and you measured it.

---

## 5. Minimal product checklist (best practice only)

Implement or verify these before sessions — enough for honest Q1–Q5, no Spec theatre:

| Need for questionnaire | Best-practice feature | Priority |
| ---------------------- | --------------------- | -------- |
| Q1 | Clear HITL + Confirm flow | Must have (exists) |
| Q2 | Image + extract + edit; CER/WER available | Must have (exists) |
| Q3 | “Candidate for review” wording; different-ingredient clarity; Reject | Must fix copy if missing |
| Q4 | Provenance + rule-based score + RAG / insufficient evidence | Must have / tighten |
| Q5 | Disclaimer + pharmacist-final decision | Must have (exists) |
| DQ2 | Optional simple P@3 logging of accept/reject | Nice |
| DQ3 | Insufficient-evidence string | Must have |
| Governance | Spec PDF not in clinical RAG | Must have |

**Out of scope for questionnaire best practice:** Rebuilding Streamlit, full FAISS, claiming TE from MCS, fabricating n=143.

---

## 6. Suggested one-paragraph Spec relevance statement (thesis)

*The approved Specification defined O1–O6 and a pharmacist Likert instrument (Q1–Q5) for DQ4. The implemented artefact realises the same research intent on a FastAPI/React stack with catalog-backed HITL, FDA/DrugBank/SPL provenance, post-confirmation candidate ranking (with optional RDKit MCS as structural context only), and evidence-grounded explanations. Spec technologies such as Streamlit, FAISS, and SHAP-as-primary-XAI were treated as design options; where the build differs, modifications preserve safety (pharmacist as final decision-maker) and keep evaluation constructs Q1–Q5 answerable without claiming unsupported therapeutic equivalence.*

---

## 7. What you report after n=5

| Deliverable | Content |
| ----------- | ------- |
| Table | Q1–Q5 mean, SD, min, max (n=5) |
| Themes | 3–5 themes from free text |
| Technical | CER/WER on confirmed synthetic Rx (state n images) |
| Ranking | P@3/R@3 only if gold labels collected |
| Limits | Small n; synthetic Rx; descriptive stats only; decision-support prototype |

**Never** fill Likert or metric tables with invented numbers.
