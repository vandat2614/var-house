import logging
"""
Match Detail Transformer

Converts raw FotMob match detail content (output of crawl_match_detail)
into structured records for fact_event and fact_lineup tables.

--- fact_event schema ---
  match_id            str
  event_type          str       "Goal" | "Card" | "Substitution" | "AddedTime" | ...
  minute              int|None
  is_home             bool|None
  player_id           str
  player_name         str
  assist_player_id    str|None
  assist_player_name  str|None
  is_own_goal         bool
  card_type           str|None  "Yellow" | "Red" | None  (only for Card events)
  player_in_id        str|None  (only for Substitution events)
  player_in_name      str|None
  player_out_id       str|None
  player_out_name     str|None
  added_time          int|None  minutes added  (only for AddedTime events)
  new_score_home      int|None
  new_score_away      int|None

--- fact_lineup schema ---
  match_id      str
  team_id       str
  team_name     str
  player_id     str
  player_name   str
  shirt_number  str
  position_id   str
  is_starter    bool
  rating        float|None
  age           int|None
  country       str|None

--- fact_stats schema ---
  match_id    str
  period      str       "All" | "FirstHalf" | "SecondHalf"
  group       str       e.g. "Top stats", "Shots", "Passes", "Defence" ...
  stat_key    str       e.g. "BallPossesion", "expected_goals", "corners"
  stat_title  str       Human-readable label
  home_value  str       Raw value for home team (always string for consistency)
  away_value  str       Raw value for away team

--- fact_player_stats schema ---
  match_id    str
  player_id   str
  player_name str
  team_id     str
  team_name   str
  group       str       e.g. "Top stats", "Attack", "Defence", "Duels"
  stat_key    str       e.g. "goals", "accurate_passes", "rating_title"
  stat_title  str       Human-readable label
  value       str       Primary numeric value (always string)
  value_total str|None  Denominator for fraction stats (e.g. total passes)
"""

import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)



# ---------------------------------------------------------------------------
# Event Transform
# ---------------------------------------------------------------------------

def _transform_event(ev: Dict[str, Any], match_id: str) -> Optional[Dict[str, Any]]:
    """Transform a single raw event dict into a structured fact_event record."""
    event_type = str(ev.get("type", "Unknown"))

    player_obj = ev.get("player", {})
    if isinstance(player_obj, dict):
        player_id   = str(player_obj.get("id", "") or "")
        player_name = player_obj.get("name") or ""
    else:
        player_id   = ""
        player_name = str(player_obj or "")

    minute = ev.get("time") or ev.get("timeStr")
    try:
        minute = int(minute) if minute is not None else None
    except (ValueError, TypeError):
        minute = None

    new_score = ev.get("newScore") or []
    home_score = int(new_score[0]) if len(new_score) > 0 else None
    away_score = int(new_score[1]) if len(new_score) > 1 else None

    # --- Card: extract Yellow / Red ---
    card_type = ev.get("card") or None  # "Yellow", "Red", "YellowRed", or None

    # --- Substitution: extract player in / player out from swap list ---
    player_in_id    = None
    player_in_name  = None
    player_out_id   = None
    player_out_name = None
    if event_type == "Substitution":
        swap = ev.get("swap") or []
        if len(swap) >= 2:
            player_in_id    = str(swap[0].get("id", "") or "")
            player_in_name  = swap[0].get("name") or ""
            player_out_id   = str(swap[1].get("id", "") or "")
            player_out_name = swap[1].get("name") or ""
        elif len(swap) == 1:
            player_in_id   = str(swap[0].get("id", "") or "")
            player_in_name = swap[0].get("name") or ""

    # --- AddedTime: extract minutes added ---
    added_time = None
    if event_type == "AddedTime":
        try:
            added_time = int(ev["minutesAddedInput"]) if ev.get("minutesAddedInput") is not None else None
        except (ValueError, TypeError):
            pass

    return {
        "match_id":           match_id,
        "event_type":         event_type,
        "minute":             minute,
        "is_home":            ev.get("isHome"),
        "player_id":          player_id,
        "player_name":        player_name,
        "assist_player_id":   str(ev.get("assistPlayerId", "")) or None,
        "assist_player_name": ev.get("assistInput") or None,
        "is_own_goal":        bool(ev.get("ownGoal")),
        "card_type":          card_type,
        "player_in_id":       player_in_id,
        "player_in_name":     player_in_name,
        "player_out_id":      player_out_id,
        "player_out_name":    player_out_name,
        "added_time":         added_time,
        "new_score_home":     home_score,
        "new_score_away":     away_score,
    }


