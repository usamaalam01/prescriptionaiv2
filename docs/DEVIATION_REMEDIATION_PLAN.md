# PharmaAssist — Deviation Remediation Plan (gated, one unit at a time)

Companion to [`SPEC_CONFORMANCE_AUDIT.md`](SPEC_CONFORMANCE_AUDIT.md). This plan sequences the
**active** deviations into small work-units that are cleared **one at a time**, each with an
explicit *done → validate → test → gate* definition. Nothing moves to the next unit until you
approve.

## Progress

| Done | Unit | Result |
|---|---|---|
| ✅ | **U1 — semantic FAISS RAG (DQ3 path)** | Cleared **D5-rag-08**; partial **D5-rag-06 / D5-rag-02**. 2 validation passes (the 2nd, adversarial, found + fixed 3 defects incl. a real metric-comparability bug). Activate with `ENABLE_SEMANTIC_RAG=true`. |
| ◑ | **U2 — real BERTScore in DQ3 (mechanism only; D7-02 still OPEN)** | Removed the **fabricated-`None`** (real, deterministic, gated metric; P/R/F1 surface + persist) — an integrity fix. **But the spec metric is in-substance unmet:** the explanation embeds its evidence → score is *circular* (F1 ≈ 0.92 contained vs ≈ 0.77 independent); reference truncated at ~512 tokens (0.91→0.47 if match buried); spec's *generated-vs-independent-label* needs Groq (off) + ≥0.80 threshold (U12). **Both substantive halves deferred → D7-02 / D7-V1 remain OPEN.** Two independent validations. Activate with `ENABLE_BERTSCORE=true`. |
| ◑ | **U10 — real SHAP + LIME + dashboard (substantially addressed)** | Real `shap`/`lime` over the additive score, **reconciled with exact `w·x`** (~1e-14); pure-SVG SHAP/LIME dashboard. Was **not** U5-blocked. **2nd (adversarial) validation found + FIXED a defect:** product-candidate bars summed to base not `base+mcs_bonus` (now include an `mcs_structural_bonus` bar → bars sum to displayed score). **Remaining polish (not literal B4):** one accordion+2 SVG sections not 3 tabs; libs default OFF (analytical bars shown by default). Activate with `ENABLE_SPEC_SHAP`/`ENABLE_SPEC_LIME=true`. |

**Recommended next:** **U3 — resolve the fabricated DQ1 harness** — the *other* critical fabricated-metric
integrity item. It's a **Decision** (drop DQ1 vs wire it to Google Vision), so it needs your call first —
see the Decision Register. *(Note: fully closing D7-02 is now folded into the deferred RAG/Groq unit —
an independent LLM narrative removes the circularity.)*

*(Deployment note: HF-Spaces deploy is **paused** — HF now gates Docker Spaces behind PRO; the Neon DB +
runtime artefacts are staged and the app is deploy-ready for any container host. Unrelated to the units below.)*

## Scope

- **Accepted / out of scope** (per your decisions): the entire **OCR** dimension (D1 — Vision-primary,
  TrOCR bolt-on, mock fallback, etc.) and the **Streamlit → React+FastAPI+Postgres+Docker platform**
  change incl. no Hugging-Face-Spaces deployment (D4-05, D8 architecture/deployment, D2 React-not-Streamlit).
- **In scope:** the remaining **7 critical + 23 major** deviations. Moderate/minor (37 + 6) are a final sweep.

## How we work each unit (the gate protocol)

1. **Kickoff** — I restate the unit's goal, acceptance criteria and test plan; you say *go*.
2. **Implement** — smallest coherent change, on a feature branch (`fix/<unit-id>`).
3. **Self-validate** — app imports, `alembic`/migrations clean if touched, `/health` + `/ready` green.
4. **Test** — a concrete check (unit test, API call, or harness run) with output shown to you.
5. **Record** — tick this plan's tracking table + update the finding's status in the audit doc.
6. **Gate** — you review and approve → next unit. No unit starts without your go-ahead.

## Two conformance routes (chosen per unit)

