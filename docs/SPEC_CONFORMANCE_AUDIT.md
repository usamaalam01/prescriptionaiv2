# PharmaAssist — Spec-Conformance Deviation Audit

**As-built code vs. the approved CSCK700 Specification and Design Report** (*Design and Evaluation of an AI-Powered Pharma Assistant* v1.0; ethics 18274; manifest SHA-256 `fde3eac1…1c1d91f`, 25 pp).

| | |
|---|---|
| Audited artefact | `D:\AI Learning\AIPrescription\new` (FastAPI + React + Postgres) |
| Approved spec | `Documents/Spec Design Report.pdf` |
| Method | 8-dimension parallel code audit + independent adversarial verification pass (16 sub-agents) |
| Verification | 64 CONFIRMED, 6 CORRECTED (refined, not rejected), 0 rejected; 15 further deviations surfaced by the verifier |
| Total deviations | **85** (critical 12 · major 30 · moderate 37 · minor 6) |
| Status | **Report only — no implementation performed.** |

> **Legend.** Severity: **critical** = a headline spec/DQ claim cannot be evidenced from the as-built system; **major** = an approved capability is materially absent, non-functional, or contradicts the spec; **moderate** = partial / degraded / config-dependent divergence; **minor** = cosmetic, wording, or documentation drift. `[V]` = surfaced by the verification pass (missed by the first audit).

## 1. Executive summary

The delivered artefact is a **well-engineered FastAPI + React + PostgreSQL system**, but it is a *different artefact* from the one the Spec approved on several headline points. The four dissertation questions (DQ1–DQ4) are the worst affected: their **named technologies are absent, optional, or never execute in the default runtime**.

- **DQ1 (TrOCR OCR accuracy):** TrOCR is **not** the primary engine and its `torch`/`transformers` stack is **not installed or installable** in the current venv — Google Vision is primary in every shipped config. TrOCR WER/CER cannot be produced.
- **DQ2 (RDKit-MCS therapeutic matching):** *(original finding — since SUPERSEDED by O3/U5)* RDKit was not installed and MCS never ran. **Now:** `rdkit==2026.3.5` is installed; real rdFMCS atom coverage feeds a bounded score bonus and a `mean_mcs_atom_coverage` DQ2 metric (see the D3-02 / D3-03 status blocks). Matching remains catalogue/rule-based with MCS as a supporting structural signal, not a gate.
- **DQ3 (FAISS RAG + BERTScore):** retrieval is **keyword SPL lookup**, not FAISS vector RAG; BERTScore optional.
- **DQ4 (SHAP/LIME XAI):** the scoring model is explained by a **bespoke additive breakdown**; SHAP is optional/never fires, LIME absent.
- **Platform:** approved Streamlit/HF-Spaces UI was **re-platformed to React + FastAPI + Docker/Postgres** (an A10-scale change) — legitimate but must be documented as an approved deviation, not shipped silently.

### Deviations by dimension

| Dimension | n | Critical | Major | Moderate | Minor |
|---|--:|--:|--:|--:|--:|
| D1-ocr — OCR pipeline & engines | 16 | 3 | 5 | 6 | 2 |
| D2-hitl — HITL workflow & platform | 9 | 0 | 2 | 7 | 0 |
| D3-recommend — Recommendation / therapeutic matching | 12 | 2 | 5 | 5 | 0 |
| D4-knowledge-graph — Knowledge graph / catalogue | 8 | 2 | 3 | 1 | 2 |
| D5-rag — RAG & evidence retrieval | 10 | 1 | 4 | 4 | 1 |
| D6-xai — XAI / explainability | 7 | 1 | 3 | 3 | 0 |
| D7-evaluation — Evaluation harness (DQ1–DQ4) | 12 | 2 | 4 | 6 | 0 |
| D8-platform-governance — Platform, deployment & governance | 11 | 1 | 4 | 5 | 1 |
| **Total** | **85** | **12** | **30** | **37** | **6** |

## 2. Critical deviations (12)

#### `D1-01` — OCR pipeline & engines  ·  _critical_

- **Spec ref (O1 / A8 / A10 / B1):** O1: "Develop a transformer-based OCR pipeline using TrOCR with fallback Google Cloud Vision and Tesseract"; A8: "TrOCR (primary) + Google Cloud Vision + Tesseract (fallbacks)"; A10 approved change: original "Tesseract as primary" was "Replaced with TrOCR (primary); Tesseract + Google Vision as fallbacks"; B1: "TrOCR (primary), Google Vision, Tesseract (fallback)"
- **As-built:** Google Cloud Vision is the primary engine in every shipped configuration; TrOCR is not in the default engine chain at all. run_ocr_stack builds the engine order from OCR_PRIMARY/OCR_FALLBACK_ORDER, and only substitutes the spec order (trocr,google_vision,tesseract) when OCR_PROFILE == 'spec'. No shipped configuration file sets OCR_PROFILE=spec — config default, .env.example and docker-compose all pin 'production'. The real .env does not set OCR_PROFILE at all, so the pydantic default 'production' applies, and sets OCR_PRIMARY=google_vision. Net runtime chain: google_vision -> tesseract -> MOCK. TrOCR-primary is dead configuration reachable only by hand-editing an env var, and no code path activates it.
- **Research/DQ impact:** O1 unsupportable as written: the delivered pipeline is a Vision-based OCR pipeline with a transformer bolt-on, not a transformer-based pipeline. DQ1 (TrOCR accuracy) has no production data because TrOCR never produces the text pharmacists verify. B1's module-to-DQ mapping (OCR Multi-Engine -> DQ1) is broken at the primary-engine level.
- **Why critical:** A10 is an explicitly approved design change that made TrOCR primary and demoted Tesseract AND Google Vision to fallbacks. The artefact silently reverts to a third position (Vision primary) that was never approved. The dissertation's headline claim — a transformer-based OCR pipeline using TrOCR — is contradicted by the default runtime behaviour, so O1 cannot be evidenced from the as-built system and DQ1's subject engine never runs in the production path.
- **Evidence:**
    - backend/app/core/config.py:60 — OCR_PROFILE: str = "production"
    - backend/app/core/config.py:61 — OCR_PRIMARY: str = "google_vision"
    - backend/app/core/config.py:62 — OCR_FALLBACK_ORDER: str = "tesseract"  (TrOCR not present)
    - backend/app/services/ocr/engines.py:470 — order = parse_engine_order(settings.OCR_PRIMARY, settings.OCR_FALLBACK_ORDER)
    - backend/app/services/ocr/engines.py:471-477 — profile read; spec order applied only `if profile == "spec"`
    - backend/app/services/ocr/engines.py:479-481 — warning text: "Production HITL should use OCR_PROFILE=production with Google Vision primary."
- **→ Conformance enhancement:** Make the spec order the default: set OCR_PROFILE default to "spec" (or delete the dual-profile branch entirely) in backend/app/core/config.py:60, and change OCR_PRIMARY default to "trocr" with OCR_FALLBACK_ORDER "google_vision,tesseract" (config.py:61-62). Update .env:37, .env.example:50-52 and docker-compose.yml:41-44 to the same values. If Vision-primary must be retained for operational reasons, that is a new A10-class design change and must be re-approved and re-documented as a deviation, not shipped silently.
- **Effort:** S  ·  **Files:** backend/app/core/config.py, .env, .env.example, docker-compose.yml, backend/app/services/ocr/engines.py

#### `D1-02` — OCR pipeline & engines  ·  _critical_

- **Spec ref (A12 / O1 / DQ1):** A12 software stack: "HuggingFace Transformers (TrOCR)"; O1 requires TrOCR to actually run; DQ1 requires TrOCR WER/CER to be measurable
- **As-built:** torch and transformers are not installed in backend/.venv and are not declared in any installable requirements file, so every TrOCR call fails at import time and is swallowed. _trocr_transformers_crop wraps `import torch` / `from transformers import TrOCRProcessor, VisionEncoderDecoderModel` in a bare try/except that logs a warning and returns None. Consequently _run_trocr_document always returns None and the TrOCR engine reports status 'unavailable' even when OCR_PROFILE=spec. The venv is Python 3.13.6, while the project's own optional-requirements note says TrOCR needs Python 3.10-3.12, so TrOCR is not installable into this venv without rebuilding it.
- **Research/DQ impact:** DQ1 ("How accurately does TrOCR extract drug names and dosages? (WER/CER)") is unanswerable from this artefact — there is no execution path that yields a real TrOCR hypothesis string. O1's "transformer-based" claim has no runnable transformer. A12's stack listing is false for this environment.
- **Why critical:** The spec-named primary technology is not merely mis-ordered, it is not installed and not installable from any declared requirements file on the audited machine. Even correcting D1-01's configuration would leave TrOCR returning 'unavailable' and silently falling through to Vision. No TrOCR output can be produced, therefore no TrOCR WER/CER can be measured.
- **Evidence:**
    - backend/app/services/ocr/engines.py:245-246 — import torch / from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    - backend/app/services/ocr/engines.py:273-275 — `except Exception as excel: logger.warning("TrOCR crop failed: %s", excel); return None` (silent degradation)
    - backend/app/services/ocr/engines.py:386-392 — _run_trocr_document returns None and logs status=empty_or_unavailable / unavailable
    - backend/.venv/Lib/site-packages — contains only PIL, cv2, numpy, pytesseract, google/google_auth, httpx, fastapi, sqlalchemy…; no torch*, transformers*, tokenizers*, safetensors*, huggingface* directories or dist-info
    - backend/.venv/pyvenv.cfg — version = 3.13.6
    - backend/requirements.txt:1-22 — no torch, no transformers
- **→ Conformance enhancement:** Declare the TrOCR stack as a first-class dependency: add `torch`, `torchvision`, `transformers`, `safetensors` with pins to backend/requirements.txt (or a new backend/requirements-trocr.txt that is installed by default in the Dockerfile and documented in README), rebuild backend/.venv on Python 3.12 so wheels resolve, and pre-download microsoft/trocr-large-handwritten. Then change engines.py:273-275 to fail loud: record an EngineAttempt with status='error'/error_code='trocr_dependency_missing' and surface it in the response warnings instead of returning None, so an unavailable spec-primary engine can never be mistaken for a working one.
- **Effort:** L  ·  **Files:** backend/requirements.txt, backend/Dockerfile, backend/app/services/ocr/engines.py, backend/.venv (rebuild on Python 3.12)
- **Verifier correction:** Core finding is correct and stays critical, but two supporting assertions are inaccurate and must be corrected. Verified true: no torch/transformers/tokenizers/safetensors/huggingface in backend/.venv/Lib/site-packages (only PIL, cv2, numpy, pytesseract, google, httpx, fastapi, sqlalchemy present); neither is declared in requirements.txt or any installable requirements-*.txt (only prose comments in requirements-ocr-optional.txt / requirements-ml-optional.txt); engines.py:245-246 imports are wrapped in try/except that swallows and returns None (273-275), so _run_trocr_document returns None (386-392) and TrOCR is 'unavailable' even under OCR_PROFILE=spec. INACCURATE clauses: (1) 'Python 3.13.6, TrOCR not installable without rebuilding the venv' — torch and transformers publish cp313 wheels; the '3.10–3.12' note (requirements-ocr-optional.txt) is the project's own note and chiefly concerns PaddleOCR/paddlepaddle, not the torch+transformers TrOCR stack, so the real blocker is that the deps are undeclared/uninstalled, not the interpreter; (2) 'no TrOCR output can be produced' / 'A12 stack is false for this environment' overreaches — the Docker image (python:3.12-slim) DOES install torch (Dockerfile:18) and pulls transformers transitively via bert-score (Dockerfile:19), so TrOCR can import there (its usability is then limited by D1-09/D1-10, not absence).

#### `D1-03` — OCR pipeline & engines  ·  _critical_

- **Spec ref (DQ1 / B1 / O6):** DQ1: "How accurately does TrOCR extract drug names and dosages? (Word/Character Error Rate)"; B1 maps the OCR Multi-Engine Module to DQ1
- **As-built:** The only DQ1 WER/CER endpoint never invokes any OCR engine. run_dq1_ocr_evaluation calls simulate_engine_outputs, which manufactures each engine's "hypothesis" by applying random single-character substitutions to the pharmacist-confirmed ground truth at hardcoded per-engine noise rates (trocr 0.05, google_vision 0.02, hybrid 0.03, paddleocr 0.08, tesseract 0.12). Those fabricated strings are then scored against the same ground truth, persisted into ocr evaluation runs with cer/wer columns, and returned with availability='AVAILABLE'. The real-engine harness was never written — `_timed` is a stub that raises NotImplementedError. The reported engine ranking is therefore predetermined by the noise constants, not measured: Vision must always beat TrOCR, which must always beat Tesseract. The reviewer UI presents this as "Run multi-engine OCR evaluation (confirmed GT required)" directly beneath an instruction that reads "Do not invent WER/CER."
- **Research/DQ impact:** DQ1 cannot be answered at all: there is no measurement of TrOCR (or any engine) against real images. O6/R20 evaluation-metric claims built on this endpoint are invalid. Because the per-engine noise rates encode the desired ordering, the endpoint will also appear to 'confirm' that Vision outperforms TrOCR — a conclusion with zero empirical basis that would directly mislead the dissertation's engine-selection justification.
- **Why critical:** The mechanism that is supposed to answer DQ1 is replaced by a random-noise simulator that derives the hypothesis from the reference. The resulting WER/CER are arithmetic functions of hardcoded constants, carry no information about any OCR engine, and are emitted as AVAILABLE (not as a simulation) and written to the evaluation database. Any DQ1 result quoted from this endpoint would be a fabricated research finding.
- **Evidence:**
    - backend/app/services/research_eval/service.py:132-135 — engine_outputs = simulate_engine_outputs(ground_truth_text=gt.instruction_text or "", ground_truth_fields=gt_fields)
    - backend/app/services/research_eval/ocr_engines.py:54-63 — docstring "For offline/synthetic evaluation when live engines are unavailable"
    - backend/app/services/research_eval/ocr_engines.py:65-71 — hardcoded noise dict {trocr:0.05, google_vision:0.02, hybrid:0.03, paddleocr:0.08, tesseract:0.12}
    - backend/app/services/research_eval/ocr_engines.py:74-75 — hyp_text = _apply_char_noise(ground_truth_text, rate, ...)
    - backend/app/services/research_eval/ocr_engines.py:88-98 — _apply_char_noise replaces alnum chars with random chars
    - backend/app/services/research_eval/ocr_engines.py:22-23 — def _timed(...): raise NotImplementedError
- **→ Conformance enhancement:** Replace simulate_engine_outputs in the DQ1 path with real engine execution: load the evaluation case's stored image, and for each id in CONFIGURED_ENGINES call the corresponding real adapter (engines._run_trocr_document, engines.google_vision_document_text, tesseract_adapter.run_tesseract, engines.paddle_detect_lines) independently, recording raw_text/confidence/processing_ms/error_status per engine and emitting availability='ENGINE_UNAVAILABLE' for engines that cannot run rather than a synthetic score. Delete simulate_engine_outputs and _apply_char_noise (backend/app/services/research_eval/ocr_engines.py:54-98) or move them behind an explicit RESEARCH_ALLOW_SIMULATED_OCR flag defaulting to False that stamps every emitted metric with availability='SIMULATED' and a visible banner. Remove the stub _timed at ocr_engines.py:22-23.
- **Effort:** L  ·  **Files:** backend/app/services/research_eval/service.py, backend/app/services/research_eval/ocr_engines.py, backend/app/api/v1/research_eval.py, frontend/src/components/ResearchEvaluationPanel.tsx

#### `D3-01` — Recommendation / therapeutic matching  ·  _critical_

- **Spec ref (A8 IT Artefact / B2 Similarity Scoring Algorithm / B4 Step-4 screenshot):** A8/B2/B4: weighted score = Strength x 0.4 + Metadata x 0.4 + FormRoute x 0.2; Score = (Strength_score x 0.4) + (Metadata_score x 0.4) + (FormRoute_score x 0.2); Metadata_score = Base 60 | Brand name present (+20) | RDKit graph isomorphism passed (+20); Final = (100.0*0.4)+(100.0*0.4)+(100.0*0.2).
- **As-built:** The approved three-component weighted formula does not exist. The live scorer is calculate_evidence_match_score, a 9-component additive 'Evidence Match Score' out of 100 (indication_relationship 35, atc_or_therapeutic_class 15, mechanism_relationship 10, target_or_pathway 5, route_compatibility 10, dosage_form_compatibility 5, patient_population_compatibility 10, contraindication 5, interaction 5). There is no Strength_score, no FormRoute_score, no Metadata_score, and no 0.4/0.4/0.2 weighting anywhere. Strength is only a hard ±5% eligibility gate, never a graded 0.4-weighted contribution. A repo-wide grep for strength_score/form_route_score/metadata returns nothing.
- **Research/DQ impact:** DQ2 and O3: the recommendation ranking the dissertation claims to evaluate (Strength/Metadata/FormRoute weighted, RDKit isomorphism worth +20) is not the ranking that runs. Any Precision@K/Recall@K reported against this scorer does not measure the approved algorithm.
- **Why critical:** The exact scoring formula, weights, and the Metadata_score composition (Base 60 + Brand +20 + isomorphism +20) are an explicitly approved design decision documented verbatim in A8, B2 and a B4 screenshot. The code implements a materially different scoring model, so the headline B4 reasoning-trail claim and the DQ2 scoring basis are not supportable as approved.
- **Evidence:**
    - backend/app/services/therapeutic/scoring.py:6-16 (WEIGHTS dict = 9 clinical-evidence components, not Strength/Metadata/FormRoute)
    - backend/app/services/therapeutic/scoring.py:102-114 (total = sum of awarded component points, maximum_score 100; no weighted 0.4/0.4/0.2 combine)
    - backend/app/services/therapeutic/evaluate.py:356-374 (calculate_evidence_match_score is the only scorer; adjusted = base + mcs bonus)
    - grep for 'strength_score|form_route_score|formroute|Metadata|base 60|brand +20' across backend/app returns no matches
    - backend/app/services/therapeutic/mandatory_filters.py:57-68 (strength is only a ±5% gate, not a graded score)
- **→ Conformance enhancement:** Add a spec-conformant scorer (e.g. scoring.compute_similarity_score) that returns Strength_score (absolute % difference from reference strength), Metadata_score (base 60 + brand-name-present +20 + RDKit-isomorphism-passed +20) and FormRoute_score (broad substring), combines them as 0.4/0.4/0.2, and use that as the ranking key in evaluate._evaluate_one instead of calculate_evidence_match_score. Keep the current 9-component score only as a secondary/informational panel if desired.
- **Effort:** L  ·  **Files:** backend/app/services/therapeutic/scoring.py, backend/app/services/therapeutic/evaluate.py

#### `D3-02` — Recommendation / therapeutic matching  ·  _critical_

