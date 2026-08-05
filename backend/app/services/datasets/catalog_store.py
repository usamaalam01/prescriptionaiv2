"""Runtime access to the SQLite medicine catalog."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.datasets.paths import catalog_db_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MedicineRecord:
    id: int
    canonical_name: str
    drugbank_id: str | None
    product_ndc: str | None
    dosage_forms: list[str]
    routes: list[str]
    sources: list[str]
    indication: str | None
    strengths: list[str]
    aliases: list[str]
    spl_set_id: str | None = None


@dataclass(frozen=True)
class ProductRecord:
    strength: str | None
    dosage_form: str | None
    route: str | None
    product_ndc: str | None
    source: str
    spl_set_id: str | None = None


def catalog_available() -> bool:
    """True when the catalog file exists and can be opened for reads."""
    path = catalog_db_path()
    try:
        if not path.exists() or path.stat().st_size <= 0:
            return False
    except OSError:
        return False
    try:
        with _connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
    except Exception:  # noqa: BLE001
        return False


def catalog_has_products_table() -> bool:
    if not catalog_available():
        return False
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='products'"
            ).fetchone()
            return bool(row)
    except Exception:  # noqa: BLE001
        return False


def _open_sqlite_ro(path: Path) -> sqlite3.Connection:
    """Open catalog for read. Prefer immutable (Docker/bind mounts); fall back safely."""
    posix = path.as_posix()
    attempts = (
        f"file:{posix}?mode=ro&immutable=1",
        f"file:{posix}?mode=ro",
        posix,  # plain path (writable dirs / copied runtime file)
    )
    last_err: Exception | None = None
    for uri in attempts:
        try:
            if uri.startswith("file:"):
                conn = sqlite3.connect(uri, uri=True)
            else:
                conn = sqlite3.connect(uri)
            conn.execute("SELECT 1").fetchone()
            return conn
        except sqlite3.OperationalError as exc:
            last_err = exc
            continue
    assert last_err is not None
    raise last_err


@lru_cache(maxsize=1)
def _runtime_catalog_copy() -> Path | None:
    """Copy catalog to a local temp file for fast repeated reads (Docker bind mounts are slow)."""
    src = catalog_db_path()
    if not src.exists():
        return None
    dest = Path(tempfile.gettempdir()) / "pharmaassist_medicine_catalog.sqlite3"
    try:
        need_copy = (
            not dest.exists()
            or dest.stat().st_size != src.stat().st_size
            or dest.stat().st_mtime < src.stat().st_mtime
        )
        if need_copy:
            tmp = dest.with_suffix(".sqlite3.partial")
            shutil.copy2(src, tmp)
            tmp.replace(dest)
            logger.info("Catalog SQLite staged at %s for fast HITL/OCR reads", dest)
        return dest
    except OSError as exc:
        logger.error("Failed to copy medicine catalog to %s: %s", dest, exc)
        return None


def clear_runtime_catalog_copy_cache() -> None:
    _runtime_catalog_copy.cache_clear()


def _connect() -> sqlite3.Connection:
    path = catalog_db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Medicine catalog not built: {path}. Run: python -m app.services.datasets.build_index"
        )
    # Prefer a local copy: bind-mounted SQLite on Docker Desktop/Windows is very slow
    # per open (~1s+), which made OCR catalog checks look hung.
    local = _runtime_catalog_copy()
    open_path = local if local is not None else path
    try:
        conn = _open_sqlite_ro(open_path)
    except sqlite3.OperationalError:
        if local is not None and open_path != path:
            conn = _open_sqlite_ro(path)
        else:
            raise
    conn.row_factory = sqlite3.Row
    return conn


def get_meta() -> dict[str, str]:
    if not catalog_available():
        return {}
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT key, value FROM meta").fetchall()
    except Exception:  # noqa: BLE001
        return {}
    return {r["key"]: r["value"] for r in rows}


def get_medicine(medicine_id: int) -> MedicineRecord | None:
    return _get_medicine_cached(int(medicine_id))


@lru_cache(maxsize=8192)
def _get_medicine_cached(medicine_id: int) -> MedicineRecord | None:
    """Cached medicine row. Alias list is capped — full synonym dump is too slow on bind mounts."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM medicines WHERE id=?", (medicine_id,)).fetchone()
        if not row:
            return None
        strengths = [
            r[0]
            for r in conn.execute(
                "SELECT strength FROM strengths WHERE medicine_id=? ORDER BY strength LIMIT 40",
                (medicine_id,),
            ).fetchall()
        ]
        aliases = [
            r[0]
            for r in conn.execute(
                """
                SELECT alias_raw FROM aliases
                WHERE medicine_id=?
                ORDER BY length(alias_raw), alias_raw
                LIMIT 24
                """,
                (medicine_id,),
            ).fetchall()
        ]
        keys = set(row.keys())
    return MedicineRecord(
        id=row["id"],
        canonical_name=row["canonical_name"],
        drugbank_id=row["drugbank_id"],
        product_ndc=row["product_ndc"],
        dosage_forms=json.loads(row["dosage_forms"] or "[]"),
        routes=json.loads(row["routes"] or "[]"),
        sources=json.loads(row["sources"] or "[]"),
        indication=row["indication"],
        strengths=strengths,
        aliases=aliases,
        spl_set_id=row["spl_set_id"] if "spl_set_id" in keys else None,
    )


