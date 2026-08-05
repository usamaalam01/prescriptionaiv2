"""Build a diligence-grade SQLite medicine catalog from FDA NDC + DrugBank + FDA SPL.

Run:
  python -m app.services.datasets.build_index

Indexes:
  - medicines / aliases / strengths (identity + union fields)
  - products (per-source strength + form + route + NDC / set_id)
  - label_sections (SPL / DrugBank diligence text for HITL evidence)

PharmaAssist remains pharmacist decision-support (not clinical care).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
from pathlib import Path
from xml.etree import ElementTree as ET

from app.services.datasets.paths import (
    catalog_db_path,
    drugbank_xml_path,
    ndc_json_path,
    spl_json_path,
    spl_label_paths,
)

_NS = "{http://www.drugbank.ca}"
_SPACE = re.compile(r"\s+")
_SECTION_MAX = 2500
# Keep more of dosage_and_administration for SIG extract (dose + frequency)
_DOSAGE_ADMIN_MAX = 16000
_INDICATION_MAX = 2500

# SPL sections kept for catalog diligence (truncated)
_SPL_SECTIONS = (
    "indications_and_usage",
    "dosage_and_administration",
    "dosage_forms_and_strengths",
    "contraindications",
    "warnings_and_cautions",
    "warnings",
    "drug_interactions",
    "adverse_reactions",
)


def normalize(value: str | None) -> str:
    if not value:
        return ""
    return _SPACE.sub(" ", value.strip().lower().replace("-", " "))


def _clip(text: str | None, limit: int = _SECTION_MAX) -> str | None:
    if not text:
        return None
    cleaned = _SPACE.sub(" ", str(text).strip())
    if not cleaned:
        return None
    if len(cleaned) > limit:
        return cleaned[:limit].rstrip() + "…"
    return cleaned


def _first_list_text(value) -> str | None:
    """First non-empty openFDA list string, whitespace-normalized (no length clip).

    Callers must clip for storage (_insert_section / _INDICATION_MAX). Early clipping
    here previously capped dosage_and_administration at 2500 before the 16k path ran.
    """
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            if item is None:
                continue
            cleaned = _SPACE.sub(" ", str(item).strip())
            if cleaned:
                return cleaned
        return None
    cleaned = _SPACE.sub(" ", str(value).strip())
    return cleaned or None


def _connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS indication_options;
        DROP TABLE IF EXISTS label_dose_frequency_options;
        DROP TABLE IF EXISTS label_frequency_options;
        DROP TABLE IF EXISTS label_dose_options;
        DROP TABLE IF EXISTS label_sections;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS aliases;
        DROP TABLE IF EXISTS strengths;
        DROP TABLE IF EXISTS medicines;
        DROP TABLE IF EXISTS meta;

        CREATE TABLE medicines (
            id INTEGER PRIMARY KEY,
            canonical_name TEXT NOT NULL,
            canonical_key TEXT NOT NULL UNIQUE,
            drugbank_id TEXT,
            product_ndc TEXT,
            dosage_forms TEXT,
            routes TEXT,
            sources TEXT NOT NULL,
            indication TEXT,
            spl_set_id TEXT
        );
        CREATE TABLE aliases (
            alias_key TEXT NOT NULL,
            medicine_id INTEGER NOT NULL,
            alias_raw TEXT NOT NULL,
            PRIMARY KEY (alias_key, medicine_id),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE strengths (
            medicine_id INTEGER NOT NULL,
            strength TEXT NOT NULL,
            PRIMARY KEY (medicine_id, strength),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            strength TEXT,
            dosage_form TEXT,
            route TEXT,
            product_ndc TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL,
            UNIQUE (medicine_id, strength, dosage_form, route, product_ndc, source),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE label_sections (
            medicine_id INTEGER NOT NULL,
            section_key TEXT NOT NULL,
            section_text TEXT NOT NULL,
            source TEXT NOT NULL,
            PRIMARY KEY (medicine_id, section_key, source),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE label_dose_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dosage_form TEXT,
            dose_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE label_frequency_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            frequency_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, frequency_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE label_dose_frequency_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dose_label TEXT NOT NULL,
            frequency_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label, frequency_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE indication_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            indication_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            source TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, indication_label, source),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        );
        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE INDEX idx_aliases_key ON aliases(alias_key);
        CREATE INDEX idx_products_medicine ON products(medicine_id);
        CREATE INDEX idx_products_route ON products(route);
        CREATE INDEX idx_label_medicine ON label_sections(medicine_id);
        CREATE INDEX idx_label_dose_lookup
          ON label_dose_options(medicine_id, route, strength);
        CREATE INDEX idx_label_freq_lookup
          ON label_frequency_options(medicine_id, route, strength);
        CREATE INDEX idx_label_dose_freq_lookup
          ON label_dose_frequency_options(medicine_id, route, strength, dose_label);
        CREATE INDEX idx_indication_options_medicine
          ON indication_options(medicine_id);
        """
    )
    conn.commit()


