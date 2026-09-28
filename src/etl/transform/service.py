import logging
"""
Transform Service — single public interface for the transform layer.
All internal transformers are private implementation details.
"""

from typing import Any, Dict, List

from src.etl.transform.match_detail_transformer import transform_match_detail as _transform_match_detail
from src.etl.transform.fixture_transformer import (
    transform_fixtures as _transform_fixtures,
    extract_teams as _extract_teams,
)

logger = logging.getLogger(__name__)


class TransformService:
    """
    Public interface for the transform layer.

    Usage:
        svc = TransformService()
        result = svc.transform_match_detail("5868011", raw_content)
        matches = svc.transform_fixtures(raw_list)
        teams   = svc.extract_teams(raw_list)
    """

    def transform_match_detail(self, match_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw FotMob match content into structured fact/dimension records.

        Returns dict with keys: match, teams, players, events, lineup, stats.
        """
        home_team = payload.get("lineup", {}).get("homeTeam", {}).get("name", "Unknown")
        away_team = payload.get("lineup", {}).get("awayTeam", {}).get("name", "Unknown")
        logger.info(f"[Transform] Match {match_id}: {home_team} vs {away_team}")

        result = _transform_match_detail(payload, match_id)
        logger.info(
            f"[Transform] Done: {len(result.get('events', []))} events, "
            f"{len(result.get('lineup', []))} lineup records"
        )
        return result

    def transform_fixtures(self, raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform raw fixture list into structured dim_match records.

        Note: returned records do not include league_slug / season.
        Caller is responsible for enriching those fields.
        """
        return _transform_fixtures(raw_list)

    def extract_teams(self, raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique team records (dim_team format) from a raw fixture list."""
        return _extract_teams(raw_list)
