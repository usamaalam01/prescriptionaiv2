# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository (the **PharmaAssist "new" project**).
These instructions override default behavior — follow them.

## What This Project Is

**PharmaAssist** — an AI-powered pharmacist **decision-support** prototype (University of Liverpool CSCK700
capstone; student Muhammad Zohaib, #200052400; ethics 18274). A pharmacist uploads a handwritten
prescription → OCR extracts drug fields → the pharmacist verifies/corrects them (HITL) → the system
recommends therapeutically-relevant alternatives with a rule-based **Evidence Match Score**, FDA-label
evidence (RAG), FDA **Orange Book** therapeutic-equivalence ratings, and SHAP/LIME explanations. A separate
**research-evaluation** layer answers four dissertation questions (DQ1–DQ4).

**It is decision support only.** Every extracted field and every suggested alternative must be confirmed by a
pharmacist (HITL). The system never auto-substitutes. Preserve this framing in all code and copy.

This is a **re-platform** of an earlier Streamlit prototype (in `_reference-old-project/`, read-only). The
approved spec is `docs/PharmaAssist_Complete_Specification.md` / the original `Spec Design Report`. Divergences
from the spec are tracked and remediated one unit at a time — **see [How work happens here](#how-work-happens-here).**

## Architecture

- **Backend:** FastAPI 0.128 + SQLAlchemy 2 + Alembic (12 migrations) + **PostgreSQL**. The app uses Postgres
  **named schemas** (`auth`, `config`, `admin`, `clinical`, `consent`, `ocr`, `prescription`, `research`,
  `security`, `audit`, `monitoring`) — so **SQLite is not a substitute for the app DB.** JWT + Argon2 auth;
  three roles: `administrator`, `pharmacist`, `reviewer`.
- **Frontend:** React 19 + MUI 7 + Vite + TypeScript. Calls the API with `axios baseURL: ''` (relative), so
  it can run same-origin behind the backend in one container, or via the Vite dev proxy locally.
- **Read-only drug catalogue:** `data/medicine_catalog.sqlite3` (~400 MB, 41,020 medicines, built from FDA NDC +
  DrugBank + FDA SPL) — this is a **separate** SQLite file from the Postgres app DB. It also holds derived
  tables built by scripts: `smiles_by_name` (RDKit MCS), `orange_products` (Orange Book TE).
- **Deployment:** single Docker container (SPA served by FastAPI, same-origin, port 7860) + external Postgres.
  HF Spaces deploy is **paused** (HF now gates Docker Spaces behind PRO); Fly.io is the free path. See
  `docs/HF_DEPLOYMENT_PLAN.md`.

### Data flow
```
image → services/ocr (Google Vision primary; Tesseract/TrOCR fallbacks) → structured fields
  → HITL verify/confirm (React VerificationTable → prescription.* tables)
  → services/therapeutic/evaluate.py
      identity → retriever/product_candidates → mandatory_filters → scoring (Evidence Match Score)
      + mcs.py (RDKit structural bonus)  + orange_book.py (FDA TE evidence)  + rag_evidence.py (FDA label RAG)
      + xai.py / xai_real.py (SHAP/LIME)
  → candidate payloads with score breakdown, TE block, evidence, explanations
Research path (reviewer): services/research_eval/service.py runs DQ1–DQ4 harnesses.
```

## Running Locally (native, no Docker)

Windows PowerShell. **Python 3.13** venv at `backend/.venv`. Local **Postgres must be running on :5432**
(the app DB), and `backend/.env` must point `DATABASE_URL` at it with the **`+psycopg`** driver
(`postgresql+psycopg://…`, not bare `postgresql://`).

```bash
# Backend (from backend/). Migrations first, then uvicorn.
backend/.venv/Scripts/python.exe -m alembic upgrade head
backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (from frontend/) — Vite dev server, proxies /api,/health,/ready → 127.0.0.1:8000
npm run dev     # → http://localhost:5173
```

Full stack via Docker: `docker compose up --build` (services: `postgres`, `api`, `web`).

**Local login (seed accounts):** `admin`/`ChangeMeAdmin!234`, `pharmacist`/`ChangeMePharm!234`,
`reviewer`/`ChangeMeReview!234` (the reviewer seed password varies — reset via a script if login fails).
There is a self-service **Register** flow; the admin approves registrations. The admin dashboard deliberately
shows **only self-registered, non-seed, non-mock** data — so directly-inserted users and seed sessions show
as zero. That is by design (anti-fabrication), not a bug.

## Tests

`cd backend && ./.venv/Scripts/python.exe -m pytest -q` (35 test files). Focused suites:
- `tests/test_research_evaluation.py` — DQ1–DQ4 harness (fast; the suite to run for RAG/BERTScore/MCS/XAI work).
- `tests/test_therapeutic_alternatives.py` — recommendation engine.

**Known pre-existing failures (NOT caused by current work):** in the full suite, ~a handful fail on
test/code drift — notably `test_health.py` patches a nonexistent `app.main.check_database` (health is built in
`app.services.readiness`), and two `test_therapeutic_alternatives.py` asserts (`classification`,
`explanation_mode`) predate the current engine. When you run the full suite, expect these; confirm any *new*
failure is genuinely yours before claiming a regression.

## Feature Flags (config.py) — most heavy features are OFF by default

| Flag | Default | Effect |
|---|---|---|
| `ENABLE_SEMANTIC_RAG` | false | Real MiniLM+FAISS RAG for the DQ3 research path (reuses `data/rag_index.faiss`, 10k chunks) |
| `ENABLE_BERTSCORE` | false | Real BERTScore in DQ3 |
| `ENABLE_SPEC_MCS` | **true** | RDKit MCS structural bonus in the score |
| `ENABLE_ORANGE_BOOK` | **true** | FDA Orange Book TE evidence on candidates (no-op if `orange_products` absent) |
| `ENABLE_SPEC_SHAP` / `ENABLE_SPEC_LIME` | false | Real shap/lime libraries (else exact analytical attribution) |
| `ENABLE_SPEC_GROQ` | false | Groq LLM narrative for evidence (needs `GROQ_API_KEY`) |
| `ENABLE_TROCR_RETRY` / `ENABLE_PADDLE_DETECT` | (env) | OCR extras — **keep OFF locally** (see gotchas) |

## Key Modules

**`backend/app/services/therapeutic/`** (recommendation engine)
- `evaluate.py` — orchestrator; builds candidate payloads (two paths: same-active-moiety products,
  different-active-ingredient therapeutic candidates).
- `scoring.py` — **Evidence Match Score**: a 9-component additive model (`WEIGHTS`, sums to 100). *Note:* this
  differs from the spec's 3-component formula — that's deviation D3-01 (a pending decision, U8).
- `mcs.py` + `smiles_catalog.py` + `smiles_seed.py` — RDKit Maximum Common Substructure. SMILES resolve from
  the catalogue's `smiles_by_name` table (salt-normalized) with a curated seed fallback. MCS is a **bounded
  supporting bonus**, never an equivalence gate.
- `orange_book.py` — FDA Orange Book **therapeutic-equivalence** (`te_status_for`). Returns the `TE_Code` split
  into **per-subletter subgroups** (AB1 ≠ AB2 ≠ AB3 are NOT mutually substitutable — honor this), RLD brand(s),
  DISCN filter, single-source detection. Evidence only; never auto-substitutes.
- `rag_evidence.py` — production evidence (keyword over `label_sections`) + optional Groq summary.

**`backend/app/services/research_eval/`** (DQ1–DQ4 harness, reviewer-only)
- `service.py` — `run_dq1/dq2/dq3_...`; `metric_status.py` has `metric_envelope` + `ACCEPTANCE_TARGETS`
  (B3 thresholds WER<0.15, CER<0.10, P@3≥0.70, R@3≥0.60, BERTScore≥0.80 → PASS/FAIL badges).
- `semantic_retriever.py` (U1 FAISS RAG), `xai_real.py` (U10 real SHAP/LIME + reconciliation), `ocr_engines.py`.

**`backend/app/services/ocr/`** — Google Vision primary, Tesseract/TrOCR fallbacks, preprocessing, consensus.
**`backend/app/api/v1/`** — routers: auth, registration, consent_docs, admin, prescriptions, clinical,
therapeutic_alternatives, analytics, datasets, research_eval.

## Rebuilding derived catalogue tables (scripts)

These populate tables **inside** `medicine_catalog.sqlite3` (gitignored under `data/`) — reproducible, not
committed:
```bash
python -m scripts.build_smiles_table    # smiles_by_name (RDKit MCS source; ~60k name→SMILES)
python -m scripts.build_orange_book     # orange_products (FDA Orange Book, 48,502 rows)
```

## How work happens here

This repo is being brought into conformance with the approved spec **one gated unit at a time**. The living
plan is **`docs/DEVIATION_REMEDIATION_PLAN.md`** (unit tracking, status, decision register) and the evidence is
**`docs/SPEC_CONFORMANCE_AUDIT.md`**. When you complete or change a unit, **update both** to stay truthful.

**Working protocol (established and expected):**
1. **Plan before non-trivial units** — restate goal, acceptance, test plan; get sign-off on approach and on any
   Decision (some units are "fix vs re-document" calls that need the user/supervisor).
2. **Implement the smallest coherent change**, feature-flagged and graceful when deps/data are absent.
3. **Validate independently and adversarially.** Every substantive unit here has had an independent skeptical
   review that found real defects — including a *clinical-safety overstatement* (Orange Book subletters) and
   *fabricated-metric* issues. Do the same: probe the riskiest claim, don't just confirm the happy path.
4. **Never overstate.** Do not claim a metric/rule is honored without verifying it (this has bitten us
   repeatedly). Report partial/mechanism-only status honestly; distinguish "code exists" from "spec is met."
5. **Record** the outcome in the plan + audit; **commit + push** (repo:
   `github.com/usamaalam01/prescriptionaiv2`, branch `main`). Keep `data/`, `.env`, `.venv`, `node_modules`,
   and secrets out of commits (`.gitignore`/`.dockerignore` cover them).

## Integrity & safety rules (non-negotiable)

- **No fabricated metrics.** Do not present invented/simulated numbers as real evaluation results, and don't
  attach PASS/FAIL or equivalence claims to fabricated data. (DQ1's `simulate_engine_outputs` is a known
  fabrication under decision U3.)
- **Therapeutic equivalence is regulatory, not chemical.** Orange Book `TE_Code` is the authoritative source;
  RDKit MCS is only a chemical *support* signal. Honor the **subletter rule** and exclude DISCN.
- **HITL is mandatory** — the pharmacist confirms fields and decides on alternatives; the system only proposes.
- **No PII beyond accounts.** Synthetic prescriptions only; registration IDs are encrypted.

## Environment gotchas (Windows / Python 3.13)

- **TrOCR (`trocr-large-handwritten`) segfaults torch on this Windows box** — even standalone. Keep OCR
  **Vision-only** locally (`ENABLE_TROCR_RETRY=false`, `ENABLE_PADDLE_DETECT=false`). TrOCR is expected to work
  only in the Linux Docker image.
- **RAG + BERTScore together** need `KMP_DUPLICATE_LIB_OK=TRUE` (faiss + torch OpenMP conflict) — set in the
  Dockerfile and `.env`. RDKit itself installs/runs fine.
- Use `backend/.venv/Scripts/python.exe` explicitly; `streamlit`/`uvicorn` may not be on PATH.

## Key Docs (docs/)

`DEVIATION_REMEDIATION_PLAN.md` (unit plan + status) · `SPEC_CONFORMANCE_AUDIT.md` (deviation evidence) ·
`PharmaAssist_Complete_Specification.md` (approved spec) · `HF_DEPLOYMENT_PLAN.md` (deploy runbook) ·
`U-TE_ORANGE_BOOK_PLAN.md`, `U10_XAI_PLAN.md` (unit plans) · `specification_traceability_matrix.md`,
`research_question_alignment.md`, `evaluation_protocol.md`.
