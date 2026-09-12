import logging
import os
from typing import Any, Dict, Tuple

from src.transform.match_detail_transformer import transform_match_detail
from src.utils import save_json
from src.config import TRANSFORMED_DIR

logger = logging.getLogger(__name__)

class MatchTransformService:
    """
    Service class responsible for orchestrating the transformation of raw match data.
    It handles logging metadata extraction, core transformation, and persisting to the Silver layer.
    """

    @staticmethod
    def _extract_logging_metadata(payload: Dict[str, Any]) -> Tuple[str, str, str]:
        """Extract basic info (teams, date) from raw payload for logging purposes."""
        home_team = payload.get("lineup", {}).get("homeTeam", {}).get("name", "Unknown")
        away_team = payload.get("lineup", {}).get("awayTeam", {}).get("name", "Unknown")

        match_date_str = "Unknown time"
        try:
            # Fallback for various structures
            match_date = payload.get("matchFacts", {}).get("infoBox", {}).get("Match Date")
            if isinstance(match_date, dict) and "utcTime" in match_date:
                match_date_str = match_date["utcTime"]
            elif isinstance(match_date, str):
                match_date_str = match_date
            elif payload.get("general", {}).get("matchTimeUTCDate"):
                match_date_str = payload.get("general", {}).get("matchTimeUTCDate")
        except Exception:
            pass

        return home_team, away_team, match_date_str

    def process_and_save(self, match_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the raw payload and persist it.
        Returns the transformed structured dictionary.
        """
        home_team, away_team, match_date_str = self._extract_logging_metadata(payload)
        logger.info(f"Received raw match {match_id} [{match_date_str}] ({home_team} vs {away_team}) from Kafka. Transforming...")

        # 1. Transform raw payload to structured facts
        result_dict = transform_match_detail(payload, match_id)

        # 2. Persist structured JSON to disk (Silver file layer)
        match_info = result_dict.get("match", {}) or {}
        season = match_info.get("season", "unknown")
        league_slug = match_info.get("league_slug", "unknown")
        
        season_safe = season.replace("/", "_").replace("-", "_") if season else "unknown"
        league = league_slug or "unknown"
        out_path = os.path.join(TRANSFORMED_DIR, "match-details", season_safe, league, f"{match_id}.json")
        
        save_json(result_dict, out_path)
        logger.info(f"    Saved Silver JSON -> {out_path}")

        return result_dict