- **Fix** — make the code do what the spec says.
- **Re-document** — record the divergence as an *approved design change* (the legitimate route the
  spec itself used in A10), with rationale + supervisor sign-off. Cheaper; valid when the as-built
  choice is defensible. Some units are a **Decision** between the two — flagged in the Decision Register.

---

## Phase A — RAG + evaluation integrity (start here)

*Highest value: you asked to bring RAG, and it unlocks the DQ3 integrity items. Also resolves the
fabricated-metric problems, which are the only non-negotiable fixes.*

### U1 — Bring real semantic FAISS RAG from the old project ✅ DONE (DQ3 path)
- **Actually cleared:** **D5-rag-08** (orphaned artefacts now loaded/queried). **Partial:** **D5-rag-06**
  (DQ3 `faiss` arm now real MiniLM + `IndexFlatL2` over the OpenFDA corpus — BERTScore still pending → U2)
  and **D5-rag-02** (MiniLM wired for DQ3 *query* embedding — production build+query still pending → U1b).
  **NOT cleared (deferred → U1b):** **D5-rag-01** (crit, production path still keyword) and **D5-rag-04**
  (512/50 token chunking + ~1.37M corpus — U1 reuses the legacy ~10k dev index, no re-chunk). **Route:** Fix.
- **As-built (delivered):** added `faiss-cpu==1.9.0.post1` + `sentence-transformers==3.3.1` +
  `huggingface_hub==0.27.1` to `backend/requirements.txt`; new
  `research_eval/semantic_retriever.py::SemanticFaissSplRetriever(EvidenceRetriever)` with an
  `@lru_cache` singleton loader (+ HF self-heal) reading `data/rag_index.faiss` + `rag_chunks.pkl` and
  embedding queries with `all-MiniLM-L6-v2`; `ENABLE_SEMANTIC_RAG` flag + `rag_*_path()` resolvers; DQ3
  `run_dq3_rag_evaluation` now loads the real 10k corpus (`_load_dq3_corpus`) and routes the `faiss`
  condition through the semantic retriever (`_build_faiss_condition`), with graceful fallback to the toy
  retriever + 2-row demo corpus when the flag is off. **Production `therapeutic/rag_evidence.py` was left
  untouched** (scope-limited to DQ3, per the U1 plan) — hence D5-rag-01 remains open.
- **Validated (all pass):** app imports flag-on/off; retriever smoke (10k vectors, dim 384, descending
  scores); DQ3 e2e (keyword+faiss over real corpus, 0/5 top-5 overlap across 3 clinical queries — semantic
  surfaces on-target chunks keyword misses; `citation_coverage=1.0`); flag-off fallback (2-row demo + toy);
  `/health`+`/ready` 200 with catalog 41,020 intact; existing `test_research_evaluation.py` 16/16 green.
- **2nd (adversarial) validation — 3 defects found & fixed:** (1)+(2) the keyword condition inherited the
  legacy `chunk_id` (=`"0"` for ~69% of rows), giving non-unique, substring-collidable citation ids that
  silently inflated `citation_coverage` for the keyword arm only — so the two DQ3 conditions were **not
  metric-comparable**. Fixed: `_load_dq3_corpus` now assigns unique `chunk-{i}` ids aligned to the semantic
  retriever's scheme (both arms verified to resolve to the same corpus rows). (3) `top_k<=0` crashed the
  retriever (faiss `assert k>0`); fixed with a guard. Accepted (safe-but-degraded, → U1b): lru_cache
  cold-start race, prefix-based dedup, toy-retriever fallback over 10k when deps fail.
- **Activate:** set `ENABLE_SEMANTIC_RAG=true` in `new/.env`. **Effort:** L–XL (~2 GB deps). **Deps:** none.
- **Follow-up (U1b):** production wiring in `rag_evidence.py` + a **spec-compliant rebuild** (512-token/
  50-overlap chunker, catalogue-keyed) against the new catalogue's `label_sections` (41,020 medicines) —
  this is what closes D5-rag-01/02/04. The shipped index is the old ~10k-chunk **dev** index.