def _upsert_medicine(
    conn: sqlite3.Connection,
    *,
    canonical_name: str,
    aliases: set[str],
    strengths: set[str],
    dosage_forms: set[str],
    routes: set[str],
    source: str,
    drugbank_id: str | None = None,
    product_ndc: str | None = None,
    indication: str | None = None,
    spl_set_id: str | None = None,
) -> int | None:
    key = normalize(canonical_name)
    if not key or len(key) < 2:
        return None
    row = conn.execute(
        "SELECT id, sources, dosage_forms, routes, drugbank_id, product_ndc, indication, spl_set_id FROM medicines WHERE canonical_key=?",
        (key,),
    ).fetchone()
    if row:
        mid, sources, forms_json, routes_json, dbid, ndc, ind, set_id = row
        src = set(json.loads(sources or "[]"))
        src.add(source)
        forms = set(json.loads(forms_json or "[]")) | dosage_forms
        rts = set(json.loads(routes_json or "[]")) | routes
        conn.execute(
            """
            UPDATE medicines SET
              sources=?, dosage_forms=?, routes=?,
              drugbank_id=COALESCE(?, drugbank_id),
              product_ndc=COALESCE(?, product_ndc),
              indication=COALESCE(?, indication),
              spl_set_id=COALESCE(?, spl_set_id)
            WHERE id=?
            """,
            (
                json.dumps(sorted(src)),
                json.dumps(sorted(forms)),
                json.dumps(sorted(rts)),
                drugbank_id,
                product_ndc,
                indication,
                spl_set_id,
                mid,
            ),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO medicines(
              canonical_name, canonical_key, drugbank_id, product_ndc,
              dosage_forms, routes, sources, indication, spl_set_id
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                canonical_name.strip(),
                key,
                drugbank_id,
                product_ndc,
                json.dumps(sorted(dosage_forms)),
                json.dumps(sorted(routes)),
                json.dumps([source]),
                indication,
                spl_set_id,
            ),
        )
        mid = cur.lastrowid

    for alias in aliases:
        akey = normalize(alias)
        if not akey or len(akey) < 2:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO aliases(alias_key, medicine_id, alias_raw) VALUES (?,?,?)",
            (akey, mid, alias.strip()),
        )
    for strength in strengths:
        s = strength.strip()
        if not s:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO strengths(medicine_id, strength) VALUES (?,?)",
            (mid, s),
        )
    return int(mid)


def _insert_product(
    conn: sqlite3.Connection,
    medicine_id: int,
    *,
    strength: str | None,
    dosage_form: str | None,
    route: str | None,
    product_ndc: str | None,
    source: str,
    spl_set_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO products(
          medicine_id, strength, dosage_form, route, product_ndc, spl_set_id, source
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            medicine_id,
            (strength or "").strip() or None,
            (dosage_form or "").strip() or None,
            (route or "").strip() or None,
            (product_ndc or "").strip() or None,
            (spl_set_id or "").strip() or None,
            source,
        ),
    )


def _insert_section(
    conn: sqlite3.Connection,
    medicine_id: int,
    *,
    section_key: str,
    section_text: str | None,
    source: str,
) -> None:
    limit = _DOSAGE_ADMIN_MAX if section_key == "dosage_and_administration" else _SECTION_MAX
    text = _clip(section_text, limit)
    if not text:
        return
    conn.execute(
        """
        INSERT OR REPLACE INTO label_sections(medicine_id, section_key, section_text, source)
        VALUES (?,?,?,?)
        """,
        (medicine_id, section_key, text, source),
    )


