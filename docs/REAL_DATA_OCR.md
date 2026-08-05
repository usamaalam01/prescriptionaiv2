# Real datasets & OCR (full data)

PharmaAssist is a **pharmacist decision-support prototype** (not clinical care).

## Full local files

| File | Size (approx) | Role |
|------|----------------|------|
| `data/drug-ndc-0001-of-0001.json` | ~227 MB | FDA NDC products, strengths, forms |
| `data/drugbank.xml` | ~1.8 GB | Licensed DrugBank names, synonyms, products |
| `data/openfda-spl-labels.json` | ~8 GB | FDA SPL labels / indications |

## Build the FULL catalog (no row limits)

Streams all three sources into `data/medicine_catalog.sqlite3`:

```powershell
cd D:\Projects\PharmaAssist\backend
.\.venv\Scripts\python.exe -m app.services.datasets.build_index
```

Log to a file (recommended — NDC+DrugBank+SPL can take a long time):

```powershell
.\.venv\Scripts\python.exe -m app.services.datasets.build_index *> ..\data\catalog_build.log
```

NDC + DrugBank only (still full files, skip 8GB SPL):

```powershell
.\.venv\Scripts\python.exe -m app.services.datasets.build_index --skip-spl
```

## After build

- `GET /api/v1/catalog/status`
- `POST /api/v1/catalog/suggest` with `{ "query": "Ibrufen", "top_k": 3 }`
- HITL drug dropdown uses catalog top-3 candidates when SQLite exists
- **Analyzer upload pipeline** (`engine: "pipeline"`) uses `run_ocr_stack` → line parser → catalog formulary checks

## Real OCR (Google Vision REST)

Windows Application Control often blocks the gRPC Vision client. PharmaAssist calls
**Vision REST** `images:annotate` with `DOCUMENT_TEXT_DETECTION` instead.

In `.env` set **one** of:

```powershell
# Service account (Cloud Vision API enabled on the GCP project)
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/gcp-service-account.json

# Or API key restricted to Cloud Vision API
GOOGLE_VISION_API_KEY=your-key
```

Then restart the backend. Without credentials, OCR stays labelled MOCK but still
validates against the full medicine catalog.

Paddle detect / TrOCR are optional secondary stages (`ENABLE_PADDLE_DETECT`,
`ENABLE_TROCR_RETRY`) — leave false on unsupported Python/Windows builds.
