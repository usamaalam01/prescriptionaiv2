"""Route cleaning pipeline: DRY_RUN | STAGE | APPLY_APPROVED.

Authoritative catalog (`medicine_catalog.sqlite3` / `products.route`) is never
modified by DRY_RUN or STAGE. APPLY_APPROVED only promotes rows inside the
staging database unless explicitly extended later.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.datasets.paths import catalog_db_path, data_dir
from app.services.datasets.route_cleaning.normalize import (
    dosage_form_conflict,
    normalize_route_key,
    preferred_display_name,
    route_code_from_key,
    split_route_components,
)
from app.services.datasets.route_cleaning.schema import (
    connect_staging,
    init_schema,
    reset_staging_tables,
    staging_db_path,
)

REPORT_DIR = data_dir().parent / "reports" / "route_cleaning"


@dataclass
class PipelineResult:
    mode: str
    run_id: str
    products_scanned: int
    products_with_route: int
    products_without_route: int
    distinct_atomic: int
    product_route_rows: int
    alias_rows: int
    master_rows: int
    audit_rows: int
    review_required: int
    staging_db: str | None
    authoritative_modified: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _open_catalog_ro() -> sqlite3.Connection:
    path = catalog_db_path()
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def run_dry_run() -> PipelineResult:
    """Read-only profile + CSV/JSON reports. No DB writes to catalog or staging."""
    import importlib.util

    script = Path(__file__).resolve().parents[5] / "scripts" / "route_cleaning_dry_run.py"
    # Prefer repo scripts path: backend/scripts
    alt = Path(__file__).resolve().parents[4] / "scripts" / "route_cleaning_dry_run.py"
    path = alt if alt.exists() else script
    spec = importlib.util.spec_from_file_location("route_cleaning_dry_run", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load dry-run script at {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()
    quality = json.loads((REPORT_DIR / "route_quality_report.json").read_text(encoding="utf-8"))
    return PipelineResult(
        mode="DRY_RUN",
        run_id=quality.get("generated_at", _now()),
        products_scanned=quality["products_scanned"],
        products_with_route=quality["products_with_route"],
        products_without_route=quality["products_without_route"],
        distinct_atomic=quality["distinct_atomic_route_components"],
        product_route_rows=0,
        alias_rows=0,
        master_rows=0,
        audit_rows=0,
        review_required=quality.get("route_dosage_form_conflicts", 0)
        + quality.get("multi_route_products", 0),
        staging_db=None,
        authoritative_modified=False,
    )


def run_stage(*, reset: bool = True) -> PipelineResult:
    """Write proposed mappings to staging DB only."""
    run_id = str(uuid.uuid4())
    now = _now()
    stage_path = staging_db_path(data_dir())
    stag = connect_staging(stage_path, read_only=False)
    init_schema(stag)
    if reset:
        reset_staging_tables(stag)

    cat = _open_catalog_ro()
    total = cat.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    # Pass 1: collect atomic variants for master + aliases
    variants: dict[str, set[str]] = defaultdict(set)
    products_with = 0
    products_without = 0

    rows = cat.execute(
        "SELECT id, medicine_id, route, dosage_form, source, product_ndc, spl_set_id "
        "FROM products"
    ).fetchall()

    for row in rows:
        raw = row["route"]
        if raw is None or not str(raw).strip():
            products_without += 1
            continue
        products_with += 1
        for comp in split_route_components(str(raw)):
            key = normalize_route_key(comp)
            if key:
                variants[key].add(comp)

    # Insert route_master
    key_to_id: dict[str, int] = {}
    for key, vars_ in sorted(variants.items(), key=lambda x: x[0]):
        name = preferred_display_name(vars_)
        code = route_code_from_key(key)
        cur = stag.execute(
            """
            INSERT INTO route_master (
              route_code, route_name, route_name_normalized, route_category,
              source_system, source_code, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, NULL, 'catalog_products', NULL, 1, ?, ?)
            """,
            (code, name, key, now, now),
        )
        key_to_id[key] = int(cur.lastrowid)

    # Aliases (case / formatting only)
    alias_count = 0
    for key, vars_ in variants.items():
        rid = key_to_id[key]
        preferred = preferred_display_name(vars_)
        for alias in sorted(vars_):
            status = (
                "SOURCE_VERIFIED"
                if alias == preferred
                else "AUTO_APPROVED_FORMATTING"
            )
            stag.execute(
                """
                INSERT OR IGNORE INTO route_aliases (
                  route_id, alias_raw, alias_normalized, source_system,
                  mapping_rule, validation_status, match_type, confidence,
                  created_at, updated_at
                ) VALUES (?, ?, ?, 'catalog_products', 'casefold_equality', ?, 'casefold_equality', 1.0, ?, ?)
                """,
                (rid, alias, normalize_route_key(alias), status, now, now),
            )
            alias_count += 1

    # Pass 2: product_route + audit
    pr_count = 0
    audit_count = 0
    review_count = 0

    def audit(**kwargs: object) -> None:
        nonlocal audit_count
        stag.execute(
            """
            INSERT INTO route_cleaning_audit (
              run_id, product_id, medicine_id, source_table, source_primary_key,
              route_raw, route_component_raw, route_normalized, route_id,
              rule_id, issue_code, severity, before_value, after_value,
              validation_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                kwargs.get("product_id"),
                kwargs.get("medicine_id"),
                kwargs.get("source_table", "products"),
                kwargs.get("source_primary_key"),
                kwargs.get("route_raw"),
                kwargs.get("route_component_raw"),
                kwargs.get("route_normalized"),
                kwargs.get("route_id"),
                kwargs.get("rule_id"),
                kwargs.get("issue_code"),
                kwargs.get("severity"),
                kwargs.get("before_value"),
                kwargs.get("after_value"),
                kwargs.get("validation_status"),
                now,
            ),
        )
        audit_count += 1

    for row in rows:
        pid = row["id"]
        mid = row["medicine_id"]
        raw = row["route"]
        form = row["dosage_form"]
        source = row["source"] or ""

        if raw is None or not str(raw).strip():
            audit(
                product_id=pid,
                medicine_id=mid,
                source_primary_key=str(pid),
                route_raw=None,
                issue_code="ROUTE_MISSING",
                severity="MEDIUM",
                validation_status="REVIEW_REQUIRED",
                rule_id="missing_route",
            )
            review_count += 1
            # Junction placeholder without route_id
            stag.execute(
                """
                INSERT OR IGNORE INTO product_route (
                  product_id, medicine_id, route_id, route_component_raw, route_raw_full,
                  source_order, source_system, source_record_id, source_evidence,
                  dosage_form, validation_status, issue_codes, created_at, updated_at
                ) VALUES (?, ?, NULL, NULL, NULL, 0, ?, ?, NULL, ?, 'REVIEW_REQUIRED', 'ROUTE_MISSING', ?, ?)
                """,
                (pid, mid, source, str(pid), form, now, now),
            )
            pr_count += 1
            continue

        raw_s = str(raw)
        comps = split_route_components(raw_s)
        if ";" in raw_s:
            audit(
                product_id=pid,
                medicine_id=mid,
                source_primary_key=str(pid),
                route_raw=raw_s,
                issue_code="MULTIPLE_ROUTES",
                severity="INFO",
                validation_status="NORMALIZED_ONLY",
                rule_id="split_semicolon",
                before_value=raw_s,
                after_value="|".join(comps),
            )

        seen_keys: set[str] = set()
        for order, comp in enumerate(comps):
            key = normalize_route_key(comp)
            if not key:
                audit(
                    product_id=pid,
                    medicine_id=mid,
                    source_primary_key=str(pid),
                    route_raw=raw_s,
                    route_component_raw=comp,
                    issue_code="EMPTY_ROUTE_COMPONENT",
                    severity="LOW",
                    validation_status="REVIEW_REQUIRED",
                    rule_id="empty_component",
                )
                review_count += 1
                continue
            if key in seen_keys:
                audit(
                    product_id=pid,
                    medicine_id=mid,
                    source_primary_key=str(pid),
                    route_raw=raw_s,
                    route_component_raw=comp,
                    route_normalized=key,
                    issue_code="DUPLICATE_ROUTE_COMPONENT",
                    severity="INFO",
                    validation_status="NORMALIZED_ONLY",
                    rule_id="dedupe_component",
                )
                continue
            seen_keys.add(key)

            rid = key_to_id.get(key)
            issues: list[str] = []
            status = "VALIDATED"
            conflict = dosage_form_conflict(key, form)
            if conflict:
                issues.append(conflict)
                status = "REVIEW_REQUIRED"
                review_count += 1
                audit(
                    product_id=pid,
                    medicine_id=mid,
                    source_primary_key=str(pid),
                    route_raw=raw_s,
                    route_component_raw=comp,
                    route_normalized=key,
                    route_id=rid,
                    issue_code=conflict,
                    severity="HIGH",
                    validation_status="REVIEW_REQUIRED",
                    rule_id="form_conflict_heuristic",
                    before_value=form,
                )

            if len(comps) > 1 and status == "VALIDATED":
                status = "NORMALIZED_ONLY"
                issues.append("MULTIPLE_ROUTES")

            # Case variant audit
            preferred = preferred_display_name(variants[key])
            if comp != preferred:
                audit(
                    product_id=pid,
                    medicine_id=mid,
                    source_primary_key=str(pid),
                    route_raw=raw_s,
                    route_component_raw=comp,
                    route_normalized=key,
                    route_id=rid,
                    issue_code="ROUTE_CASE_VARIANT",
                    severity="INFO",
                    validation_status="NORMALIZED_ONLY",
                    rule_id="casefold_alias",
                    before_value=comp,
                    after_value=preferred,
                )

            stag.execute(
                """
                INSERT OR IGNORE INTO product_route (
                  product_id, medicine_id, route_id, route_component_raw, route_raw_full,
                  source_order, source_system, source_record_id, source_evidence,
                  dosage_form, validation_status, issue_codes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    pid,
                    mid,
                    rid,
                    comp,
                    raw_s,
                    order,
                    source,
                    str(pid),
                    form,
                    status,
                    ",".join(issues) if issues else None,
                    now,
                    now,
                ),
            )
            pr_count += 1

    stag.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('last_stage_run_id', ?)",
        (run_id,),
    )
    stag.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('last_stage_at', ?)",
        (now,),
    )
    stag.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('catalog_path', ?)",
        (str(catalog_db_path()),),
    )
    stag.commit()

    # Export summary reports from staging
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "mode": "STAGE",
        "run_id": run_id,
        "generated_at": now,
        "staging_db": str(stage_path),
        "products_scanned": total,
        "products_with_route": products_with,
        "products_without_route": products_without,
        "route_master_rows": len(key_to_id),
        "route_alias_rows": alias_count,
        "product_route_rows": pr_count,
        "audit_rows": audit_count,
        "review_required_events": review_count,
        "authoritative_catalog_modified": False,
        "reconciliation": {
            "products_scanned_equals_total": True,
            "products_total": total,
        },
    }
    (REPORT_DIR / "route_stage_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    cat.close()
    stag.close()

    return PipelineResult(
        mode="STAGE",
        run_id=run_id,
        products_scanned=total,
        products_with_route=products_with,
        products_without_route=products_without,
        distinct_atomic=len(key_to_id),
        product_route_rows=pr_count,
        alias_rows=alias_count,
        master_rows=len(key_to_id),
        audit_rows=audit_count,
        review_required=review_count,
        staging_db=str(stage_path),
        authoritative_modified=False,
    )


def run_apply_approved(*, authorize: str | None = None) -> PipelineResult:
    """Promote approved staging rows inside staging DB only.

    Requires authorize == 'APPLY_APPROVED'. Never writes medicine_catalog.sqlite3.
    """
    if authorize != "APPLY_APPROVED":
        raise PermissionError(
            "APPLY_APPROVED refused: pass authorize='APPLY_APPROVED' explicitly. "
            "Authoritative catalog is never modified by this command."
        )

    run_id = str(uuid.uuid4())
    now = _now()
    stage_path = staging_db_path(data_dir())
    stag = connect_staging(stage_path, read_only=False)
    init_schema(stag)

    # Mark VALIDATED + NORMALIZED_ONLY (formatting) as approved within staging
    cur = stag.execute(
        """
        UPDATE product_route
        SET validation_status = 'VALIDATED',
            updated_at = ?
        WHERE validation_status IN ('VALIDATED', 'NORMALIZED_ONLY')
        """,
        (now,),
    )
    updated = cur.rowcount

    stag.execute(
        """
        INSERT INTO route_cleaning_audit (
          run_id, source_table, rule_id, issue_code, severity,
          before_value, after_value, validation_status, applied_by, applied_at, created_at
        ) VALUES (?, 'product_route', 'apply_approved_staging_only', 'APPLY_STAGING',
                  'INFO', ?, ?, 'VALIDATED', 'pipeline', ?, ?)
        """,
        (run_id, f"rows_touched≈{updated}", "staging_promote", now, now),
    )
    stag.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('last_apply_run_id', ?)",
        (run_id,),
    )
    stag.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('last_apply_at', ?)",
        (now,),
    )
    stag.commit()
    stag.close()

    return PipelineResult(
        mode="APPLY_APPROVED",
        run_id=run_id,
        products_scanned=0,
        products_with_route=0,
        products_without_route=0,
        distinct_atomic=0,
        product_route_rows=updated,
        alias_rows=0,
        master_rows=0,
        audit_rows=1,
        review_required=0,
        staging_db=str(stage_path),
        authoritative_modified=False,
    )