### U2 — Compute real BERTScore in DQ3 ◑ PARTIAL (mechanism done; reference semantics open)
- **Effect:** removes the *fabricated-`None`* (real metric now computes) and **finishes D5-rag-06**
  (with U1). **Does NOT fully clear D7-02 / D7-V1** — see the circularity limitation below.
  **Route:** Fix. **Deps:** U1 ✅.
- **⚠ Limitations found across TWO independent adversarial validations of U2:**
  1. *Circular reference:* `build_explanation_from_evidence` embeds the retrieved evidence verbatim, so
     BERTScore(explanation, evidence) is overlap-inflated — F1 ≈ 0.92 (hypothesis contains reference) vs
     ≈ 0.77 (independent paraphrase). Spec (B3/A9) wants *generated explanation vs an independent
     reference OpenFDA label* — **both** the hypothesis (needs a Groq LLM narrative, `ENABLE_SPEC_GROQ`
     off) and the reference (independent label) are non-spec. Folded into the deferred **RAG/Groq unit**.
  2. *512-token truncation:* the DistilBERT scorer truncates at ~512 tokens (measured F1 0.91→0.47 when
     the match is buried past the limit). U2 now caps the reference to a defined ~1800-char window so the
     truncation is explicit, not silent.
  3. *Threshold:* the B3 ≥ 0.80 acceptance gate is **U12**.
  **Net:** U2 removes the *fabrication* only; the DQ3 BERTScore as specified is still produced by no code
  path → **D7-02 / D7-V1 remain open** (not "finished").
- **As-built (delivered):** new `_compute_bertscore_for_condition(explanation, evidence, metrics)` in
  `service.py` calls the existing `analytics/bertscore_optional.score_pairs` — **hypothesis** = the
  generated explanation, **reference** = the concatenated retrieved FDA-SPL evidence. Replaces the
  hard-coded `bertscore_precision/recall/f1 = None`. Availability is honest per condition:
  `AVAILABLE` (scored), `NOT_CALCULATED` (no evidence → the `none` arm), `DEPENDENCY_UNAVAILABLE`
  (flag off / package missing / scorer failed). Also fixed a latent bug: the `bertscore_f1`
  `metric_envelope` passed no `value=`, so a computed F1 would never surface in the API response.
  `bert-score==0.3.13` installed (DistilBERT scorer, CPU, no baseline rescale).
- **Validated (all pass):** with `ENABLE_BERTSCORE=true` — `keyword` F1 = 0.8036, `faiss` F1 = 0.7878
  (real, in [0,1]), `none` = `NOT_CALCULATED`; deterministic re-run matches (0.7878 == 0.7878). Flag
  off → all `None`/unavailable, no compute, no crash. `test_research_evaluation.py` 16/16 green.
- **Activate:** `ENABLE_BERTSCORE=true` (+ `ENABLE_SEMANTIC_RAG=true` for real corpus). **Effort:** L.

### U3 — Resolve the fabricated DQ1 harness *(Decision)*
- **Clears:** D7-01 / D1-03 (crit — integrity). **Route:** Decision.
- **Since OCR is accepted, pick one:**
  - **(a) Drop DQ1** — delete `simulate_engine_outputs`/`_apply_char_noise` from the evaluated path,
    guard/remove the endpoint, and document "DQ1 not evaluated — OCR accepted as operational." *(S)*
  - **(b) Keep DQ1 real** — wire the harness to the accepted **Google Vision** engine to produce real
    WER/CER (note: measures Vision, not TrOCR). *(M)*
- **Test:** no fabricating code remains in the evaluated path; either the endpoint is gone/guarded, or
  it emits real metrics over a labelled sample.

---

## Phase B — Therapeutic equivalence & chemistry chain

*Reprioritised: **U-TE (FDA Orange Book)** now leads this phase and precedes the MCS chain (U4–U5).*
*Rationale: therapeutic equivalence is a **regulatory determination**, not a chemical inference. The*
*supervisor validated that NDC + DrugBank + SPL do not encode it; the Orange Book `products.txt`*
*`TE_Code` does. Orange Book therefore becomes the **authoritative backbone** for DQ2 / therapeutic*
*matching, and the RDKit-MCS work (U4/U5) is demoted to a **supporting chemical signal**, not the*
*basis of the equivalence claim (which directly resolves the R28 "MCS ≠ regulatory TE" honesty gap).*

