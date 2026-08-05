"""Real-dataset catalog services (FDA_NDC, DrugBank, optional FDA_SPL)."""

from app.services.datasets.match import DISCLAIMER, CatalogHit, reload_catalog, suggest_medicines
from app.services.datasets.catalog_store import catalog_available, get_meta
from app.services.datasets.paths import (
    catalog_db_path,
    drugbank_xml_path,
    ndc_json_path,
    spl_json_path,
    spl_label_paths,
)

__all__ = [
    "CatalogHit",
    "DISCLAIMER",
    "catalog_available",
    "catalog_db_path",
    "drugbank_xml_path",
    "get_meta",
    "ndc_json_path",
    "reload_catalog",
    "spl_json_path",
    "spl_label_paths",
    "suggest_medicines",
]