def get_medicine_by_canonical(name: str) -> MedicineRecord | None:
    """Lookup a medicine row by canonical name (case/space insensitive)."""
    if not name or not name.strip():
        return None
    key = " ".join(name.strip().lower().replace("-", " ").split())
    with _connect() as conn:
        row = conn.execute(
            "SELECT id FROM medicines WHERE canonical_key=?",
            (key,),
        ).fetchone()
        if not row:
            alias = conn.execute(
                "SELECT medicine_id FROM aliases WHERE alias_key=? LIMIT 1",
                (key,),
            ).fetchone()
            if not alias:
                return None
            mid = alias["medicine_id"]
        else:
            mid = row["id"]
    return get_medicine(mid)


def list_products_for_medicine(medicine_id: int, *, limit: int = 400) -> list[ProductRecord]:
    if not catalog_has_products_table():
        return []
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT strength, dosage_form, route, product_ndc, source, spl_set_id
            FROM products
            WHERE medicine_id=?
            ORDER BY source, route, dosage_form, strength
            LIMIT ?
            """,
            (medicine_id, limit),
        ).fetchall()
    return [
        ProductRecord(
            strength=r["strength"],
            dosage_form=r["dosage_form"],
            route=r["route"],
            product_ndc=r["product_ndc"],
            source=r["source"],
            spl_set_id=r["spl_set_id"],
        )
        for r in rows
    ]


def list_label_sections(medicine_id: int) -> dict[str, str]:
    """Return section_key -> text (prefer FDA_SPL over DrugBank when both exist)."""
    if not catalog_available():
        return {}
    try:
        with _connect() as conn:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='label_sections'"
            ).fetchone()
            if not exists:
                return {}
            rows = conn.execute(
                """
                SELECT section_key, section_text, source
                FROM label_sections
                WHERE medicine_id=?
                ORDER BY CASE source WHEN 'FDA_SPL' THEN 0 WHEN 'DrugBank' THEN 1 ELSE 2 END
                """,
                (medicine_id,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, str] = {}
    for r in rows:
        key = r["section_key"]
        if key not in out:
            out[key] = r["section_text"]
    return out


@dataclass(frozen=True)
class LabelDoseOption:
    dose_label: str
    evidence_excerpt: str | None
    confidence: float
    dosage_form: str | None
    source: str


def catalog_has_label_dose_options_table() -> bool:
    if not catalog_available():
        return False
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='label_dose_options'"
            ).fetchone()
            return bool(row)
    except Exception:  # noqa: BLE001
        return False


def list_label_dose_options(
    medicine_id: int,
    *,
    route: str,
    strength: str,
) -> list[LabelDoseOption]:
    """Return FDA_SPL-extracted dose labels for medicine + route + strength."""
    if not medicine_id or not route or not strength:
        return []
    if not catalog_has_label_dose_options_table():
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT dose_label, evidence_excerpt, confidence, dosage_form, source
                FROM label_dose_options
                WHERE medicine_id=?
                  AND LOWER(TRIM(route))=LOWER(TRIM(?))
                  AND LOWER(TRIM(strength))=LOWER(TRIM(?))
                ORDER BY confidence DESC, dose_label COLLATE NOCASE
                """,
                (medicine_id, route, strength),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    out: list[LabelDoseOption] = []
    seen: set[str] = set()
    for r in rows:
        label = (r["dose_label"] or "").strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(
            LabelDoseOption(
                dose_label=label,
                evidence_excerpt=r["evidence_excerpt"],
                confidence=float(r["confidence"] or 0.0),
                dosage_form=r["dosage_form"],
                source=r["source"] or "FDA_SPL",
            )
        )
    return out


@dataclass(frozen=True)
class LabelFrequencyOption:
    frequency_label: str
    evidence_excerpt: str | None
    confidence: float
    source: str


@dataclass(frozen=True)
class LabelDoseFrequencyOption:
    dose_label: str
    frequency_label: str
    evidence_excerpt: str | None
    confidence: float
    source: str


@dataclass(frozen=True)
class IndicationOptionRecord:
    indication_label: str
    evidence_excerpt: str | None
    confidence: float
    source: str


def catalog_has_label_frequency_options_table() -> bool:
    if not catalog_available():
        return False
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='label_frequency_options'"
            ).fetchone()
            return bool(row)
    except Exception:  # noqa: BLE001
        return False