### U-TE — FDA Orange Book therapeutic-equivalence layer *(new — leads Phase B)*
- **Clears / reframes:** the core of the **D3 recommendation cluster** as it relates to *therapeutic
  equivalence* — reframes **D3-02 (crit, MCS-as-equivalence)** and the R28 honesty gap, and provides the
  missing **DQ2 gold standard** behind **D7-03 / D7-04** (relevant set = A-rated products in the same
  pharmaceutical-equivalence group). **Route:** Fix (+ a Decision-lite: scope-addition doc, A10-style,
  since the approved spec named RDKit-MCS, not Orange Book).
- **What it is:** the FDA *Approved Drug Products with Therapeutic Equivalence Evaluations* dataset at
  `new/data/orange/` — `products.txt` (48,501 rows, 2,739 ingredients; **key file**), plus secondary
  `patent.txt` / `exclusivity.txt` (availability/expiry, **not** equivalence).
- **TE model to encode:** group by **Ingredient + Dosage Form + Route + Strength** (pharmaceutical-
  equivalence group) against the **RLD/RS** reference; then:
  - `A*` code ⇒ therapeutically equivalent / substitutable (21,784 rows);
  - `B*` code ⇒ **not** equivalent (69);
  - empty ⇒ single-source / innovator, no equivalence to assert (26,649 ≈ 55%);
  - **subletter is safety-critical:** `AB1 ≠ AB2 ≠ AB3` — substitute **only within the same subletter**;
  - **filter `DISCN`** (23,060 discontinued) out of live recommendations.
- **Approach (planning only — no code yet):**
  1. Ingest `products.txt` (+ patent/exclusivity) into new read-only tables in `medicine_catalog.sqlite3`
     keyed on `Appl_No` + `Product_No`, retaining `TE_Code`, `RLD`, `RS`, `Type`, `Appl_Type`.
  2. **Crosswalk to the catalogue** — the catalogue has **no `Appl_No`/`TE_Code`**, so bridge by either
     **(a)** normalised **Ingredient + Dosage Form + Route + Strength** (needs unit/vocabulary
     normalisation: OB `500MG` vs NDC-style `2 mg/1`; `DF;Route` vs split columns), or **(b) precise**
     `product_ndc` → NDC dataset `application_number` → OB `Appl_No` (requires re-ingesting
     `application_number`, which the catalogue did not retain).
  3. Make the recommendation engine **surface the FDA TE code** as the primary equivalence determinant
     (with the subletter rule + DISCN/RX filter); MCS/9-component score become supporting signals.
  4. Use the OB A-group as the **DQ2 gold standard** for Precision@K / Recall@K.
- **Validate:** ingest is read-only and idempotent; `/health` + `/ready` catalog stay green; TE tables
  queryable; a known group (e.g. METFORMIN 500MG TABLET;ORAL) returns its RLD + A-rated generics with
  correct subletter separation.
- **Test:** crosswalk match-rate report (how many catalogue medicines resolve to an OB group); a sample
  recommendation shows the FDA TE code + reference; a `DISCN`/empty-TE case correctly reports "no A-rated
  equivalent".
- **Effort:** L–XL (ingest S–M; crosswalk normalisation M; engine wiring M; DQ2 gold standard S).
  **Deps:** none (independent of U4/U5; those become supporting once this lands).
- **Recommendation:** run a **read-only crosswalk feasibility probe** at kickoff to size the join before
  committing to strategy (a) vs (b).

### U4 — Ingest chemical structures (SMILES) into the catalogue
- **Clears:** D3-04 (major), D4-04 (major). **Route:** Fix.
- **Approach:** add a `smiles` (+`inchikey`) column to `medicines`; populate from DrugBank structures in
  the catalogue build; rebuild `medicine_catalog.sqlite3` (or ship a supplementary structures table).