def ingest_ndc(conn: sqlite3.Connection, path: Path, *, limit: int | None = None) -> int:
    import ijson

    if not path.exists():
        raise FileNotFoundError(f"FDA NDC JSON not found: {path}")

    count = 0
    with path.open("rb") as f:
        for row in ijson.items(f, "results.item"):
            brand = (row.get("brand_name") or row.get("brand_name_base") or "").strip()
            generic = (row.get("generic_name") or "").strip()
            canonical = generic or brand
            if not canonical:
                continue
            aliases = {a for a in (brand, generic) if a}
            strengths: set[str] = set()
            for ing in row.get("active_ingredients") or []:
                name = (ing.get("name") or "").strip()
                strength = (ing.get("strength") or "").strip()
                if name:
                    aliases.add(name)
                if strength:
                    strengths.add(strength)
            form = str(row.get("dosage_form") or "").strip() or None
            routes = [str(r).strip() for r in (row.get("route") or []) if r]
            forms = {form} if form else set()
            route_set = set(routes)
            product_ndc = (row.get("product_ndc") or "").strip() or None
            mid = _upsert_medicine(
                conn,
                canonical_name=canonical.title() if canonical == canonical.upper() else canonical,
                aliases=aliases,
                strengths=strengths,
                dosage_forms=forms,
                routes=route_set,
                source="FDA_NDC",
                product_ndc=product_ndc,
            )
            if mid is None:
                continue
            # One product row per strength × route (form shared); empty strength still recorded
            strength_list = sorted(strengths) or [None]
            route_list = routes or [None]
            for strength in strength_list:
                for route in route_list:
                    _insert_product(
                        conn,
                        mid,
                        strength=strength,
                        dosage_form=form,
                        route=route,
                        product_ndc=product_ndc,
                        source="FDA_NDC",
                    )
            count += 1
            if count % 5000 == 0:
                conn.commit()
                print(f"  NDC ingested {count}...", flush=True)
            if limit is not None and count >= limit:
                break
    conn.commit()
    return count


def ingest_drugbank(conn: sqlite3.Connection, path: Path, *, limit: int | None = None) -> int:
    if not path.exists():
        raise FileNotFoundError(f"DrugBank XML not found: {path}")

    count = 0
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != f"{_NS}drug":
            continue
        # Top-level DrugBank entries carry type="small molecule"|"biotech"|...
        # Nested <drug> stubs (interactions, mixtures) must be skipped.
        if "type" not in elem.attrib:
            elem.clear()
            continue
        name_el = elem.find(f"{_NS}name")
        name = (name_el.text or "").strip() if name_el is not None else ""
        if not name:
            elem.clear()
            continue

        dbid = None
        for id_el in elem.findall(f"{_NS}drugbank-id"):
            if id_el.attrib.get("primary") == "true" and id_el.text:
                dbid = id_el.text.strip()
                break
        if dbid is None:
            first = elem.find(f"{_NS}drugbank-id")
            if first is not None and first.text:
                dbid = first.text.strip()

        groups = {
            (g.text or "").strip().lower()
            for g in elem.findall(f"{_NS}groups/{_NS}group")
            if g.text
        }
        if groups and "approved" not in groups and "vet_approved" not in groups:
            elem.clear()
            continue

        aliases: set[str] = {name}
        for syn in elem.findall(f"{_NS}synonyms/{_NS}synonym"):
            if syn.text and syn.text.strip():
                aliases.add(syn.text.strip())

        indication_el = elem.find(f"{_NS}indication")
        indication = _clip(
            (indication_el.text or "").strip() if indication_el is not None else None,
            _INDICATION_MAX,
        )

        strengths: set[str] = set()
        forms: set[str] = set()
        routes: set[str] = set()
        product_rows: list[tuple[str | None, str | None, str | None]] = []
        for prod in elem.findall(f"{_NS}products/{_NS}product"):
            pn = prod.find(f"{_NS}name")
            if pn is not None and pn.text and pn.text.strip():
                aliases.add(pn.text.strip())
            strength_el = prod.find(f"{_NS}strength")
            df = prod.find(f"{_NS}dosage-form")
            rt = prod.find(f"{_NS}route")
            strength = strength_el.text.strip() if strength_el is not None and strength_el.text else None
            form = df.text.strip() if df is not None and df.text else None
            route = rt.text.strip() if rt is not None and rt.text else None
            if strength:
                strengths.add(strength)
            if form:
                forms.add(form)
            if route:
                routes.add(route)
            if strength or form or route:
                product_rows.append((strength, form, route))

        mid = _upsert_medicine(
            conn,
            canonical_name=name,
            aliases=aliases,
            strengths=strengths,
            dosage_forms=forms,
            routes=routes,
            source="DrugBank",
            drugbank_id=dbid,
            indication=indication,
        )
        if mid is not None:
            for strength, form, route in product_rows:
                _insert_product(
                    conn,
                    mid,
                    strength=strength,
                    dosage_form=form,
                    route=route,
                    product_ndc=None,
                    source="DrugBank",
                )
            if indication:
                _insert_section(
                    conn,
                    mid,
                    section_key="indications_and_usage",
                    section_text=indication,
                    source="DrugBank",
                )
            # Additional diligence snippets when present
            for tag, key in (
                ("pharmacodynamics", "pharmacodynamics"),
                ("mechanism-of-action", "mechanism_of_action"),
                ("toxicity", "overdosage"),
            ):
                el = elem.find(f"{_NS}{tag}")
                if el is not None and el.text and el.text.strip():
                    _insert_section(
                        conn,
                        mid,
                        section_key=key,
                        section_text=el.text,
                        source="DrugBank",
                    )

        count += 1
        elem.clear()
        if count % 2000 == 0:
            conn.commit()
            print(f"  DrugBank ingested {count}...", flush=True)
        if limit is not None and count >= limit:
            break
    conn.commit()
    return count


