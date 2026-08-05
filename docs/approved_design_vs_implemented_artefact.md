# Approved design vs implemented artefact (Sprint 1)

**Spec:** Design and Evaluation of an AI-Powered Pharma Assistant v1.0  
**Artefact:** FastAPI + React + PostgreSQL + SQLite catalogue  

## Indication-based alternatives (retained)

The application continues to retrieve **different-active-ingredient** candidates using verified indication overlap from the FDA/DrugBank catalogue (and DEMO seed when applicable). These are labelled:

**Different-active-ingredient therapeutic candidate** / banner:  
`Different active ingredient — pharmacist assessment required`

They are **not** Orange Book therapeutic equivalents and are never auto-applied.

## Product vs therapeutic candidate separation (new)

| List | Type | Gate |
| ---- | ---- | ---- |
| Product Candidates | `SAME_ACTIVE_MOIETY_PRODUCT` | Mandatory filters **before** score/MCS |
| Therapeutic Candidates | `DIFFERENT_ACTIVE_INGREDIENT` | Indication/class evidence; explicit warning |

Lists are separate in API (`product_candidates`, `therapeutic_candidates`) and UI tabs/sections.

## Safe operational definition of DQ2

DQ2 (Spec: MCS / Precision@K for generics) is operationalised as:

1. Ranking **same-active-moiety product candidates** after mandatory eligibility filters.  
2. Optional RDKit MCS as **supporting structural evidence only**.  
3. Separate therapeutic candidates for pharmacist review.  
4. Pharmacist Accept for review / Reject / Request more evidence.

**MCS does not establish clinical interchangeability.**

## Role and limitation of RDKit MCS

- Calculated only after mandatory filters pass (product path).  
- On therapeutic (different ingredient) path, MCS is display-only and does **not** add score bonus.  
- UI limitation text: structural similarity supporting evidence only.

## Score explanation vs surrogate XAI

Primary UI/API explanation: **Rule-based score explanation** (component weights, mandatory filters, provenance).  
Experimental feature attribution / optional SHAP remains secondary and labelled experimental.

## Design Science Research build–evaluate modifications

| Spec design | Implemented artefact | Reason | Clinical-safety impact | DQ impact | Validation method | Remaining limitation |
| ----------- | -------------------- | ------ | ---------------------- | --------- | ----------------- | -------------------- |
| Streamlit / HF Spaces | React + FastAPI + Docker | Production HITL UX & RBAC | Positive — clearer Confirm gate | All DQs evaluated in reviewer UI | Compose health + RBAC tests | Spec diagram outdated |
| Serialised files | PostgreSQL + SQLite catalogue | Auditability, multi-user | Positive — durable audit | Snapshots in `research` schema | Alembic 0012 | Dual store complexity |
| TrOCR primary OCR | Vision production primary (`OCR_PROFILE=production`); Spec order via `OCR_PROFILE=spec` + Research Evaluation DQ1 | Best operational OCR for HITL; Spec order for dissertation | Neutral — pharmacist GT remains truth | DQ1 can measure TrOCR vs Vision honestly | `OCR_PROFILE`, `test_r01_ocr_engines.py` | Live TrOCR weights / Tesseract binary optional |
| FAISS primary RAG | Keyword SPL production + experimental FAISS | Fail-closed evidence | Positive — empty → insufficient evidence | DQ3 three-way comparison | Retriever parity tests | FAISS optional / hashing fallback |
| MCS as generic equivalence | Mandatory-filtered same-moiety + MCS supporting | Avoid false TE claims | Strong positive | DQ2 P@K on gold standards | Sprint1 + ranking metric tests | Gold set not yet complete |
| SHAP/LIME as primary XAI | Rule-based production; Conditions A/B/C research | Honest explanation of score | Neutral | DQ4 Likert by condition | Additive SHAP reconcile tests | Inferential stats deferred |

## Research evaluation layer (post Sprint 1)

Separate reviewer-only **Research Evaluation** panel under the existing reviewer dashboard: Dataset/GT, DQ1–DQ4, Combined results & export. Aggregate metrics are snapshot-bound and never manually entered.