> **O3/U5 status — RDKit-MCS now real (structural signal).** `rdkit==2026.3.5` is installed and runs on
> this env (no segfault, unlike torch/TrOCR). `mcs.py:compute_mcs_similarity` computes genuine
> `rdFMCS.FindMCS` atom coverage from catalogue SMILES (`smiles_by_name`, built by
> `scripts/build_smiles_table.py`), and `mcs_score_points` feeds a **bounded 0–15 bonus** into the
> Evidence Match Score (already wired in `evaluate.py`; surfaced as the `mcs_structural_bonus` XAI bar).
> Verified sensible: amoxicillin vs ampicillin 0.96 (≥0.9), ibuprofen vs naproxen 0.65, metformin vs
> atorvastatin 0.05. **DQ2 correction (from O3's independent validation):** re-ordering pharmacist-valid
> candidates by MCS coverage does **not** change P@K/R@K (valids always rank first; those metrics are
> set-membership over top-K) — so the MCS effect is instead surfaced as a **distinct
> `mean_mcs_atom_coverage`** metric on `rules_plus_mcs` (null on `rules_only`), which is where the real
> MCS signal is reported. **Design note:** MCS is a *supporting bonus*, not an equivalence gate — Orange Book `TE_Code`
> (U-TE) remains the intended regulatory backbone for therapeutic equivalence; MCS is chemical support.
> Gated by `ENABLE_SPEC_MCS` (default on), graceful when RDKit/SMILES absent.
>
> **U-TE status — regulatory TE backbone IN PLACE (subletter-safe after validation).** The FDA Orange
> Book is ingested (`orange_products`, 48.5k rows); `orange_book.te_status_for` resolves a medicine's
> authoritative `TE_Code` (A* = substitutable, empty = single-source), excluding DISCN. Each candidate
> carries a `therapeutic_equivalence` **evidence** block (surfaced, not auto-substituted — HITL).
> **Subletter safety (fixed in U-TE validation):** the first cut returned a flat `substitutable=True`
> over mixed AB1/AB2/AB3 — validation caught this as unsafe. Now A-codes are split into per-subletter
> subgroups (`subletter_subgroups`), `substitution_scope=subletter_scoped` + a `subletter_warning` when
> multiple exist, and RLD brands are surfaced at group level (`reference_listed_drugs` — verified:
> metformin ER → FORTAMET/GLUCOPHAGE XR/GLUMETZA as distinct references). Different-ingredient candidates
> carry `applies_to=candidate_own_generics_only` + a cross-ingredient note so their TE is never misread
> as equivalence to the prescribed drug. So D3-02 is addressed on **both** axes: chemical (MCS support)
> and regulatory (Orange Book TE). Remaining: A10-style scope-addition sign-off; crosswalk is US-only /
> name+form+strength (misses foreign/compounded/combinations).

- **Spec ref (O3 / A8 / A10):** O3: 'Implement a salt-aware therapeutic recommendation engine using RDKit Maximum Common Substructure (MCS)'. A8: 'NetworkX DiGraph + RDKit MCS (90% atom coverage)'. A10 approved change: VF2 was 'Replaced with RDKit MCS'.
- **As-built:** RDKit MCS is NOT the matching algorithm and is not a gate. The actual candidate matcher is name-based salt normalisation + mandatory hard filters; MCS runs strictly AFTER mandatory filters as optional 'supporting evidence' that can add at most a 15-point bonus and 'must never override filters'. Moreover rdkit is not installed in backend/.venv and is declared only in the optional requirements-spec-research.txt, so rdkit_available() returns False and compute_mcs_similarity returns status 'unavailable' with atom_coverage=None by default — contributing 0 to ranking. The 90%/0.9 atom-coverage threshold is computed only as an informational meets_spec_threshold_0_9 flag, never used to include/exclude a candidate.
- **Research/DQ impact:** O3 cannot be claimed: the engine does not match generics via RDKit MCS. DQ2 ('how effectively does RDKit MCS identify TE generics') has no live MCS-driven matching to measure. A10's justification (MCS more robust across salt/ester variants) is untested because MCS never decides eligibility.
- **Why critical:** O3 names RDKit MCS as the engine and A10 records it as the approved replacement for VF2; A8 makes 90% atom coverage the criterion. In the as-built default environment MCS is uninstalled, silently degrades, and even when installed is only a post-filter cosmetic bonus, not the matching mechanism or a 90% gate. The approved objective O3 and DQ2 cannot be evidenced as specified from the running system.
- **Evidence:**
    - backend/app/services/therapeutic/mcs.py:1-5 ('Optional — disabled when RDKit/SMILES missing')
    - backend/app/services/therapeutic/mcs.py:17-23 (rdkit_available import guard) and :65-67 ('RDKit not installed — MCS skipped')
    - backend/app/services/therapeutic/evaluate.py:322-334 ('MCS only AFTER mandatory filters'; 'MCS must never override filters ... no score from MCS alone for eligibility')
    - backend/app/services/therapeutic/mcs.py:128-133 (mcs_score_points caps MCS at 15 bonus points and returns 0 unless status=='ok')
    - backend/app/services/therapeutic/mcs.py:100-113 (meets_spec_threshold_0_9 computed but only reported, never gates)
    - backend/requirements-spec-research.txt:3 (rdkit optional) vs backend/requirements.txt:23-24 (commented out); rdkit absent from backend/.venv/Lib/site-packages
- **→ Conformance enhancement:** Install rdkit into the runtime env (move rdkit from requirements-spec-research.txt into requirements.txt) and make MCS a first-class matching signal: either gate SAME_ACTIVE_MOIETY candidates on atom_coverage >= 0.9 as A8 states, or feed 'RDKit isomorphism passed' into the Metadata_score +20 per B4. Replace the silent 'unavailable' degrade with an explicit surfaced status so the research claim is falsifiable. Ensure evaluate._evaluate_one uses the MCS result in the ranking key, not just as a display field.
- **Effort:** L  ·  **Files:** backend/requirements.txt, backend/app/services/therapeutic/mcs.py, backend/app/services/therapeutic/evaluate.py
- **Verifier correction:** Substance is correct and severity (critical) is fair, but the deviation_type label 'disabled_by_default' mischaracterizes the mechanism. ENABLE_SPEC_MCS actually defaults True (config.py:43), so MCS is NOT switched off by a feature flag. Verified true parts: rdkit is declared only in requirements-spec-research.txt:3 and is NOT installed in .venv (124 packages, no rdkit), so rdkit_available() is False and compute_mcs_similarity returns status 'unavailable', atom_coverage None (mcs.py:17-23,65-67). MCS runs strictly after mandatory filters as supporting evidence (evaluate.py:322-334) and caps at a 0-15 bonus (mcs.py:128-133); meets_spec_threshold_0_9 is only reported, never gates (mcs.py:113). So the correct characterization is (a) optional dependency ABSENT from the runtime + (c) even when present it is a post-filter cosmetic bonus, not the matching algorithm or a 90% gate. This matters practically: flipping ENABLE_SPEC_MCS does nothing; one must pip-install rdkit AND populate SMILES.

#### `D4-01` — Knowledge graph / catalogue  ·  _critical_

> **U9 status — RE-DOCUMENTED (approved A10-style substitute).** Decision resolved: the spec's
> NetworkX DiGraph (Ingredient → Salt → Product → Strength/Route/Form) is **substituted by the
> relational `medicine_catalog.sqlite3`**, which models the same entities and relationships as
> tables/joins and already drives live candidate retrieval — the same traversal, expressed relationally.
> No functional loss; a separate in-memory DiGraph would duplicate the catalogue. This is recorded as an
> approved design change in the spirit of the spec's own A10 (which likewise re-platformed
> FastAPI/Postgres and swapped VF2→MCS). **Supervisor sign-off pending** (same governance route as the
> platform change). A literal NetworkX build remains available if the supervisor requires the exact
> artefact, but is not recommended (duplicative, no added capability).

- **Spec ref (A8 / B1 / A12 / C Deliverables):** Recommendation Engine built on a 'NetworkX DiGraph'; A12 technology stack lists 'NetworkX'; C Deliverables: 'NetworkX salt-aware knowledge graph (OpenFDA + DrugBank) | Complete'.
- **As-built:** NetworkX is not used anywhere in the new codebase. There is no DiGraph, no add_node/add_edge, and none of the named edge types. The drug knowledge structure is a relational SQLite catalogue (data/medicine_catalog.sqlite3) with 8 flat tables (medicines, aliases, strengths, products, label_sections, label_dose_options, label_frequency_options, meta) built by build_index.py. A legacy data/knowledge_graph.pkl (49 MB) exists in data/ but is never loaded by any new-app module.
- **Research/DQ impact:** Directly undermines the recommendation-engine objective (A8/B1) and the 'salt-aware knowledge graph' deliverable (C). Any dissertation claim/DQ that the therapeutic-equivalence engine is realised as a NetworkX graph over OpenFDA+DrugBank is unsupportable; the graph-based methodology cannot be demonstrated.
- **Why critical:** The named data structure of the approved recommendation engine (NetworkX DiGraph) is absent entirely and replaced by relational SQLite. Deliverable C claims a 'NetworkX salt-aware knowledge graph ... Complete'; that headline deliverable cannot be evidenced at all as specified. The A10 data-storage change only authorised moving the 1.37M TEXT CHUNKS out of the graph (to FAISS) while the drug graph 'itself remained NetworkX' - removing the entire graph exceeds and contradicts that approved change.
- **Evidence:**
    - backend/requirements.txt:1-20 (no networkx); requirements-ml-optional.txt, requirements-spec-research.txt, requirements-ocr-optional.txt, requirements-bertscore.txt (no networkx in any)
    - backend/.venv/Lib/site-packages: `ls | grep -i networkx` -> NOT INSTALLED
    - repo-wide grep for networkx|DiGraph|add_edge|HAS_SALT|IS_ACTIVE_IN|HAS_STRENGTH|HAS_ROUTE|HAS_DOSAGE_FORM over backend/app + frontend -> zero application hits (only false-positive substrings in numpy/pip vendored files)
    - backend/app/services/datasets/build_index.py:112-224 (relational CREATE TABLE schema, no graph)
    - grep knowledge_graph|.pkl|pickle over backend/app -> No matches (data/knowledge_graph.pkl is orphaned)
- **→ Conformance enhancement:** Reintroduce a NetworkX DiGraph as the recommendation substrate: add `networkx` to backend/requirements.txt and install it; build the graph (in build_index.py or a knowledge_graph module) with the six node types and five edges over the ingested catalogue; load it and traverse it in app/services/therapeutic/product_candidates.py instead of the SQL-LIKE lookup. Alternatively, if the relational store is retained, obtain an explicit spec amendment - but as the spec stands this is a deviation.
- **Effort:** XL  ·  **Files:** backend/requirements.txt, backend/app/services/datasets/build_index.py, backend/app/services/therapeutic/product_candidates.py

#### `D4-05` — Knowledge graph / catalogue  ·  _critical_

- **Spec ref (A10 Approved Changes (Architecture / Data Storage)):** A10 approved change, Architecture: 'FastAPI + PostgreSQL' was 'Removed; replaced with serialised pickle (.pkl) files - reduced complexity for single-user prototype.'
- **As-built:** The as-built runs the exact stack the approved change says was removed: FastAPI + PostgreSQL via SQLAlchemy (create_engine(settings.DATABASE_URL)), DATABASE_URL=postgresql+psycopg://...:5432/pharmaassist, a postgres:16-alpine service in docker-compose, and 12 Alembic migrations (0001..0012). No pickle serialisation is used by the app (grep pickle over app -> none). The only .pkl files (knowledge_graph.pkl, drugbank_parsed.pkl, rag_*.pkl) are orphaned legacy artefacts in data/ that no new-app code loads.
- **Research/DQ impact:** Invalidates the A10 architecture/data-storage narrative in the dissertation: claims about a simplified pickle-based single-user prototype cannot be evidenced, and the traceability/approved-change record is materially wrong versus the artefact.
- **Why critical:** This directly contradicts an explicitly approved design decision recorded in A10: the spec commits to REMOVING FastAPI+PostgreSQL in favour of pickle files for a reduced-complexity single-user prototype, yet the artefact ships a full client-server PostgreSQL stack with 12 migrations and no pickles. The approved 'reduced complexity / single-user pickle' headline is invalidated. Per the audit rubric, contradicting an explicitly approved design decision is critical (the spec is the commitment even where the code looks like an improvement).
- **Evidence:**
    - backend/app/db/session.py:6 (create_engine(settings.DATABASE_URL))
    - .env: DATABASE_URL=postgresql+psycopg://pharmaassist:...@localhost:5432/pharmaassist
    - docker-compose.yml:4-15 (postgres:16-alpine service, postgres_data volume)
    - backend/alembic/versions/*.py -> 12 migrations 0001_phase1b .. 0012_research_evaluation
    - grep pickle over backend/app -> No matches
- **→ Conformance enhancement:** To conform to the approved spec, replace the PostgreSQL application store with serialised pickle (.pkl) structures for the single-user prototype: remove the postgres service from docker-compose.yml, drop the SQLAlchemy engine/Alembic migration stack (or gate it off), and persist app state via pickle as A10 records. If Postgres is intentionally retained, the specification/approved-change register must be formally amended to reflect it.
- **Effort:** XL  ·  **Files:** docker-compose.yml, backend/app/db/session.py, backend/alembic/versions/, backend/requirements.txt

#### `D5-rag-01` — RAG & evidence retrieval  ·  _critical_

> **U1 status (DQ3 research path only).** The DQ3 harness now uses a real semantic FAISS retriever
> (`SemanticFaissSplRetriever`, `all-MiniLM-L6-v2`, `IndexFlatL2`, top-k by ascending L2) over the
> prebuilt 10k-chunk index, and both the `keyword` and `faiss` conditions now run over that real
> OpenFDA-SPL corpus. Precise effect on the D5-rag findings:
> - **`D5-rag-08` — CLEARED:** the previously-orphaned `rag_index.faiss` + `rag_chunks.pkl` are now
>   loaded and queried by backend code (`semantic_retriever.py`).
> - **`D5-rag-06` — PARTIAL:** DQ3 `faiss` arm is now real MiniLM + `IndexFlatL2` over the OpenFDA
>   corpus (was MD5-hash / `IndexFlatIP` / 2-row demo). **Still open within D5-rag-06:** BERTScore is
>   not yet computed (deferred to **U2**).
> - **`D5-rag-02` — PARTIAL:** all-MiniLM-L6-v2 is now wired for *query embedding on the DQ3 path*.
>   **Still open:** the spec wants it in the production `rag_evidence.py` build+query path (below).
> - **`D5-rag-01` (this finding) and `D5-rag-04` (512/50 chunking, ~1.37M corpus) — NOT cleared.**
>   U1 reuses the legacy ~10k dev index as-is; production wiring + a spec-compliant chunked rebuild
>   against the new catalogue are deferred to **U1b**.

- **Spec ref (O4, A8 (RAG Framework), B1, B2 (RAG Pipeline)):** O4 / A8 / B1 / B2: RAG must use FAISS IndexFlatL2 vector retrieval over ~1.37M OpenFDA SPL chunks, retrieving the top-5 nearest chunks by L2 distance.
- **As-built:** The production evidence path performs deterministic keyword token-overlap ranking over the SQLite `label_sections` table. There is no vector index, no L2 distance, no FAISS. The function even returns method='catalog_label_sections_keyword' and a `faiss_note` conceding the substitution.
- **Research/DQ impact:** O4 (FAISS vector retrieval) and DQ3 (FAISS-based RAG framework) — the headline retrieval technology does not exist in the running system, so any DQ3 result about a 'FAISS-based RAG framework' would be about a keyword baseline, not what was approved.
- **Why critical:** The FAISS vector-retrieval mechanism named across O4/A8/B1/B2 is entirely replaced by SQLite keyword matching in the live artefact. DQ3, framed as 'How does the FAISS-based RAG framework affect...', cannot be evidenced as specified, and O4's 'FAISS vector retrieval' half is unmet.
- **Evidence:**
    - backend/app/services/therapeutic/rag_evidence.py:33 (docstring: 'Keyword retrieval over medicine_catalog.label_sections')
    - backend/app/services/therapeutic/rag_evidence.py:102-111 (token-overlap `density` scoring, no embeddings)
    - backend/app/services/therapeutic/rag_evidence.py:128 ("method": "catalog_label_sections_keyword")
    - backend/app/services/therapeutic/rag_evidence.py:133-136 (faiss_note: 'Academic Spec used FAISS IndexFlatL2; this build retrieves the same SPL/catalog sections with deterministic keyword ranking (FAISS optional later).')
    - backend/app/services/therapeutic/evaluate.py:377-382 and 581-586 (the only runtime callers use retrieve_label_excerpts, i.e. keyword retrieval)
    - grep of backend/app for faiss/IndexFlatL2/SentenceTransformer/MiniLM: only the flag-gated experimental import at evidence_retrievers.py:83
- **→ Conformance enhancement:** Introduce a real dense-retrieval path: build a FAISS IndexFlatL2 over all-MiniLM-L6-v2 (384-dim) embeddings of the SPL section chunks, load rag_index.faiss/rag_chunks.pkl at startup, and make retrieve_label_excerpts embed the query and search the index (top-5 by L2 distance) instead of token-overlap. Keep keyword ranking only as an explicit fallback.
- **Effort:** XL  ·  **Files:** backend/app/services/therapeutic/rag_evidence.py, backend/app/services/datasets/build_index.py, backend/requirements.txt

#### `B4 / A8 / O5 / DQ4` — XAI / explainability  ·  _critical_

> **U10 status — SUBSTANTIALLY ADDRESSED (not literal-spec CLEARED).** Verified by an independent
> adversarial review. **What genuinely holds:** the spec-named **`shap` and `lime` libraries** run over
> the additive Evidence Match Score (`research_eval/xai_real.py`); library SHAP is **verified to
> reconcile with the exact analytical `w·x` attribution** (residual ~1e-14, `ExactExplainer`, zeros
> background); LIME keys map to bare feature names (not condition strings — checked); each ranked
> candidate carries a `real_xai` block; the React panel renders SHAP + LIME **signed SVG bar charts**
> with a reconciliation chip and disclaimer; the "depends on U5" assumption was false (live score has no
> MCS feature). XAI never raises into a request (guarded).
>
> **Honest gaps that keep this short of literal B4 conformance:**
> 1. **Defect found & FIXED (two validation rounds):** for same-moiety product candidates the SHAP/LIME
>    bars summed to the *base* score, not the displayed `base + mcs_bonus` — a provable explanation↔headline
>    mismatch of up to +15. Fixed with an explicit `mcs_structural_bonus` feature; a further round caught
>    that the displayed score is `min(100, …)` while the bonus was uncapped (bars could reach 115 vs a
>    capped 100), so the bonus weight is now **clamped to `100 − base`**. Re-verified across the cap
>    boundary (base 100 + bonus 15 → bars sum 100; base 50 + bonus 12 → 62; all reconciled).
> 2. **Layout differs from spec:** spec named a **three-tab** dashboard ("SHAP | LIME | FDA Sources")
>    with chart titles "SHAP Feature Contributions" / "LIME Local Explanation"; as-built is one
>    Explainability accordion with two SVG sections, and FDA Sources remains a separate provenance
>    accordion. Functionally equivalent, not literally the B4 screenshot layout.
> 3. **Flags default OFF** (`ENABLE_SPEC_SHAP`/`ENABLE_SPEC_LIME`) — the *library* SHAP/LIME +
>    reconciliation run only when enabled; the default runtime shows the exact **analytical** bars
>    (still correct attributions, just not the library path).
>
> Net: the critical "no SHAP/LIME, no charts" deviation is resolved (real libs + charts exist and are
> correct); full B4 literal conformance (3 tabs + exact titles + on-by-default) is a small remaining
> polish item, tracked here rather than claimed as done.

- **Spec ref (B4 screenshots / A8 IT Artefact / O5):** B4 required UI: an "Explainability Dashboard" with THREE TABS "SHAP | LIME | FDA Sources" — SHAP tab a horizontal bar chart titled "SHAP Feature Contributions", LIME tab a chart titled "LIME Local Explanation", FDA Sources tab numbered evidence cards. A8: "SHAP + LIME + source attribution cards embedded inline in Step 4". O5: integrate SHAP and LIME for transparency in the recommendation flow.
- **As-built:** No Explainability Dashboard and no charts exist anywhere in the frontend. In the inline Step-4 alternatives panel, feature attribution is rendered as a single one-line text caption ('Experimental component contribution: feature (+contribution), ...'). The Research Evaluation DQ4 tab only offers a 'Preview explanation conditions A/B/C' button that dumps raw JSON via JSON.stringify, plus a survey-import button. There are no SHAP/LIME tabs, no bar charts, no feature-importance visualisation. No charting library (recharts, chart.js, d3, plotly, victory, nivo) is declared in frontend/package.json.
- **Research/DQ impact:** DQ4 ('impact of SHAP/LIME explanations and source attribution on pharmacist trust') cannot be evidenced as specified: the SHAP/LIME explanation condition has no visual artefact for participants to react to. O5 ('integrate SHAP and LIME ... in the recommendation flow') and A7 hybrid inline explainability are unsupportable in the UI.
- **Why critical:** The headline approved artefact for O5/DQ4 — the three-tab SHAP|LIME|FDA-Sources Explainability Dashboard with feature-importance charts — does not exist. Pharmacists never see SHAP or LIME visualisations, so DQ4's controlled comparison of 'SHAP/LIME explanations' impact on trust cannot be run as specified; the B4 screenshots cannot be reproduced from the artefact.
- **Evidence:**
    - frontend/src/components/TherapeuticAlternativesPanel.tsx:315
    - frontend/src/components/TherapeuticAlternativesPanel.tsx:318
    - frontend/src/components/ResearchEvaluationPanel.tsx:307
    - frontend/src/components/ResearchEvaluationPanel.tsx:598
    - frontend/src/components/ResearchEvaluationPanel.tsx:612
    - frontend/package.json (no chart library dependency)
- **→ Conformance enhancement:** Build an Explainability Dashboard component with three MUI tabs (SHAP | LIME | FDA Sources), add a chart library (e.g. recharts) to render the horizontal SHAP bar chart ('SHAP Feature Contributions') and the LIME local-explanation chart with green/orange signed bars, and embed it inline in each recommendation card in Step 4. Wire it to the backend feature_attribution/shap/lime payloads.
- **Effort:** XL  ·  **Files:** frontend/src/components/TherapeuticAlternativesPanel.tsx, frontend/package.json, frontend/src/components/ResearchEvaluationPanel.tsx

#### `D7-01` — Evaluation harness (DQ1–DQ4)  ·  _critical_

- **Spec ref (O6, A9 (Quantitative-OCR), B3 (DQ1)):** A9/DQ1: 'WER & CER - Measure TrOCR primary engine + fallback performance on handwritten text'; O6 'Assess technical performance (WER, CER, ...)'.
- **As-built:** The DQ1 harness never runs any OCR engine. run_dq1_ocr_evaluation calls simulate_engine_outputs(), which fabricates each engine's 'hypothesis' by randomly corrupting the pharmacist ground-truth string at fixed hard-coded per-engine noise rates (trocr=0.05, google_vision=0.02, hybrid=0.03, paddleocr=0.08, tesseract=0.12). WER/CER are then computed on this synthetic text. The real engine adapter _timed() raises NotImplementedError, and no torch/transformers (TrOCR) is installed. The WER/CER formulas themselves are correct, but the inputs are manufactured, so the 'TrOCR' arm and every engine ranking are predetermined by the noise constants.
- **Research/DQ impact:** O6/DQ1: WER<15% and CER<10% cannot be evidenced for the spec-named TrOCR engine or its fallbacks; the harness outputs values fixed by injected noise rates rather than recognition performance.
- **Why critical:** DQ1 as specified (WER/CER of TrOCR + fallbacks on handwritten prescriptions) cannot be answered from this harness: the numbers are synthetic noise, not real OCR output. Presenting these as measured OCR performance is a research-integrity risk that invalidates the headline DQ1 claim.
- **Evidence:**
    - backend/app/services/research_eval/ocr_engines.py:54
    - backend/app/services/research_eval/ocr_engines.py:65
    - backend/app/services/research_eval/ocr_engines.py:88
    - backend/app/services/research_eval/ocr_engines.py:22
    - backend/app/services/research_eval/service.py:132
    - backend/app/services/research_eval/service.py:137
- **→ Conformance enhancement:** Wire the real OCR engines (services/ocr) into run_dq1_ocr_evaluation so each configured engine (TrOCR primary per OCR_SPEC_PRIMARY, plus Google Vision/Tesseract fallbacks) actually transcribes the synthetic handwritten images; delete simulate_engine_outputs/_apply_char_noise from the evaluated path and implement _timed(); install torch+transformers (requirements-ml-optional) for TrOCR. Score real transcriptions against pharmacist-confirmed ground truth.
- **Effort:** XL  ·  **Files:** backend/app/services/research_eval/ocr_engines.py, backend/app/services/research_eval/service.py, backend/requirements-ml-optional.txt

#### `D7-02` — Evaluation harness (DQ1–DQ4)  ·  _critical_

> **U2 status — mechanism delivered; spec metric IN SUBSTANCE STILL UNMET (D7-02 / D7-V1 remain OPEN).**
> Two independent adversarial validations of U2 agree: `run_dq3_rag_evaluation` now computes a **real,
> deterministic, correctly-gated** BERTScore via `_compute_bertscore_for_condition` (the fabricated
> hard-coded `None` is gone, availability is honest, P/R/F1 all surface + persist). **That is real
> engineering progress — but it does NOT satisfy the spec metric**, for three reasons:
> 1. **Circular reference.** The explanation (`build_explanation_from_evidence`) embeds the retrieved
>    evidence verbatim, so explanation-vs-that-evidence is overlap-inflated (F1 ≈ 0.92 contained vs
>    ≈ 0.77 independent). The spec wants *generated explanation vs an independent reference OpenFDA
>    label* — neither the hypothesis (needs an independent **Groq LLM narrative**, `ENABLE_SPEC_GROQ`
>    off) nor the reference (independent label) is spec-correct. **Both substantive halves are deferred**
>    to the RAG/Groq unit.
> 2. **512-token truncation (2nd validation).** DistilBERT truncates inputs at ~512 tokens; a
>    multi-chunk reference is truncated (measured F1 0.91→0.47 when the match is buried past the limit).
>    U2 now caps the reference to a defined ~1800-char window so truncation is explicit, not silent.
> 3. **The B3 ≥ 0.80 acceptance threshold** is not yet encoded (→ **U12**).
>
> **Verdict: D7-02 and D7-V1 stay OPEN.** U2 removed the *fabrication* (an integrity fix worth having)
> but the DQ3 BERTScore *as specified* is produced by no code path until the RAG/Groq unit lands. Minor:
> the `none` row carries row-level `availability=AVAILABLE` while its per-metric `bertscore_availability`
> is `NOT_CALCULATED` (row-level = "some metric available"; documented in code).

- **Spec ref (O6, A9 (Quantitative-RAG), B3 (DQ3), B4 Tab 2):** A9/DQ3: 'BERTScore - Semantic alignment between generated drug explanations and official OpenFDA regulatory records'; B3 target 'BERTScore F1 ... generated explanation and reference OpenFDA label ... >= 0.80'.
- **As-built:** The DQ3 harness never computes BERTScore. run_dq3_rag_evaluation hard-codes bertscore_precision/recall/f1 = None; even when it detects bert_score is importable it deliberately sets availability to NOT_CALCULATED with a comment that it is 'not auto-run ... until an explicit BERTScore evaluation path is invoked' — but no such path exists. DQ3 instead reports citation_coverage and unsupported_claim_rate. A real BERTScorer does exist, but only in the separate pharmacist Summary Analytics path (analytics/bertscore_optional.py + compute.py), where it compares OCR-extracted instruction text vs pharmacist-confirmed instruction text ('Full prescription OCR vs pharmacist-accepted instructions') — an OCR-agreement measure, NOT the spec's generated-explanation-vs-OpenFDA-label comparison.
- **Research/DQ impact:** O6/DQ3: BERTScore F1 >= 0.80 semantic alignment of generated explanations to OpenFDA labels is unsupportable; DQ3 in the dashboard shows a permanently-unavailable BERTScore slot plus substitute metrics the spec did not approve.
- **Why critical:** The spec's DQ3 BERTScore metric (explanation vs OpenFDA label) is produced by no active code path. The only real BERTScore compares the wrong text pair for a different purpose, so DQ3 as specified cannot be evidenced under any configuration.
- **Evidence:**
    - backend/app/services/research_eval/service.py:319
    - backend/app/services/research_eval/service.py:323
    - backend/app/services/research_eval/service.py:367
    - backend/app/services/analytics/compute.py:470
    - backend/app/services/analytics/compute.py:472
    - backend/app/services/analytics/bertscore_optional.py:47
- **→ Conformance enhancement:** In run_dq3_rag_evaluation, call bertscore_optional.score_pairs(generated_explanation, reference_openfda_label_text) for each RAG condition and populate bertscore_f1/precision/recall with real values; source the reference label from the FDA SPL corpus already retrieved. Gate on ENABLE_BERTSCORE and report DEPENDENCY_UNAVAILABLE only when the package is genuinely missing.
- **Effort:** L  ·  **Files:** backend/app/services/research_eval/service.py, backend/app/services/research_eval/evidence_retrievers.py

#### `A8/B1/A10-architecture` — Platform, deployment & governance  ·  _critical_

- **Spec ref (A8 / B1 / A10 (approved modifications table)):** "The primary IT artefact is a web-based AI-Powered Pharma Assistant prototype ... implemented on Hugging Face Spaces" (A8); "a modular, five-component web-based system deployed as a Streamlit application on Hugging Face Spaces" (B1). A10 approved-changes table explicitly records Architecture "FastAPI + PostgreSQL" -> "Removed; replaced with serialised pickle (.pkl) files - reduced complexity for single-user prototype".
- **As-built:** The artefact is a React 19 + MUI + Vite single-page app talking to a FastAPI backend backed by PostgreSQL, orchestrated by Docker Compose (postgres + api + nginx web). There is no Streamlit anywhere (no app.py entrypoint, streamlit is not in any requirements file, and is not installed in backend/.venv). The FastAPI+PostgreSQL stack that A10 recorded as REMOVED is the live runtime.
- **Research/DQ impact:** Undermines O1 (build the specified MVP artefact) and the DSR artefact-identity: the system actually evaluated for DQ1-DQ4 is not the approved artefact. Any DSR claim that the evaluated prototype matches the approved design is unsupportable without a formally re-approved architecture change.
- **Why critical:** A8/B1 are approved design decisions and the headline identity claim of the artefact ('Streamlit MVP on Hugging Face Spaces'). The as-built not only replaces Streamlit but re-introduces the exact FastAPI+PostgreSQL stack that the approved A10 modifications table recorded as REMOVED - a direct contradiction of an approved change, invalidating the headline platform claim.
- **Evidence:**
    - docker-compose.yml:4-9 (postgres:16-alpine service)
    - docker-compose.yml:22-58 (FastAPI 'api' service running uvicorn app.main:app, DATABASE_URL postgresql+psycopg)
    - docker-compose.yml:60-68 (nginx 'web' service)
    - backend/app/main.py:1-13 (FastAPI app is the entrypoint)
    - backend/requirements.txt:2 (fastapi==0.128.0), :6-8 (sqlalchemy, psycopg[binary], alembic)
    - backend/Dockerfile:2,28 (python:3.12-slim, CMD uvicorn app.main:app)
- **→ Conformance enhancement:** Either (a) re-platform to a Streamlit application persisting to serialised .pkl files per A10 (removing FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker/nginx) - effort XL; or (b) obtain and record a formal supervisor/ethics re-approval of the architecture change and update the approved-modifications register accordingly. The project's own docs currently instruct 'do not re-platform' (docs/specification_traceability_matrix.md), which does not by itself constitute approved-spec conformance.
- **Effort:** XL  ·  **Files:** docker-compose.yml, backend/app/main.py, backend/requirements.txt, frontend/, docs/approved-specification/specification_manifest.json

## 3. Major deviations (30)

#### `D1-04` — OCR pipeline & engines  ·  _major_

- **Spec ref (O1 / A8 / B1):** O1 / A8 / B1: TrOCR is the primary full-page recognition engine, with Vision and Tesseract as fallbacks
- **As-built:** In the active (production) profile TrOCR exists only as a per-line crop retry triggered when a Vision line falls below TROCR_CONFIDENCE_THRESHOLD (0.75). Worse, when the transformer weights are unavailable — which is always, per D1-02 — that 'TrOCR retry' silently becomes a second Google Vision REST call on a preprocessed crop, and the pipeline layer then relabels that Google Vision output as engine='trocr' with is_mock=False. engines.py is honest at its own layer (it tags the result 'google_vision_crop_retry'), but pipeline.TrocrRetryAdapter._try_real discards the returned engine name and substitutes self.name ('trocr'). That mislabelled candidate is written into MergedLine.selected_engine, persisted in pipeline_json, and displayed to the pharmacist as the source engine.
- **Research/DQ impact:** O1's engine hierarchy is inverted (DQ1's subject engine is a conditional refinement, not the recogniser). The mislabelling actively corrupts DQ1 evidence: engine attribution in the artefact's own data cannot be trusted, so a reviewer cannot separate TrOCR from Vision performance even qualitatively.
- **Why major:** The specified mechanism (TrOCR as the primary full-page recogniser) is replaced by a materially different one (Vision full-page + optional per-line second pass), and the substitute engine's identity is falsified in the persisted provenance. Any 'trocr' label in pipeline_json, in the HITL UI, or in downstream analytics may in fact be Google Vision output, so provenance-based DQ1 evidence is not defensible. Not critical only because the honest label does survive at the engines.py layer and the mechanism is at least present.
- **Evidence:**
    - backend/app/services/ocr/engines.py:226-232 — trocr_recognize_crop docstring: "Secondary recognizer on a cropped medicine line" … "Otherwise re-run Google Vision on an aggressively preprocessed crop"
    - backend/app/services/ocr/engines.py:236-239 — real = _trocr_transformers_crop(...); if real is not None: return real; return _vision_retry_crop(...)
    - backend/app/services/ocr/engines.py:278-279 — _vision_retry_crop: "Second-pass Vision on a deskewed/ink-isolated crop when TrOCR weights are unavailable"
    - backend/app/services/ocr/engines.py:305 — doc = _google_vision_via_rest(enhanced)
    - backend/app/services/ocr/engines.py:316 — engine="google_vision_crop_retry" (honest label at this layer)
    - backend/app/services/ocr/engines.py:507-524 — crop retry only fires when engine_id == "google_vision" and line.confidence < TROCR_CONFIDENCE_THRESHOLD
- **→ Conformance enhancement:** Two changes. (1) Provenance: in backend/app/services/pipeline.py:225-233 propagate the true engine name — `engine=result.engine` (e.g. 'trocr-large-handwritten' or 'google_vision_crop_retry') — instead of `engine=self.name`, and rename TrocrRetryAdapter to something engine-neutral (e.g. LowConfidenceRetryAdapter) so the class name cannot re-introduce the mislabel. (2) Role: once D1-01/D1-02 are fixed, make _run_trocr_document the primary recogniser in the default order and demote the Vision crop retry to an explicitly-named 'vision_crop_retry' stage rather than a TrOCR impersonation.
- **Effort:** M  ·  **Files:** backend/app/services/pipeline.py, backend/app/services/ocr/engines.py, frontend/src/components/OcrConflictPanel.tsx

#### `D1-05` — OCR pipeline & engines  ·  _major_

- **Spec ref (O1 / A8 / DQ1):** O1 / A8: TrOCR is a real transformer engine whose output and confidence reflect model inference; DQ1 requires TrOCR outputs to be genuine
- **As-built:** When the crop retry cannot run a real model, TrocrRetryAdapter.retry_line fabricates a 'TrOCR' result: it applies a hardcoded string substitution ('Amoxycillin' -> 'Amoxicillin'), strips mock noise markers, and invents a confidence of line.confidence + 0.25 (or + 0.12) capped at 0.93/0.90, returning it labelled engine='trocr'. Because CandidateMerger.merge selects by max confidence, the invented confidence bump guarantees the fabricated 'TrOCR' candidate always wins the merge and becomes the selected text and selected_engine for that line. The separate legacy mock adapter module also ships a MockTrocrEngine and a MockTesseractEngine that mutates drug spellings.
- **Research/DQ impact:** DQ1: any accuracy or confidence statistic attributed to 'trocr' from the production pipeline may be measuring a hardcoded spelling substitution with an arithmetic confidence bump. O1's transformer claim is simulated rather than implemented on this path.
- **Why major:** A named spec technology's output is simulated by a string rewrite plus a synthetic confidence, and the synthetic confidence is constructed so that it dominates the real engine's candidate in the merge. is_mock=True is propagated and the HITL Confirm gate blocks confirmation of mock sessions, which is why this is major rather than critical — but the fabricated candidate still becomes the displayed selected text and selected_engine for affected lines.
- **Evidence:**
    - backend/app/services/pipeline.py:195-198 — corrected = line.text; if "Amoxycillin" in corrected: corrected = corrected.replace("Amoxycillin", "Amoxicillin")
    - backend/app/services/pipeline.py:199-201 — strips " [n=" mock marker
    - backend/app/services/pipeline.py:202 — conf = min(0.93, line.confidence + 0.25) if "Amoxicillin" in corrected else min(0.90, line.confidence + 0.12)
    - backend/app/services/pipeline.py:203-210 — returned as LineCandidate(engine=self.name /*trocr*/, is_mock=True, source_stage="trocr_retry")
    - backend/app/services/pipeline.py:250 — best = max(candidates, key=lambda c: c.confidence) — invented confidence always wins
    - backend/app/services/pipeline.py:1566 — comment: "Real TrOCR when available; labelled mock spelling assist otherwise"