def transform_events(content: Dict[str, Any], match_id: str) -> List[Dict[str, Any]]:
    """
    Extract and transform all events from a raw match content dict.

    Args:
        content:  The `content` dict from FotMob __NEXT_DATA__ pageProps.
        match_id: FotMob match ID string.

    Returns:
        List of structured fact_event records.
    """
    events_container = content.get("matchFacts", {}).get("events", {})
    raw_events = (
        events_container.get("events", [])
        if isinstance(events_container, dict)
        else []
    )

    result = []
    for ev in raw_events:
        try:
            record = _transform_event(ev, match_id)
            if record:
                result.append(record)
        except Exception as exc:
            logger.warning(f"  [Warn] Skipping event in match {match_id}: {exc}")
            
    # Sort events by minute (ascending order). Put events with None minute at the end.
    result.sort(key=lambda x: (x.get("minute") is None, x.get("minute")))
    return result


# ---------------------------------------------------------------------------
# Lineup Transform
# ---------------------------------------------------------------------------

def _transform_player(
    p: Dict[str, Any],
    team_id: str,
    team_name: str,
    match_id: str,
    is_starter: bool,
) -> Dict[str, Any]:
    """Transform a single raw player dict into a structured fact_lineup record."""
    rating = None
    perf = p.get("performance", {})
    if isinstance(perf, dict) and "rating" in perf:
        try:
            rating = float(perf["rating"])
        except (ValueError, TypeError):
            pass

    age = None
    try:
        age = int(p["age"]) if p.get("age") is not None else None
    except (ValueError, TypeError):
        pass

    country = p.get("countryName") or p.get("countryCode")

    return {
        "match_id":     match_id,
        "team_id":      team_id,
        "team_name":    team_name,
        "player_id":    str(p.get("id", "")),
        "player_name":  p.get("name", ""),
        "shirt_number": str(p.get("shirtNumber", "")),
        "position_id":  str(p.get("positionId", "")),
        "is_starter":   is_starter,
        "rating":       rating,
        "age":          age,
        "country":      str(country) if country else None,
    }


def transform_lineups(content: Dict[str, Any], match_id: str) -> List[Dict[str, Any]]:
    """
    Extract and transform lineup (starters + bench) for both teams.

    Args:
        content:  The `content` dict from FotMob __NEXT_DATA__ pageProps.
        match_id: FotMob match ID string.

    Returns:
        List of structured fact_lineup records.
    """
    lineup_data = content.get("lineup", {})
    result = []

    for side in ("homeTeam", "awayTeam"):
        team_obj = lineup_data.get(side, {})
        if not isinstance(team_obj, dict):
            continue

        team_id   = str(team_obj.get("id", ""))
        team_name = team_obj.get("name", "")

        for p in team_obj.get("starters", []):
            try:
                result.append(_transform_player(p, team_id, team_name, match_id, is_starter=True))
            except Exception as exc:
                logger.warning(f"  [Warn] Skipping starter {p.get('name')} in match {match_id}: {exc}")

        for p in team_obj.get("subs", []):
            try:
                result.append(_transform_player(p, team_id, team_name, match_id, is_starter=False))
            except Exception as exc:
                logger.warning(f"  [Warn] Skipping sub {p.get('name')} in match {match_id}: {exc}")

    return result


# ---------------------------------------------------------------------------
# Stats Transform
# ---------------------------------------------------------------------------

