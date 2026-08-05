"""One-time startup provisioning for Hugging Face Spaces (single-container deploy).

Runs from the FastAPI lifespan, guarded by ``SPACE_ID`` so it is a no-op in local
dev and CI. On an HF Space it:

  1. Redirects HF/transformers caches to a writable dir (Spaces' ``$HOME`` is not
     writable for the app user — this is the fix the old Streamlit Space needed for
     the MiniLM download to succeed).
  2. Downloads the runtime data artefacts from a private HF *dataset* repo if they
     are not already present under ``DATA_DIR`` (catalog SQLite + FAISS index +
     chunks). Raw source datasets (DrugBank XML, NDC/SPL bulk) are NOT needed at
     runtime and are never downloaded.
  3. Applies Alembic migrations against the configured (external) Postgres.
  4. Optionally seeds demo pharmacist/reviewer accounts (idempotent).

Required Space secrets: ``HF_TOKEN`` (dataset read), ``DATABASE_URL`` (external
Postgres). Optional: ``PHARMAASSIST_DATA_REPO`` to override the dataset repo id,
``SEED_DEMO_USERS=true`` to seed accounts.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger("pharmaassist.startup_hf")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def on_hf_space() -> bool:
    return bool(os.environ.get("SPACE_ID", "").strip())


# Runtime artefacts (only what the app reads at request time).
_REQUIRED_ARTEFACTS = (
    "medicine_catalog.sqlite3",
    "rag_index.faiss",
    "rag_chunks.pkl",
)
_DEFAULT_DATA_REPO = "pharma-project-2026/pharmaassist-data"  # private HF dataset repo


def _redirect_hf_caches() -> None:
    """Point every HF/transformers cache env var at a writable dir."""
    cache_root = os.environ.get("HF_CACHE_ROOT", "/data/hf-cache").strip() or "/tmp/hf-cache"
    try:
        Path(cache_root).mkdir(parents=True, exist_ok=True)
    except Exception:
        cache_root = "/tmp/hf-cache"
        Path(cache_root).mkdir(parents=True, exist_ok=True)
    for var in (
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "TRANSFORMERS_CACHE",
        "SENTENCE_TRANSFORMERS_HOME",
        "XDG_CACHE_HOME",
    ):
        os.environ.setdefault(var, cache_root)
    _log(f"[startup] HF caches -> {cache_root}")


def _data_dir() -> Path:
    # Mirror app.services.datasets.paths.data_dir() without importing settings early.
    d = os.environ.get("DATA_DIR", "").strip()
    return Path(d).expanduser() if d else Path(__file__).resolve().parents[2] / "data"


def _download_artefacts() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    missing = [f for f in _REQUIRED_ARTEFACTS if not (data_dir / f).exists()]
    if not missing:
        _log("[startup] All runtime artefacts already present; skipping download.")
        return
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set but runtime artefacts are missing "
            f"({missing}). Set the HF_TOKEN secret with read access to the "
            "private data dataset repo."
        )

    from huggingface_hub import hf_hub_download

    repo = os.environ.get("PHARMAASSIST_DATA_REPO", _DEFAULT_DATA_REPO).strip() or _DEFAULT_DATA_REPO
    for filename in missing:
        _log(f"[startup] Downloading {filename} from {repo} ...")
        t0 = time.time()
        hf_hub_download(
            repo_id=repo,
            filename=filename,
            repo_type="dataset",
            token=token,
            local_dir=str(data_dir),
        )
        size_mb = (data_dir / filename).stat().st_size / 1024 / 1024
        _log(f"[startup] {filename} downloaded ({size_mb:.0f} MB in {time.time()-t0:.0f}s).")


def _run_migrations() -> None:
    """Apply Alembic migrations against the configured database."""
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]  # .../backend
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    _log("[startup] Running alembic upgrade head ...")
    command.upgrade(cfg, "head")
    _log("[startup] Migrations applied.")


def _seed_demo_users() -> None:
    if os.environ.get("SEED_DEMO_USERS", "").strip().lower() not in {"1", "true", "yes"}:
        return
    try:
        from app.scripts_seed import seed_named_pharmacists  # type: ignore

        seed_named_pharmacists()
        _log("[startup] Demo users seeded.")
    except Exception as exc:  # noqa: BLE001
        _log(f"[startup] Demo-user seed skipped ({type(exc).__name__}: {exc}).")


def run() -> None:
    """Provision the Space. Safe to call unconditionally; no-op off HF."""
    if not on_hf_space():
        return
    _log("[startup] HF Space detected — provisioning ...")
    _redirect_hf_caches()
    try:
        _download_artefacts()
    except Exception as exc:  # noqa: BLE001
        _log(f"[startup] ERROR provisioning artefacts: {exc}")
        raise
    try:
        _run_migrations()
    except Exception as exc:  # noqa: BLE001
        _log(f"[startup] ERROR running migrations: {exc}")
        raise
    _seed_demo_users()
    _log("[startup] Provisioning complete.")
