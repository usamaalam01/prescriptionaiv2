---
title: PharmaAssist
emoji: 💊
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: AI-powered pharmacist decision-support (FDA NDC / DrugBank / SPL).
---

# PharmaAssist — award-path HITL decision support

Pharmacist **decision-support** prototype (University of Liverpool CSCK700).  
Uses local **FDA NDC + DrugBank + FDA SPL** for verification. **Not clinical care.**

> **Hugging Face Spaces:** the YAML front-matter above configures this repo as a **Docker SDK**
> Space serving the React SPA + FastAPI API from one origin on port `7860`. Required/optional Space
> secrets, the runtime-artefact download, and the full deploy runbook are in
> [`docs/HF_DEPLOYMENT_PLAN.md`](docs/HF_DEPLOYMENT_PLAN.md).

## Quick start (local)

```powershell
# Postgres
docker compose up -d postgres

cd D:\Projects\PharmaAssist\backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd D:\Projects\PharmaAssist\frontend
npm run dev
```

Dev login: `pharmacist` / `ChangeMePharm!234`

## Full stack (Docker)

Requires `data/medicine_catalog.sqlite3` (build once with `python -m app.services.datasets.build_index`).

```powershell
docker compose up --build
```

- UI: http://127.0.0.1:8080  
- API: http://127.0.0.1:8000/health  

## Award surfaces

| Surface | Path |
|--------|------|
| Phase 1 auth gate (register → admin approve) | [`docs/PHASE1_AUTH.md`](docs/PHASE1_AUTH.md) · `/register` · `/admin` |
| Administrator portal | `/admin` (Dashboard, Registrations, Catalog, Prescriptions, Analytics) |
| Catalog explorer | `/catalog` |
| Analyzer + HITL cascade | `/analyzer` |
| Forced password change | `/change-password` (seed accounts) |
| Health / readiness | `/health`, `/ready` |
| Async OCR queue | Analyzer polls `/ocr/.../run-async` + `/ocr/jobs/{id}` |
| Rate limits | Login / upload / OCR async (429 when exceeded) |
| Rx retention | Encrypted temp images: cancel / confirm-all / timed purge |
| Recorded demo | [`docs/RECORDED_DEMO.md`](docs/RECORDED_DEMO.md) |
| Viva demo script | [`docs/AWARD_DEMO.md`](docs/AWARD_DEMO.md) |

## Pharmacist field cascade

OCR → Drug (FDA/DrugBank similar) → Strength → Dosage → Frequency → optional Indication → Confirm.
