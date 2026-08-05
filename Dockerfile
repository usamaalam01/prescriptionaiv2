# PharmaAssist — single-container image for Hugging Face Spaces (Docker SDK).
# Stage 1 builds the React SPA; stage 2 runs FastAPI and serves that build,
# so the whole app is one origin on one port (7860, HF's default).

# ---- Stage 1: build the frontend --------------------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build          # -> /fe/dist

# ---- Stage 2: python runtime ------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Where the SPA build lives (read by app/web_spa.py) + a writable HF cache.
    FRONTEND_DIST_DIR=/app/frontend/dist \
    HF_CACHE_ROOT=/tmp/hf-cache \
    # App reads runtime artefacts from here (downloaded at startup on HF).
    DATA_DIR=/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps. Torch comes from the CPU wheel index to avoid the ~2 GB
# CUDA build; faiss-cpu / sentence-transformers / the rest resolve from PyPI.
COPY backend/requirements.txt backend/requirements-bertscore.txt ./
RUN pip install --upgrade pip \
    && pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt \
    && pip install -r requirements-bertscore.txt

# App code + migrations + the built SPA.
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts
COPY --from=frontend /fe/dist ./frontend/dist

# HF Spaces provides a writable /data volume; make DATA_DIR + cache dirs exist.
RUN mkdir -p /data /tmp/hf-cache

EXPOSE 7860

# Single worker: keeps the FAISS index + embedding model singletons in one
# process (the @lru_cache loaders are per-process). Migrations + artefact
# download run in the FastAPI lifespan (app/startup_hf.py), gated by SPACE_ID.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
