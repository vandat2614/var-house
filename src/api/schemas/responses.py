"""
API-specific Pydantic response schemas (frontend-friendly).
Separate from src/schemas/match_schemas.py which is used internally by ETL pipeline.
"""

from typing import List, Optional
from pydantic import BaseModel


class MatchListItem(BaseModel):
    match_id: str
    league_slug: str
    season: str
    round: str
    home_team_id: str
    home_team_name: str
    away_team_id: str
    away_team_name: str
    kickoff_utc: str
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None


class EventItem(BaseModel):
    event_type: str
    minute: Optional[int] = None
    is_home: Optional[bool] = None
    player_name: Optional[str] = None
    assist_player_name: Optional[str] = None
    is_own_goal: bool = False
    card_type: Optional[str] = None
    player_in_name: Optional[str] = None
    player_out_name: Optional[str] = None
    added_time: Optional[int] = None
    new_score_home: Optional[int] = None
    new_score_away: Optional[int] = None


class LineupPlayer(BaseModel):
    player_id: str
    player_name: str
    shirt_number: Optional[str] = None
    position_id: Optional[str] = None
    is_starter: bool
    rating: Optional[float] = None


class TeamLineup(BaseModel):
    team_id: str
    team_name: str
    is_home: bool
    starters: List[LineupPlayer]
    substitutes: List[LineupPlayer]


class StatItem(BaseModel):
    period: str
    group: str
    stat_title: str
    home_value: Optional[str] = None
    away_value: Optional[str] = None


class MatchDetailResponse(BaseModel):
    match: MatchListItem
    events: List[EventItem] = []
    lineup: List[TeamLineup] = []
    stats: List[StatItem] = []


class MatchListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    matches: List[MatchListItem]


class LeagueItem(BaseModel):
    slug: str
    name: str
    fotmob_id: int