def catalog_has_label_dose_frequency_options_table() -> bool:
    if not catalog_available():
        return False
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='label_dose_frequency_options'"
            ).fetchone()
            return bool(row)
    except Exception:  # noqa: BLE001
        return False


def catalog_has_indication_options_table() -> bool:
    if not catalog_available():
        return False
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='indication_options'"
            ).fetchone()
            return bool(row)
    except Exception:  # noqa: BLE001
        return False


def list_label_frequency_options(
    medicine_id: int,
    *,
    route: str,
    strength: str,
) -> list[LabelFrequencyOption]:
    """Return FDA_SPL-extracted frequency labels for medicine + route + strength."""
    if not medicine_id or not route or not strength:
        return []
    if not catalog_has_label_frequency_options_table():
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT frequency_label, evidence_excerpt, confidence, source
                FROM label_frequency_options
                WHERE medicine_id=?
                  AND LOWER(TRIM(route))=LOWER(TRIM(?))
                  AND LOWER(TRIM(strength))=LOWER(TRIM(?))
                ORDER BY confidence DESC, frequency_label COLLATE NOCASE
                """,
                (medicine_id, route, strength),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    out: list[LabelFrequencyOption] = []
    seen: set[str] = set()
    for r in rows:
        label = (r["frequency_label"] or "").strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(
            LabelFrequencyOption(
                frequency_label=label,
                evidence_excerpt=r["evidence_excerpt"],
                confidence=float(r["confidence"] or 0.0),
                source=r["source"] or "FDA_SPL",
            )
        )
    return out


def list_label_dose_frequency_options(
    medicine_id: int,
    *,
    route: str,
    strength: str,
    dose_label: str,
) -> list[LabelDoseFrequencyOption]:
    """Return frequencies typed to medicine + route + strength + dose.

    Backwards-compatible: returns [] when the table is absent (older catalogs).
    """
    if not medicine_id or not route or not strength or not dose_label:
        return []
    if not catalog_has_label_dose_frequency_options_table():
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT dose_label, frequency_label, evidence_excerpt, confidence, source
                FROM label_dose_frequency_options
                WHERE medicine_id=?
                  AND LOWER(TRIM(route))=LOWER(TRIM(?))
                  AND LOWER(TRIM(strength))=LOWER(TRIM(?))
                  AND LOWER(TRIM(dose_label))=LOWER(TRIM(?))
                ORDER BY confidence DESC, frequency_label COLLATE NOCASE
                """,
                (medicine_id, route, strength, dose_label),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    out: list[LabelDoseFrequencyOption] = []
    seen: set[str] = set()
    for r in rows:
        label = (r["frequency_label"] or "").strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(
            LabelDoseFrequencyOption(
                dose_label=(r["dose_label"] or dose_label).strip(),
                frequency_label=label,
                evidence_excerpt=r["evidence_excerpt"],
                confidence=float(r["confidence"] or 0.0),
                source=r["source"] or "FDA_SPL",
            )
        )
    return out


def list_indication_options(medicine_id: int) -> list[IndicationOptionRecord]:
    """Return indexed indication labels for a medicine.

    Backwards-compatible: returns [] when the table is absent (older catalogs).
    """
    if not medicine_id:
        return []
    if not catalog_has_indication_options_table():
        return []
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT indication_label, evidence_excerpt, confidence, source
                FROM indication_options
                WHERE medicine_id=?
                ORDER BY confidence DESC, indication_label COLLATE NOCASE
                """,
                (medicine_id,),
            ).fetchall()
    except Exception:  # noqa: BLE001
        return []
    out: list[IndicationOptionRecord] = []
    seen: set[str] = set()
    for r in rows:
        label = (r["indication_label"] or "").strip()
        key = label.lower()
        if not label or key in seen:
            continue
        seen.add(key)
        out.append(
            IndicationOptionRecord(
                indication_label=label,
                evidence_excerpt=r["evidence_excerpt"],
                confidence=float(r["confidence"] or 0.0),
                source=r["source"] or "FDA_SPL",
            )
        )
    return out


@lru_cache(maxsize=1)
def _alias_rows() -> list[tuple[str, int, str]]:
    """Load alias index into memory for fuzzy search (built once per process)."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT alias_key, medicine_id, alias_raw FROM aliases"
            ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load catalog aliases: %s", exc)
        return []
    return [(r["alias_key"], r["medicine_id"], r["alias_raw"]) for r in rows]


def clear_alias_cache() -> None:
    _alias_rows.cache_clear()
    clear_runtime_catalog_copy_cache()
    try:
        _get_medicine_cached.cache_clear()
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.datasets.match import _alias_indexes

        _alias_indexes.cache_clear()
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services.datasets.match import _alias_indexes

        _alias_indexes.cache_clear()
    except Exception:  # noqa: BLE001
        pass