def ingest_spl_full(conn: sqlite3.Connection, path: Path, *, limit: int | None = None) -> int:
    """Stream full openFDA SPL JSON into medicines + products + label_sections."""
    if not path.exists():
        print(f"  SPL skipped (missing): {path}", flush=True)
        return 0
    import ijson

    # openFDA drug-label shards use results.item; legacy monolith may use item
    def _iter_rows(fh):
        # Peek which path yields rows without loading whole file
        yield from ijson.items(fh, "results.item")

    count = 0
    with path.open("rb") as f:
        rows = _iter_rows(f)
        # If first path yields nothing, reopen with legacy "item"
        try:
            first = next(rows)
        except StopIteration:
            first = None
        if first is None:
            print(f"  SPL path results.item empty; trying item: {path.name}", flush=True)
            with path.open("rb") as f2:
                for row in ijson.items(f2, "item"):
                    n = _ingest_spl_row(conn, row)
                    if n:
                        count += 1
                    if count % 2000 == 0 and count:
                        conn.commit()
                        print(f"  SPL ingested {count}...", flush=True)
                    if limit is not None and count >= limit:
                        break
            conn.commit()
            return count

        def _all_rows():
            yield first
            yield from rows

        for row in _all_rows():
            if _ingest_spl_row(conn, row):
                count += 1
            if count % 2000 == 0 and count:
                conn.commit()
                print(f"  SPL ingested {count}...", flush=True)
            if limit is not None and count >= limit:
                break
    conn.commit()
    return count


