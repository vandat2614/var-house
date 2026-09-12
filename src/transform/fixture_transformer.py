import logging
"""
Fixture Transformer

Converts raw FotMob fixture list (output of crawl_fixtures) into
structured records for the dim_match table.

Output schema per record:
  match_id        str       FotMob match ID
  league_slug     str       e.g. "premier_league"
  season          str       "2026-2027"
  round           int       Matchweek number
  home_team_id    str
  home_team_name  str
  away_team_id    str
  away_team_name  str
  kickoff_utc     str       ISO-8601 UTC timestamp
  status          str       "upcoming" | "ongoing" | "finished" | "cancelled"
  home_score      int|None  Final score (None if not finished)
  away_score      int|None
"""

import json
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


CURRENT_SEASON = "2026-2027"
TRANSFORMED_DIR = os.path.join("data", "transformed", "fixtures")


def _parse_score(score_str: Optional[str]) -> tuple:
    """
    Parse '1 - 2' -> (1, 2). Returns (None, None) if unavailable.
    """
    if not score_str or "-" not in score_str:
        return None, None
    parts = score_str.replace(" ", "").split("-")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None, None


def _parse_status(status: Dict[str, Any]) -> str:
    if status.get("cancelled"):
        return "cancelled"
    if status.get("finished"):
        return "finished"
    if status.get("ongoing") or status.get("started"):
        return "ongoing"
    return "upcoming"


def transform_fixture(raw: Dict[str, Any], league_slug: str) -> Dict[str, Any]:
    """
    Transform a single raw match dict from FotMob fixtures payload
    into a structured dim_match record.
    """
    status = raw.get("status", {})
    status_str = _parse_status(status)

    score_str = status.get("scoreStr")
    home_score, away_score = _parse_score(score_str) if status_str == "finished" else (None, None)

    return {
        "match_id":       str(raw.get("id", "")),
        "league_slug":    league_slug,
        "season":         CURRENT_SEASON,
        "round":          int(raw.get("roundName") or raw.get("round") or 0),
        "home_team_id":   str(raw.get("home", {}).get("id", "")),
        "home_team_name": raw.get("home", {}).get("name", ""),
        "away_team_id":   str(raw.get("away", {}).get("id", "")),
        "away_team_name": raw.get("away", {}).get("name", ""),
        "kickoff_utc":    status.get("utcTime", ""),
        "status":         status_str,
        "home_score":     home_score,
        "away_score":     away_score,
    }


def transform_fixtures(
    raw_list: List[Dict[str, Any]],
    league_slug: str,
) -> List[Dict[str, Any]]:
    """
    Transform a full list of raw fixture dicts into structured dim_match records.

    Args:
        raw_list:    Output of crawl_fixtures().
        league_slug: e.g. "premier_league".

    Returns:
        List of structured match dicts.
    """
    result = []
    for raw in raw_list:
        if not raw.get("id"):
            continue
        try:
            result.append(transform_fixture(raw, league_slug))
        except Exception as exc:
            logger.warning(f"  [Warn] Skipping match {raw.get('id')}: {exc}")
    return result



def transform_teams_from_fixtures(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract a unique list of teams (DimTeam format) from raw fixtures.
    """
    teams = []
    seen = set()
    for raw in raw_list:
        if not raw.get("id"):
            continue
            
        for side in ("home", "away"):
            team_obj = raw.get(side, {})
            t_id = str(team_obj.get("id", ""))
            t_name = team_obj.get("name", "")
            
            if t_id and t_id not in seen:
                teams.append({
                    "team_id": t_id,
                    "team_name": t_name,
                    "short_name": t_name,
                })
                seen.add(t_id)
    
    logger.info(f"  [Extracted Teams] Found {len(teams)} unique teams from fixtures.")
    return teams

def save_fixtures(records: List[Dict[str, Any]], league_slug: str) -> str:
    """
    Persist transformed dim_match records to the Silver layer.

    Saved to: data/transformed/fixtures/{league_slug}_{season}.json

    Args:
        records:     Output of transform_fixtures().
        league_slug: e.g. "premier_league".

    Returns:
        Path of the saved file.
    """
    os.makedirs(TRANSFORMED_DIR, exist_ok=True)
    path = os.path.join(TRANSFORMED_DIR, f"{league_slug}_{CURRENT_SEASON}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    logger.info(f"[Saved Transformed Fixtures] {len(records)} records -> {path}")
    return path
