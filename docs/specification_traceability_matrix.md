# Specification Traceability Matrix

**Document:** Design and Evaluation of an AI-Powered Pharma Assistant (Specification and Design Report)  
**Version:** 1.0 · **Status:** Approved (ethics 18274)  
**SHA-256:** `fde3eac1d146f7171b64bb949a3c20425af2e33b1998cb4a76b3e0c491c1d91f`  
**Source file:** `c:\Users\mzoha\Downloads\Spec Design Report.pdf` (25 pages)  
**Application source of truth:** `D:\Projects\PharmaAssist` (FastAPI + React + PostgreSQL + SQLite catalog)  
**Language:** British English  

**Status key:** Implemented · Partially implemented · Missing · Conflicting · Not verifiable · Out of MVP scope  

| Requirement ID | PDF section/page | Approved requirement | Current implementation | Status | Evidence/file | Gap | Recommended change | Acceptance test |
| -------------- | ---------------- | -------------------- | ---------------------- | ------ | ------------- | --- | ------------------ | --------------- |
| R01 | O1 p.3–5; A8; A10; B1 p.12 | Multi-engine OCR: TrOCR primary; Google Vision + Tesseract fallbacks (Spec research order) | **Dual-path (DSR):** Production HITL uses Google Vision primary (+ Tesseract fallback, optional TrOCR crop retry). Spec order TrOCR→Vision→Tesseract via `OCR_PROFILE=spec` and Research Evaluation DQ1 (independent engine outputs). Common `EngineAttempt` contract + Tesseract adapter. | Implemented (dual-path) | `ocr/engines.py`, `ocr/contract.py`, `ocr/tesseract_adapter.py`, `ocr/consensus.py`, `OCR_PROFILE`, Research Evaluation DQ1 | Live TrOCR weights / Tesseract binary environment-dependent; Spec Streamlit engine radio UI not ported | Keep production Vision-primary; run Spec profile only for DQ1 | `tests/test_r01_ocr_engines.py` |
| R02 | O1; B2 | Image preprocessing for handwritten Rx | Deskew, ink isolate, binarise, sharpen (config flags) | Implemented | `ocr/preprocess.py`, `OCR_PREPROCESS_*` | — | Keep; document in Spec & Governance | Preprocess toggles change OCR input hash in audit |
| R03 | O1; A3 | Structured extraction: drug, dosage (strength/dose/freq) | Pipeline extracts medicines + SIG fields; duration/indication OCR limited | Partially implemented | `pipeline.py`, `field_verification.py` | Duration rarely extracted; indication not from OCR (HITL catalog pick); per-field engine provenance incomplete | Persist per-field: raw OCR, engine, confidence, alts, pharmacist value | API returns field provenance schema for one medicine |
| R04 | O2; A3–A4 | Pharmacist HITL review/correction before recommendations | Red/green cascade Drug→Route→Strength→Dose→Frequency (+ optional Indication); Confirm gated | Implemented | `field_verification.py`, `VerificationTable` / Analyzer UI | Explicit state machine labels (UPLOADED→…→DECIDED) not first-class enum | Add session/medicine state enum aligned to approved workflow; block alternatives until `PHARMACIST_CONFIRMED` (already de facto) | Confirm blocked until all required greens; evaluate rejects unverified |
| R05 | O2 | Edit each field; accept/reject; override reasons | Field edits via catalog options; reject reason on alternatives; HITL audit events | Partially implemented | `hitl_audit.py`, alternatives decision API | Override reason not required for every SIG field change | Optional override_reason on Confirm when AI≠pharmacist | Audit row stores override reason when values diverge |
| R06 | — / clinical safety | Never silently correct OCR | Catalog suggestions + pharmacist pick; fail-closed templates | Partially implemented | `catalog_sig_options.py`, HITL flags | Auto-promotion of unit strengths / fuzzy match may feel like silent correction | UI label “suggested — not auto-corrected”; keep OCR raw visible | UI shows ai_value alongside pharmacist value |
| R07 | O2, DQ | Drug-name normalisation / catalog match | RapidFuzz / alias match to SQLite medicines; Title Case display | Partially implemented | `datasets/match.py`, `catalog_store.py` | No formal salt/base/ester canonical model | Introduce canonical ingredient envelope (see R08) without breaking HITL IDs | Mapping table: brand→ingredient with confidence+method |
| R08 | O3 salt-aware | Salt/base/ester mapping (e.g. cetirizine HCl) | Canonical envelope + salt normalisation for product path | Implemented | `salt_normalisation.py`, `canonical_envelope.py`, `test_sprint1_clinical_safety.py` | Not all catalogue rows have salt fields | Expand mapping table | Unit: cetirizine ↔ dihydrochloride |
| R12 | O3 / DQ2 | Candidate-alternative ranking (MCS, score≥70, top-3) | Dual lists + mandatory filters + gold-standard P@K harness | Partially implemented | Sprint1 + `research_eval` DQ2 API | Gold judgements not yet study-complete | Collect pharmacist gold set | P@1/P@3/R@3 fixtures green |
| R13 | O3 safety | Mandatory filters | Filter matrix with structured reject reasons | Implemented | `mandatory_filters.py`, product path | — | Keep MCS after filters only | Each reject reason unit-tested |
| R14 | O4 | RAG / insufficient evidence | Keyword production + experimental FAISS; insufficient string | Partially implemented | `evidence_retrievers.py`, `rag_evidence.py` | FAISS experimental | Enable FAISS flag in reviewer eval | Empty → insufficient string |
| R18 | O5 | SHAP/LIME | Production rule-based; research Conditions A/B/C | Partially implemented | `xai_conditions.py`, DQ4 API | Not a trained ranker | Keep additive SHAP on scoring fn | SHAP reconciles to score |
| R19 | O6 | Evaluation dashboard | Research Evaluation tabs on reviewer dashboard | Implemented | `ResearchEvaluationPanel.tsx`, `/api/v1/research/eval/*` | Study data incomplete | Run evaluations after GT deposit | Availability chips never show fake zero |
| R20 | O6, DQ1 | WER and CER | Research OCR metrics + production analytics | Implemented | `ocr_metrics.py`, `edit_distance.py` | — | Document normalisation | Fixture WER/CER match |
| R21 | O6 | Entity P/R/F1 | Medicine-name P/R/F1 in DQ1 runner | Implemented | `ocr_metrics.entity_prf` | Full NER suite deferred | — | Fixture F1 |
| R22 | DQ2 | Precision@K Recall@K | Ranking metrics + gold standard tables | Implemented (not evaluated) | `ranking_metrics.py`, `recommendation_*` | Needs gold data | Deposit judgements | Toy gold → P@3/R@3 |
| R23 | O6, DQ3 | BERTScore / groundedness | Citation coverage + unsupported-claim; BERTScore optional | Partially implemented | `evidence_retrievers.py`, DQ3 runs | BERTScore dep often absent | Install bert-score for study | Unavailable → DEPENDENCY_UNAVAILABLE |
| R24 | O6, DQ4 | Pharmacist Likert | External questionnaire (Forms); app imports pseudonymised export only | Implemented (not evaluated) | `survey_responses_v1.json`, DQ4 import/summary | n=0 until Forms export imported | Collect n=5 externally | Export without PII |
| R29 | Eval claims | 143 Rx / 10 pharmacists | Derived counts; Spec 25–30 / n=5 | Not verifiable | `claim_143_or_10_status` | Incomplete evidence | Do not claim until snapshots prove | Display Not verifiable string |
| R30 | Governance | Spec embed | Spec PDF not served in-app; metadata manifest only; clinical RAG must not index Spec | Out of MVP / docs only | `docs/approved-specification/specification_manifest.json` | No in-app PDF viewer | Keep Spec outside product UI | clinical_knowledge_source false |
| R09 | Data / OpenFDA | FDA NDC validation / product identity | NDC in catalog products; HITL uses catalog NDC provenance | Partially implemented | `build_index.py`, products table | No live NDC checksum validation at Confirm | Soft-validate product_ndc format; show NDC on evidence panel | Invalid NDC format → warning, not silent accept |
| R10 | O4 | FDA SPL evidence retrieval | Keyword production + experimental FAISS (`EvidenceRetriever`) | Partially implemented | `rag_evidence.py`, `evidence_retrievers.py` | FAISS experimental | Typed SPL sections + FAISS flag | Retrieval returns section + SPL id |
| R11 | O3–O4, data | DrugBank integration | ~4,952 medicines with drugbank_id in SQLite; SMILES seed subset for MCS | Partially implemented | catalog DB, `smiles_seed.py` | Full DrugBank structure/KG not in app path | Expand SMILES/moiety cache from DrugBank for MCS demos; keep catalog as runtime source | MCS ok for ≥N seeded pairs |
| R15 | O4, safety | LLM must not invent clinical facts | Groq prompt constrained; default off; citation binding in research RAG | Partially implemented | `maybe_groq_summarise`, `build_explanation_from_evidence` | Need stronger refuse | Cite excerpt IDs; empty → insufficient | Fixture: empty excerpts → insufficient string |
| R16 | Provenance | Source provenance FDA/DrugBank/SPL | Provenance chips; source_claims; DQ4 condition C | Implemented | `xai.py`, UI ProvenanceChip | — | Extend to RAG excerpts | Every claim has dataset+record id |
| R17 | O3 score | Score transparency | Evidence Match component breakdown + MCS bonus + feature attribution | Partially implemented | `scoring.py`, `feature_xai.py` | Must not call deterministic score “ML explainability” | UI labels: Rule-based score explanation / Component contribution | Accordion title uses rule-based wording |
| R25 | Ethics | Privacy / PII / synthetic Rx | Encrypted temp images; 24h retention; redaction; synthetic study design | Partially implemented | `encryption.py`, `retention.py`, `ocr/privacy.py` | Raw OCR may still persist in places — audit | Inventory persisted OCR fields; minimise; confirm purge on Confirm | Retention job deletes expired blobs |
| R26 | Ethics / FATE | Audit trail and RBAC | Roles admin/pharmacist/reviewer; HITL + therapeutic audit; research eval reviewer-gated | Implemented | auth models, `HitlAuditEvent`, research_eval API | — | Spec & Governance admin page | Role gate reviewer for research eval |
| R27 | B1 | Deployment Streamlit on HF Spaces | **Docker Compose: FastAPI + React + Postgres** | Conflicting | `docker-compose.yml` | PDF architecture superseded | Document as DSR modification — do **not** re-platform | Compose up healthy API+web |
| R28 | O3 wording | “Therapeutically equivalent” via MCS | Candidate alternative for pharmacist review | Partially implemented | UI copy, Sprint1 | Must use “candidate alternative for pharmacist review” | Global copy pass | Grep UI: no “equivalent” without authority |