- **Test:** ≥ N medicines have non-null `smiles`; sample lookups return a structure.
- **Effort:** L. **Deps:** none (prerequisite for U5).

### U5 — Install RDKit + make MCS a real matching signal
- **Clears:** D3-02 (crit), D3-03 (major). **Route:** Fix. **Deps:** U4.
- **Approach:** move `rdkit` into `requirements.txt`; make `compute_mcs_similarity` gate/feed the
  scorer (atom_coverage ≥ 0.9 per A8, or +20 into the metadata score per B4); drive DQ2's
  `rules_plus_mcs` from a real coverage result.
- **Test:** `compute_mcs_similarity` returns atom_coverage for two known SMILES; DQ2 `rules_plus_mcs`
  differs from `rules_only`.
- **Effort:** L.

### U6 — Data-driven salt-awareness
- **Clears:** D3-10 (major), D4-03 (major). **Route:** Fix.
- **Approach:** derive salt/base equivalence from DrugBank salt data instead of the hardcoded
  ~16-ingredient `_MOIETY_FORMS` dict.
- **Test:** salt normalisation covers materially more than 16 ingredients from real data.
- **Effort:** M.

### U7 — Eligibility threshold *(Decision-lite)*
- **Clears:** D3-06 (major). **Route:** Fix or Re-document.
- **Approach:** add a configurable min-score threshold (spec ≥70), or document that hard filters replace it.
- **Test:** a candidate below threshold is excluded from results.
- **Effort:** S.

---

## Phase C — Scoring & knowledge-graph *(Decisions)*

### U8 — Reconcile the similarity score *(Decision)*
- **Clears:** D3-01 (crit). **Route:** Decision.
  - **Reconcile:** implement spec `0.4·Strength + 0.4·Metadata + 0.2·FormRoute`. *(M)*
  - **Re-document:** keep the 9-component "Evidence Match" model as an approved improvement. *(S)*
- **Recommendation:** re-document (the 9-component model is more defensible) — supervisor call.

### U9 — Knowledge graph *(Decision)*
- **Clears:** D4-01 (crit), D3-05 (major), D4-02 (major). **Route:** Decision.
  - **Build:** add `networkx`, construct the 6-node/5-edge DiGraph over the catalogue, traverse it in
    candidate search. *(XL)*
  - **Re-document:** record the relational-catalogue model as an approved substitute (like the platform change). *(S)*
- **Recommendation:** re-document unless a graph adds real capability — supervisor call.

---

## Phase D — Explainability

### U10 — Real SHAP + LIME + Explainability Dashboard ✅ DONE
- **Cleared:** D6-xai (crit), D6 SHAP-never-fires, D6 LIME-absent, D6 feature-mismatch, D8 LIME-dep.
  **Route:** Fix (hybrid — exact additive breakdown as ground truth + real spec-named libraries).
- **Correction to earlier plan:** the "**Deps: U5 (molecular feature)**" assumption was **wrong** — the
  live Evidence Match Score is a 9-feature additive model with **no MCS feature**, so U10 was *not*
  blocked. Verified against `scoring.py:WEIGHTS`.
- **As-built (delivered):**
  - `research_eval/xai_real.py` — real `shap.Explainer` + `lime.lime_tabular` over the additive score
    fn, with a **reconciliation** that asserts library SHAP == exact analytical `w_i·x_i`
    (verified `reconciled`, max residual ~1e-14). Flag-gated (`ENABLE_SPEC_SHAP`/`ENABLE_SPEC_LIME`)
    with graceful analytical fallback; never raises into a request.
  - `therapeutic/evaluate.py` — `_real_xai_for_score` attaches a `real_xai` block to each **ranked**
    candidate (both Path A products + Path B different-ingredient). Verified end-to-end (Amoxicillin →
    5 alternatives, Doxycycline carries populated `real_xai`).
  - `frontend/.../TherapeuticAlternativesPanel.tsx` — **Explainability** accordion with **pure-SVG**
    signed bar charts (no chart dep) for SHAP + LIME, a reconciliation chip, library labels, and the
    honesty disclaimer. `npm run build` clean.
  - deps: `shap==0.46.0`, `lime==0.2.0.1` (sklearn/numpy/scipy already present).
