# PharmaAssist — Capstone poster pack (British English)

**Module:** CSCK700 Computer Science Capstone Project  
**Programme:** MSc Information Systems Management  
**University:** University of Liverpool  
**Student:** Muhammad Zohaib (200052400)  
**Advisor:** Dr. Nazmul Hussain  

**Format reminder:** A1 (594 × 841 mm) · ≥2 cm margins · ≥14 pt body · title readable at ~3 m · ~300–800 words · static images only · paste into the university PowerPoint template.

---

## 1. Approach validation (Spec vs built) — use this in viva / report, not all on the poster

| Criterion | Spec Design (Streamlit + RDKit MCS + FAISS/RAG/Groq + SHAP/LIME) | Built system (React + FastAPI + catalog HITL) | Winner |
| --------- | ---------------------------------------------------------------- | --------------------------------------------- | ------ |
| Pharmacy workflow fit | Research notebook UI; weak pharmacist cascade | Field-by-field Confirm with red/green gates | **Built** |
| Clinical safety for decision-support | RAG/LLM risk of invented dose/advice; SHAP/LIME explain model weights, not Rx identity | Catalog-constrained options; fail-closed; no auto-prescribe | **Built** |
| Evidence provenance | Vector retrieval may blur source boundaries | Explicit FDA NDC / DrugBank / FDA SPL badges | **Built** |
| Handwritten Rx problem | MCS is structure similarity, not OCR entity matching | OCR → catalog suggest → pharmacist Confirm | **Built** |
| Deployable academic artefact | Streamlit prototype | Dockerised API + web UI + Postgres sessions | **Built** |
| Interpretability story | SHAP/LIME stronger for black-box model essays | Audit trail + catalog match reasons; less “XAI theatre” | Spec (narrow) |
| Molecular similarity research | RDKit MCS stronger | Not the core product need | Spec (narrow) |

**Verdict:** For an **AI-powered Pharma Assistant** that verifies handwritten prescriptions with a pharmacist in the loop, the **built catalog-first HITL approach is better**. Keep Spec elements (RAG/SHAP/MCS) as *future work*, not as the poster’s primary message.

**Poster one-liner:**  
*We prioritised pharmacist-controlled, evidence-linked verification over generative retrieval and molecular similarity — reducing invented clinical values.*

---

## 2. Suggested poster title (short, readable at 3 m)

**PharmaAssist: Human-in-the-Loop Verification of Handwritten Prescriptions**

Subtitle (smaller):  
Catalog-backed decision support using FDA NDC, DrugBank and FDA SPL · University of Liverpool · CSCK700

---

## 3. Poster body copy (paste into PowerPoint) — ~550 words

### Header strip
Muhammad Zohaib · MSc Information Systems Management · CSCK700 Capstone · University of Liverpool · Advisor: Dr. Nazmul Hussain

### Introduction
Handwritten prescriptions remain hard for machines to read reliably. Errors in drug name, strength or directions can harm patients. **PharmaAssist** is an academic decision-support prototype that extracts medicine details from prescription images, matches them to a trusted medicines catalog, and requires a pharmacist to confirm every field before a record is accepted. The system does **not** diagnose, prescribe or dispense.

### 1 · Problem and design choice
The original Spec Design emphasised Streamlit, molecular similarity (RDKit MCS), FAISS/RAG with a generative model, and SHAP/LIME explanations. For pharmacy verification, those tools are a weaker fit: similarity search and generative text can invent doses or blur evidence sources, while pharmacists need **constrained, auditable options**.

**Built approach (preferred):** React + FastAPI + PostgreSQL sessions + local medicines catalog (SQLite), with OCR and a mandatory human-in-the-loop (HITL) cascade.

### 2 · System architecture
**Flow:** Prescription image → OCR (Google Cloud Vision; optional PaddleOCR / TrOCR) → structured extraction → catalog suggestions → pharmacist HITL cascade → Confirm → session analytics / optional therapeutic alternatives.

**Catalog scale (application database):**
- 41,020 medicines · 373,959 aliases · 929,832 products  
- Evidence sources: FDA NDC · DrugBank (~4,952 linked medicines) · FDA SPL label sections  
- Curated dose/frequency options support Confirm for a focused subset (~1,100+ medicines with complete SIG rows)

