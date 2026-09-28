import logging
"""
Load Service — single public interface for the load layer.
All internal loaders are private implementation details.
"""

from typing import Any, Dict, List

from src.schemas.match_schemas import MatchDetailBundle
from src.etl.load.iceberg_loader import (
    load_match_detail_iceberg as _load_match_detail,
    load_dim_matches as _load_dim_matches,
    load_dim_teams as _load_dim_teams,
)

logger = logging.getLogger(__name__)


class LoadService:
    """
    Public interface for the load layer.

    Usage:
        svc = LoadService()
        svc.load_match_detail("5868011", structured_payload)
        svc.load_fixtures(matches_list)
        svc.load_teams(teams_list)
    """

    def load_match_detail(self, match_id: str, payload: Dict[str, Any]) -> None:
        """
        Validate and load a full match detail bundle into Iceberg.
        Includes: dim_match, dim_team, dim_player, fact_event, fact_lineup.
        """
        team_names = list(set(
            p.get("team_name") for p in payload.get("lineup", []) if p.get("team_name")
        ))
        team_str = " vs ".join(team_names) if team_names else "Unknown Teams"
        logger.info(f"[Load] Match {match_id} ({team_str})")

        bundle = MatchDetailBundle.model_validate(payload)
        _load_match_detail(match_id=match_id, bundle=bundle)
        logger.info(f"[Load] Match {match_id} loaded successfully.")

    def load_fixtures(self, matches: List[Dict[str, Any]]) -> None:
        """
        Load a list of dim_match records into Iceberg.
        Typically called after TransformService.transform_fixtures().
        """
        if not matches:
            logger.warning("[Load] load_fixtures called with empty list.")
            return
        logger.info(f"[Load] Loading {len(matches)} fixture records.")
        _load_dim_matches(matches)

    def load_teams(self, teams: List[Dict[str, Any]]) -> None:
        """
        Load a list of dim_team records into Iceberg.
        Typically called after TransformService.extract_teams().
        """
        if not teams:
            logger.warning("[Load] load_teams called with empty list.")
            return
        logger.info(f"[Load] Loading {len(teams)} team records.")
        _load_dim_teams(teams)