- **→ Conformance enhancement:** Delete the fabrication branch: in backend/app/services/pipeline.py:195-210 return None (no retry candidate) when _try_real fails, and have the merger keep the original line untouched plus a warning 'trocr_retry_unavailable'. Remove MockTrocrEngine/MockTesseractEngine/MockPaddleEngine/HybridMockEngine and the ENGINES registry from backend/app/services/ocr_service.py, or restrict them behind a test-only import that the API cannot reach (see D1-07). Never emit an engine label for text a given engine did not produce, and never synthesise a confidence value.
- **Effort:** M  ·  **Files:** backend/app/services/pipeline.py, backend/app/services/ocr_service.py

#### `D1-06` — OCR pipeline & engines  ·  _major_

- **Spec ref (B4 Step 1):** B4 Step 1: "Select the OCR engine using radio buttons" with choices TrOCR / Google Vision / Tesseract
- **As-built:** There is no engine selector in the UI. AnalyzerPage hardcodes engine: 'pipeline' on the only OCR request it makes; a repo-wide grep of frontend/src finds no RadioGroup or <Radio> for engine choice (the only ToggleButtonGroup is a line-filter in OcrConflictPanel, and the only engine list in ResearchEvaluationPanel is a static non-interactive grid of labels). The API does accept an engine parameter, but its allowed set is `pipeline|mock|paddleocr|tesseract|trocr|hybrid` — 'google_vision', the engine that actually runs, is not even a legal value — and every non-'pipeline' value is routed to the MOCK adapters rather than to run_ocr_stack. So the pharmacist cannot select an engine, and the only selectable engine names return synthetic text.
- **Research/DQ impact:** B4's approved Step 1 interaction cannot be demonstrated or screenshotted. It also removes the manual mechanism a reviewer would use to obtain per-engine outputs on the same image for DQ1, compounding D1-03 and D1-08.
- **Why major:** An explicit approved UI requirement (B4 Step 1 radio buttons over three named engines) is entirely absent from the frontend, and the residual server-side selection capability is worse than absent: it exposes three spec-named engine identifiers that all return labelled synthetic prescriptions and omits the one engine that really runs. Not critical because O1/DQ1 could in principle still be evidenced by a fixed pipeline, but the specified pharmacist control does not exist.
- **Evidence:**
    - frontend/src/pages/AnalyzerPage.tsx:236 — engine: 'pipeline' (hardcoded in the POST body to /api/v1/ocr/{id}/run-async)
    - frontend/src/pages/AnalyzerPage.tsx:598-601 — the only OCR control is a single 'Run OCR pipeline' / 'Upload & run pipeline' button
    - frontend/src/components/ResearchEvaluationPanel.tsx:419-434 — static array of [id,label,role] rendered as read-only Boxes, no onChange/selection
    - frontend/src/components/OcrConflictPanel.tsx:133-144 — the only ToggleButtonGroup is attention/conflict/all line filtering
    - backend/app/schemas/prescription.py:19-22 — engine: str = Field(default="pipeline", pattern="^(pipeline|mock|paddleocr|tesseract|trocr|hybrid)$") — no google_vision
    - backend/app/services/prescription_service.py:226-236 — run_session_ocr: if engine == "pipeline" -> real pipeline; otherwise result = run_ocr(engine, image_bytes)
- **→ Conformance enhancement:** Add a MUI RadioGroup to Step 1 of frontend/src/pages/AnalyzerPage.tsx with values trocr / google_vision / tesseract, defaulting to trocr, and send the selection instead of the hardcoded 'pipeline' at line 236. Extend backend/app/schemas/prescription.py:19-22 to `^(pipeline|trocr|google_vision|tesseract)$`, and change backend/app/services/prescription_service.py:226-236 so a named engine runs that engine through the real stack (run_ocr_stack with a per-request engine override) instead of app.services.ocr_service.run_ocr. Persist the chosen engine in ReviewSession.selected_ocr_engine rather than the literal 'pipeline'.
- **Effort:** M  ·  **Files:** frontend/src/pages/AnalyzerPage.tsx, backend/app/schemas/prescription.py, backend/app/services/prescription_service.py, backend/app/services/ocr/engines.py

#### `D1-07` — OCR pipeline & engines  ·  _major_

- **Spec ref (O1 / A8 / B1 / DQ1):** O1 / A8 / B1 name three real engines (TrOCR, Google Cloud Vision, Tesseract). The approved spec contains no mock/synthetic OCR engine, and DQ1 requires that measured text originate from a real engine.
- **As-built:** A MOCK OCR engine is enabled by default and its kill-switch cannot switch it off in development. run_ocr_stack falls back to a fixed 4-drug synthetic prescription whenever every configured engine fails, guarded by `if settings.OCR_ALLOW_MOCK_FALLBACK or settings.APP_ENV == "development"` — the OR means setting OCR_ALLOW_MOCK_FALLBACK=false still yields mock output while APP_ENV=development, which is exactly the shipped .env. The mock text is crafted to parse cleanly into four medicines (including a deliberate 'Arcabose' misspelling), so it flows through the parser, formulary validation and HITL tables like a real extraction. On the audited machine the fallback is easy to reach: TrOCR is unavailable (D1-02) and Tesseract is unavailable (D1-11), so a single Vision failure lands on MOCK. There are real mitigations, but also a residual leak: PipelineResult.is_mock is an AND-collapse across medicines, so one non-mock candidate line flips the whole job to non-mock, and analytics/compute.py computes CER/WER with no is_mock check at all.
- **Research/DQ impact:** Threatens the integrity of every OCR-derived figure (DQ1 WER/CER, HITL correction rates for O2): a run that silently degraded to MOCK produces a clean, plausible four-medicine extraction. Because the mock text is fixed, aggregate statistics contaminated by it would be systematically biased rather than noisy.
- **Why major:** A synthetic engine that is not in the approved spec is the default terminal fallback, is reachable in one engine failure on this machine, and its documented disable flag is defeated by an OR with APP_ENV=development. The labelling and Confirm-gate mitigations are genuine and well built, which keeps this out of critical, but the AND-collapsed is_mock propagation and the unguarded analytics CER/WER path leave a real route for synthetic text to reach research figures.
- **Evidence:**
    - backend/app/services/ocr/engines.py:592-604 — `if settings.OCR_ALLOW_MOCK_FALLBACK or settings.APP_ENV == "development": … return mock` else RuntimeError
    - backend/app/core/config.py:67 — OCR_ALLOW_MOCK_FALLBACK: bool = True
    - .env:2 — APP_ENV=development ; .env:38 — OCR_ALLOW_MOCK_FALLBACK=true
    - docker-compose.yml:40 — OCR_ALLOW_MOCK_FALLBACK: "true"
    - backend/app/services/ocr/engines.py:49-78 — _mock_document: fixed 15-line synthetic Rx, 4 drugs, engine_primary="mock"
    - backend/app/services/pipeline.py:1587 — is_mock = ocr.is_mock and (not medicines or all(m.is_mock for m in medicines))  (AND-collapse)
- **→ Conformance enhancement:** Make the flag authoritative: change backend/app/services/ocr/engines.py:593 from `OCR_ALLOW_MOCK_FALLBACK or APP_ENV == "development"` to `OCR_ALLOW_MOCK_FALLBACK` alone, and flip the default to False in backend/app/core/config.py:67, .env:38 and docker-compose.yml:40 so the RuntimeError path is the default. Change pipeline.py:1587 from AND to OR (`is_mock = ocr.is_mock or any(m.is_mock for m in medicines)`) so mock never gets cleared by a single real line. Add an is_mock guard in backend/app/services/analytics/compute.py:430 that emits availability='MOCK_OCR_EXCLUDED' instead of CER/WER values for mock sessions.
- **Effort:** S  ·  **Files:** backend/app/services/ocr/engines.py, backend/app/core/config.py, .env, docker-compose.yml, backend/app/services/pipeline.py, backend/app/services/analytics/compute.py

#### `D1-08` — OCR pipeline & engines  ·  _major_

