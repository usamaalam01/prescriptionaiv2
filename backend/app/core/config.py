from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "PharmaAssist"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    DATABASE_URL: str = (
        "postgresql+psycopg://pharmaassist:pharmaassist_dev_password@localhost:5432/pharmaassist"
    )

    JWT_SECRET_KEY: str = "dev-only-change-me-jwt-secret-key-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 2

    MAX_FAILED_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15

    FIELD_ENCRYPTION_KEY: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    STUDY_CODE: str = "CSCK700-PHARMAASSIST-2026"

    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "../storage/tmp"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    ENABLE_BERTSCORE: bool = False

    # U1 — semantic FAISS RAG for the DQ3 research path. Off by default so the heavy
    # embedding stack (faiss-cpu + sentence-transformers + torch) loads only when enabled.
    # Reuses the prebuilt index shipped in DATA_DIR (no rebuild); empty paths resolve to
    # DATA_DIR/rag_index.faiss and DATA_DIR/rag_chunks.pkl.
    ENABLE_SEMANTIC_RAG: bool = False
    RAG_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RAG_FAISS_INDEX_PATH: str = ""
    RAG_CHUNKS_PATH: str = ""

    # Spec Design O3–O5 research layers (post-HITL Confirm only — never auto-prescribe)
    ENABLE_SPEC_MCS: bool = True
    # U-TE — FDA Orange Book therapeutic-equivalence signal (decision-support evidence
    # only; never auto-substitutes). No-op when the orange_products table is absent.
    ENABLE_ORANGE_BOOK: bool = True
    ENABLE_SPEC_RAG: bool = True
    ENABLE_SPEC_GROQ: bool = False
    ENABLE_SPEC_SHAP: bool = False
    ENABLE_SPEC_LIME: bool = False  # U10 — real lime library over the additive score
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Real datasets under DATA_DIR (defaults resolve filenames in that folder)
    DATA_DIR: str = str(Path(__file__).resolve().parents[3] / "data")
    FDA_NDC_JSON_PATH: str = ""
    FDA_SPL_JSON_PATH: str = ""
    DRUGBANK_XML_PATH: str = ""
    MEDICINE_CATALOG_DB: str = ""

    # Production OCR: Google Vision primary (best operational accuracy for HITL).
    # Spec O1 research order (TrOCR → Vision → Tesseract) is used by Research Evaluation / OCR_PROFILE=spec.
    OCR_STRATEGY: str = "sequential"  # sequential | hybrid | legacy
    OCR_PROFILE: str = "production"  # production | spec
    OCR_PRIMARY: str = "google_vision"
    OCR_FALLBACK_ORDER: str = "tesseract"
    OCR_MIN_CONFIDENCE: float = 0.60
    OCR_HYBRID_CONSENSUS_ENABLED: bool = False
    # False in production for latency; Research Evaluation retains per-engine outputs separately.
    OCR_PRESERVE_ENGINE_OUTPUTS: bool = False
    OCR_ALLOW_MOCK_FALLBACK: bool = True
    # Spec research engine order (DQ1 / Spec O1) — does not change production primary.
    OCR_SPEC_PRIMARY: str = "trocr"
    OCR_SPEC_FALLBACK_ORDER: str = "google_vision,tesseract"
    # When False (default), pharmacist cannot Confirm medicines extracted from mock OCR
    HITL_ALLOW_MOCK_CONFIRM: bool = False
    # When False (default), dose dropdowns are FDA_SPL-extracted only (fail-closed).
    # Set True to restore form/route SIG templates for demos without a dose index.
    HITL_ALLOW_DOSE_TEMPLATES: bool = False
    # When False (default), frequency dropdowns are FDA_SPL-extracted only (fail-closed).
    HITL_ALLOW_FREQ_TEMPLATES: bool = False
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_VISION_API_KEY: str = ""
    ENABLE_PADDLE_DETECT: bool = True
    ENABLE_TROCR_RETRY: bool = True
    TROCR_CONFIDENCE_THRESHOLD: float = 0.75
    # Handwritten Rx preprocess (deskew / ink / soft-binarize) — best practice defaults ON
    OCR_PREPROCESS_DESKEW: bool = True
    OCR_PREPROCESS_INK_ISOLATE: bool = True
    OCR_PREPROCESS_BINARIZE: bool = True
    OCR_PREPROCESS_SHARPEN: bool = True
    OCR_PREPROCESS_MAX_SIDE: int = 2400

    # Comma-separated browser origins (production: set explicitly)
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Encrypted temporary Rx image retention (research / consent alignment)
    TEMP_FILE_RETENTION_HOURS: int = 24
    DELETE_TEMP_WHEN_SESSION_CONFIRMED: bool = True
    PURGE_EXPIRED_ON_STARTUP: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
