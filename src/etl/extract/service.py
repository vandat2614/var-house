import logging
"""
Extract Service — single public interface for the extract layer.
All internal crawlers are private implementation details.
"""

from typing import Any, Dict, List

from src.etl.extract.fixture_crawler import crawl_fixtures as _crawl_fixtures
from src.etl.extract.match_detail_crawler import crawl_match_detail as _crawl_match_detail

logger = logging.getLogger(__name__)


class ExtractService:
    """
    Public interface for the extract layer.

    Usage:
        svc = ExtractService()
        raw_matches = svc.crawl_fixtures("premier-league", "2025-2026")
        raw_content = svc.crawl_match_detail("5868011")
    """

    def crawl_fixtures(self, league_slug: str, season: str) -> List[Dict[str, Any]]:
        """Fetch raw fixture list for a league and season from FotMob."""
        return _crawl_fixtures(league_slug, season)

    def crawl_match_detail(self, match_id: str) -> Dict[str, Any]:
        """Fetch raw match content for a single match from FotMob."""
        return _crawl_match_detail(match_id)