def transform_stats(content: Dict[str, Any], match_id: str) -> List[Dict[str, Any]]:
    """
    Extract and flatten team stats across all periods (All, FirstHalf, SecondHalf).

    Args:
        content:  The `content` dict from FotMob __NEXT_DATA__ pageProps.
        match_id: FotMob match ID string.

    Returns:
        List of structured fact_stats records.
    """
    stats_data = content.get("stats") or {}
    periods_data = stats_data.get("Periods", {})
    result = []

    for period, period_obj in periods_data.items():
        if not isinstance(period_obj, dict):
            continue
        for group in period_obj.get("stats", []):
            group_title = group.get("title", "")
            for stat in group.get("stats", []):
                values = stat.get("stats", [])
                home_val = str(values[0]) if len(values) > 0 else None
                away_val = str(values[1]) if len(values) > 1 else None
                result.append({
                    "match_id":   match_id,
                    "period":     period,
                    "group":      group_title,
                    "stat_key":   stat.get("key", ""),
                    "stat_title": stat.get("title", ""),
                    "home_value": home_val,
                    "away_value": away_val,
                })

    return result


# ---------------------------------------------------------------------------
# Player Stats Transform
# ---------------------------------------------------------------------------

def transform_player_stats(content: Dict[str, Any], match_id: str) -> List[Dict[str, Any]]:
    """
    Extract per-player stats for all players in the match.

    Args:
        content:  The `content` dict from FotMob __NEXT_DATA__ pageProps.
        match_id: FotMob match ID string.

    Returns:
        List of structured fact_player_stats records.
    """
    player_stats_raw = content.get("playerStats") or {}
    result = []

    for player_id_str, p in player_stats_raw.items():
        if not isinstance(p, dict) or not p.get("stats"):
            continue

        player_id   = str(p.get("id", player_id_str))
        player_name = p.get("name", "")
        team_id     = str(p.get("teamId", ""))
        team_name   = p.get("teamName", "")

        for group in p.get("stats", []):
            group_title = group.get("title", "")
            for stat_title, stat_obj in group.get("stats", {}).items():
                if not isinstance(stat_obj, dict):
                    continue
                stat_data  = stat_obj.get("stat", {})
                stat_key   = stat_obj.get("key") or ""
                raw_value  = stat_data.get("value")
                raw_total  = stat_data.get("total")

                if raw_value is None:
                    continue

                result.append({
                    "match_id":    match_id,
                    "player_id":   player_id,
                    "player_name": player_name,
                    "team_id":     team_id,
                    "team_name":   team_name,
                    "group":       group_title,
                    "stat_key":    stat_key,
                    "stat_title":  stat_title,
                    "value":       str(raw_value),
                    "value_total": str(raw_total) if raw_total is not None else None,
                })

    return result




# ---------------------------------------------------------------------------
# Dimensions Transform
# ---------------------------------------------------------------------------

def transform_match_info(content: dict, match_id: str) -> dict | None:
    """Extract match information for dim_match."""
    try:
        lineup = content.get("lineup", {})
        ht = lineup.get("homeTeam", {})
        at = lineup.get("awayTeam", {})
        
        ib = content.get("matchFacts", {}).get("infoBox", {})
        
        # Check if we have minimum data
        if not ht and not at and not ib:
            return None
            
        tournament = ib.get("Tournament", {})
        league_slug = "unknown"
        round_name = 0
        season = "unknown"
        if isinstance(tournament, dict):
            league_slug = tournament.get("leagueName", "unknown").lower().replace(" ", "_")
            try:
                round_name = int(tournament.get("round", "0"))
            except ValueError:
                round_name = 0

        # Extract season from raw data (e.g. "2026/2027" -> "2026-2027")
        general = content.get("general", {})
        parent_league = general.get("parentLeague", {}) or {}
        season_raw = parent_league.get("parentLeagueSeason", "")
        if not season_raw:
            # Fallback: try to derive from kickoff year
            match_date_raw = ib.get("Match Date", {})
            kickoff_raw = match_date_raw.get("utcTime", "") if isinstance(match_date_raw, dict) else ""
            if kickoff_raw and len(kickoff_raw) >= 4:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(kickoff_raw.replace("Z", "+00:00"))
                    year = dt.year
                    month = dt.month
                    # European football season: Aug-May. If month >= 8 -> season is year/year+1
                    if month >= 7:
                        season_raw = f"{year}/{year+1}"
                    else:
                        season_raw = f"{year-1}/{year}"
                except Exception:
                    pass
        if season_raw:
            season = season_raw.replace("/", "-")

        match_date = ib.get("Match Date", {})
        kickoff = match_date.get("utcTime", "") if isinstance(match_date, dict) else ""

        return {
            "match_id": str(match_id),
            "league_slug": league_slug,
            "season": season,
            "round": round_name,
            "home_team_id": str(ht.get("id", "")),
            "home_team_name": ht.get("name", ""),
            "away_team_id": str(at.get("id", "")),
            "away_team_name": at.get("name", ""),
            "kickoff_utc": kickoff,
            "status": "finished", # Assume finished if we have details
            "home_score": None,
            "away_score": None
        }
    except Exception as exc:
        logger.warning(f"  [Warn] Failed to transform match info for {match_id}: {exc}")
        return None

