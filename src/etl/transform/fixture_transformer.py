import logging
"""
Fixture Transformer

Converts raw FotMob fixture list (output of crawl_fixtures) into
structured records for the dim_match and dim_team tables.

Responsibility: TRANSFORM only.
  - Receive raw list of match dicts
  - Return structured records

Does NOT save to disk, does NOT fetch, does NOT load.
"""

from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _parse_score(score_str: Optional[str]) -> tuple:
    """Parse '1 - 2' -> (1, 2). Returns (None, None) if unavailable."""
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


def transform_fixture(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a single raw match dict from FotMob fixtures payload
    into a structured dim_match record.

    Note: league_slug and season are NOT included here.
    The caller (orchestrator) knows which league/season it crawled
    and can enrich the record after the fact.
    """
    status = raw.get("status", {})
    status_str = _parse_status(status)
    score_str = status.get("scoreStr")
    home_score, away_score = _parse_score(score_str) if status_str == "finished" else (None, None)

    return {
        "match_id":       str(raw.get("id", "")),
        "round":          str(raw.get("roundName") or raw.get("round") or ""),
        "home_team_id":   str(raw.get("home", {}).get("id", "")),
        "home_team_name": raw.get("home", {}).get("name", ""),
        "away_team_id":   str(raw.get("away", {}).get("id", "")),
        "away_team_name": raw.get("away", {}).get("name", ""),
        "kickoff_utc":    status.get("utcTime", ""),
        "status":         status_str,
        "home_score":     home_score,
        "away_score":     away_score,
    }


def transform_fixtures(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform a list of raw fixture dicts into structured dim_match records.

    Args:
        raw_list: Output of crawl_fixtures().

    Returns:
        List of structured match dicts (without league_slug / season).
        Caller is responsible for enriching with those fields.
    """
    result = []
    for raw in raw_list:
        if not raw.get("id"):
            continue
        try:
            result.append(transform_fixture(raw))
        except Exception as exc:
            logger.warning(f"  [Warn] Skipping match {raw.get('id')}: {exc}")
    return result


def extract_teams(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract unique team records (dim_team format) from a raw fixture list.

    Args:
        raw_list: Output of crawl_fixtures().

    Returns:
        List of unique team dicts with team_id, team_name, short_name.
    """
    teams = []
    seen = set()
    for raw in raw_list:
        if not raw.get("id"):
            continue
        for side in ("home", "away"):
            team_obj = raw.get(side, {})
            t_id = str(team_obj.get("id", ""))
            if t_id and t_id not in seen:
                teams.append({
                    "team_id":    t_id,
                    "team_name":  team_obj.get("name", ""),
                    "short_name": team_obj.get("shortName", team_obj.get("name", "")),
                })
                seen.add(t_id)
    return teams