- **Validated (2 passes; 2nd was adversarial):** SHAP reconciles to exact attribution (~1e-14, exact
  explainer); LIME keys are bare feature names (not condition strings); flag-off → analytical fallback,
  app healthy; frontend builds; backend suites **37 passed / 2 pre-existing failures (unrelated)**.
- **⚠ Defect found in 2nd validation & FIXED:** product-candidate SHAP/LIME bars summed to the *base*
  score, not the displayed `base + mcs_bonus` (mismatch up to +15). Fixed by injecting an explicit
  `mcs_structural_bonus` feature (value 1.0, weight = bonus pts) so bars sum to the displayed score
  (re-verified 62==62, still reconciled).
- **Remaining B4-literal polish (tracked, not claimed done):** (1) one Explainability accordion + two
  SVG sections rather than the spec's 3 tabs "SHAP | LIME | FDA Sources" with exact chart titles (FDA
  Sources is a separate provenance accordion); (2) `ENABLE_SPEC_SHAP/LIME` default OFF, so the *library*
  path + reconciliation run only when enabled (analytical bars shown by default).
- **Not in scope:** the MCS feature itself (U5) and the 9-feature model (U8 decision). **Effort:** XL.

---

## Phase E — Evaluation harness correctness & data

### U11 — DQ2 fed by real engine output
- **Clears:** D7-03 (major). **Deps:** Phase B. **Approach:** build DQ2 `retrieved_ranked` from the
  actual recommendation engine, not a re-sorted pharmacist list. **Test:** ranking traces to engine. **Effort:** M.

### U12 — Encode approved acceptance thresholds
- **Clears:** D7-04 (major). **Approach:** encode WER<15%, CER<10%, P@3≥0.70, R@3≥0.60, BERTScore≥0.80 as
  pass/fail in the harness + UI. **Test:** harness reports pass/fail vs each threshold. **Effort:** S.

### U13 — Evaluation dataset (synthetic Rx images + ground truth)
- **Clears:** D7-09 (major). **Route:** Data (needs your input). **Approach:** add the spec's 25–30
  synthetic handwritten prescriptions + GT so DQ1/DQ2 can actually run. **Test:** N images present;
  a DQ run consumes them. **Effort:** M (data-dependent).

---

## Phase F — Features & governance

### U14 — "Direct Drug Search" use case (B1 UC2)
- **Clears:** D2 Direct-Drug-Search (major). **Approach:** add a pharmacist entry point to pick a
  DrugBank ingredient → confirm → image-free session → `/therapeutic-alternatives/evaluate`.
  **Test:** end-to-end direct search yields provenance-tagged recommendations. **Effort:** L.

### U15 — Evaluation Dashboard access for pharmacists *(Decision-lite)*
- **Clears:** D8 reviewer-only-dashboard (major). **Approach:** grant pharmacist access per spec, or
  document the reviewer-gating as intentional. **Test:** pharmacist can/can't per decision. **Effort:** S.

### U16 — Ethics / PII posture *(Decision — sensitive)*
- **Clears:** D8 A6 PII/consent (major). **Route:** Re-document + consent alignment. **Approach:** the
  app now stores usernames + consent (spec A6 said "no PII"); document the change, confirm the consent
  form covers account data, ensure ethics sign-off. **Test:** governance record + consent copy updated. **Effort:** S.

---

## Phase G — Moderate / minor sweep (later)

Batch the 37 moderate + 6 minor (mostly config defaults, wording, route scope) once the above land.
Full list in the audit doc's tables.

---

## Decision Register (need your / supervisor call before those units)

| Unit | Decision |
|---|---|
| U-TE | Crosswalk strategy — normalised Ingredient+Form+Route+Strength **(a)**, **or** precise NDC→`application_number`→`Appl_No` **(b)** (requires NDC re-ingest)? Plus: document Orange Book as an approved scope addition (A10-style), since the spec named RDKit-MCS. |
| U3 | Drop DQ1, **or** keep it real over Google Vision? |
| U7 | Add ≥70 threshold, **or** document hard-filter approach? |
| U8 | Reconcile to spec 3-component score, **or** re-document the 9-component model? |
| U9 | Build a NetworkX graph, **or** re-document the relational catalogue? |
| U15 | Give pharmacists the Evaluation Dashboard, **or** keep reviewer-only? |
| U16 | Ethics/PII re-documentation + consent alignment (supervisor sign-off). |

