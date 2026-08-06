# PharmaAssist → Hugging Face Spaces (Docker SDK) — deployment plan

**Goal (confirmed):** full app live on an HF Space — React UI + FastAPI API, single container,
same-origin. **Database:** external free Postgres (Neon or Supabase) so data persists across the
Space's ephemeral restarts and the app's `CREATE SCHEMA` migrations work.

> **Environment finding (local testing, 2026-08):** on the local **Windows + Python 3.13** dev box,
> **TrOCR (`trocr-large-handwritten`) segfaults torch intermittently** — it crashes even in a bare
> standalone process (no server / faiss / BERTScore), with *and* without `KMP_DUPLICATE_LIB_OK`,
> exiting 0 once and 139 twice on the identical load+generate. This is a **native torch/OpenMP
> instability on Windows**, not an app bug. Consequences: (1) for **local** testing, keep OCR
> **Vision-only** (`ENABLE_TROCR_RETRY=false`, `ENABLE_PADDLE_DETECT=false`) — stable and fast;
> (2) TrOCR is expected to work in the **Linux Docker** image (Linux torch builds don't hit this
> conflict; `KMP_DUPLICATE_LIB_OK=TRUE` is already set in the Dockerfile as defensive cover). Also
> note: running **RAG + BERTScore together** on Windows needs `KMP_DUPLICATE_LIB_OK=TRUE` (already
> in `.env`/Dockerfile) or it segfaults on the same class of OpenMP conflict.

## Why one container, same-origin
The frontend already calls the API with `axios baseURL: ''` (relative `/api`), so if FastAPI serves
the built React `dist/`, the browser talks to one origin — no CORS, no Vite proxy, no second service.
HF Spaces gives exactly one container on one port, so this is the natural fit.

## What's missing today (the actual work)
1. FastAPI does **not** serve the frontend (no `StaticFiles`). → add SPA mounting.
2. No **migrations on boot** (lifespan only purges). → run `alembic upgrade head` at startup.
3. No **artefact provisioning** — `DATA_DIR` is local-only; there is no `hf_startup.py`. The runtime
   needs `medicine_catalog.sqlite3` (402 MB) + `rag_index.faiss` + `rag_chunks.pkl` (~32 MB), which are
   gitignored and far too big for the Space repo. → download from a **private HF dataset repo** at boot.
4. No **single build** that compiles the React app and bundles it with the API.

## Steps

### 1. External Postgres (persistent DB)
- Create a free Neon (or Supabase) Postgres. Grab the connection string.
- It becomes the Space secret `DATABASE_URL=postgresql+psycopg://…` (note the `+psycopg` driver the app
  uses). Schemas (`auth`, `config`, …) are created by the existing migrations on first boot.

### 2. Serve the React SPA from FastAPI  *(code change — `backend/app/main.py`)*
- After all routers are mounted, if a built `frontend/dist` exists: mount `StaticFiles` for assets and add
  a catch-all `GET` that returns `index.html` for non-`/api|/health|/ready|/docs` paths (SPA fallback).
- Gate it so local dev (Vite on :5173) is unaffected — only serve static when the dist dir is present.

### 3. Run migrations + provision artefacts on startup  *(new `backend/app/startup_hf.py`, called from lifespan)*
- Guard with `SPACE_ID` (HF-only), mirroring the old project's `hf_startup.py` pattern.
- On boot: (a) if artefacts absent under `DATA_DIR`, `hf_hub_download` each from the private dataset repo
  using `HF_TOKEN`; (b) `alembic upgrade head`; (c) optional seed of the demo pharmacist/reviewer accounts.
- Redirect HF caches (`HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE`, `SENTENCE_TRANSFORMERS_HOME`) to a
  writable dir — the fix the old Space needed for the MiniLM download.

### 4. Upload runtime data to a private HF dataset repo (one-time, ~434 MB)
- Create dataset repo (e.g. `<user>/pharmaassist-data`, **private**).
- Upload only the runtime files: `medicine_catalog.sqlite3`, `rag_index.faiss`, `rag_chunks.pkl`.
  **Not** the 13 GB raw sources (drugbank.xml, NDC/SPL zips) — the app doesn't need them at runtime.

### 5. Single Dockerfile at the Space root  *(new — multi-stage)*
- **Stage 1 (node):** `npm ci && npm run build` in `frontend/` → `dist/`.
- **Stage 2 (python:3.12-slim):** system libs (`libpq5`, `tesseract-ocr`); `pip install -r requirements.txt`
  + CPU torch (`--index-url https://download.pytorch.org/whl/cpu`) + `requirements-bertscore.txt`; copy
  `app/ alembic/ alembic.ini scripts/` and the built `dist/`; `EXPOSE 7860`; CMD uvicorn on **:7860**
  (HF's expected port), single worker (keeps the FAISS/model singletons in one process).
- Extends the existing `backend/Dockerfile` (already installs libpq5 + tesseract + CPU torch).

### 6. Space repo layout + secrets
- New Space, **SDK = Docker**, `app_port: 7860` in `README.md` front-matter.
- Repo = this Dockerfile + `backend/` + `frontend/` (source). `.dockerignore` excludes `.venv`, `data/`,
  `node_modules`, raw sources.
- **Secrets:** `DATABASE_URL`, `HF_TOKEN` (dataset read), `JWT_SECRET_KEY` (real 32+ char), 
  `FIELD_ENCRYPTION_KEY` (real Fernet key), `GOOGLE_VISION_API_KEY`, `ENABLE_SEMANTIC_RAG=true`,
  `GROQ_API_KEY` (if explanations wanted). Start the Space on a **CPU-upgrade** tier if the free 16 GB
  RAM struggles with torch + 402 MB catalog.

## Validation (once live)
- Space build succeeds; container boots; logs show artefact download + `alembic upgrade head` OK.
- `GET /health` and `/ready` → 200, `database.status=ok`, `catalog.available=true` (41,020 meds).
- Open the Space URL → React login renders; register/login works (persists — verify by restarting the
  Space and logging in again); a therapeutic-alternatives run returns results; DQ3 semantic RAG runs.

## Honest risks / caveats
- **Image size & cold start:** torch + faiss + transformers + 402 MB catalog → a large image and a slow
  first boot (multi-minute artefact download + model load). Free tier *may* OOM; CPU-upgrade tier is safer.
- **Two secrets are currently dev placeholders** (`JWT_SECRET_KEY`, `FIELD_ENCRYPTION_KEY`) — must be real
  in the Space or the production guard warns and encryption is insecure.
- **Neon free tier auto-suspends** on idle; first request after idle has a ~1 s cold start. Fine for a demo.
- This is **not** a one-file drop-in like the old Streamlit app — expect the 6 steps above (~1 day).

## Out of scope (this plan)
Rebuilding the RAG index against the new catalogue (U1b), CI/CD, custom domain, autoscaling.