### 3 · Pharmacist HITL cascade
Fields unlock in order: **Drug → Route → Strength → Dose → Frequency** (indication optional).  
- Red = not in catalog options · Green = catalog-valid  
- Confirm is blocked until the row is complete  
- Therapeutic alternatives are suggestions only — never auto-substituted  
- Encrypted image handling and short retention support academic ethics

### 4 · Evaluation metrics (honest)
| Metric | Role on poster | Value to show |
| ------ | -------------- | ------------- |
| Catalog medicines / aliases | Scale | 41,020 / 373,959 |
| DrugBank-linked medicines | Multi-source evidence | 4,952 |
| Complete HITL SIG medicines | Coverage limit | ~1,143 |
| Demo OCR field match (messy Rx) | Feasibility illustration | 16/16 fields on a 4-drug curated image* |
| Session CER / WER / field F1 | Live demo vs pharmacist Confirm | Use your recorded session — do not invent a target |

\*Single curated demo — **not** a large-n clinical benchmark. Prefer a small chart of catalog scale + one demo accuracy callout.

### 5 · Ethics and limits
Synthetic prescriptions · participant information / consent for studies · decision-support only · pharmacist confirmation mandatory · not for clinical care. Dose and frequency come from curated catalog options, not free-form LLM dosing.

### Conclusion
PharmaAssist shows that **catalog-constrained HITL** is a safer academic path to prescription verification than generative RAG-first designs. Next steps: enlarge SIG coverage, strengthen DrugBank product linkage in ETL enrichment, and run a pharmacist usability study with CER/WER against confirmed labels.

### References (short list — expand in report)
1. U.S. FDA National Drug Code Directory.  
2. U.S. FDA Structured Product Labeling (SPL).  
3. Wishart et al. DrugBank.  
4. Google Cloud Vision API — DOCUMENT_TEXT_DETECTION.  
5. Amann et al. (2020). Explainability for AI in medicine — use with clinical oversight.  
6. University of Liverpool CSCK700 Capstone guidelines.

---

## 4. Layout map for A1 PowerPoint (portrait or landscape per template)

```
┌────────────────────────────────────────────────────────────┐
│ TITLE (largest) · Programme · University · Student name    │
├──────────────┬─────────────────────┬───────────────────────┤
│ Introduction │ 2 Architecture      │ 3 HITL cascade        │
│ + Problem    │   (flowchart fig)   │   (funnel / UI fig)   │
├──────────────┼─────────────────────┼───────────────────────┤
│ 4 Metrics    │ 5 Ethics / limits   │ Conclusion            │
│ (bar chart)  │                     │ + References          │
└──────────────┴─────────────────────┴───────────────────────┘
```

**Figures to draw (static only):**
1. Horizontal pipeline boxes (OCR → Catalog → HITL → Confirm).  
2. Bar chart: Medicines / Aliases / Products (log scale optional) or three big numbers.  
3. Screenshot of red/green verification table (blur any personal data).  
4. Small table: Spec vs Built (3 rows only).

**Visual tips:** One accent colour · generous white space · no dense paragraphs · bullets under each headline · remove chart junk (no 3D, no grid clutter).

---

## 5. Metrics you may print (supportable)

| Metric | Count | Notes |
| ------ | ----: | ----- |
| Medicines | 41,020 | App SQLite catalog |
| Aliases | 373,959 | Brand/generic matching |
| Products | 929,832 | Package/product rows |
| Strengths | 88,891 | Catalog strength options |
| DrugBank IDs on medicines | 4,952 | ~12% of medicines |
| Label sections | 136,167 | SPL-derived evidence text |
| Dose options | 28,988 | Table count |
| Frequency options | 45,189 | Table count |
| Complete SIG medicines (HITL-ready) | ~1,143 | Honest coverage gap |
| Demo messy-Rx fields matched | 16/16 | Curated single image |

**Do not claim on the poster:** production clinical deployment; automatic prescribing; CER/WER &lt;5% unless you measured it; 100% SIG coverage; ETL parquet as the live app database.

---

## 6. Spec → Built justification (two sentences for conclusion or viva)

The Spec’s RAG/MCS/SHAP stack is stronger for exploratory ML research, but weaker for safe prescription verification. The built system better matches the problem: noisy OCR, trusted catalog evidence, and mandatory pharmacist confirmation.