def _ingest_spl_row(conn: sqlite3.Connection, row: dict) -> bool:
    openfda = row.get("openfda") or {}
    brands = list(openfda.get("brand_name") or [])
    generics = list(openfda.get("generic_name") or [])
    substances = list(openfda.get("substance_name") or [])
    if not brands and not generics:
        pde = row.get("spl_product_data_elements") or []
        if pde and isinstance(pde, list) and pde:
            head = str(pde[0]).split()
            if head:
                brands = [head[0]]
    canonical = (generics[0] if generics else (brands[0] if brands else "")).strip()
    if not canonical:
        return False

    aliases = {*(brands or []), *(generics or []), *(substances or [])}
    routes = {str(r).strip() for r in (openfda.get("route") or []) if r}
    forms: set[str] = set()
    if openfda.get("dosage_form"):
        forms = {str(x).strip() for x in openfda.get("dosage_form") or [] if x}

    product_ndcs = [str(x).strip() for x in (openfda.get("product_ndc") or []) if x]
    product_ndc = product_ndcs[0] if product_ndcs else None
    set_ids = openfda.get("spl_set_id") or ([] if not row.get("set_id") else [row.get("set_id")])
    spl_set_id = str(set_ids[0]).strip() if set_ids else (str(row.get("set_id") or "").strip() or None)

    indication = _clip(
        _first_list_text(row.get("indications_and_usage")),
        _INDICATION_MAX,
    )
    mid = _upsert_medicine(
        conn,
        canonical_name=str(canonical).title() if str(canonical).isupper() else str(canonical),
        aliases={str(a) for a in aliases if a},
        strengths=set(),
        dosage_forms=forms,
        routes=routes,
        source="FDA_SPL",
        product_ndc=product_ndc,
        indication=indication,
        spl_set_id=spl_set_id,
    )
    if mid is None:
        return False

    route_list = sorted(routes) or [None]
    form_list = sorted(forms) or [None]
    ndc_list = product_ndcs or [None]
    for route in route_list:
        for form in form_list:
            for ndc in ndc_list[:3]:
                _insert_product(
                    conn,
                    mid,
                    strength=None,
                    dosage_form=form,
                    route=route,
                    product_ndc=ndc,
                    source="FDA_SPL",
                    spl_set_id=spl_set_id,
                )

    dosage_admin = None
    for section_key in _SPL_SECTIONS:
        text = _first_list_text(row.get(section_key))
        if text:
            _insert_section(
                conn,
                mid,
                section_key=section_key,
                section_text=text,
                source="FDA_SPL",
            )
            if section_key == "dosage_and_administration":
                dosage_admin = text
    if dosage_admin:
        _insert_dose_options_from_section(
            conn,
            mid,
            section_text=dosage_admin,
            spl_set_id=spl_set_id,
        )
    return True


def ensure_label_dose_options_table(conn: sqlite3.Connection) -> None:
    """Create dose/frequency/indication option tables on an existing catalog."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS label_dose_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dosage_form TEXT,
            dose_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS label_frequency_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            frequency_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, frequency_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS label_dose_frequency_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            strength TEXT NOT NULL,
            dose_label TEXT NOT NULL,
            frequency_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            spl_set_id TEXT,
            source TEXT NOT NULL DEFAULT 'FDA_SPL',
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, route, strength, dose_label, frequency_label),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS indication_options (
            id INTEGER PRIMARY KEY,
            medicine_id INTEGER NOT NULL,
            indication_label TEXT NOT NULL,
            evidence_excerpt TEXT,
            source TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.8,
            UNIQUE (medicine_id, indication_label, source),
            FOREIGN KEY (medicine_id) REFERENCES medicines(id)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_label_dose_lookup
          ON label_dose_options(medicine_id, route, strength)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_label_freq_lookup
          ON label_frequency_options(medicine_id, route, strength)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_label_dose_freq_lookup
          ON label_dose_frequency_options(medicine_id, route, strength, dose_label)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_indication_options_medicine
          ON indication_options(medicine_id)
        """
    )
    conn.commit()


def _product_triples_for_medicine(conn: sqlite3.Connection, medicine_id: int) -> list[tuple]:
    products = conn.execute(
        """
        SELECT DISTINCT strength, dosage_form, route
        FROM products
        WHERE medicine_id=? AND strength IS NOT NULL AND TRIM(strength) != ''
        """,
        (medicine_id,),
    ).fetchall()
    if products:
        return list(products)
    strengths = [
        r[0]
        for r in conn.execute(
            "SELECT strength FROM strengths WHERE medicine_id=?",
            (medicine_id,),
        ).fetchall()
    ]
    routes_json = conn.execute(
        "SELECT routes, dosage_forms FROM medicines WHERE id=?",
        (medicine_id,),
    ).fetchone()
    routes = list(json.loads(routes_json[0] or "[]")) if routes_json else []
    forms = list(json.loads(routes_json[1] or "[]")) if routes_json else []
    out: list[tuple] = []
    for strength in strengths:
        for route in routes or [None]:
            for form in forms or [None]:
                out.append((strength, form, route))
    return out


