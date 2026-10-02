"""
FastAPI dependency factories.
Extracted here to break the circular import between main.py and controllers.
"""

import time

from src.config import CRAWL_CURRENT_SEASON
from src.etl.load.iceberg_catalog import get_catalog
from src.api.repositories.match_repository import MatchRepository, warm_arrow_cache
from src.api.services.match_service import MatchService
from src.api.repositories.dashboard_repository import DashboardRepository
from src.api.services.dashboard_service import DashboardService

# Catalog is expensive to recreate (connects to Neon). Keep it alive for 10 min.
# Iceberg metadata is re-read per load_table() call so we still see new writes.
_CATALOG_TTL_SECONDS = 600

_catalog_cache = {"catalog": None, "created_at": 0.0}


def _get_catalog_cached():
    """Return a catalog, refreshing it if the TTL has expired."""
    now = time.monotonic()
    if _catalog_cache["catalog"] is None or (now - _catalog_cache["created_at"]) > _CATALOG_TTL_SECONDS:
        _catalog_cache["catalog"] = get_catalog()
        _catalog_cache["created_at"] = now
    return _catalog_cache["catalog"]


def _get_repository() -> MatchRepository:
    catalog = _get_catalog_cached()
    return MatchRepository(catalog=catalog, season=CRAWL_CURRENT_SEASON)


def get_match_service() -> MatchService:
    return MatchService(repo=_get_repository())



def get_dashboard_service() -> DashboardService:
    catalog = _get_catalog_cached()
    repo = DashboardRepository(catalog)
    return DashboardService(repo)

def warmup():
    """Pre-load the most frequently accessed table into the in-process Arrow cache."""
    catalog = _get_catalog_cached()
    warm_arrow_cache(catalog)
