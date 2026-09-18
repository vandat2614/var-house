"""
Dimension Extractor for Teams and Players.

Extracts unique DimTeam and DimPlayer records from:
  - Raw fixtures (home/away team metadata)
  - Raw/transformed match lineups & player stats
"""

from typing import Dict, List, Any
from src.schemas import DimTeam, DimPlayer


def extract_dim_teams(fixtures_raw: List[Dict[str, Any]]) -> List[DimTeam]:
    """
    Extract unique team dimension records from raw fixtures payload.
    """
    teams_map: Dict[str, DimTeam] = {}

    for m in fixtures_raw:
        for side in ("home", "away"):
            team = m.get(side, {})
            team_id = str(team.get("id", ""))
            if team_id and team_id not in teams_map:
                teams_map[team_id] = DimTeam(
                    team_id=team_id,
                    team_name=team.get("name", ""),
                    short_name=team.get("shortName"),
                )

    return list(teams_map.values())


def extract_dim_players(lineup_records: List[Dict[str, Any]]) -> List[DimPlayer]:
    """
    Extract unique player dimension records from lineup records.
    """
    players_map: Dict[str, DimPlayer] = {}

    for p in lineup_records:
        player_id = str(p.get("player_id", ""))
        if not player_id:
            continue

        if player_id not in players_map:
            players_map[player_id] = DimPlayer(
                player_id=player_id,
                player_name=p.get("player_name", ""),
                current_team_id=p.get("team_id"),
                current_team_name=p.get("team_name"),
                age=p.get("age"),
                country=p.get("country"),
            )

    return list(players_map.values())