- **Spec ref (DQ1 / B1 / O6):** DQ1 requires per-engine WER/CER for TrOCR specifically; B1 traces the OCR Multi-Engine Module to DQ1, which presupposes engine-attributable output
- **As-built:** The production path destroys engine attribution before persistence. run_ocr_stack does build a per-engine EngineAttempt list and attach it to the result, but PipelineResult has no engine_attempts field, so those attempts are dropped in PrescriptionPipeline.run and never reach the database. What is persisted instead is the literal string 'pipeline' in both OcrJob.engine and ReviewSession.selected_ocr_engine, so no stored row ever records that Google Vision (or TrOCR, or Tesseract) produced the text. PrescriptionMedicine stores only parser_confidence — there are no per-field engine or per-field OCR-confidence columns. Line-level engine labels do survive inside pipeline_json, but they are the labels D1-04 shows can be falsified, and the analytics layer reads the pre-merge line list as `paddle_lines` and reports it as the 'raw OCR' arm for raw_cer/raw_wer even though PaddleOcrAdapter is instantiated and never called — those lines actually come from whichever engine run_ocr_stack selected.
- **Research/DQ impact:** DQ1 cannot be evidenced from real usage: no query over the database can separate TrOCR from Vision from Tesseract performance. The Summary Analytics raw_cer/raw_wer figures are attributed to PaddleOCR in name while actually measuring the selected engine, so any table reproducing them would misstate the engine under test.
- **Why major:** The evidence substrate DQ1 needs — which engine produced which field, at what confidence — is generated in memory and then discarded, and the one persisted engine field is a constant. A defensible per-engine WER/CER claim cannot be reconstructed from stored production data even after the configuration is corrected. Compounded by the mislabelled 'paddle_lines' arm, which attributes the raw-stage error rate to an engine that never ran.
- **Evidence:**
    - backend/app/services/ocr/engines.py:632 — selected_doc.engine_attempts = [a.to_dict() for a in attempts]
    - backend/app/services/pipeline.py:87-105 — PipelineResult dataclass: no engine_attempts field; to_json serialises only these fields
    - backend/app/services/pipeline.py:1595-1602 — PipelineResult(...) constructed without ocr.engine_attempts
    - backend/app/services/prescription_service.py:191 — OcrJob(engine="pipeline", ...)
    - backend/app/services/prescription_service.py:205 — job.engine = "pipeline"
    - backend/app/services/prescription_service.py:91 and 217 — session.selected_ocr_engine = "pipeline"
- **→ Conformance enhancement:** Add `engine_attempts: list[dict]` to PipelineResult (backend/app/services/pipeline.py:87-105), populate it from ocr.engine_attempts at pipeline.py:1595, and persist it (it will serialise into pipeline_json via to_json). Set OcrJob.engine and ReviewSession.selected_ocr_engine to the real selected engine (ocr.selected_engine) instead of "pipeline" at prescription_service.py:191, 205, 91, 217. Add nullable per-field provenance columns to PrescriptionMedicine (e.g. ai_<field>_engine, ai_<field>_confidence) with an Alembic migration, populated from the merged line that produced each field. Rename the pipeline_json key `paddle_lines` to `primary_engine_lines` and update backend/app/services/analytics/compute.py:429-436 to label that arm with the actual engine id.
- **Effort:** L  ·  **Files:** backend/app/services/pipeline.py, backend/app/services/prescription_service.py, backend/app/models/prescription.py, backend/alembic/versions (new migration), backend/app/services/analytics/compute.py

#### `A8/B1/B4` — HITL workflow & platform  ·  _major_

- **Spec ref (A8 / B1 / B4):** A8: 'HITL Verification | Streamlit-based pharmacist review layer'. B1: 'HITL Verification Interface | Streamlit st.form, st.selectbox (reactive)'. B4: 'The prototype interface is structured as a two-page Streamlit application.'
- **As-built:** The entire HITL interface is a React 19 + MUI 7 single-page app served by a FastAPI backend. There is no Streamlit anywhere in the new project (only in docs PDF extract and the _reference-old-project). No st.form / st.selectbox / st.radio exist. The app is also NOT two pages: it exposes 11 role-based React pages (Home, Login, Register, RegistrationStatus, AdminPortal, AdminRegistrations, Analyzer, CatalogExplorer, ReviewerDashboard, ChangePassword, ForgotPassword) with router gating by role.
- **Research/DQ impact:** O2 ('human-in-the-loop validation interface') and DQ1 ('pharmacist-verified drug query'): the HITL claim survives but cannot be evidenced as a Streamlit artefact; any thesis claim tied to Streamlit st.form/st.selectbox or a two-page Streamlit app is unsupportable and must be reworded to a React/FastAPI HITL.
- **Why major:** The approved implementation technology named in three separate spec clauses (A8/B1/B4) is entirely absent and replaced by a different stack; the 'two-page Streamlit application' design decision is fully contradicted. Rated major rather than critical because the substantive research objective O2 (a HITL review/correction/confirm interface) is still delivered and evidenceable via the React cascade — only the named technology and the two-page structure are invalidated. The project docs (specification_manifest.json, specification_traceability_matrix.md R27) themselves record this as a documented conflict.
- **Evidence:**
    - frontend/package.json:react ^19.1.0, @mui/material ^7.0.2 (dependencies block)
    - frontend/src/pages/AnalyzerPage.tsx:15 imports VerificationTable (MUI Table cascade, not Streamlit)
    - frontend/src/components/VerificationTable.tsx:1-27 (MUI Autocomplete/Select HITL, not st.selectbox)
    - frontend/src/App.tsx:5-14 (11 page imports) and :78-205 (role-gated routes)
    - backend/app/api/v1/clinical.py:1-20 (FastAPI router serves the HITL endpoints)
    - grep for 'streamlit' across new/ (excl _reference-old-project, node_modules, .venv): only docs/_pdf_eval_extract.txt
- **→ Conformance enhancement:** Either (a) re-implement the HITL review layer as the approved two-page Streamlit application (st.form + reactive st.selectbox cascade) mirroring the current FastAPI HITL endpoints, or (b) obtain a formal, dated spec amendment (Design Science modification register) reclassifying A8/B1/B4 UI technology to React+FastAPI before the artefact is submitted against the approved spec. Do not silently rely on the docs' self-declared 'improvement'.
- **Effort:** XL  ·  **Files:** frontend/src/pages/AnalyzerPage.tsx, frontend/src/components/VerificationTable.tsx, docs/specification_traceability_matrix.md
- **Verifier correction:** Core deviation is real and correctly severed: verified React ^19.1.0 / react-dom ^19.1.0 / @mui/material ^7.0.2 (frontend/package.json), no 'streamlit' anywhere in code — grep across new/ (excl _reference-old-project) returns only docs/_pdf_eval_extract.txt (lines 147,208,375,414,421,580); no st.form/st.selectbox/st.radio anywhere; streamlit NOT in any requirements*.txt and NOT installed in backend/.venv/Lib/site-packages; HITL served by FastAPI (clinical.py, prescriptions.py, therapeutic_alternatives.py). Spec wording confirmed verbatim at _pdf_eval_extract.txt:421 (Streamlit st.form/st.selectbox) and :580 (two-page Streamlit application). Major (not critical) is fair because O2's HITL review/correct/confirm substance is still evidenceable via the React cascade. CORRECTION to the as-built evidence: the bullet 'App.tsx:5-14 (11 page imports)' is inaccurate — App.tsx lines 5-14 import 10 page components (Home, Login, Register, RegistrationStatus, AdminPortal, Analyzer, CatalogExplorer, ReviewerDashboard, ChangePassword, ForgotPassword; line 4 is AppShell, a component). AdminRegistrationsPage.tsx exists as a file but is NOT a routed top-level page — /admin/registrations merely redirects to /admin?tab=registrations (App.tsx:132-141). Role-gated routes span App.tsx:73-194, not :78-205. These evidence slips do not affect the deviation or its major severity.

#### `B1 Use Case 2 (Direct Drug Search)` — HITL workflow & platform  ·  _major_

- **Spec ref (B1 Use Cases (Fig 3)):** B1 Use Case 2: 'Direct Drug Search - Pharmacist manually selects a drug from the DrugBank ingredient dropdown and confirms or rejects the selected drug (HITL validation)'; system 'validates the pharmacist-confirmed drug selection, searches the database, and generates recommendation results with traceable provenance information'.
- **As-built:** No such analysis entry point exists. CatalogExplorerPage is a read-only lookup: it searches the catalog and displays strengths/forms/routes/indications, but it never confirms/rejects a drug and never generates recommendation results — its only action toward analysis is an 'Open Analyzer' link. The Analyzer requires an image upload to create a ReviewSession (upload endpoint is File(...) mandatory), and therapeutic-alternatives/evaluate requires an existing image-derived session plus pharmacist-confirmed medicines. There is no image-free path from a directly selected DrugBank ingredient to recommendations.
- **Research/DQ impact:** B1 use-case coverage and O2: the 'Direct Drug Search' HITL-validation path (and its traceable-provenance recommendations) is unevidenceable; only Use Case 1 (image-based) and Use Case 3 (evaluation dashboard) can be demonstrated.
- **Why major:** One of the three approved use cases cannot be exercised as specified: a pharmacist cannot start an analysis or obtain recommendation results by directly selecting/confirming a drug — an image upload is mandatory. The specified direct-search-to-recommendation mechanism is replaced by a read-only browser. Not critical because the image-based path still evidences O2/DQ1, so the overall HITL claim is partially supportable; but a headline use case is missing.
- **Evidence:**
    - frontend/src/pages/CatalogExplorerPage.tsx:88-105 (lookup only) and :206-211 (Lookup + 'Open Analyzer' link; no confirm/reject, no evaluate call)
    - frontend/src/pages/CatalogExplorerPage.tsx:134-137 ('Use this to verify ... before HITL confirmation in the Analyzer' — explicitly not an analysis path)
    - backend/app/api/v1/prescriptions.py:22-33 (upload requires file: UploadFile = File(...); session created only from upload)
    - backend/app/api/v1/therapeutic_alternatives.py:84-86 (evaluate requires an existing owned ReviewSession) and :121-125 (requires pharmacist-confirmed medicines)
- **→ Conformance enhancement:** Add a direct-search entry point that lets the pharmacist pick a DrugBank ingredient from the dropdown, confirm/reject it, create an image-free (or synthetic) ReviewSession + confirmed PrescriptionMedicine, and call /therapeutic-alternatives/evaluate to produce provenance-tagged recommendations from CatalogExplorerPage.
- **Effort:** L  ·  **Files:** frontend/src/pages/CatalogExplorerPage.tsx, backend/app/api/v1/prescriptions.py, backend/app/services/prescription_service.py

#### `D3-03` — Recommendation / therapeutic matching  ·  _major_

> **O3/U5 status — updated (the As-built below is now HISTORICAL).** DQ2's `rules_plus_mcs` no longer
> uses the `same_active_moiety` flag: `run_dq2_recommendation_evaluation` now calls real
> `compute_mcs_similarity` (rdFMCS atom coverage over catalogue SMILES) per (reference, candidate) pair,
> cached. **Nuance (found in validation):** re-ordering pharmacist-valid candidates by coverage does not
> change P@K/R@K (valids always rank first; those metrics are set-membership over top-K), so the MCS
> effect is reported as a **distinct `mean_mcs_atom_coverage`** metric on `rules_plus_mcs` (a
> `metric_envelope`; `NOT_CALCULATED` on `rules_only`). So DQ2 now genuinely exercises RDKit MCS, but its
> *quantitative* contribution is the coverage metric, not P@K/R@K. The As-built text and line refs below
> predate this change.

- **Spec ref (DQ2):** DQ2: 'How effectively does RDKit MCS identify therapeutically equivalent generic medicines? (Precision@K & Recall@K)'.
- **As-built:** The DQ2 evaluation compares two conditions 'rules_only' vs 'rules_plus_mcs', but the 'rules_plus_mcs' condition does not invoke RDKit MCS at all. It re-ranks gold-standard rows using a stored boolean flag RecommendationGoldStandard.same_active_moiety as a proxy 'MCS rank boost'. No atom coverage, no rdFMCS, no SMILES are involved in the metric. Precision/Recall functions themselves are correct, but the 'MCS' condition is a name/flag simulation.
- **Research/DQ impact:** DQ2 answer is not evidenced by RDKit MCS. Any Precision@K/Recall@K delta between conditions reflects the same_active_moiety label, not chemical MCS, so the causal claim about MCS is unsupported.
- **Why major:** The DQ2 headline comparison purports to quantify RDKit MCS effectiveness but substitutes a name-derived same_active_moiety flag for the MCS computation, so the reported 'rules_plus_mcs' Precision@K/Recall@K does not attribute anything to RDKit MCS. The DQ can be reported only with a substantial caveat.
- **Evidence:**
    - backend/app/services/research_eval/service.py:219-232 (build_per_case uses use_mcs_rank_boost and x.same_active_moiety flag, not rdkit)
    - backend/app/services/research_eval/service.py:246-247 (rules_only vs rules_mcs built from the same flag)
    - backend/app/services/research_eval/service.py:275-280 ('rules_plus_mcs' reported as the MCS condition)
    - backend/app/services/research_eval/ranking_metrics.py:8-30 (precision/recall are correct but MCS-agnostic)
- **→ Conformance enhancement:** In run_dq2_recommendation_evaluation, drive the 'rules_plus_mcs' condition from an actual compute_mcs_similarity(atom_coverage>=0.9) result per candidate (requires SMILES for gold candidates and rdkit installed) rather than the same_active_moiety boolean; store the MCS atom_coverage on the gold-standard/evaluation record so the metric is reproducible.
- **Effort:** M  ·  **Files:** backend/app/services/research_eval/service.py

#### `D3-04` — Recommendation / therapeutic matching  ·  _major_

- **Spec ref (A8 / A10 / O3):** A8/A10/O3 imply RDKit MCS over molecular structures to identify base molecules across salt/ester variants (SMILES needed for source and candidate salt forms).
- **As-built:** The SQLite catalogue that supplies candidates carries NO chemical structure at all: no smiles/structure/inchi/mol column exists in any table (medicines, products, strengths, aliases, label_sections, label_dose_options, label_frequency_options, meta). SMILES come only from a hardcoded 10-entry seed of BASE ingredients (ibuprofen, naproxen, diclofenac, aspirin, acetaminophen, amoxicillin, cetirizine, loratadine, omeprazole, pantoprazole). No salt-form SMILES are seeded and the name lookup keys are base names only, so a salt-form candidate (e.g. 'cetirizine hydrochloride') resolves to the base SMILES if at all — making the MCS across salt/ester variants (the exact A10 rationale) structurally trivial or impossible for anything outside the 10-drug demo set.
- **Research/DQ impact:** O3/DQ2 generalisability collapses to ~10 seeded base ingredients; the salt/ester robustness claim from A10 is unevidenced because salt-form structures are absent from both the catalogue and the seed.
- **Why major:** Even if rdkit were installed, MCS could only run for a 10-drug demo subset of base ingredients and cannot distinguish salt/ester variants (no salt SMILES). The very capability A10 claims MCS provides — matching base molecules across salt variants — is not backed by data, so O3/DQ2 are only demo-supportable.
- **Evidence:**
    - data/medicine_catalog.sqlite3 schema (queried read-only): tables aliases, label_dose_options, label_frequency_options, label_sections, medicines, meta, products, strengths — no smiles/structure/inchi/mol column in any of them
    - medicines columns = id, canonical_name, canonical_key, drugbank_id, product_ndc, dosage_forms, routes, sources, indication, spl_set_id (no structure column)
    - backend/app/services/therapeutic/smiles_seed.py:9-36 (only 10 base-ingredient SMILES; BY_NAME keys are base names only, no salt forms)
    - backend/app/services/therapeutic/mcs.py:77-83 (status 'no_smiles' when either side unseeded — 'MCS applies to the seeded DrugBank subset (Spec O3 demo path)')
- **→ Conformance enhancement:** Add a smiles (and optionally inchikey) column to the medicines table and populate it from DrugBank structures during catalogue build; extend smiles_seed or resolve_smiles to fetch salt-form SMILES; then MCS can actually compare source vs salt/ester candidate structures across the full catalogue.
- **Effort:** XL  ·  **Files:** data/medicine_catalog.sqlite3 (build script), backend/app/services/therapeutic/smiles_seed.py, backend/app/services/therapeutic/mcs.py

#### `D3-05` — Recommendation / therapeutic matching  ·  _major_

- **Spec ref (A8 / A12 stack):** A8 IT Artefact, Recommendation Engine: 'NetworkX DiGraph + RDKit MCS'.
- **As-built:** There is no NetworkX graph in the recommendation engine. networkx is not imported anywhere in backend/app, is not declared in any requirements*.txt, and is not installed in backend/.venv. Candidate retrieval is plain SQL 'canonical_name LIKE %term%' over salt-map surface forms, with in-Python moiety comparison — no graph structure, nodes, or edges.
- **Research/DQ impact:** O3 architecture claim (graph-based salt/ingredient/product relationships) is not evidenced; the artefact's described data model differs from what runs.
- **Why major:** A8 names 'NetworkX DiGraph' as half of the engine's data structure and A12 lists it in the stack. It is entirely absent; the retrieval mechanism is a materially different SQL substring search. The engine architecture claim is only partially supportable.
- **Evidence:**
    - grep 'networkx|DiGraph|isomorph|vf2' across backend/app returns no matches
    - networkx absent from all backend/requirements*.txt and from backend/.venv/Lib/site-packages
    - backend/app/services/therapeutic/product_candidates.py:47-66 (candidate search is SQL LIKE over name tokens, not a graph traversal)
    - backend/app/services/therapeutic/salt_normalisation.py:12-56 (salt relations held in a plain dict, not a NetworkX DiGraph)
- **→ Conformance enhancement:** Either implement the ingredient→salt→product relationships as a NetworkX DiGraph used by product_candidates retrieval (to match A8), or, if SQL is intentionally the design, submit a documented approved-change amendment; do not leave A8/A12 asserting NetworkX while none exists.
- **Effort:** L  ·  **Files:** backend/app/services/therapeutic/product_candidates.py, backend/app/services/therapeutic/salt_normalisation.py, backend/requirements.txt

#### `D3-06` — Recommendation / therapeutic matching  ·  _major_

- **Spec ref (A8 / B2):** A8/B2: 'threshold >=70'; 'Candidates with Score < 70 are excluded.'
- **As-built:** There is no >=70 score threshold in the recommendation path. Eligibility is decided purely by mandatory hard filters + safety screening; surviving candidates are ranked by total_score and truncated to top_n with no minimum-score cutoff applied. The only '70' in the therapeutic package is an unrelated fuzzy name-match min_score in catalog_therapeutic.py.
- **Research/DQ impact:** O3/DQ2: precision claims that assume a 70-point quality floor are not backed; returned candidate quality is governed only by hard filters, not the approved score cutoff.
- **Why major:** A named approved threshold (Score < 70 excluded) is absent from the scoring/ranking path, so the claim that only >=70 candidates are surfaced is unsupportable; low-scoring candidates can be returned.
- **Evidence:**
    - backend/app/services/therapeutic/evaluate.py:306-320 (eligibility = mandatory filters only), :450-454 (sort then [:top_n], no score floor)
    - backend/app/services/therapeutic/evaluate.py:573-602 (therapeutic path sorts and truncates; no >=70 gate)
    - grep '70' in backend/app/services/therapeutic returns only catalog_therapeutic.py:90 min_score=70.0 (fuzzy NAME match, not the recommendation score)
- **→ Conformance enhancement:** After computing the spec-conformant weighted score (see D3-01), drop candidates with score < 70 before ranking/truncation in evaluate._evaluate_one; expose the threshold as a config constant.
- **Effort:** S  ·  **Files:** backend/app/services/therapeutic/evaluate.py

#### `D3-10` — Recommendation / therapeutic matching  ·  _major_

- **Spec ref (O3 / A10):** O3/A10: salt-awareness achieved via RDKit MCS identifying base molecules across salt/ester variants (chemical basis).
- **As-built:** Salt-awareness is implemented by a curated, name-based salt/base surface-form map covering only 16 base ingredients, plus token-strip heuristics and confidence thresholds. same_active_moiety() decides salt equivalence purely from normalised name strings; the chemical structure (MCS) plays no part in the eligibility decision. Anything outside the 16-ingredient map falls to a low-confidence 'passthrough' that fails the moiety gate.
- **Research/DQ impact:** O3: salt-awareness is demonstrable only for 16 curated ingredients and by string matching, not by the approved chemical MCS mechanism; the robustness claim of A10 (base molecule across salt/ester variants) is not achieved chemically.
- **Why major:** O3's salt-awareness and A10's approved rationale rest on RDKit MCS over molecular structure; the code instead uses a hand-curated 16-ingredient name map. The mechanism is materially different and its coverage is narrow, so the 'salt-aware via MCS' claim is only partially supportable.
- **Evidence:**
    - backend/app/services/therapeutic/salt_normalisation.py:12-56 (_MOIETY_FORMS: 16 ingredients only)
    - backend/app/services/therapeutic/salt_normalisation.py:180-202 (same_active_moiety compares base_ingredient strings + confidence, no structure)
    - backend/app/services/therapeutic/mandatory_filters.py:88-93 (moiety gate driven entirely by same_active_moiety name result)
    - backend/app/services/therapeutic/product_candidates.py:78-83 (candidate accepted iff resolve_moiety base name matches)
- **→ Conformance enhancement:** Make MCS atom-coverage the (or a mandatory) determinant of same-moiety eligibility once SMILES are populated (D3-04) and rdkit installed (D3-02); retain the curated name map only as a fast pre-filter/fallback, and expand its coverage or derive it from DrugBank salt records rather than a 16-entry hardcode.
- **Effort:** L  ·  **Files:** backend/app/services/therapeutic/salt_normalisation.py, backend/app/services/therapeutic/mandatory_filters.py, backend/app/services/therapeutic/mcs.py

#### `D4-02` — Knowledge graph / catalogue  ·  _major_