---

## Architecture conflict register (PDF vs application)

| Topic | PDF | Application | Resolution principle |
| ----- | --- | ----------- | -------------------- |
| UI platform | Streamlit / Hugging Face Spaces | React + FastAPI + Docker | **Keep application** — document modification |
| OCR primary | TrOCR | Google Cloud Vision | Keep Vision (production-proven); TrOCR as retry; add Tesseract optional |
| Alternatives intent | MCS salt-aware / generics-like | Different-ingredient indication alternatives + MCS bonus | **Clarify two product modes**; never claim TE from MCS alone |
| RAG | FAISS ~1.37M chunks + Groq | SQLite label_sections keyword + optional Groq | Keep catalog RAG for MVP; FAISS as P2 if measurable gain |
| XAI | SHAP/LIME primary | Rule-based score + optional SHAP surrogate | Rule-based primary (honest) |
| Eval n | 25–30 Rx; 5 pharmacists | Session analytics; no locked study artefact | Not verifiable until study data deposited |

---

## Notes

- Clinical knowledge sources: FDA NDC, FDA SPL, DrugBank only. Spec PDF is **not** a clinical evidence source (`clinical_knowledge_source: false`).
- Homeopathic exclusion remains in-scope for catalog builds; not treated as a defect.
- Dose/frequency: curated SIG / SPL-extracted options — must not be labelled as FDA NDC or DrugBank product fields.