## Tracking

| Unit | Clears | Route | Effort | Status |
|---|---|---|---|---|
| U1 RAG (semantic FAISS) | D5-rag-08 ✅; D5-rag-06/02 *partial* (BERTScore→U2; prod→U1b); D5-rag-01/04 deferred→U1b | Fix | L–XL | ✅ **done — validated (DQ3 path)** |
| U2 Real BERTScore | removes fabricated-`None` (mechanism). D7-02/D7-V1 **still OPEN** — circular ref + threshold both → RAG/Groq unit + U12 | Fix | L | ◑ **mechanism only — 2× validated** |
| U3 DQ1 fabrication | D7-01/D1-03 | Decision | S/M | ☐ |
| **U-TE Orange Book TE layer** | D3-02 (reframe), R28, DQ2 gold std (D7-03/04) | Fix + Doc | L–XL | ☐ *(leads Phase B)* |
| U4 SMILES ingest | D3-04, D4-04 | Fix | L | ☐ *(now supporting)* |
| U5 RDKit MCS | D3-02, D3-03 | Fix | L | ☐ |
| U6 Salt-awareness | D3-10, D4-03 | Fix | M | ☐ |
| U7 Threshold | D3-06 | Fix/Doc | S | ☐ |
| U8 Score formula | D3-01 | Decision | S/M | ☐ |
| U9 Knowledge graph | D4-01, D3-05, D4-02 | Decision | S/XL | ☐ |
| U10 SHAP/LIME + dashboard | D6-xai (crit) + SHAP/LIME/feature-mismatch + D8 LIME-dep | Fix | XL | ◑ **substantially addressed — 2× validated (defect fixed; B4-literal polish remains)** |
| U11 DQ2 real engine | D7-03 | Fix | M | ☐ |
| U12 Eval thresholds | D7-04 | Fix | S | ☐ |
| U13 Eval dataset | D7-09 | Data | M | ☐ |
| U14 Direct Drug Search | D2 UC2 | Fix | L | ☐ |
| U15 Dashboard access | D8 reviewer-only | Fix/Doc | S | ☐ |
| U16 Ethics/PII | D8 A6 | Re-document | S | ☐ |
| Phase G | 37 moderate + 6 minor | mixed | — | ☐ |

## Remaining critical deviations (snapshot)

| Crit | Unit | Blocking status |
|---|---|---|
| D7-02 / D7-V1 (BERTScore) | U2 + RAG/Groq | Fabrication removed ✅; spec metric OPEN (needs independent LLM narrative + U12 threshold) |
| D7-01 / D1-03 (fabricated DQ1) | **U3** | **Ready — needs a Decision (drop DQ1 vs run over Google Vision)** |
| D3-02 (MCS = TE) | U-TE / U5 | Reframed by Orange Book; needs U-TE crosswalk decision |
| D3-01 (score formula) | U8 | Decision (reconcile vs re-document) |
| D4-01 (knowledge graph) | U9 | Decision (build vs re-document) |
| D6-xai (SHAP/LIME) | U10 | Fix, XL; deps U5 |
| D5-rag-01 (production RAG) | U1b | Deferred (production wiring + spec chunked rebuild) |

**Recommended next unit → U3 (fabricated DQ1 harness).** Rationale: it's the *only remaining
critical that is fully ready to start* (no dependency, no rebuild, no external data) and it removes the
last **fabricated-metric integrity** problem — the highest-value class, and the same class U2 just
addressed. It needs one small **decision** from you (drop DQ1 vs wire to Google Vision) — see the
Decision Register. Everything else critical is either a bigger Decision (U8/U9), depends on the
Orange-Book crosswalk call (U-TE), or is XL/deferred (U10/U1b).
