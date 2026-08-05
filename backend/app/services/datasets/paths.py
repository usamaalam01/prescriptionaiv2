"""Dataset path resolution for real FDA NDC / openFDA SPL / DrugBank files."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings


def data_dir() -> Path:
    return Path(settings.DATA_DIR).expanduser().resolve()


def ndc_json_path() -> Path:
    if settings.FDA_NDC_JSON_PATH:
        return Path(settings.FDA_NDC_JSON_PATH).expanduser().resolve()
    return data_dir() / "drug-ndc-0001-of-0001.json"


def spl_label_paths() -> list[Path]:
    """Return openFDA drug-label shard files in order (preferred diligence source).

    Looks for ``drug-label-NNNN-of-NNNN.json`` under data/. Falls back to a single
    configured path or legacy ``openfda-spl-labels.json`` only when no shards exist.
    """
    if settings.FDA_SPL_JSON_PATH:
        p = Path(settings.FDA_SPL_JSON_PATH).expanduser().resolve()
        return [p] if p.exists() else []

    d = data_dir()
    shards = sorted(d.glob("drug-label-*-of-*.json"))
    if shards:
        return shards

    legacy = d / "openfda-spl-labels.json"
    return [legacy] if legacy.exists() else []


def spl_json_path() -> Path:
    """Primary SPL path (first shard or legacy monolith) for status/display."""
    paths = spl_label_paths()
    if paths:
        return paths[0]
    if settings.FDA_SPL_JSON_PATH:
        return Path(settings.FDA_SPL_JSON_PATH).expanduser().resolve()
    return data_dir() / "openfda-spl-labels.json"


def drugbank_xml_path() -> Path:
    if settings.DRUGBANK_XML_PATH:
        return Path(settings.DRUGBANK_XML_PATH).expanduser().resolve()
    return data_dir() / "drugbank.xml"


def catalog_db_path() -> Path:
    if settings.MEDICINE_CATALOG_DB:
        return Path(settings.MEDICINE_CATALOG_DB).expanduser().resolve()
    return data_dir() / "medicine_catalog.sqlite3"


def rag_faiss_path() -> Path:
    """Prebuilt semantic FAISS index reused by the DQ3 research path (U1)."""
    if settings.RAG_FAISS_INDEX_PATH:
        return Path(settings.RAG_FAISS_INDEX_PATH).expanduser().resolve()
    return data_dir() / "rag_index.faiss"


def rag_chunks_path() -> Path:
    """Chunk records (pickle) aligned 1:1 with the FAISS index vectors (U1)."""
    if settings.RAG_CHUNKS_PATH:
        return Path(settings.RAG_CHUNKS_PATH).expanduser().resolve()
    return data_dir() / "rag_chunks.pkl"