- **Spec ref (B2 Knowledge Graph Schema):** B2 Knowledge Graph Schema: six node types (Ingredient, Salt Form, NDC Product, Strength, Route, Dosage Form) and five edges (HAS_SALT: Ingredient->Salt Form; IS_ACTIVE_IN: Salt Form->NDC Product; HAS_STRENGTH; HAS_ROUTE; HAS_DOSAGE_FORM).
- **As-built:** The six nodes / five edges are flattened into relational columns and inferred at query time. Ingredient -> `medicines` row; NDC Product -> `products` row (products.medicine_id FK collapses Ingredient->Product directly). Strength/Route/DosageForm are NOT nodes - they are inline text columns on products (products.strength/route/dosage_form) plus JSON blobs on medicines.dosage_forms/routes. Critically the Salt Form node and the HAS_SALT edge are LOST: there is no salt-form table or column; salt names are dissolved into the flat `aliases` strings. So IS_ACTIVE_IN (Salt Form->Product) collapses to Ingredient->Product, and HAS_SALT has no representation.
- **Research/DQ impact:** Weakens the B2 'salt-aware knowledge graph' methodology claim: the Ingredient->SaltForm->Product hierarchy that justifies salt-aware equivalence is not stored, so the recommendation-engine objective can only be defended with heavy caveats about a flat catalogue plus an external map.
- **Why major:** The graph schema is materially replaced by a relational one and the salt-aware backbone (Salt Form node + HAS_SALT edge) has no persisted representation, so the 'salt-aware graph' claim survives only in reworded form (a query-time salt map, not a graph). Strength/Route/Form as attributes rather than shared nodes also means the graph's shared-node semantics (many products pointing to one Strength node) are not preserved.
- **Evidence:**
    - backend/app/services/datasets/build_index.py:112-148 (medicines / aliases / strengths / products tables; products has strength,dosage_form,route as columns, medicine_id FK)
    - live schema dump: tables = aliases, label_dose_options, label_frequency_options, label_sections, medicines, meta, products, strengths; schema keyword scan salt/smiles/inchi/ingredient/saltform/moiety -> all False
    - backend/app/services/datasets/build_index.py:299-306 (salt/synonym surface forms inserted into `aliases`, not a salt-form node)
- **→ Conformance enhancement:** Add a persisted salt-form layer: a `salt_forms` table (or graph nodes) linking Ingredient(medicine) -HAS_SALT-> SaltForm -IS_ACTIVE_IN-> Product, populated from DrugBank <salts>; represent Strength/Route/DosageForm as first-class shared nodes (or normalise into lookup tables) so the five spec edges are explicit rather than inferred from LIKE queries.
- **Effort:** L  ·  **Files:** backend/app/services/datasets/build_index.py, backend/app/services/datasets/catalog_store.py

#### `D4-03` — Knowledge graph / catalogue  ·  _major_

- **Spec ref (B1 / B2 (salt-aware traversal)):** 'Salt-aware knowledge graph' where salt/base relationships derive from the DrugBank-sourced Salt Form nodes and are traversed by the recommendation engine (A8/B1/B2).
- **As-built:** Salt-awareness is a hardcoded curated Python dictionary `_MOIETY_FORMS` of ~16 base ingredients (cetirizine, amlodipine, diclofenac, metformin, omeprazole, pantoprazole, ibuprofen, naproxen, loratadine, paracetamol/acetaminophen, amoxicillin, sertraline, fluoxetine, losartan, atorvastatin) plus a fixed `_SALT_TOKENS` list. Candidate retrieval is a SQL `LIKE '%term%'` substring search over medicines.canonical_name, not graph traversal; graph functions find_products/find_equivalent_salts do not exist in the new app.
- **Research/DQ impact:** The recommendation/therapeutic-equivalence objective (A8/B1) is demonstrable only for the ~16 curated moieties; for the rest the system falls back to fragile substring matching, so quantitative claims about salt-aware equivalence coverage are not defensible.
- **Why major:** The specified salt-aware graph mechanism is replaced by a materially different one: a ~16-drug hand-maintained lookup covering a tiny fraction of the 41,020 catalogue medicines, plus substring SQL. The salt-aware equivalence claim is only partially supportable and does not scale from the data as the spec implies.
- **Evidence:**
    - backend/app/services/therapeutic/salt_normalisation.py:12-56 (16-entry _MOIETY_FORMS hardcode), :64-96 (_SALT_TOKENS)
    - backend/app/services/therapeutic/product_candidates.py:39-58 (builds LIKE terms from _MOIETY_FORMS and runs `WHERE lower(canonical_name) LIKE ?`)
    - grep find_products|find_equivalent_salts over backend/app -> No matches
- **→ Conformance enhancement:** Derive salt/base relationships from ingested DrugBank <salts> into graph edges (HAS_SALT/IS_ACTIVE_IN) and traverse them in product_candidates.py; retire the hardcoded _MOIETY_FORMS map (or reduce it to a small override list), replacing the LIKE search with graph/relational joins over the salt-form layer.
- **Effort:** L  ·  **Files:** backend/app/services/therapeutic/salt_normalisation.py, backend/app/services/therapeutic/product_candidates.py, backend/app/services/datasets/build_index.py

#### `D4-04` — Knowledge graph / catalogue  ·  _major_

- **Spec ref (A11 / B2 / Section 15 (data sources)):** DrugBank XML contributes ingredients/salts (and, per B2, is the source for Salt Form nodes / API ingredient list); Section 15 data sources cite DrugBank for chemical/salt data.
- **As-built:** DrugBank ingestion (ingest_drugbank) extracts only: primary drugbank-id, name+synonyms+product names (-> flat aliases), product strength/dosage-form/route, indication, and a few free-text diligence sections (pharmacodynamics, mechanism_of_action, toxicity). It never parses the DrugBank <salts> element, nor <calculated-properties>/<experimental-properties> (SMILES/InChI). Verified: no salt/smiles/inchi columns exist and the parser has no such lookups. drugbank_id IS captured (4,952 of 41,020 medicines).
- **Research/DQ impact:** The claim that Salt Form nodes and salt-aware equivalence derive from DrugBank is unsupported; combined with D4-03 the salt logic rests on a manual map, not DrugBank, weakening the data-provenance argument for the recommendation objective.
- **Why major:** DrugBank contributes identity (drugbank_id) and product attributes, but the specific DrugBank data the salt-aware graph is supposed to be built from - salt variants and chemical structure - is not ingested at all. The 'OpenFDA + DrugBank salt-aware' claim is therefore only partially backed by DrugBank.
- **Evidence:**
    - backend/app/services/datasets/build_index.py:445-548 (parses name/synonyms/products/indication/pharmacodynamics/mechanism-of-action/toxicity only)
    - grep -i salts|smiles|inchi|calculated-propert|experimental-propert over build_index.py -> No matches
    - SQLite query: medicines with non-empty drugbank_id = 4952 / total 41020; meta.stats drugbank=4953
    - schema keyword scan for salt/smiles/inchi -> all False
- **→ Conformance enhancement:** Extend ingest_drugbank to parse <salts><salt> (name, drugbank-id, cas, inchikey) and <calculated-properties> SMILES/InChI, persist them (new salt_forms table / columns), and wire them into the salt-aware traversal so DrugBank genuinely sources the Salt Form nodes.
- **Effort:** M  ·  **Files:** backend/app/services/datasets/build_index.py
- **Verifier correction:** The literal claims all hold: ingest_drugbank (build_index.py:432-558; parsing body ~445-548) extracts only the primary drugbank-id, name+synonyms+product names (into aliases), per-product strength/dosage-form/route, indication, and pharmacodynamics/mechanism-of-action/toxicity free-text; grep salts|smiles|inchi|calculated-propert|experimental-propert over build_index.py = none; no salt/smiles/inchi columns exist; drugbank_id populated for 4,952/41,020 (meta.stats drugbank=4953). Correction needed only for completeness of the as-built description: chemical structure is NOT wholly absent from the codebase — a separate hand-curated 10-entry SMILES seed exists (smiles_seed.py:9-20, drugbank_id->canonical SMILES for ibuprofen/naproxen/diclofenac/aspirin/acetaminophen/amoxicillin/cetirizine/loratadine/omeprazole/pantoprazole) which feeds an optional RDKit MCS path (mcs.py:12,72-89; therapeutic/evaluate.py:78 'structure_source: smiles_seed+rdkit'), gated by RDKit that lives in requirements-spec-research.txt (optional, not installed by default). Crucially this seed is a manual dictionary, NOT parsed from the DrugBank XML, so it reinforces rather than weakens the deviation (DrugBank is not the structural/salt source). Severity 'major' is retained.

#### `D5-rag-02` — RAG & evidence retrieval  ·  _major_

