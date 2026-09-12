import os
import logging
from pyiceberg.catalog.sql import SqlCatalog

logger = logging.getLogger(__name__)

# Defaults
from src.config import ICEBERG_CATALOG_DB, ICEBERG_WAREHOUSE_DIR

DEFAULT_CATALOG_URI = f"sqlite:///{ICEBERG_CATALOG_DB}"
DEFAULT_WAREHOUSE_PATH = ICEBERG_WAREHOUSE_DIR
DEFAULT_NAMESPACE = "football"

_catalog = None

def get_catalog() -> SqlCatalog:
    """Return the cached Iceberg SQLCatalog, creating it on first call."""
    global _catalog
    if _catalog is None:
        os.makedirs(DEFAULT_WAREHOUSE_PATH, exist_ok=True)
        # Ensure the directory for sqlite db exists
        db_path = DEFAULT_CATALOG_URI.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        logger.info(f"[Iceberg] Connecting to Catalog -> {DEFAULT_CATALOG_URI}")
        logger.info(f"[Iceberg] Warehouse path -> {DEFAULT_WAREHOUSE_PATH}")
        
        _catalog = SqlCatalog(
            "default",
            **{
                "type": "sql",
                "uri": DEFAULT_CATALOG_URI,
                "warehouse": f"file://{DEFAULT_WAREHOUSE_PATH}"
            }
        )
        
        # Create default namespace if not exists
        ensure_namespace(DEFAULT_NAMESPACE)
            
    return _catalog


def ensure_namespace(namespace: str) -> None:
    """Create the namespace if it does not already exist."""
    catalog = get_catalog() if _catalog is not None else None
    if catalog is None:
        # get_catalog() hasn't been called yet, call it first
        catalog = get_catalog()
    namespaces = catalog.list_namespaces()
    if (namespace,) not in namespaces:
        catalog.create_namespace(namespace)
        logger.info(f"[Iceberg] Created namespace: {namespace}")


def get_namespace_for_season(season: str) -> str:
    """
    Convert a season string into an Iceberg namespace name.
    
    Examples:
        "2026-2027" -> "football_2026_2027"
        "2026/2027" -> "football_2026_2027"
        "unknown"   -> "football"
    """
    if not season or season == "unknown":
        return DEFAULT_NAMESPACE
    season_safe = season.replace("/", "_").replace("-", "_")
    return f"football_{season_safe}"

