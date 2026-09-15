import os
import logging
from pyiceberg.catalog.sql import SqlCatalog

logger = logging.getLogger(__name__)

# Defaults
from src.config import (
    ICEBERG_CATALOG_DB, ICEBERG_WAREHOUSE_DIR,
    ICEBERG_POSTGRES_URI, S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET_NAME
)

DEFAULT_CATALOG_URI = f"sqlite:///{ICEBERG_CATALOG_DB}"
DEFAULT_WAREHOUSE_PATH = ICEBERG_WAREHOUSE_DIR
DEFAULT_NAMESPACE = "football"

_catalog = None

def get_catalog() -> SqlCatalog:
    global _catalog
    if _catalog is None:
        kwargs = {"type": "sql"}
        
        # Check if Cloud config exists
        if ICEBERG_POSTGRES_URI and S3_ENDPOINT:
            # Fix postgres:// -> postgresql+psycopg2:// for SQLAlchemy
            uri = ICEBERG_POSTGRES_URI
            if uri.startswith("postgres://"):
                uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
            elif uri.startswith("postgresql://") and not uri.startswith("postgresql+psycopg2://"):
                uri = uri.replace("postgresql://", "postgresql+psycopg2://", 1)
            
            kwargs["uri"] = uri
            kwargs["warehouse"] = f"s3://{S3_BUCKET_NAME}"
            kwargs["s3.endpoint"] = S3_ENDPOINT
            kwargs["s3.access-key-id"] = S3_ACCESS_KEY_ID
            kwargs["s3.secret-access-key"] = S3_SECRET_ACCESS_KEY
            logger.info(f"[Iceberg] Connecting to Cloud Catalog -> Neon.tech")
            logger.info(f"[Iceberg] Warehouse path -> s3://{S3_BUCKET_NAME}")
        else:
            # Fallback local
            os.makedirs(DEFAULT_WAREHOUSE_PATH, exist_ok=True)
            db_path = DEFAULT_CATALOG_URI.replace("sqlite:///", "")
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            kwargs["uri"] = DEFAULT_CATALOG_URI
            kwargs["warehouse"] = f"file://{DEFAULT_WAREHOUSE_PATH}"
            logger.info(f"[Iceberg] Connecting to Local Catalog -> {DEFAULT_CATALOG_URI}")
            
        _catalog = SqlCatalog("default", **kwargs)
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