- **Spec ref (A8 (RAG Framework), B1, B2):** A8 / B1 / B2: embeddings must be all-MiniLM-L6-v2 (384-dim sentence-transformer).
- **As-built:** No embedding model exists in the codebase. No SentenceTransformer/all-MiniLM/transformers usage anywhere in app code. The only vectorisation is a 64-dim MD5-hash bag-of-words in the flag-gated experimental retriever — not a MiniLM sentence embedding.
- **Research/DQ impact:** DQ3 (semantic agreement of drug explanations) — semantic/dense retrieval is impossible without an embedding model, so 'semantic agreement' cannot be measured against the approved embedding.
- **Why major:** The specifically named embedding technology (all-MiniLM-L6-v2) is absent and not installable from any requirements file, so the semantic-agreement claim in DQ3 has no MiniLM basis; part of the same O4/DQ3 mechanism as D5-rag-01 but a distinct named artefact.
- **Evidence:**
    - grep backend/app for SentenceTransformer|MiniLM|from sentence_transformers|IndexFlatL2|.encode( embeddings: no application matches (only byte .encode and JWT/hash)
    - backend/app/services/research_eval/evidence_retrievers.py:90-98 (_embed: 64-dim vector filled via hashlib.md5 token hashing — not MiniLM, not 384-dim)
    - backend/.venv/Lib/site-packages: sentence_transformers, transformers, torch all absent (only numpy present)
- **→ Conformance enhancement:** Add sentence-transformers (all-MiniLM-L6-v2) to requirements and install it; wire a cached SentenceTransformer encoder used by both index build and query embedding in rag_evidence.py.
- **Effort:** L  ·  **Files:** backend/requirements.txt, backend/app/services/therapeutic/rag_evidence.py, backend/app/services/datasets/build_index.py

#### `D5-rag-03` — RAG & evidence retrieval  ·  _major_

- **Spec ref (A8, B2 (RAG Pipeline), B4):** A8 / B2: Groq API (llama-3.3-70b-versatile, temp 0.0) produces an evidence-grounded narrative of 2-3 summary sentences followed by 4-6 evidence bullets citing only retrieved text.
- **As-built:** Groq generation is present but disabled by default (ENABLE_SPEC_GROQ=False) with an empty GROQ_API_KEY and no .env override, so in the current build maybe_groq_summarise always returns status='disabled' and no narrative is produced. The model id and temperature 0.0 are configured, but the prompt does not request the '2-3 sentences + 4-6 bullets' structure, and the frontend never renders the summary field.
- **Research/DQ impact:** O4 (explainability) and DQ3 (factual reliability of drug explanations) — with Groq off and unrendered, there is no LLM-generated explanation to evaluate, so the 'evidence-grounded drug explanation' deliverable is not demonstrable out of the box.
- **Why major:** The LLM explanation layer is inactive by default and its required output structure is not implemented, so O4 explainability via evidence-grounded LLM narrative and the B2/B4 narrative claim are only partially supportable; the mechanism exists but produces nothing in the default build.
- **Evidence:**
    - backend/app/core/config.py:45 (ENABLE_SPEC_GROQ: bool = False)
    - backend/app/core/config.py:47 (GROQ_API_KEY: str = "")
    - .env contains no GROQ/SPEC_GROQ keys (grep returned nothing) — defaults apply
    - backend/app/services/therapeutic/rag_evidence.py:145-151 (returns disabled when flag off)
    - backend/app/services/therapeutic/rag_evidence.py:167-171 (prompt: 'Summarise ONLY the following label excerpts' — no 2-3 sentence / 4-6 bullet instruction)
    - backend/app/services/therapeutic/rag_evidence.py:178-180,204 (model llama-3.3-70b-versatile, temperature 0.0 — correct)
- **→ Conformance enhancement:** Default ENABLE_SPEC_GROQ=True (or document a required .env), supply a key, rewrite the prompt in maybe_groq_summarise to require '2-3 summary sentences then 4-6 evidence bullets citing only retrieved text', and render rag_summary/source_rag_summary in TherapeuticAlternativesPanel as an 'FDA Evidence & Explanation' block.
- **Effort:** M  ·  **Files:** backend/app/core/config.py, backend/app/services/therapeutic/rag_evidence.py, frontend/src/components/TherapeuticAlternativesPanel.tsx, .env

#### `D5-rag-04` — RAG & evidence retrieval  ·  _major_

- **Spec ref (B2 (RAG Pipeline), C (Deliverables)):** B2: chunk SPL text at 512 tokens with 50-token overlap; C: OpenFDA RAG knowledge base of ~1.37M chunks, Complete.
- **As-built:** There is no chunking at all. build_index.py stores each whole SPL section clipped to 2,500 chars (16,000 for dosage_and_administration). No tokenizer, no 512-token windows, no 50-token overlap, no distance-threshold dedup. The corpus is 136,167 whole label-section rows, not ~1.37M chunks.
- **Research/DQ impact:** O4/DQ3 and Deliverable C — retrieval granularity and corpus size differ by an order of magnitude from the approved design; any factual-reliability claim rests on a different corpus than specified.
- **Why major:** The named chunking parameters (512/50) are absent and the corpus is ~136K clipped sections rather than the ~1.37M chunks claimed Complete in deliverable C, so the knowledge-base characterisation underpinning DQ3 is materially different.
- **Evidence:**
    - backend/app/services/datasets/build_index.py:34-36 (_SECTION_MAX=2500, _DOSAGE_ADMIN_MAX=16000)
    - backend/app/services/datasets/build_index.py:347-365 (_insert_section clips by char length; no tokenisation/overlap)
    - catalog meta stats (queried read-only): label_sections=136167, spl labels ingested=255904 — no 1.37M chunk artefact
    - grep: no token/chunk/overlap=50/512 logic in build_index.py
- **→ Conformance enhancement:** Add a token-based chunker (512 tokens, 50 overlap) in build_index.py that splits each SPL section into chunks, embeds each chunk, and stores chunk rows; regenerate the FAISS index and report the true chunk count in meta stats.
- **Effort:** L  ·  **Files:** backend/app/services/datasets/build_index.py, backend/app/services/datasets/catalog_store.py

#### `D5-rag-06` — RAG & evidence retrieval  ·  _major_

- **Spec ref (DQ3, A8):** DQ3: evidence the FAISS-based RAG framework via BERTScore & OpenFDA cross-validation.
- **As-built:** The DQ3 reviewer harness runs three conditions (none/keyword/faiss), but the 'faiss' condition is FAISSSPLRetriever behind RESEARCH_FAISS_ENABLED (default off) which, with faiss uninstalled, falls back to a 64-dim MD5-hash cosine; when faiss is present it builds IndexFlatIP (inner product), not IndexFlatL2. BERTScore is never computed (always None; ENABLE_BERTSCORE=False and bert-score uninstalled), and the DQ3 corpus defaults to two hardcoded demo SPL sentences, not OpenFDA.
- **Research/DQ impact:** DQ3 (semantic agreement + factual reliability via BERTScore & OpenFDA cross-validation) — none of the three named evaluation ingredients (real FAISS/MiniLM, BERTScore, OpenFDA corpus) is actually exercised, so DQ3 cannot be answered as specified.
- **Why major:** The DQ3 evidencing pipeline exists but cannot produce the specified evidence: its 'FAISS' arm is a hash-cosine/IndexFlatIP surrogate, BERTScore is never calculated, and the corpus is a 2-row demo, so the DQ3 result as approved is not obtainable.
- **Evidence:**
    - backend/app/services/research_eval/evidence_retrievers.py:81-88 (RESEARCH_FAISS_ENABLED gate; faiss import failure tolerated)
    - backend/app/services/research_eval/evidence_retrievers.py:104-110 (IndexFlatIP, not IndexFlatL2)
    - backend/app/services/research_eval/evidence_retrievers.py:90-98,136-156 (MD5-hash 64-dim cosine fallback)
    - backend/app/services/research_eval/service.py:290-305 (DQ3 default corpus = 2 hardcoded demo rows)
    - backend/app/services/research_eval/service.py:318-322 (bertscore_precision/recall/f1 hardcoded None)
    - backend/app/core/config.py:40 (ENABLE_BERTSCORE=False); requirements-bertscore.txt only; not installed in .venv
- **→ Conformance enhancement:** Point the DQ3 harness at the real OpenFDA chunk corpus, replace the hash-embedding FAISSSPLRetriever with the MiniLM+IndexFlatL2 retriever, enable BERTScore (install bert-score, ENABLE_BERTSCORE=True) and actually compute precision/recall/f1 in run_dq3_rag_evaluation.
- **Effort:** L  ·  **Files:** backend/app/services/research_eval/evidence_retrievers.py, backend/app/services/research_eval/service.py, backend/app/core/config.py, backend/requirements.txt

#### `A8 / A12 / O5 / DQ4 / C` — XAI / explainability  ·  _major_

- **Spec ref (A8 IT Artefact / A12 / B4):** A8: LIME (LimeTabularExplainer). A12 stack includes 'LIME'. O5: integrate SHAP and LIME. B4 LIME tab with 'LIME Local Explanation' chart and 'Local-model R² = 0.993' caption.
- **As-built:** The lime library and LimeTabularExplainer are used nowhere — grep for 'import lime|from lime|LimeTabularExplainer' across backend/app and frontend/src returns nothing. lime is not declared in requirements.txt or requirements-spec-research.txt. Both 'LIME' implementations are hand-rolled: feature_xai.explain_score_features just sorts components by contribution ('lime_style': True), and xai_conditions._lime_perturb runs 40 uniform random perturbations of the additive scoring function and returns per-feature least-squares slopes ('perturbation_lime_on_scoring_fn'). No local-model R² is computed.
- **Research/DQ impact:** O5's LIME integration cannot be evidenced at all, and DQ4's SHAP/LIME condition is missing its LIME half. The B4 'LIME Local Explanation' chart and 'Local-model R² = 0.993' figure cannot be produced from the artefact.
- **Why major:** A spec-named technology (LimeTabularExplainer / the lime library) is completely absent — not imported, not installed, and not even declared in any requirements file — and is replaced by a bespoke perturbation-correlation routine. The 'LIME' claim in O5/A8/A12 and the B4 LIME tab (including its R² caption) are unsupportable.
- **Evidence:**
    - backend/app/services/therapeutic/feature_xai.py:59
    - backend/app/services/research_eval/xai_conditions.py:48
    - backend/app/services/research_eval/xai_conditions.py:80
    - backend/requirements.txt:24
    - backend/requirements-spec-research.txt:1
- **→ Conformance enhancement:** Add lime to requirements.txt, install it, and use lime.lime_tabular.LimeTabularExplainer over the scoring function to produce local explanations, returning the local linear coefficients and the surrogate model R². Render them in the LIME tab.
- **Effort:** L  ·  **Files:** backend/app/services/research_eval/xai_conditions.py, backend/app/services/therapeutic/feature_xai.py, backend/requirements.txt

#### `B2 / A8 / A12 / O5` — XAI / explainability  ·  _major_

- **Spec ref (B2 XAI Pseudocode / A8 / A12):** B2 XAI pseudocode (verbatim): SHAP_i = coef_i × (x_i − E[x_i]) where coef_i is from sklearn.LinearRegression fitted on a 44-sample Cartesian background, x_i is the actual feature value, and E[x_i] its expectation over the background. A8/A12: SHAP (analytical, sklearn.LinearRegression, 44-sample background) + Scikit-learn.
- **As-built:** The active SHAP path (research_eval.xai_conditions.explain_additive_score, used by service.assign_dq4_conditions) computes contribution = w_i × x_i with baseline defaulting to 0.0 — plain arithmetic mislabeled 'analytical_additive_shap'. There is no expectation term E[x_i], no sklearn.LinearRegression coefficient fit, and no 44-sample Cartesian background. The only shap-library path (therapeutic.feature_xai._optional_shap) is gated behind ENABLE_SPEC_SHAP (default False) and, even when enabled, uses sklearn Ridge (not LinearRegression), a 64-row Gaussian random neighbourhood (not a 44-sample Cartesian background) and shap.Explainer — and shap+sklearn are not installed. grep for 'LinearRegression' across backend/app returns nothing.
- **Research/DQ impact:** O5's SHAP integration and the B2 methodological claim are not reproducible: the exact formula, the LinearRegression coefficients, and the 44-sample background the dissertation describes are not in the code, so any SHAP figures in the report cannot be regenerated from the artefact.
- **Why major:** The named algorithm and technology stack in the approved spec (analytical SHAP formula coef_i×(x_i−E[x_i]), sklearn.LinearRegression, 44-sample Cartesian background) is entirely absent; it is replaced by w_i×x_i arithmetic (active) and, behind a default-off flag with the library uninstalled, by a different Ridge+shap.Explainer surrogate. The 'SHAP (analytical)' claim is therefore only nominally supportable.
- **Evidence:**
    - backend/app/services/research_eval/xai_conditions.py:26
    - backend/app/services/research_eval/xai_conditions.py:32
    - backend/app/services/therapeutic/feature_xai.py:74
    - backend/app/services/therapeutic/feature_xai.py:86
    - backend/app/services/therapeutic/feature_xai.py:93
    - backend/app/services/therapeutic/feature_xai.py:96
- **→ Conformance enhancement:** Implement the spec formula in xai_conditions.explain_additive_score: build the 44-sample Cartesian background over the feature grid, fit sklearn.linear_model.LinearRegression on it, compute E[x_i] per feature, and return SHAP_i = coef_i×(x_i − E[x_i]) with baseline E[f(x)]. Replace Ridge with LinearRegression in feature_xai._optional_shap, add shap+scikit-learn to the main requirements.txt, install them, and default ENABLE_SPEC_SHAP to True.
- **Effort:** L  ·  **Files:** backend/app/services/research_eval/xai_conditions.py, backend/app/services/therapeutic/feature_xai.py, backend/app/core/config.py, backend/requirements.txt

#### `B4 / B2` — XAI / explainability  ·  _major_

- **Spec ref (B4 screenshots (SHAP tab)):** B4 SHAP tab features: 'Molecular Isomorphism +4.00', 'Brand Name +4.00', 'Strength Difference (%) +20.00', with caption 'Baseline E[f(x)] = 72.0 | Actual score = 100.0 | Sum check: 72.0 + (+20.00 + +4.00 + +4.00) = 100.0'.
- **As-built:** None of the three named features exist. The scoring model uses nine components: indication_relationship, atc_or_therapeutic_class, mechanism_relationship, target_or_pathway, route_compatibility, dosage_form_compatibility, patient_population_compatibility, contraindication_warning_assessment, interaction_assessment_coverage, plus an optional molecular_similarity_mcs feature. There is no 'Brand Name' or 'Strength Difference (%)' feature; the closest to 'Molecular Isomorphism' is molecular_similarity_mcs, which is named differently and only appears when RDKit MCS returns status 'ok' (RDKit is not installed). No baseline E[f(x)]=72.0 or sum-check caption is produced (baseline defaults to 0.0).
- **Research/DQ impact:** B2/B4 SHAP illustrations are not reproducible from the artefact; the dissertation's worked SHAP example (Molecular Isomorphism/Brand Name/Strength Difference, baseline 72.0 → 100.0) has no basis in the running code, weakening the O5/DQ4 transparency evidence.
- **Why major:** The specific SHAP feature set the spec commits to (and the exact B4 screenshot values +4.00/+4.00/+20.00 and baseline 72.0) is entirely different from what the code computes, so the approved SHAP figures cannot be regenerated and the SHAP claim is only partially supportable.
- **Evidence:**
    - backend/app/services/therapeutic/scoring.py:6
    - backend/app/services/therapeutic/feature_xai.py:41
    - backend/app/services/research_eval/xai_conditions.py:18
    - backend/app/services/therapeutic/feature_xai.py:44
- **→ Conformance enhancement:** Either align the code's SHAP feature set and baseline to the spec's named features (Molecular Isomorphism, Brand Name, Strength Difference (%)) and the E[f(x)]=72.0 baseline, or (if the 9-component model is intentional) correct the spec/report — but per audit rules the code must be changed to match the approved spec: add these named features to the attribution output and compute the baseline expectation and sum-check.
- **Effort:** M  ·  **Files:** backend/app/services/therapeutic/scoring.py, backend/app/services/therapeutic/feature_xai.py, backend/app/services/research_eval/xai_conditions.py
- **Verifier correction:** As-built is accurate: the scoring model uses nine components (scoring.py:6-16: indication_relationship, atc_or_therapeutic_class, mechanism_relationship, target_or_pathway, route_compatibility, dosage_form_compatibility, patient_population_compatibility, contraindication_warning_assessment, interaction_assessment_coverage) plus an optional molecular_similarity_mcs feature (feature_xai.py:41) that is only appended when mcs status=='ok' (feature_xai.py:38) — which never fires because RDKit is not installed. There is no 'Brand Name' or 'Strength Difference (%)' feature and no baseline E[f(x)]=72.0 or sum-check caption (baseline defaults to 0.0, xai_conditions.py:18). However the severity should be MODERATE, not major: per the rubric, divergence in feature naming/coverage where the per-feature attribution mechanism still exists and the research claim survives with reworded feature names/values is moderate, not major. The underlying weighted per-component attribution is implemented and rendered; only the specific spec-illustration feature names, +4.00/+4.00/+20.00 values and 72.0 baseline are not reproducible.

#### `D7-03` — Evaluation harness (DQ1–DQ4)  ·  _major_

> **U-TE status — regulatory gold standard added.** DQ2 now exposes `orange_book_gold_standard` — for
> each reference medicine, the FDA Orange Book **A-rated products in the same pharmaceutical-equivalence
> group** (DISCN excluded). This is a *defensible regulatory relevant-set* for Precision@K/Recall@K,
> offered alongside (not replacing) the pharmacist-confirmed gold — addressing the "no defensible
> relevant set" gap. **Scope caveat (validation):** as wired in the DQ2 harness it is computed
> **ingredient-wide** (no form/strength filter), so it spans forms/strengths and mixes subletters — a
> *coarse* regulatory ground truth, not a strict PE-group set (narrow by form+route+strength for that).
> Verified: metformin returns its A-rated group, aspirin returns none (single-source). Remaining: the
> harness *exposes* the set but does not yet *compute* P@K/R@K against it; + the synthetic dataset (D7-09).

- **Spec ref (O6, A9 (Quantitative-Recommendation), B3 (DQ2)):** A9/DQ2: 'Precision@K & Recall@K - Effectiveness of RDKit MCS identifying therapeutically equivalent alternatives in top-ranked results'; B3 targets P@3>=0.70, R@3>=0.60.
- **As-built:** DQ2 does not evaluate the recommendation engine's output. build_per_case constructs the 'retrieved_ranked' list by sorting the pharmacist gold-standard rows themselves (valid-first, optional same_active_moiety boost, then stored candidate_rank) — comment: 'Simulated retrieved ranking: gold ranks, optionally boost same-moiety with MCS flag'. Because the 'retrieved' list is derived from the gold labels, Precision@K/Recall@K are largely self-fulfilling. The 'rules_plus_mcs' condition boosts by the boolean same_active_moiety gold field, not by RDKit maximum-common-substructure; rdkit is not installed and the real MCS module (services/therapeutic/mcs.py) is never invoked in DQ2.
- **Research/DQ impact:** O3/DQ2: P@3>=0.70 and R@3>=0.60 for RDKit-MCS-driven recommendation are not evidenced against the real system; results reflect gold-label ordering, not engine retrieval quality.
- **Why major:** P@K/R@K are correctly implemented and the harness could ingest real retrievals, but as wired it measures a re-sort of the gold set, and 'MCS' is a stored boolean rather than RDKit MCS. The specific claim 'effectiveness of RDKit MCS in top-ranked results' cannot be supported.
- **Evidence:**
    - backend/app/services/research_eval/service.py:219
    - backend/app/services/research_eval/service.py:223
    - backend/app/services/research_eval/service.py:225
    - backend/app/services/research_eval/service.py:246
    - backend/app/models/research_eval.py:108
    - backend/app/services/therapeutic/mcs.py:39
- **→ Conformance enhancement:** Feed run_dq2_recommendation_evaluation the actual ranked output of the therapeutic recommendation engine (services/therapeutic evaluate/retriever) for each reference medicine, and compute the rules_plus_mcs condition from real RDKit MCS atom-coverage (mcs.py) rather than the same_active_moiety boolean; install rdkit (requirements-spec-research.txt).
- **Effort:** XL  ·  **Files:** backend/app/services/research_eval/service.py, backend/app/services/therapeutic/mcs.py, backend/requirements-spec-research.txt

#### `D7-04` — Evaluation harness (DQ1–DQ4)  ·  _major_

> **U12 status — mechanism CLEARED; WER/CER verdicts gated to real data.** `metric_status.py` encodes
> the B3 targets (`ACCEPTANCE_TARGETS`: WER<0.15, CER<0.10, P@3≥0.70, R@3≥0.60, BERTScore F1≥0.80) with
> per-metric direction, and `metric_envelope` attaches `acceptance{target,direction,label,pass}` keyed by
> metric name (DQ1/DQ2/DQ3 emitters pick it up automatically). `pass` is computed only on an AVAILABLE
> numeric value; NaN/bool are guarded → no verdict. `ResearchEvaluationPanel.tsx` renders a PASS/FAIL chip.
> Verified: direction/boundary correctness, availability gating, key-match reachability (all 5 targets
> reachable by live emitters).
>
> **Honesty gate (from U12's independent validation):** the **DQ1 WER/CER** metrics are computed over
> `simulate_engine_outputs` noise (the DQ1 fabrication, see D7-01), so attaching an official PASS/FAIL to
> them would certify fabricated data. U12 therefore **suppresses the acceptance badge for DQ1** — WER/CER
> PASS/FAIL is withheld until a real DQ1 path + evaluation dataset exist (U3 / D7-09). So the *threshold
> mechanism* is done and correct; the P@3/R@3 (DQ2) and BERTScore (DQ3, itself circular pending U2)
> badges render, but the OCR-target verdicts are intentionally not shown until real data backs them.

- **Spec ref (B3 (Quantitative targets), B4 Page 2):** B3 quantitative targets table (all must be checkable): WER<15%, CER<10%, P@3>=0.70, R@3>=0.60, BERTScore>=0.80.
- **As-built:** None of the approved numeric acceptance thresholds are encoded anywhere. A repo-wide search found only unrelated numbers (OCR confidence 0.60/0.75, MCS atom-coverage 0.9). ranking_metrics/ocr_metrics contain no threshold constants; service wrap() emits raw values with no pass/fail; the frontend MetricValue simply renders value.toFixed(4) with no comparison to a target. So the dashboard cannot report metrics against the approved acceptance criteria.
- **Research/DQ impact:** DQ1-DQ3: the Evaluation Dashboard shows scores but cannot evidence conformance to WER<15%, CER<10%, P@3>=0.70, R@3>=0.60, BERTScore>=0.80 as required by B3.
- **Why major:** The approved acceptance criteria are the pass/fail commitments of the study; with no thresholds encoded, the artefact cannot state whether any DQ target was met, so B3 is not checkable in the deliverable.
- **Evidence:**
    - backend/app/services/research_eval/ranking_metrics.py:8
    - backend/app/services/research_eval/service.py:263
    - frontend/src/components/ResearchEvaluationPanel.tsx:24
    - backend/app/services/research_eval/ocr_metrics.py:33
- **→ Conformance enhancement:** Add a TARGETS constant map (wer=0.15, cer=0.10, p_at_3=0.70, r_at_3=0.60, bertscore_f1=0.80) in the research_eval service, attach a pass/fail flag to each metric_envelope, and render a PASS/FAIL badge next to each value in ResearchEvaluationPanel.
- **Effort:** S  ·  **Files:** backend/app/services/research_eval/metric_status.py, backend/app/services/research_eval/service.py, frontend/src/components/ResearchEvaluationPanel.tsx

#### `D7-09` — Evaluation harness (DQ1–DQ4)  ·  _major_

- **Spec ref (C (Deliverables), B3 (sample)):** C deliverables: 'Curated dataset of 25-30 synthetic handwritten prescription images | Partially done (2 images)'; B3 'n = 5 participants, 25-30 prescription test cases'.
- **As-built:** The repository contains zero prescription image files (recursive image search across the project, excluding deps, returns none) and no research-evaluation dataset at all: the import root data/research_evaluation does not exist, so cases_v1.json, gold_standards_v1.json and survey_responses_v1.json are absent. The DQ harness thus has 0 evaluation cases, 0 gold rows and 0 survey responses; combined_status would report every DQ as IMPLEMENTED_NOT_EVALUATED/INSUFFICIENT. Even the 2 images the spec claims as 'partially done' are not present.
- **Research/DQ impact:** O6/DQ1-DQ4: the empirical evaluation cannot be run at the specified scale from the shipped repo; all quantitative and qualitative targets are unevidenced for lack of data.
- **Why major:** With no images and no cases/gold/survey data, none of DQ1-DQ4 can produce evidence at the approved sample size (25-30 cases, n=5); the harness is an empty shell against the acceptance criteria, and even the reduced 2-image status is unmet.
- **Evidence:**
    - backend/app/services/research_eval/import_dataset.py:22
    - backend/app/services/research_eval/import_dataset.py:181
    - frontend/src/components/ResearchEvaluationPanel.tsx:117
- **→ Conformance enhancement:** Add the curated 25-30 synthetic handwritten prescription images and populate data/research_evaluation/{cases_v1,gold_standards_v1,survey_responses_v1}.json with pharmacist-confirmed ground truth and gold standards so the harness has real inputs.
- **Effort:** L  ·  **Files:** data/research_evaluation/cases_v1.json, data/research_evaluation/gold_standards_v1.json, data/research_evaluation/survey_responses_v1.json

#### `D7-V1` — Evaluation harness (DQ1–DQ4)  ·  _major_ · **[verifier-surfaced]**

- **Spec ref (O6, A9 (Quantitative-RAG), B3 (DQ3), B4 Tab 2):** A9/DQ3 & O6: 'BERTScore - Semantic alignment between generated drug explanations and official OpenFDA regulatory records'; the RAG pipeline retrieves FDA SPL evidence and generates an LLM explanation that is then compared to the reference OpenFDA label.
- **As-built:** Beyond D7-02 (BERTScore never computed), the entire DQ3 harness bypasses the real RAG pipeline, so even its substitute metrics do not reflect the system under study. (a) Retrieval runs against a hardcoded 2-chunk demo corpus (an ibuprofen indication line + an NSAID warning line) when no corpus is passed, not the real FDA SPL corpus that ships in data/openfda-spl-labels.json (backend/app/services/research_eval/service.py:290-305). (b) The 'explanation' is a deterministic template concatenation of citation snippets, not the production Groq LLM output (backend/app/services/research_eval/evidence_retrievers.py:163-177); no GROQ/LLM code exists in the research_eval package (grep confirms) and ENABLE_SPEC_GROQ defaults False (backend/app/core/config.py:45). (c) The 'FAISS' condition embeds text as a 64-dim hashed bag-of-words vector (evidence_retrievers.py:90-98, used even when faiss is present, _build lines 100-110), i.e. non-semantic hashing rather than sentence-transformer embeddings. citation_coverage and unsupported_claim_rate (service.py:317-318) are therefore computed on a toy corpus and a non-LLM template, so the DQ3 'semantic alignment of generated explanations to OpenFDA labels' claim is unsupported even in the substitute metrics, not only in the missing BERTScore.
- **Evidence:**
    - backend/app/services/research_eval/service.py:290
    - backend/app/services/research_eval/evidence_retrievers.py:163
    - backend/app/services/research_eval/evidence_retrievers.py:90
    - backend/app/core/config.py:45
- **→ Conformance enhancement:** Wire run_dq3_rag_evaluation to the production RAG path: load the real FDA SPL corpus from settings.FDA_SPL_JSON_PATH/data/openfda-spl-labels.json, retrieve with real semantic embeddings, and generate the explanation via the actual Groq LLM (ENABLE_SPEC_GROQ) rather than build_explanation_from_evidence; then compute BERTScore(generated_explanation, reference_openfda_label). Replace the hashed _embed with sentence-transformer vectors for the FAISS arm.
- **Effort:** L

#### `A12/C-XAI-SHAP-LIME` — Platform, deployment & governance  ·  _major_

- **Spec ref (A12 (software stack) / C (Statement of Deliverables, XAI Dashboard)):** A12 software stack names "SHAP (analytical), LIME"; C deliverables name an "XAI Dashboard (SHAP + LIME + source cards)".
- **As-built:** At the deliverable/dependency level, LIME is absent entirely - it is not declared in any requirements file and not installed in backend/.venv. SHAP (and scikit-learn/rdkit) are declared only in the optional requirements-spec-research.txt and are NOT installed in backend/.venv; the production XAI path is rule-based, with SHAP labelled optional/experimental. So the named 'SHAP + LIME' XAI deliverable is only partially present. (Detailed XAI mechanism conformance is owned by the XAI dimension; this finding is scoped to declared/installed dependency presence.)
- **Research/DQ impact:** O5/DQ4 (explainability) claims that reference SHAP and LIME cannot be fully evidenced from the shipped artefact: LIME is unavailable and SHAP is not installed in the runtime environment, so the default XAI is rule-based rather than the named SHAP/LIME stack.
- **Why major:** A named approved technology (LIME) is entirely absent (not even declared), and SHAP is inactive by default (optional, not installed). The 'SHAP + LIME' XAI deliverable named in A12 and C is therefore only partially supportable. Major because a named technology/algorithm in the approved spec is absent/inactive by default; the XAI-method claim survives only partially.
- **Evidence:**
    - backend/requirements-spec-research.txt:1-5 (rdkit, shap, scikit-learn - optional only)
    - backend/.venv/Lib/site-packages listing contains no shap, no lime, no sklearn/scikit-learn, no rdkit
    - grep for 'lime' across **/requirements*.txt returns no matches (LIME not declared anywhere)
    - docs/specification_traceability_matrix.md:25 (R18 SHAP/LIME marked 'Partially implemented', 'Production rule-based')
    - docs/approved_design_vs_implemented_artefact.md:55 (SHAP/LIME as primary XAI -> rule-based production; SHAP secondary/experimental)
- **→ Conformance enhancement:** Add lime (and shap, scikit-learn) to the installed runtime requirements and wire both SHAP and LIME into the XAI Dashboard as the approved explainers, or formally record the substitution of a rule-based explainer with supervisor/ethics sign-off. Effort M (coordinate with the XAI dimension owner).
- **Effort:** M  ·  **Files:** backend/requirements.txt, backend/requirements-spec-research.txt

#### `A6-ethics-PII-consent` — Platform, deployment & governance  ·  _major_

- **Spec ref (A6 (Ethics / data governance)):** "No personally identifiable information (PII) is collected at any stage"; "All questionnaire responses are strictly anonymous, collected via Microsoft Forms, stored on the University M Drive (encrypted)"; consent via a digital Consent Form sent by University email BEFORE any research activity (A6).
- **As-built:** The application collects and persists identifying account and consent data in its own PostgreSQL database: usernames, Argon2 password hashes, an (encrypted) pharmacist registration number, role/status, login history rows, and full electronic consent records linked to the user id (per-statement acceptances, PIS acknowledgement, registration request/decision). Consent is captured in-app during self-service registration rather than via a University-email Consent Form sent before research activity. Precisely NOT stored: email addresses are not collected, and IP/user-agent are not persisted to the DB (IP is used only transiently for rate limiting).
- **Research/DQ impact:** Directly touches the A6 ethics/governance basis of the study (ethics 18274). A reviewer could challenge whether the artefact conforms to the approved 'no PII' data-handling model; the DSR ethics-compliance claim needs explicit caveats about in-app account/consent storage.
- **Why major:** A6 is an explicitly approved ethics position ('No PII collected at any stage'; anonymous Microsoft Forms + M Drive; email consent before activity). The artefact now stores identifying account data (pharmacist registration number is identifying) and electronic consent linked to identity in its own DB, and moves consent capture into the app. This contradicts an approved ethics commitment, so the governance claim is only partially supportable - major. It is not critical because research questionnaire responses do remain external/anonymous and the app applies mitigations.
- **Evidence:**
    - backend/app/models/auth.py:23-41 (User: username, password_hash, role, encrypted_pharmacist_registration_id)
    - backend/app/models/auth.py:58-65 (LoginHistory: user_id, successful, created_at - no IP/user-agent)
    - backend/app/models/consent.py:65-97 (UserConsent + UserConsentResponse per-statement, linked to user_id)
    - backend/app/models/consent.py:50-62 (UserPisAcknowledgement linked to user_id)
    - backend/app/services/registration_service.py:73-127 (creates User + consent records at registration; encrypt_field(pharmacist_registration_id) at :80)
    - backend/app/models/admin.py:10-35 (RegistrationRequest/Decision retain identity + administrator_id)
- **→ Conformance enhancement:** Either bring the data model back within A6 (do not persist pharmacist registration numbers or in-app consent records; rely on the approved external Microsoft Forms + M Drive + email-consent flow), or file an ethics amendment documenting the account/consent store, its lawful basis, encryption-at-rest, retention and separation-from-research-data. Update PIS/Consent copy to describe the in-app data actually held. Effort M.
- **Effort:** M  ·  **Files:** backend/app/models/auth.py, backend/app/models/consent.py, backend/app/services/registration_service.py, backend/app/core/research_content.py

#### `A8/A10-deployment-HF-Spaces` — Platform, deployment & governance  ·  _major_

- **Spec ref (A8 / A10 (approved modifications table, Deployment row)):** "implemented on Hugging Face Spaces" (A8); A10 Deployment change "Streamlit Cloud" -> "Migrated to Hugging Face Spaces - Streamlit Cloud's 500 MB RAM limit was insufficient for TrOCR (1.5 GB) and Knowledge Graph" (HF Spaces is the approved deployment target).
- **As-built:** No Hugging Face Spaces deployment artefacts exist: no Spaces README YAML header (sdk: streamlit / app_file / colorFrom), no hf_startup.py, no HF_TOKEN data-download bootstrap, no Spaces config of any kind. Deployment is local Docker Compose with an nginx container serving the built React app.
- **Research/DQ impact:** O1/A8 headline 'deployed on Hugging Face Spaces' cannot be evidenced; any dissertation figure or statement asserting HF Spaces hosting is inaccurate.
- **Why major:** The approved deployment target (HF Spaces) is entirely absent and replaced by local Docker/nginx; the specific A8 claim 'implemented on Hugging Face Spaces' is unsupportable. Rated major rather than critical only because it compounds the same platform decision already captured as critical in the architecture finding.
- **Evidence:**
    - grep for sdk:/app_file/huggingface/spaces/HF_TOKEN/hf_startup across the project source returns hits only inside node_modules and .venv library internals, none in project source
    - frontend/nginx.conf:1 (nginx reverse-proxy config for the web container)
    - docker-compose.yml:60-68 (web = nginx container, not HF Spaces)
    - README.md:25-34 ('Full stack (Docker)' / docker compose up --build; UI at 127.0.0.1:8080) - no HF Spaces instructions
    - docs/approved-specification/specification_manifest.json:18 (admits 'Approved Spec described Streamlit/HF Spaces; implemented artefact is FastAPI + React + PostgreSQL')
- **→ Conformance enhancement:** Add a Hugging Face Spaces deployment (Streamlit SDK Space with README YAML front-matter and a data bootstrap equivalent to the reference hf_startup.py) as part of the re-platforming, or formally re-approve the deployment target. Effort L (on top of the architecture re-platform).
- **Effort:** L  ·  **Files:** README.md, docker-compose.yml

#### `B4-usecase3-eval-dashboard` — Platform, deployment & governance  ·  _major_

- **Spec ref (B4 (two-page app) / A6-B1 (pharmacist use cases)):** "two-page Streamlit application" with Page 2 = Evaluation Dashboard (B4); the spec's three use cases (including the Evaluation Dashboard, use case 3) belong to the single Pharmacist actor.
- **As-built:** The Evaluation Dashboard (Research Evaluation, DQ1-DQ4, snapshot metrics and exports) is gated to the 'reviewer' role only. The pharmacist can reach only the Analyzer and Catalog pages and is redirected away from /research/evaluation; every research-evaluation API endpoint requires the reviewer role. A spec-required pharmacist capability has been moved out of the pharmacist role.
- **Research/DQ impact:** Affects O6 (evaluation) and the DQ1-DQ4 evaluation workflow: the participants are licensed pharmacists, but the dashboard the spec places in their hands is walled off to a reviewer role, complicating any claim that pharmacists used the Evaluation Dashboard as specified.
- **Why major:** The approved design assigns the Evaluation Dashboard (use case 3) to the pharmacist actor; in the as-built the pharmacist literally cannot access it and it is behind a 'reviewer' role that does not exist in the spec. This materially changes an approved use-case-to-actor assignment, so the pharmacist-facing evaluation claim is only partially supportable.
- **Evidence:**
    - frontend/src/App.tsx:164-173 (/research/evaluation renders ReviewerDashboardPage only when user.role === 'reviewer', else Navigate away)
    - frontend/src/App.tsx:143-162 (pharmacist routes limited to /analyzer and /catalog)
    - backend/app/api/v1/research_eval.py:97,105,128,144,178,217,234,257,... (every endpoint Depends(require_reviewer))
    - frontend/src/pages/ReviewerDashboardPage.tsx:37-46 (this reviewer page IS the evaluation snapshot dashboard)
    - backend/app/security/rbac.py:51 (require_reviewer)
- **→ Conformance enhancement:** Grant the pharmacist role access to the Evaluation Dashboard route and API (add require_roles('pharmacist','reviewer') on research_eval endpoints and expose /research/evaluation to pharmacists in App.tsx), or fold the evaluation view back into the single pharmacist portal per B4. Effort M.
- **Effort:** M  ·  **Files:** backend/app/api/v1/research_eval.py, frontend/src/App.tsx, backend/app/security/rbac.py

## 4. Moderate deviations (37)

| Ref | Spec | As-built (condensed) | Conformance enhancement | Effort |
|---|---|---|---|---|
| `D1-09` | A12 / O1 / DQ1 | Even with torch/transformers installed, the TrOCR integration is not usable as written. TrOCRProcessor.from_pretrained and VisionEncoderDecoderModel.from_pretrained are called inside the per-crop function, so the ~1.4 GB microsoft/trocr-… | Hoist the processor/model into a module-level lazily-initialised cache in backend/app/services/ocr/engines.py (e.g. an @lru_cache _get_trocr() returning (processor, model) with model.eval() and an explicit device), an… | M |
| `D1-10` | O1 / A8 / B1 | The full-page TrOCR path is architecturally invalid. _run_trocr_document first asks PaddleOCR for line regions; if none are returned it calls _trocr_transformers_crop(image_bytes, None), i.e. it feeds the entire prescription page to micr… | Give TrOCR a real line-detection front end that does not depend on PaddleOCR: implement text-line segmentation in backend/app/services/ocr/preprocess.py (OpenCV is already installed — horizontal projection/contour-bas… | M |
| `D1-11` | O1 / A8 / B1 | The Tesseract adapter is genuinely implemented against the real binary, but it is inoperative on the audited machine because pytesseract.tesseract_cmd is never configured anywhere in the backend and the tesseract executable is not on PAT… | Add a TESSERACT_CMD setting to backend/app/core/config.py and set pytesseract.pytesseract.tesseract_cmd from it at the top of backend/app/services/ocr/tesseract_adapter.py (falling back to shutil.which('tesseract')). … | S |
| `D1-12` | A8 / B1 / A10 | Three capabilities beyond the approved OCR design are implemented and, for two of them, on by default. (1) PaddleOCR is a first-class engine: it has a detector adapter, is an accepted engine id in the order parser, is a selectable engine… | Declare all three as approved-scope additions in the deviation register, or reduce them. Concretely: (a) either add paddlepaddle/paddleocr as real pins in a backend/requirements-ocr-optional.txt installable section an… | M |
| `D1-V1` [V] | DQ1 / B1 | The delivered artefact silently re-scopes the approved TrOCR-specific DQ1 into a pipeline-wide, all-engines question and presents THAT as the primary research question. backend/app/services/research_eval/ocr_engines.py:132-136 sets DQ1_R… | Return and display the approved DQ1 wording ('How accurately does TrOCR extract drug names and dosages? WER/CER') as the primary research_question in ocr_engines.py and ResearchEvaluationPanel.tsx; label the pipeline-… | S |
| `D1-V2` [V] | DQ1 / O6 / B1 | The only genuine (non-simulated) WER/CER path — compute_session_analytics — does not measure OCR transcription against a ground-truth transcript; both sides are reconstructed from STRUCTURED FIELDS. _medicine_instruction joins name+stren… | For a DQ1-defensible transcription metric, compute WER/CER of each engine's raw OCR transcript against a pharmacist-confirmed transcript of the same prescription region (transcript-vs-transcript, aligned units); keep … | M |
| `B3 (Find Alternatives button)` | B3/B4 Step 3 | There is no 'Find Alternatives' button. The per-row HITL action is 'Confirm', the session action is 'Submit', and alternatives are generated only from a separate 'Alternatives' tab via buttons labelled 'Evaluate alternatives for this med… | Either rename the evaluate control to 'Find Alternatives' and surface it within the Step-3 HITL area (e.g. once a row is confirmed), or update the spec/wireframe to the actual 'Evaluate alternatives' tabbed control. | S |
| `B3 (graph inputs only)` | B3/B4 Step 3 | There is no knowledge graph in the artefact — networkx is not declared in any requirements file and is not installed in backend/.venv (it appears only in _reference-old-project docs). HITL dropdown options are sourced from the unified SQ… | Either build a knowledge-graph layer (e.g. networkx over the ingredient->salt->product->strength/route/form catalog) and source the HITL dropdowns from it, or reword the spec claim to 'catalog/SPL-constrained dropdown… | L |
| `B3-fields (Dosage form)` | B3/B4 Step 3 | The HITL cascade has NO 'Dosage form' field. FIELD_ORDER is drug, route, strength, dose, frequency, indication — 'form' is not a HITL field. The verification table columns are Drug / Route / Strength / Dosage / Frequency / Indication, wh… | Add a 'Dosage form' field to FIELD_ORDER and the cascade (options from the catalog dosage_forms already available on catalog hits), render a Form column/dropdown in VerificationTable, persist pharmacist_form in confir… | M |
| `B3-fields (extended cascade)` | B3/B4 Step 3 | The HITL cascade is a six-field sequence — drug, route, strength, dose, frequency, indication — extending well beyond the four approved fields. Confirm requires drug+route+strength+dose+frequency (dose and frequency are extra mandatory g… | Either amend the spec to record the extended cascade as an approved modification, or gate dose/frequency/indication behind an explicit 'extended HITL' flag so the default HITL matches the approved four fields (drug, d… | M |
| `B4-Step1` | B4 (Interface Design), page 17 | The analyzer stepper is STEPS = ['Upload', 'OCR pipeline', 'HITL verify', 'Confirm & review'] — Step 1 is Upload, not OCR-engine selection. There is NO OCR-engine radio-button control anywhere in the frontend; the pipeline engine is hard… | Add a Step-1 OCR-engine selector (MUI RadioGroup / Streamlit st.radio) to AnalyzerPage before upload, wiring the choice through to /ocr/{id}/run(-async) body.engine (the backend already accepts a non-'pipeline' engine… | M |
| `D2-V1` [V] | B4 Step 4 | The four-step stepper's terminal step is labelled 'Confirm & review' (AnalyzerPage.tsx:70) — a label that does not appear in the spec's step list. activeStep is computed reactively and tops out at index 3 = all-rows-confirmed (AnalyzerPa… | Re-label and re-sequence the analyzer stepper so Step 4 = 'Therapeutic suggestions' presenting the component-wise scores + RAG + XAI dashboard as the terminal sequential step (advance activeStep to a 4th 'suggestions'… | M |
| `D2-V2` [V] | B4 (Interface Design) | The two spec pages are siloed across mutually exclusive roles, so no single user ever experiences the approved two-page app. /analyzer (Page 1) is pharmacist-only and redirects any non-pharmacist away (App.tsx:142-151); /research/evaluat… | Either expose both Page 1 (Analyzer) and Page 2 (Evaluation Dashboard) to the same pharmacist role with in-app navigation between them, matching the approved single two-page app, OR record the role-based split of the … | M |
| `D3-07` | A8 / B2 | The default result cap is 5, not 3. evaluate_prescription/_evaluate_one default top_n=5 and the API EvaluateRequest.top_n defaults to 5 (range 1–10). Each candidate path is truncated with [:top_n], so up to 5 product candidates and 5 the… | Change default top_n to 3 in evaluate.evaluate_prescription/_evaluate_one and in the API EvaluateRequest (default=3, le=3), or clamp the returned lists to 3. | S |
| `D3-08` | B2 | There is no deduplication by the (name, dosage_form, strength) tuple. The only dedup is by catalogue medicine id (mid) during retrieval, and by medicine id when building therapeutic candidates. Two catalogue rows with the same name/form/… | Add a dedup pass in evaluate._evaluate_one keyed on (normalized candidate_name, canonical dosage_form, normalised strength) before ranking/truncation for both product and therapeutic candidate lists. | S |
| `D3-09` | B2 / B4 | The reasoning trail surfaced to the pharmacist does not contain the approved weighted breakdown. The frontend shows a single 'Rule-based score {n}/100' chip and, only if MCS status=='ok', an 'MCS {x}%' chip. The backend rule_based_explan… | Once the weighted scorer (D3-01) exists, surface each component (Strength_score x0.4, Metadata_score x0.4 with its Base/Brand/isomorphism sub-lines, FormRoute_score x0.2) and the explicit 'Final = ...' line in rule_ba… | M |
| `D3-V1` [V] | B4 / B2 / A8 | On the SAME_ACTIVE_MOIETY_PRODUCT path the scorer is called with indication_related=False, mechanism_related=False, target_related=False HARDCODED (evaluate.py:356-366). Against the 9-component weights (scoring.py:6-16) the maximum achie… | Adopt the spec 0.4/0.4/0.2 Strength/Metadata/FormRoute scorer (per D3-01) for the product path so that same-ingredient + same-strength + same-form + brand-present + isomorphism-passed yields Final=100; stop hardcoding… | M |
| `D3-V2` [V] | B2 / A8 / DQ4 | The one place the system does present a weighted 'component_score_breakdown' to pharmacists — the DQ4 explanation conditions B/C — uses a THIRD distinct weighting: default weights {'mcs':0.3,'route_match':0.4,'strength':0.3} over default… | Align the DQ4 explain_additive_score default weights/feature_values with the approved Strength 0.4 / Metadata 0.4 / FormRoute 0.2 components (or drive them from the real spec-conformant recommendation scorer once it e… | S |
| `D4-V1` [V] | A10 Approved Changes (Data Storage) / A12 stack | FAISS is not the active retrieval mechanism and is not installable by default. It is absent from backend/requirements.txt and not present in backend/.venv/Lib/site-packages. The default therapeutic evidence path (rag_evidence.retrieve_la… | Add faiss-cpu (and the all-MiniLM-L6-v2 embedding stack) to backend/requirements.txt, build a FAISS IndexFlatL2 over label_sections at catalogue-build time, and make FAISS the default retrieval inside rag_evidence.ret… | — |
| `D5-V1` [V] | A8 (RAG Framework), B2 (RAG Pipeline) | Beyond replacing vector search with keyword scoring (D5-rag-01), the production retriever restricts the candidate pool to a SINGLE medicine's own label sections before ranking: it SELECTs label_sections WHERE medicine_id = ? LIMIT 40 (re… | Replace the per-medicine LIMIT-40 SELECT with a global FAISS IndexFlatL2 nearest-neighbour search: embed the query with all-MiniLM-L6-v2 and retrieve the top-5 chunks by L2 distance across the full embedded SPL chunk … | L |
| `D5-rag-05` | B4 (Step 4 screenshot) | The UI shows retrieved excerpts as plain 'source · section_key' + excerpt text nested inside a 'Rule-based score explanation' accordion. There is no vector 'Relevance distance' value (no distance concept exists), no numbered section head… | Once dense retrieval exists, surface each chunk's L2 distance and section heading as numbered 'FDA Evidence Sources' cards and render the Groq narrative as 'FDA Evidence & Explanation' in TherapeuticAlternativesPanel. | M |
| `D5-rag-07` | B2 (RAG Pipeline) | Verified against the live catalogue: SPL sections actually ingested are indications_and_usage, dosage_and_administration, warnings, warnings_and_cautions, adverse_reactions, contraindications, drug_interactions, dosage_forms_and_strength… | Add 'clinical_pharmacology' to _SPL_SECTIONS in build_index.py and rebuild the catalogue/index; decide whether to keep dosage_forms_and_strengths as an extra. | S |
| `D5-rag-08` | C (Deliverables), A10 (approved change) | Pre-built FAISS artefacts sit in data/ (rag_index.faiss 15MB, rag_chunks.pkl 17MB, rag_index.pkl 32MB) but no backend code references or loads them — they are orphaned leftovers from the legacy Streamlit project. Runtime retrieval uses t… | Either load data/rag_index.faiss + rag_chunks.pkl in rag_evidence.py and query them, or regenerate a compatible index from the current catalogue; then remove the unused legacy .pkl to avoid confusion. | M |
| `B1` | B1 component table | Matplotlib is not declared in any requirements file, is not installed in backend/.venv, and is never imported (grep 'matplotlib|pyplot' across backend/app and frontend/src returns nothing). No feature-importance charts are generated serv… | Add a charting mechanism (Matplotlib server-side rendering to embedded images, or a JS chart library client-side) and render feature-importance bar charts from the SHAP/LIME payloads. | M |
| `B4 / A8 / DQ4` | B4 screenshots (FDA Sources tab) | Source attribution cards ARE rendered inline (source + section_key + excerpt) in the alternatives panel, but no 'Relevance distance' value is displayed. The backend computes a keyword-overlap relevance 'score' (higher = more relevant, no… | Render the retrieval score as a numbered, labelled 'Relevance distance' on each evidence card (and, if the FAISS-distance semantics are required, expose an L2 distance from the vector index rather than the keyword sco… | S |
| `D6-V1` [V] | A8 IT Artefact / A10 / O5 | The additive-SHAP + perturbation-LIME code (xai_conditions.explain_additive_score) that the auditor treated as 'the active SHAP path' is invoked ONLY by the DQ4 research-assignment endpoint (service.assign_dq4_conditions:390 → api/v1/res… | Wire the analytical SHAP + LimeTabularExplainer explanation into the therapeutic evaluate flow (evaluate.py) so each Step-4 candidate carries a real SHAP and LIME payload (not the default-off feature_xai._optional_sha… | — |
| `D7-05` | B4 (Evaluation Dashboard, Tab 2) | K is not user-selectable. The service computes and returns only fixed precision_at_1, precision_at_3, recall_at_3; the API exposes no k parameter; and the frontend renders three static cells (P@1, P@3, R@3) with no MUI Slider imported. K… | Add a k query parameter to the DQ2 endpoint, generalise aggregate_recommendation_metrics to emit precision_at_k/recall_at_k for the chosen k, and add a MUI Slider (min 1, max 5, default 3) to the DQ2 tab that drives it. | M |
| `D7-06` | B1 (Use case 3), B4 Page 2 | The Evaluation Dashboard is reviewer-only. Every /research/eval/* route depends on require_reviewer, and ground-truth entry (POST /ground-truth) is reviewer-gated. require_pharmacist and require_reviewer are disjoint roles (no overlap). … | Either grant pharmacists access to the evaluation dashboard/ground-truth endpoints (e.g. require_roles('pharmacist','reviewer') on the ground-truth and status routes and a pharmacist-visible route) or document an appr… | M |
| `D7-07` | B3, B4 (Pharmacist Survey tab), Appendix B, C (Questionnaire deliverable) | There is no in-app survey collection. The DQ4 endpoint docstring states 'The survey is not collected in the PharmaAssist UI'; the DQ4 tab only previews explanation conditions and imports an external JSON export. The five named Likert con… | Model the five constructs (Q1-Q5) as an enum/schema, validate SurveyIn.likert against them plus a free_text field, and add a pharmacist-facing in-app Pharmacist Survey tab (or ship the v1.2 instrument + survey_respons… | L |
| `D7-08` | O6, A9 (Qualitative), B3/B4 | DQ4 is implemented as an unapproved three-condition (A minimal / B XAI / C XAI+provenance) counterbalanced within-subject XAI-trust experiment with hand-rolled SHAP/LIME on the additive score. The survey response is keyed by explanation … | Either restrict DQ4 to the approved 5-construct Likert survey (drop or clearly label the A/B/C XAI experiment as out-of-approved-scope) or obtain an approved change; make survey summaries aggregate by construct, not b… | M |
| `D7-10` | O6, B3 (statistical analysis) | Demo-seeding scripts manufacture favourable evaluation analytics for named-pharmacist showcase sessions. create_asad_showcase_rx.py is documented to yield 'perfect OCR<->HITL match ... entity F1 = 1.0, CER/WER = 0, BertScore ~= 1' by set… | Quarantine or remove these seed scripts from any evaluation build, and never mark is_mock=False on mock OCR; if demo data is needed, label it clearly as DEMO and exclude it from reported metrics. | S |
| `D7-V2` [V] | B3 (targets), B4 Page 2 (Evaluation Dashboard status) | combined_status derives DQ readiness purely from stored run counts, independent of whether the spec-required metric was actually computed. dq3 readiness = readiness(True, n_rag, n_rag > 0), which returns EVIDENCE_COMPLETE as soon as one … | Make readiness metric-aware: for DQ3 require a computed bertscore_f1 (AVAILABLE) before EVIDENCE_COMPLETE, and do not store RagEvaluationRun availability='AVAILABLE' when the spec metric is None; add per-DQ 'target me… | M |
| `A6/B1-roles-single-actor` | A6 / B1 (actor model, UML use cases) | Three distinct roles exist - administrator, pharmacist, reviewer - with self-service registration, administrator approval workflow, JWT access/refresh tokens, Argon2 password hashing, failed-login lockout, and per-endpoint RBAC. A full a… | To match the approved single-actor model, collapse to one 'Pharmacist' (Admin Pharmacist) role and remove the reviewer/administrator roles, registration-approval, and RBAC gating - or explicitly document and re-approv… | L |
| `B4-two-page-app` | B4 (page structure) | The as-built is a multi-page role-specific React SPA with ~10 routed pages (Login, Register, RegistrationStatus, ChangePassword, ForgotPassword, Home, AdminPortal, Analyzer, CatalogExplorer, ReviewerDashboard/Evaluation) rather than two … | Consolidate to the approved two-page structure (Analyzer + Evaluation) if re-platforming to Streamlit, or document the expanded page inventory as an approved modification. Effort M. | M |
| `C-deliverable-synthetic-images` | C (Statement of Deliverables) | No synthetic prescription image files (.png/.jpg/.jpeg) exist anywhere in the repository (outside .venv/node_modules). The PIS/consent copy references reviewing '25-30 synthetic handwritten prescription samples', but the image set itself… | Add the 25-30 synthetic prescription images (and a manifest/ground-truth mapping) into a versioned data/ or tests/fixtures directory so the DQ1 dataset is reproducible. Effort S. | S |
| `D8-V2` [V] | A6 (Ethics / data governance) | The at-rest encryption protecting the stored PII is effectively public. The FIELD_ENCRYPTION_KEY that encrypts the pharmacist registration number (encrypt_field at registration_service.py:80) is a trivially-known all-'A' base64 default, … | Provision strong, unique secrets for FIELD_ENCRYPTION_KEY and JWT_SECRET_KEY from a secrets manager (never a committed default), fail startup if a default key is detected in non-dev environments, remove the real Googl… | S |
| `governance-approved-spec-PDF-absent` | Governance / traceability (approved-specification manifest) | docs/approved-specification/ contains only specification_manifest.json. It references 'Spec Design Report.pdf' by SHA-256 (matching the approved hash) and page_count 25, but explicitly notes the authoritative copy is held outside the run… | Commit the approved 'Spec Design Report.pdf' (or a controlled, access-appropriate copy) into docs/approved-specification/ and add a verification step (e.g., a script asserting sha256 == manifest value) so the manifest… | S |

## 5. Minor deviations (6)

| Ref | Spec | As-built (condensed) | Conformance enhancement | Effort |
|---|---|---|---|---|
| `D1-13` | A12 | No requirements file a reader can install declares transformers or torch. They appear only as prose comments in two optional-requirements files, and the sole place they are really installed is the Dockerfile, as a side effect of the BERT… | Create backend/requirements-trocr.txt with explicit pins (torch, torchvision, transformers, safetensors, tokenizers), reference it from backend/requirements.txt as a documented extra, install it explicitly in backend/… | S |
| `D1-14` | DQ1 / O6 (traceability) | The self-assessment docs are mixed. They are honest about the primary-engine deviation — the complete-specification doc states TrOCR is primary "Only when OCR_PROFILE=spec" and the traceability matrix concedes the engine radio UI was not… | Update docs/specification_traceability_matrix.md rows R20 and R21 to status "Partially implemented" with the gap "metric functions implemented and unit-tested, but the DQ1 runner scores simulated engine outputs (resea… | S |
| `D4-V2` [V] | B2 (Ingredient node source) / Section 15 data sources | DrugBank ingestion silently narrows the 'DrugBank ingredient list' to approved/vet_approved drugs only: ingest_drugbank skips any drug whose <groups> lack 'approved' or 'vet_approved' (build_index.py:466-468), so ~4,953 DrugBank drugs ar… | Parameterise or relax the approved-only groups filter in ingest_drugbank if fuller DrugBank ingredient coverage is intended by B2, or document the approved-only scoping as a deliberate coverage decision. Effort S. | — |
| `D4-V3` [V] | C Deliverables / reproducibility | The shipped data/medicine_catalog.sqlite3 is stale relative to its own builder: build_index.py's DDL (lines 184-207) declares label_dose_frequency_options and indication_options tables, but the live database contains only 8 tables (alias… | Rebuild the shipped medicine_catalog.sqlite3 with the current build_index.py so the artefact matches its build script, and record the build commit/hash in the meta table for traceability. Effort S. | — |
| `D5-rag-09` | A8, B2 | The default top_k is 5 and the source-medicine retrieval uses top_k=5, but the per-candidate product and therapeutic evidence retrievals request only top_k=3. | Change the top_k=3 arguments at evaluate.py:381 and 625 to 5 to match the approved Top-5. | S |
| `D8-V1` [V] | C (out-of-MVP-scope boundaries) | An in-app drug-drug interaction screen DOES exist. backend/app/services/therapeutic/safety.py:128-141 matches the patient's current_medicines against a candidate's DrugBank drug_interactions list and emits a 'serious_interaction' HARD bl… | Either remove/feature-flag the serious_interaction rule (and clarify safety.py scope) to respect the 'DDI engine not planned for MVP' boundary, or document it as an approved scope addition explicitly noting it reuses … | S |

## 6. Appendix A — What already conforms (per dimension)

**D1-ocr — OCR pipeline & engines**
- Google Cloud Vision is genuinely implemented with the spec-appropriate feature type: _google_vision_via_rest posts DOCUMENT_TEXT_DETECTION over HTTPS (backend/app/services/ocr/engines.py:145-211, feature type at :156), supports both API-key and service-account credential paths (:160-181), and parses real per-word confidences and paragraph bounding boxes out of fullTextAnnotation rather than flat text (:114-142). Failures degrade to None with a warning rather than crashing (:219-223).
- Tesseract is genuinely implemented against the real binary, not mocked: run_tesseract uses pytesseract.image_to_data for per-token confidences and bounding boxes plus image_to_string for line grouping, computes a mean confidence, and returns honest distinct statuses (unavailable / empty / success / error) with typed error codes and no raw text in logs (backend/app/services/ocr/tesseract_adapter.py:29-116).
- A sequential fallback chain in the spec's shape exists and stops at the first acceptable engine: run_ocr_stack iterates the parsed engine order and breaks once a result is accepted (backend/app/services/ocr/engines.py:580-586), and parse_engine_order's hard-coded default return value is exactly the spec order ["trocr", "google_vision", "tesseract"] (backend/app/services/ocr/contract.py:53), deduplicating while preserving primary-then-fallbacks order (:41-52).
- The exact approved spec engine order is implemented and reachable: OCR_SPEC_PRIMARY defaults to "trocr" and OCR_SPEC_FALLBACK_ORDER to "google_vision,tesseract" (backend/app/core/config.py:69-70), and run_ocr_stack substitutes that order when OCR_PROFILE=spec (backend/app/services/ocr/engines.py:471-481). The code to honour O1/A8/B1 exists; it is the default that deviates (see D1-01).
- A normalized per-engine result contract with no silent cross-engine overwrite is implemented as specified for a multi-engine module: EngineAttempt records engine_id, status, raw_text, confidence, processing_ms, error_code, is_mock and per-line detail independently per engine (backend/app/services/ocr/contract.py:9-24), a single explicit acceptance gate decides usability (:27-38), and all attempts are attached to the result (backend/app/services/ocr/engines.py:632).
- WER and CER are correctly and independently implemented with documented normalisation: character_error_rate and word_error_rate over true Levenshtein distance on characters and on token sequences, with a documented normalise_for_error_rate (lowercase, punctuation strip, whitespace collapse) applied to both reference and hypothesis (backend/app/services/research_eval/ocr_metrics.py:9-72), plus a second implementation for production analytics (backend/app/services/analytics/edit_distance.py:25-45).
- A genuine, non-simulated WER/CER measurement path exists in production analytics: compute_session_analytics computes CER and WER of the real OCR-extracted text against the pharmacist-confirmed instruction, per prescription and per medicine, with the direction of comparison explicitly documented ("Hypothesis = Original Prescription OCR extracted. Reference = Pharmacist-in-the-loop verified/confirmed") — backend/app/services/analytics/compute.py:409-448 and :519-520, 586-592. This supports a DQ1 claim for whichever engine actually ran (engine attribution is the gap — see D1-08).
- Medicine-name entity precision/recall/F1 and per-field exact-match scoring for DQ1 are implemented over the seven spec-relevant fields (medicine_name, strength, route, dosage_form, dose, frequency, duration): backend/app/services/research_eval/ocr_metrics.py:75-125.
- DQ1 fails closed without pharmacist-confirmed ground truth: run_dq1_ocr_evaluation returns availability=INSUFFICIENT_GROUND_TRUTH and empty engines unless a GroundTruthRecord exists and case.ground_truth_status == "confirmed" (backend/app/services/research_eval/service.py:112-122), and the API requires a reviewer role (backend/app/api/v1/research_eval.py:254-259).
- MOCK OCR is labelled at every layer and gated against contaminating verified data: is_mock is carried on tokens, lines and documents (backend/app/services/ocr/engines.py:17-46), explicit warnings are emitted ("MOCK OCR active - install/configure real engines for production path.", engines.py:77), pharmacist Confirm is blocked on mock sessions unless HITL_ALLOW_MOCK_CONFIRM (backend/app/services/field_verification.py:61-72 and :1335-1344) with that flag defaulting to False (backend/app/core/config.py:72), and mock-OCR sessions are excluded from research aggregates with an explicit reason code (backend/app/services/admin_dashboard.py:66-68).
- Privacy-by-design in the OCR path: engine logging records only engine_id, status and latency and never raw OCR text (backend/app/services/ocr/engines.py:563-568, and the same discipline in tesseract_adapter.py:87, 97, 109), and the selected transcript is passed through redact_ocr_text with a warning when PII/admin lines are removed (engines.py:626-631, backend/app/services/ocr/privacy.py).
- Low-confidence handling and human-review escalation are implemented: OCR_MIN_CONFIDENCE downgrades a successful attempt to status='low_confidence' with a per-engine warning for TrOCR, Vision and Tesseract alike (backend/app/services/ocr/engines.py:498-500, 504-506, 532-534), and a below-threshold selected result sets requires_human_review (engines.py:623-624), consistent with the decision-support posture.
- Line-level engine provenance is captured and surfaced to the pharmacist: LineCandidate carries engine/confidence/bbox/is_mock/source_stage and MergedLine records selected_engine, selected_confidence, all competing candidates, a conflict flag and used_trocr_retry (backend/app/services/pipeline.py:37-58), persisted in pipeline_json and rendered per line with per-candidate engine attribution in the UI (frontend/src/components/OcrConflictPanel.tsx:202, 246). The structure is right; the engine label written into it can be wrong (see D1-04).
- The multi-engine contract is unit-tested at the behaviour level, including spec-order parsing, the acceptance gate, Tesseract unavailability without crashing, normalized Tesseract success, and fallback/consensus/provenance behaviour: backend/tests/test_r01_ocr_engines.py:15-32, 34-88, 99-351.

**D2-hitl — HITL workflow & platform**
- A6 clinical-safety Confirm gate is real and fail-closed: confirm_when_ready blocks confirmation until drug+route+strength+dose+frequency are all catalog-matched (field_verification.py:1170, 1709-1718) and rejects placeholder values (field_verification.py:1719-1724), satisfying 'review and confirm AI-extracted outputs before any recommendations finalised'.
- Mock-OCR outputs cannot be confirmed by default: HITL_ALLOW_MOCK_CONFIRM defaults False (config.py:72) and _assert_confirm_allowed_for_ocr blocks confirm on mock sessions (field_verification.py:61-72, 1335-1345); frontend surfaces the block banner (VerificationTable.tsx:497-502). Strong fail-closed HITL gate supporting A6/O2.
- Reactive/cascading dropdowns (spec 'reactive' / 'responsive' selectboxes) are implemented as a live locking cascade Drug->Route->Strength->Dose->Frequency, with downstream fields cleared when the drug changes and re-fetched per selection (field_verification.py:75-77 FIELD_ORDER + apply_field_correction; VerificationTable.tsx:361-399, 588-674).
- HITL dropdown options are constrained to trusted dataset values only (no free-text invented values): DrugDropdown keeps only FDA/NDC/DrugBank/SPL-sourced options (VerificationTable.tsx:1044-1059) and both FE and BE filter forbidden placeholders (VerificationTable.tsx:266-287; field_verification.py:80-120) — preserving the safety intent of 'graph inputs only'.
- A8 substance is met: OCR-extracted drug names and dosages are shown per field (ai_value), correctable via apply_field_correction, and confirmable via confirm_when_ready — a genuine pharmacist review/correct/confirm layer (clinical.py:135-173; VerificationTable.tsx:1133-1137, 1398-1402).
- Dose and frequency template fallbacks are fail-closed by default (HITL_ALLOW_DOSE_TEMPLATES / HITL_ALLOW_FREQ_TEMPLATES both default False; config.py:75,77), so dose/frequency options are FDA-SPL-evidence-only unless explicitly enabled for offline demos.
- XAI/RAG explanation content IS embedded inline within the alternatives area as the spec's Step 4 intends (not on a separate page): each candidate card shows a 'Rule-based score explanation' with experimental feature-attribution and inline RAG evidence excerpts (TherapeuticAlternativesPanel.tsx:303-341). Component-wise score chips (score/coverage/MCS) are also inline (TherapeuticAlternativesPanel.tsx:225-229).
- Decision-support-only framing and 'pharmacist confirmation mandatory / never auto-applied' disclaimers are present throughout the HITL and alternatives UI (AnalyzerPage.tsx:430-433; VerificationTable.tsx:492-496, 706-712; TherapeuticAlternativesPanel.tsx:584-593), consistent with A6.

**D3-recommend — Recommendation / therapeutic matching**
- RDKit rdFMCS.FindMCS is correctly implemented with atom_coverage/bond_coverage computation and a 90%/0.9 atom-coverage threshold flag (backend/app/services/therapeutic/mcs.py:92-119; meets_spec_threshold_0_9 at :113) — the code artefact exists and is structurally sound, it is just inactive/optional by default.
- Salt-awareness is implemented (satisfying O3's 'salt-aware' wording at the name level) via a curated salt/base moiety map and same_active_moiety() gate (backend/app/services/therapeutic/salt_normalisation.py:12-56,180-202), including acetaminophen/paracetamol aliasing.
- FormRoute broad substring matching per B2 ('tablet' in 'film coated tablet', 'capsule', 'injection', 'solution') is present in mandatory_filters._forms_compatible (backend/app/services/therapeutic/mandatory_filters.py:39-54), plus route synonymy handling (:19-36).
- Precision@K and Recall@K metric functions for DQ2 are implemented and correct (backend/app/services/research_eval/ranking_metrics.py:8-30; precision_at_1/precision_at_3/recall_at_3 aggregated at :61-80).
- A top-N result cap and score-based ranking exist (backend/app/services/therapeutic/evaluate.py:450-454 and :573-602) — the cap mechanism is present (value differs from spec, see D3-07).
- MCS is gated behind ENABLE_SPEC_MCS and runs only post-HITL confirmation and after mandatory filters, never auto-substituting (backend/app/core/config.py:43; backend/app/services/therapeutic/mcs.py:54-63; backend/app/services/therapeutic/evaluate.py:322-334) — consistent with the decision-support ethos.
- Per-component score contributions plus a LIME-style feature attribution are surfaced as a rule-based explanation to the pharmacist (backend/app/services/therapeutic/feature_xai.py:17-67; backend/app/services/therapeutic/evaluate.py:84-111) — a reasoning trail exists, though not in the approved weighted form (see D3-09).
- A DQ2 rules_only vs rules_plus_mcs A/B evaluation harness and gold-standard storage exist and persist runs (backend/app/services/research_eval/service.py:206-280) — the evaluation scaffold is present (its MCS condition is a proxy, see D3-03).

**D4-knowledge-graph — Knowledge graph / catalogue**
- All three approved data sources are genuinely ingested: FDA NDC (build_index ingest, meta.stats ndc=132824), DrugBank XML (ingest_drugbank, drugbank=4953), and OpenFDA SPL labels (ingest_spl_full, spl=255904) - satisfying the 'OpenFDA + DrugBank' source coverage of Deliverable C.
- DrugBank identity partially contributes: medicines.drugbank_id is populated for 4,952 of 41,020 medicines (build_index.py:451-459, 504-513).
- The spec's Strength, Route, Dosage Form, and NDC Product concepts all exist as persisted catalogue data (products.strength / route / dosage_form / product_ndc; strengths table; medicines.routes/dosage_forms JSON) - build_index.py:131-148 - even though they are relational columns rather than graph nodes.
- Some salt/base 'salt-aware' intent is preserved at the matching layer via salt_normalisation.resolve_moiety and product_candidates.retrieve_same_moiety_product_candidates, so the salt-awareness concept is present (for the ~16 curated moieties) rather than wholly absent.

**D5-rag — RAG & evidence retrieval**
- OpenFDA regulatory grounding (half of O4): retrieval draws on real OpenFDA SPL label text — the build ingested 255,904 SPL labels into 136,167 label_sections rows (data/medicine_catalog.sqlite3 meta stats; build_index.py:561-694).
- Groq model id is configured exactly as specified: GROQ_MODEL='llama-3.3-70b-versatile' (config.py:48; rag_evidence.py:178,202).
- Groq temperature is 0.0 as specified (rag_evidence.py:179-180 body temperature 0.0; echoed at :204).
- Evidence-grounding intent is enforced in the LLM prompt: summarise ONLY retrieved excerpts, do not invent, say so if insufficient (rag_evidence.py:167-171), and the pipeline refuses to call Groq when no excerpts exist, returning INSUFFICIENT_EVIDENCE (evaluate.py:385-391, 587-593).
- drug_interactions — the section the brief specifically flagged — IS ingested (build_index.py:47; 5,469 FDA_SPL rows in label_sections), so 6 of the 7 named sections are present.
- Retrieval is active by default: ENABLE_SPEC_RAG=True (config.py:44) and retrieve_label_excerpts runs against the real catalogue on every evaluation (evaluate.py:377,581).
- The source-medicine evidence retrieval honours Top-5 (evaluate.py:585).
- A DQ3 evaluation harness and API/UI exist (research_eval/service.py:run_dq3_rag_evaluation; frontend ResearchEvaluationPanel.tsx 'DQ3 — RAG' tab), providing the scaffolding to compute retrieval-quality metrics once the real FAISS/MiniLM/BERTScore components are wired in.

**D6-xai — XAI / explainability**
- A10 (XAI placement moved inline into Step 4): feature attribution is rendered inline within each candidate card, not on a separate navigation page — frontend/src/components/TherapeuticAlternativesPanel.tsx:315-322; the attribution is produced unconditionally per candidate in backend/app/services/therapeutic/evaluate.py:375 and :519.
- Source attribution cards embedded inline (A8): FDA SPL / catalog label excerpts are retrieved and shown inline as evidence cards with source and section — frontend/src/components/TherapeuticAlternativesPanel.tsx:323-331; backend/app/services/therapeutic/rag_evidence.py:112-123.
- A per-feature contribution breakdown exists over the weighted scoring components (the substance of feature attribution) — backend/app/services/therapeutic/scoring.py:43-52 and backend/app/services/therapeutic/feature_xai.py:24-54.
- DQ4 controlled A/B/C explanation conditions (Minimal / XAI / XAI+provenance) are implemented in the backend with counterbalanced ordering to support the study design — backend/app/services/research_eval/xai_conditions.py:87-134 and backend/app/services/research_eval/service.py:379-401.
- Honest interpretability disclaimers are attached (XAI explains the scoring components, not therapeutic correctness/interchangeability) — backend/app/services/therapeutic/feature_xai.py:11-14 and backend/app/services/research_eval/xai_conditions.py:33-36.

**D7-evaluation — Evaluation harness (DQ1–DQ4)**
- WER and CER are implemented with the spec-correct formulas: word-level Levenshtein / reference word count and character Levenshtein / reference length, with documented normalisation (lowercase, whitespace collapse, punctuation strip). Verified in backend/app/services/research_eval/ocr_metrics.py:25-38 and unit-tested (backend/tests/test_research_evaluation.py:46-56).
- Precision@K and Recall@K are implemented with spec-consistent denominators: P@K = hits/k and R@K = |top_k ∩ relevant| / |relevant| (all valid gold candidates). Verified in backend/app/services/research_eval/ranking_metrics.py:8-25 and tested (test_research_evaluation.py:95-101).
- P@3 and R@3 (K=3) are the reported headline recommendation metrics, matching the spec DQ2 targets' K. Verified in backend/app/services/research_eval/service.py:265 and ranking_metrics.py:61-63.
- BERTScore is a genuine, integrated dependency (bert_score BERTScorer, distilbert-base-uncased) — declared in backend/requirements-bertscore.txt, installed by backend/Dockerfile and enabled via docker-compose.yml ENABLE_BERTSCORE='true'; the scoring implementation is real (backend/app/services/analytics/bertscore_optional.py:33-68). (It is applied to the wrong text pair for DQ3 — see D7-02 — but the technology itself is present and functional.)
- DQ4 statistics are descriptive only (mean, standard deviation, min, max, n), matching B3 'descriptive statistics only'. Verified in backend/app/services/research_eval/service.py:459-474.
- No study results are hard-coded: claim_143_or_10_status returns NOT_VERIFIABLE unless real stored counts reach 143/10, and metric_envelope returns value=None for any non-AVAILABLE metric so unavailable metrics are never shown as zero. Verified in backend/app/services/research_eval/metric_status.py:32-60 and tested (test_research_evaluation.py:172-181).
- Survey responses are anonymised: only participant pseudonyms are stored, and identity fields (name/email/registration/workplace/ip) are stripped on both submit and import. Verified in backend/app/services/research_eval/service.py:426-429 and import_dataset.py:147-149; questionnaire_version defaults to spec value '1.2' (models/research_eval.py:168).
- An Evaluation Dashboard with the spec's tabbed structure exists: DQ1 shows WER/CER alongside pharmacist ground-truth (Tab 1 intent), DQ2 shows Precision@K/Recall@K and DQ3 exposes a BERTScore F1 slot (Tab 2 intent), plus a DQ4 survey tab and snapshot/CSV/JSON export. Verified in frontend/src/components/ResearchEvaluationPanel.tsx:302-654 and backend/app/api/v1/research_eval.py:371-424.
- Immutable evaluation snapshots with provenance (ground-truth version, catalogue version, git commit, counts, results_json) are supported for reproducibility. Verified in backend/app/models/research_eval.py:50-69 and service.py:541-549.

**D8-platform-governance — Platform, deployment & governance**
- A6 safety statement: the 'decision-support only / not clinical care / not autonomous' designation is present and pervasive in both the UI and the API - e.g. frontend/src/components/AppShell.tsx:24, frontend/src/pages/AnalyzerPage.tsx:432, frontend/src/pages/AdminPortalPage.tsx:314-316, backend/app/main.py:102-103, backend/app/services/readiness.py:60.
- Out-of-scope boundary (DDI engine) respected: no drug-drug interaction / RxNorm / SIDER logic exists in backend/app (grep for rxnorm|sider|ddi|interaction over app/ returns no matching engine), matching the spec's 'explicitly NOT planned for MVP'.
- Out-of-scope boundary (automated RAG index rebuilding) respected: no scheduler/cron/APScheduler/Celery/@repeat_every exists in backend/app; index building is a manual CLI (app.services.datasets.build_index), matching 'Automated RAG index rebuilding pipeline' being out of MVP scope.
- Questionnaire kept external and anonymous: the research questionnaire is not embedded in the app; docs/RESEARCH_QUESTIONNAIRE_GUIDE.md:6,35 confirm the v1.2 instrument is delivered via Microsoft Forms (n=5 pharmacists, ethics 18274), consistent with A6's anonymous Microsoft Forms collection.
- Synthetic-data / temporary-image handling aligns with consent copy: prescription images are marked encrypted and purged on cancel/confirm/retention-window (backend/app/models/prescription.py:41 encrypted default True; backend/app/services/retention.py:23-108; startup purge in backend/app/main.py:20-34), matching consent statement 14 (research_content.py:115).
- PII minimisation for research exports is enforced: research exports forbid names/emails/registration IDs/IP/workplace (backend/app/core/research_content.py:65; backend/app/services/research_eval/service.py:426; backend/app/services/research_eval/import_dataset.py:148), and no email addresses are collected (backend/app/schemas/auth.py:23) - supporting the anonymisation intent of A6.
- Ethics identifiers embedded and versioned: ethics application 18274, five pharmacist participants, and the 25-30 synthetic-sample study design are reflected in the app's PIS/Consent content (backend/app/core/research_content.py) and manifest (docs/approved-specification/specification_manifest.json:11,19-24).
- The project's own governance docs candidly flag the platform divergence rather than falsely claiming conformance (docs/specification_traceability_matrix.md:42 R27 'Conflicting'; docs/approved_design_vs_implemented_artefact.md:50; specification_manifest.json:18) - the self-assessment corroborates the deviations rather than overstating completeness.