def _insert_dose_options_from_section(
    conn: sqlite3.Connection,
    medicine_id: int,
    *,
    section_text: str,
    spl_set_id: str | None = None,
) -> int:
    """Parse SPL dosage text and store doses, frequencies, and dose↔frequency pairs."""
    from app.services.catalog_sig_options import classify_route
    from app.services.datasets.label_dose_extract import (
        doses_for_label_context,
        frequencies_for_label_context,
    )

    products = _product_triples_for_medicine(conn, medicine_id)
    inserted = 0
    for strength, dosage_form, route in products:
        route_label = classify_route(route) or (str(route).strip() if route else None)
        if not route_label or not strength:
            continue
        strength_s = str(strength).strip()
        dose_cands = doses_for_label_context(
            section_text,
            route=route_label,
            strength=strength_s,
            dosage_form=dosage_form,
        )
        for cand in dose_cands:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO label_dose_options(
                      medicine_id, route, strength, dosage_form, dose_label,
                      evidence_excerpt, spl_set_id, source, confidence
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        medicine_id,
                        route_label,
                        strength_s,
                        (dosage_form or "").strip() or None,
                        cand.dose_label,
                        cand.evidence_excerpt,
                        spl_set_id,
                        "FDA_SPL",
                        float(cand.confidence),
                    ),
                )
                inserted += 1
            except sqlite3.Error:
                continue
            # Typed relation: frequencies co-occurring with this exact dose label
            for fc in frequencies_for_label_context(
                section_text,
                route=route_label,
                strength=strength_s,
                dose=cand.dose_label,
            ):
                # Prefer dose-adjacent evidence when available; keep non-adjacent as weaker
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO label_dose_frequency_options(
                          medicine_id, route, strength, dose_label, frequency_label,
                          evidence_excerpt, spl_set_id, source, confidence
                        ) VALUES (?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            medicine_id,
                            route_label,
                            strength_s,
                            cand.dose_label,
                            fc.frequency_label,
                            fc.evidence_excerpt,
                            spl_set_id,
                            "FDA_SPL",
                            float(fc.confidence),
                        ),
                    )
                    inserted += 1
                except sqlite3.Error:
                    continue
        for fc in frequencies_for_label_context(
            section_text,
            route=route_label,
            strength=strength_s,
        ):
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO label_frequency_options(
                      medicine_id, route, strength, frequency_label,
                      evidence_excerpt, spl_set_id, source, confidence
                    ) VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        medicine_id,
                        route_label,
                        strength_s,
                        fc.frequency_label,
                        fc.evidence_excerpt,
                        spl_set_id,
                        "FDA_SPL",
                        float(fc.confidence),
                    ),
                )
                inserted += 1
            except sqlite3.Error:
                continue
    return inserted


def populate_indication_options(conn: sqlite3.Connection) -> int:
    """Index selectable indication labels from medicines.indication + SPL sections.

    Lazy-imports the label miner from indication_options to avoid circular imports
    with catalog_store / runtime query paths.
    """
    ensure_label_dose_options_table(conn)
    # Import extraction only (no catalog_store writes from that module).
    from app.services.datasets.indication_options import _extract_labels

    total = 0
    rows = conn.execute(
        "SELECT id, indication, sources FROM medicines"
    ).fetchall()
    for medicine_id, indication, sources_json in rows:
        try:
            sources = json.loads(sources_json or "[]")
        except json.JSONDecodeError:
            sources = []
        primary_source = "DrugBank"
        for src in sources:
            s = str(src).upper()
            if "SPL" in s:
                primary_source = "FDA_SPL"
                break
            if "NDC" in s:
                primary_source = "FDA_NDC"
            elif "DRUGBANK" in s:
                primary_source = "DrugBank"
        if indication:
            for label in _extract_labels(indication):
                excerpt = (indication or "").strip()
                if len(excerpt) > 220:
                    excerpt = excerpt[:220].rstrip() + "…"
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO indication_options(
                          medicine_id, indication_label, evidence_excerpt, source, confidence
                        ) VALUES (?,?,?,?,?)
                        """,
                        (int(medicine_id), label, excerpt, primary_source, 0.85),
                    )
                    total += 1
                except sqlite3.Error:
                    continue

    section_rows = conn.execute(
        """
        SELECT medicine_id, section_text, source
        FROM label_sections
        WHERE section_key='indications_and_usage'
        """
    ).fetchall()
    for medicine_id, section_text, source in section_rows:
        src = str(source or "FDA_SPL").upper()
        if "SPL" in src:
            src_label = "FDA_SPL"
        elif "DRUGBANK" in src:
            src_label = "DrugBank"
        elif "NDC" in src:
            src_label = "FDA_NDC"
        else:
            src_label = src or "FDA_SPL"
        for label in _extract_labels(section_text):
            excerpt = (section_text or "").strip()
            if len(excerpt) > 220:
                excerpt = excerpt[:220].rstrip() + "…"
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO indication_options(
                      medicine_id, indication_label, evidence_excerpt, source, confidence
                    ) VALUES (?,?,?,?,?)
                    """,
                    (int(medicine_id), label, excerpt, src_label, 0.9),
                )
                total += 1
            except sqlite3.Error:
                continue
        if total and total % 5000 == 0:
            conn.commit()
            print(f"  indication option rows ~{total}...", flush=True)
    conn.commit()
    return total