def transform_teams(content: dict, match_id: str) -> list[dict]:
    """Extract team information for dim_team from general data."""
    lineup = content.get("lineup", {})
    result = []
    for side in ("homeTeam", "awayTeam"):
        team = lineup.get(side, {})
        if team and team.get("id"):
            result.append({
                "team_id": str(team.get("id")),
                "team_name": team.get("name", ""),
                "short_name": team.get("name", "")
            })
    return result

def transform_players(content: dict, match_id: str) -> list[dict]:
    """Extract player information for dim_player from lineup data."""
    lineup_data = content.get("lineup", {})
    result = []
    seen_players = set()
    
    for side in ("homeTeam", "awayTeam"):
        team_obj = lineup_data.get(side, {})
        if not isinstance(team_obj, dict):
            continue

        team_id = str(team_obj.get("id", ""))
        team_name = team_obj.get("name", "")

        for player_list in (team_obj.get("starters", []), team_obj.get("subs", [])):
            for p in player_list:
                p_id = str(p.get("id", ""))
                if not p_id or p_id in seen_players:
                    continue
                    
                seen_players.add(p_id)
                age = None
                try:
                    age = int(p["age"]) if p.get("age") is not None else None
                except (ValueError, TypeError):
                    pass
                    
                country = p.get("countryName") or p.get("countryCode")
                
                result.append({
                    "player_id": p_id,
                    "player_name": p.get("name", ""),
                    "current_team_id": team_id,
                    "current_team_name": team_name,
                    "age": age,
                    "country": str(country) if country else None,
                })
    return result


# ---------------------------------------------------------------------------
# Team Stats Transform (Top Stats only)
# ---------------------------------------------------------------------------

def transform_top_stats(content: dict, match_id: str) -> list[dict]:
    """
    Extract the 'top_stats' group from match statistics.

    Extracts: Ball possession, xG, Total shots, Shots on target,
    Touches in opp box, Big chances, Big chances missed,
    Accurate passes, Yellow cards, Corners.

    Path: content["stats"]["Periods"]["All"]["stats"] -> group key="top_stats"
    """
    result = []
    periods = content.get("stats", {}).get("Periods", {})
    all_period = periods.get("All", {})
    stat_groups = all_period.get("stats", [])

    for group in stat_groups:
        if group.get("key") != "top_stats":
            continue
        for stat in group.get("stats", []):
            vals = stat.get("stats", [])
            if len(vals) < 2:
                continue
            result.append({
                "match_id":    match_id,
                "period":      "All",
                "group":       "Top stats",
                "stat_key":    stat.get("key", ""),
                "stat_title":  stat.get("title", ""),
                "home_value":  str(vals[0]) if vals[0] is not None else None,
                "away_value":  str(vals[1]) if vals[1] is not None else None,
            })
    return result

# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

def transform_match_detail(
    content: Dict[str, Any],
    match_id: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Transform raw match content into events, lineup, and stats records.

    Args:
        content:  The `content` dict cached at data/raw/matches/{match_id}.json.
        match_id: FotMob match ID string.

    Returns:
        {
            "events": [...],   # List of fact_event records
            "lineup": [...],   # List of fact_lineup records
            "stats":  [...]    # List of fact_stats records
        }
    """
    return {
        "match":        transform_match_info(content, match_id),
        "teams":        transform_teams(content, match_id),
        "players":      transform_players(content, match_id),
        "events":       transform_events(content, match_id),
        "lineup":       transform_lineups(content, match_id),
        "stats":        transform_top_stats(content, match_id),
        "player_stats": [],
    }
