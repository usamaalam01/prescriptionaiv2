# U10 — Real SHAP + LIME + Explainability Dashboard (D6-xai, critical)

## Goal & scope
Make the therapeutic-alternative score explainable with the **spec-named SHAP and LIME libraries**
(D6-xai: spec named `shap`/`lime`; app ships a bespoke method and the libraries are absent), and expose
it in a **React dashboard**. Route = **Fix (hybrid)**: keep the exact analytical additive breakdown as
ground truth, add the real libraries alongside, and *prove they reconcile*.

## Key finding (de-risks the unit)
The live **Evidence Match Score** (`therapeutic/scoring.py:WEIGHTS`) is a **9-feature additive** model
(`indication_relationship` 35, `atc_or_therapeutic_class` 15, `mechanism_relationship` 10,
`target_or_pathway` 5, `route_compatibility` 10, `dosage_form_compatibility` 5,
`patient_population_compatibility` 10, `contraindication_warning_assessment` 5,
`interaction_assessment_coverage` 5). **None is the molecular/MCS feature** — so U10 does **NOT** depend
on U5 (RDKit) as the plan previously assumed. The dashboard explains the real, shipping 9-feature score.

## Approach

### 1. Dependencies — `backend/requirements.txt`
- `shap` and `lime` (move `shap` out of the optional file; add `lime`; both feature-gated so the app
  still runs if they fail to import).
- Frontend: add a **charting** approach. Prefer **pure-SVG bars** (no dep) to keep the bundle light and
  avoid a new supply-chain item; only add `recharts` if the design needs it. (Decision: SVG first.)

### 2. Real SHAP/LIME over the 9-feature score — `research_eval/xai_conditions.py` (or a new `xai_real.py`)
- Define the additive score as a plain callable `f(x) -> score` over the 9 features + weights.
- **SHAP:** `shap.Explainer` (LinearExplainer/exact for an additive model) → per-feature SHAP values.
- **LIME:** `lime.lime_tabular.LimeTabularExplainer` fit locally around the candidate's feature vector.
- **Reconciliation (the conformance proof):** assert the **library SHAP values ≈ the exact analytical
  `w_i·x_i`** (they must, for an additive model) within a tolerance; expose both + the residual so the
  dashboard can state "library-SHAP reconciles with exact additive attribution." This is what turns
  "bespoke, spec-named-libs-absent" into "spec-named libs used AND verified."
- Feature-flag `ENABLE_SPEC_SHAP` (already in config) + a new `ENABLE_SPEC_LIME`; graceful fallback to
  the existing analytical method when libs are unavailable (keeps prod healthy, keeps CI light).

### 3. Expose via API — `therapeutic_alternatives` path
- Attach a `real_xai` block (shap[], lime[], reconciliation{}) to each candidate's explanation payload
  (or a dedicated `/therapeutic-alternatives/{...}/xai` sub-resource). Keep the existing rule-based
  `explain_candidate` text as the human-readable layer; `real_xai` is the quantitative layer.

### 4. React dashboard — `frontend/src/components/TherapeuticAlternativesPanel.tsx`
- Add an **Explainability** section per candidate with tabs:
  - **SHAP** — signed horizontal bar chart of the 9 feature contributions (green +, red −), baseline shown.
  - **LIME** — local feature weights bar chart, with the "local approximation" caveat.
  - **FDA Sources** — the existing `source_claims` provenance cards.
- Include the reconciliation line ("exact additive ≡ library SHAP, residual < ε") and the honesty
  disclaimers already in the payloads.

## Validation
1. **Deps import:** `python -c "import shap, lime"`; `app.main` imports with flags on and off.
2. **Reconciliation test:** for a sample candidate, library-SHAP per-feature ≈ `w_i·x_i` within tol;
   sum of SHAP + baseline == score.
3. **LIME:** returns finite local weights of the right sign for the dominant features; deterministic seed.
4. **API:** a therapeutic-alternatives run returns a `real_xai` block per candidate; flag-off returns the
   analytical fallback (no crash, honest "library unavailable").
5. **Frontend:** `npm run build` succeeds; the SHAP/LIME/FDA tabs render with signed bars; no console errors.
6. **Regression:** existing therapeutic + research tests green; `/health` unaffected.

## Clears
D6-xai (crit) — spec-named SHAP/LIME now genuinely used; D6 SHAP-never-fires; D6 LIME-absent;
D6 feature-mismatch (dashboard explains the real 9 features); D8 LIME-dependency (added).
**Not in scope:** the molecular/MCS feature (that's U5/U8 — the score-model deviation), and any change to
the 9-feature model itself (U8 decision).

## Honest caveats
- SHAP/LIME explain the **scoring function**, not clinical correctness — surfaced as a disclaimer.
- Adds ML deps (shap pulls numpy/scipy/numba-adjacent; lime pulls scikit-learn — already present via
  sentence-transformers). Image/runtime weight increase is modest vs the torch already installed.
- For a purely additive model, LIME is arguably redundant with exact SHAP; we include it because the
  **spec names it** and DQ4 studies its effect — documented as such, not presented as adding new signal.