def populate_label_dose_options(conn: sqlite3.Connection) -> int:
    """Backfill dose, frequency, and dose↔frequency options from stored sections."""
    ensure_label_dose_options_table(conn)
    rows = conn.execute(
        """
        SELECT medicine_id, section_text
        FROM label_sections
        WHERE section_key='dosage_and_administration' AND source='FDA_SPL'
        """
    ).fetchall()
    total = 0
    for medicine_id, section_text in rows:
        spl_set_id = conn.execute(
            "SELECT spl_set_id FROM medicines WHERE id=?",
            (medicine_id,),
        ).fetchone()
        total += _insert_dose_options_from_section(
            conn,
            int(medicine_id),
            section_text=section_text,
            spl_set_id=(spl_set_id[0] if spl_set_id else None),
        )
        if total and total % 5000 == 0:
            conn.commit()
            print(f"  label SIG option rows ~{total}...", flush=True)
    conn.commit()
    return total


# Backward-compatible alias
ingest_spl_light = ingest_spl_full


def build_catalog(
    *,
    include_spl: bool = True,
    ndc_limit: int | None = None,
    drugbank_limit: int | None = None,
    spl_limit: int | None = None,
) -> Path:
    final_db = catalog_db_path()
    # Build to a staging file so a live API can keep reading the old catalog until swap.
    db = final_db.with_name(final_db.stem + ".build.sqlite3")
    if db.exists():
        db.unlink()
    started = time.time()
    spl_paths = spl_label_paths() if include_spl else []
    print(f"Building FULL diligence catalog -> {db}", flush=True)
    print(f"  (will replace {final_db} on success)", flush=True)
    print(f"  NDC: {ndc_json_path()}", flush=True)
    print(f"  DrugBank: {drugbank_xml_path()}", flush=True)
    if include_spl:
        print(f"  SPL shards ({len(spl_paths)}):", flush=True)
        for p in spl_paths:
            print(f"    - {p}", flush=True)
        if not spl_paths:
            print(f"  SPL: missing (looked for drug-label-*-of-*.json / {spl_json_path()})", flush=True)
    else:
        print("  SPL: skipped", flush=True)
    conn = _connect(db)
    _init_schema(conn)

    ndc_n = ingest_ndc(conn, ndc_json_path(), limit=ndc_limit)
    print(f"FDA_NDC products upserted: {ndc_n}", flush=True)
    db_n = ingest_drugbank(conn, drugbank_xml_path(), limit=drugbank_limit)
    print(f"DrugBank drugs upserted: {db_n}", flush=True)
    spl_n = 0
    if include_spl:
        remaining = spl_limit
        for i, path in enumerate(spl_paths, start=1):
            print(f"FDA_SPL shard {i}/{len(spl_paths)}: {path.name}", flush=True)
            n = ingest_spl_full(conn, path, limit=remaining)
            spl_n += n
            print(f"  shard done (+{n}); SPL total={spl_n}", flush=True)
            if remaining is not None:
                remaining -= n
                if remaining <= 0:
                    break
        print(f"FDA_SPL labels upserted: {spl_n}", flush=True)

    print("Populating label_dose_options from dosage_and_administration…", flush=True)
    dose_opt_n = populate_label_dose_options(conn)
    print(f"label_dose_options inserts attempted: {dose_opt_n}", flush=True)
    print("Populating indication_options from medicines + SPL sections…", flush=True)
    ind_opt_n = populate_indication_options(conn)
    print(f"indication_options inserts attempted: {ind_opt_n}", flush=True)

    med_count = conn.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
    alias_count = conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0]
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    section_count = conn.execute("SELECT COUNT(*) FROM label_sections").fetchone()[0]
    dose_count = conn.execute("SELECT COUNT(*) FROM label_dose_options").fetchone()[0]
    try:
        freq_count = conn.execute("SELECT COUNT(*) FROM label_frequency_options").fetchone()[0]
    except sqlite3.Error:
        freq_count = 0
    try:
        dose_freq_count = conn.execute(
            "SELECT COUNT(*) FROM label_dose_frequency_options"
        ).fetchone()[0]
    except sqlite3.Error:
        dose_freq_count = 0
    try:
        indication_count = conn.execute("SELECT COUNT(*) FROM indication_options").fetchone()[0]
    except sqlite3.Error:
        indication_count = 0
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        ("built_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
        (
            "stats",
            json.dumps(
                {
                    "medicines": med_count,
                    "aliases": alias_count,
                    "products": product_count,
                    "label_sections": section_count,
                    "label_dose_options": dose_count,
                    "label_frequency_options": freq_count,
                    "label_dose_frequency_options": dose_freq_count,
                    "indication_options": indication_count,
                    "ndc": ndc_n,
                    "drugbank": db_n,
                    "spl": spl_n,
                    "spl_shards": [p.name for p in spl_paths],
                    "source_files": {
                        "ndc": ndc_json_path().name,
                        "drugbank": drugbank_xml_path().name,
                        "spl": [p.name for p in spl_paths],
                    },
                    "full_data": True,
                    "full_diligence": True,
                    "seconds": round(time.time() - started, 1),
                }
            ),
        ),
    )
    conn.commit()
    conn.close()
    # Checkpoint/remove WAL sidecars on staging, then atomically replace live catalog.
    for suffix in ("-wal", "-shm"):
        side = Path(str(db) + suffix)
        if side.exists():
            try:
                side.unlink()
            except OSError:
                pass
    backup = final_db.with_name(final_db.stem + ".prev.sqlite3")
    if final_db.exists():
        if backup.exists():
            backup.unlink()
        try:
            final_db.replace(backup)
        except OSError:
            # Live process may hold the file; overwrite in place as fallback.
            backup = None
    try:
        db.replace(final_db)
    except OSError:
        # Fallback copy if replace blocked
        import shutil

        shutil.copy2(db, final_db)
        db.unlink(missing_ok=True)
    print(
        f"Done. medicines={med_count} aliases={alias_count} "
        f"products={product_count} sections={section_count} "
        f"dose_options={dose_count} freq_options={freq_count} "
        f"dose_freq={dose_freq_count} indications={indication_count} "
        f"in {time.time() - started:.1f}s -> {final_db}",
        flush=True,
    )
    return final_db


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build PharmaAssist full-diligence medicine catalog (NDC + DrugBank + SPL)"
    )
    parser.add_argument(
        "--skip-spl",
        action="store_true",
        help="Skip FDA SPL (still indexes full NDC + DrugBank)",
    )
    parser.add_argument("--ndc-limit", type=int, default=None, help="Dev only: limit NDC rows")
    parser.add_argument("--drugbank-limit", type=int, default=None, help="Dev only: limit DrugBank drugs")
    parser.add_argument("--spl-limit", type=int, default=None, help="Dev only: limit SPL rows")
    args = parser.parse_args()
    build_catalog(
        include_spl=not args.skip_spl,
        ndc_limit=args.ndc_limit,
        drugbank_limit=args.drugbank_limit,
        spl_limit=args.spl_limit,
    )


if __name__ == "__main__":
    main()
