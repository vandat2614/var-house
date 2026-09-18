"""
Pydantic / SQLModel Schemas for Football ETL Pipeline.

Defines database tables directly from schemas using SQLModel.
"""

from typing import List, Optional
from pydantic import BaseModel
from pydantic import BaseModel, Field

# 1. Match Dimension Schema
class DimMatch(BaseModel):
    """Schema representing a match fixture (dim_match table)."""
    match_id: str = Field(description="FotMob unique match identifier")
    league_slug: str = Field(description="League slug identifier, e.g., premier_league")
    season: str = Field(description="Season string, e.g., 2025-2026")
    round: int = Field(description="Matchweek / Round number")
    home_team_id: str = Field(description="Home team FotMob ID")
    home_team_name: str = Field(description="Home team name")
    away_team_id: str = Field(description="Away team FotMob ID")
    away_team_name: str = Field(description="Away team name")
    kickoff_utc: str = Field(description="ISO-8601 UTC timestamp of match kickoff")
    status: str = Field(description="Match status: upcoming | ongoing | finished | cancelled")
    home_score: Optional[int] = Field(default=None, description="Final score for home team")
    away_score: Optional[int] = Field(default=None, description="Final score for away team")

# 2. Team Dimension Schema
class DimTeam(BaseModel):
    """Schema representing a team (dim_team table)."""
    team_id: str = Field(description="FotMob unique team identifier")
    team_name: str = Field(description="Full team name, e.g., Arsenal")
    short_name: Optional[str] = Field(default=None, description="Short/abbreviated team name, e.g., Arsenal")

# 3. Player Dimension Schema
class DimPlayer(BaseModel):
    """Schema representing a player (dim_player table)."""
    player_id: str = Field(description="FotMob unique player identifier")
    player_name: str = Field(description="Full player name, e.g., Virgil van Dijk")
    current_team_id: Optional[str] = Field(default=None, description="Current team ID")
    current_team_name: Optional[str] = Field(default=None, description="Current team name")
    age: Optional[int] = Field(default=None, description="Player age")
    country: Optional[str] = Field(default=None, description="Player nationality / country")

# 4. Fact Events Schema
class FactEvent(BaseModel):
    """Schema representing a single in-match event (fact_event table)."""
    id: Optional[int] = Field(default=None)
    match_id: str = Field(description="FotMob match identifier")
    event_type: str = Field(description="Event type: Goal | Card | Substitution | AddedTime | VAR | MissedPenalty")
    minute: Optional[int] = Field(default=None, description="Match minute of event")
    is_home: Optional[bool] = Field(default=None, description="True if home team event, False if away team")
    player_id: Optional[str] = Field(default=None, description="Primary player ID involved")
    player_name: Optional[str] = Field(default=None, description="Primary player name")
    assist_player_id: Optional[str] = Field(default=None, description="Assisting player ID (Goal events)")
    assist_player_name: Optional[str] = Field(default=None, description="Assisting player name (Goal events)")
    is_own_goal: bool = Field(default=False, description="True if own goal")
    card_type: Optional[str] = Field(default=None, description="Yellow | Red | YellowRed (Card events)")
    player_in_id: Optional[str] = Field(default=None, description="Player IN ID (Substitution events)")
    player_in_name: Optional[str] = Field(default=None, description="Player IN name (Substitution events)")
    player_out_id: Optional[str] = Field(default=None, description="Player OUT ID (Substitution events)")
    player_out_name: Optional[str] = Field(default=None, description="Player OUT name (Substitution events)")
    added_time: Optional[int] = Field(default=None, description="Minutes added (AddedTime events)")
    new_score_home: Optional[int] = Field(default=None, description="Home team score after event")
    new_score_away: Optional[int] = Field(default=None, description="Away team score after event")

# 5. Fact Lineup Schema
class FactLineup(BaseModel):
    """Schema representing a player in match lineup/roster (fact_lineup table)."""
    id: Optional[int] = Field(default=None)
    match_id: str = Field(description="FotMob match identifier")
    team_id: str = Field(description="Team ID")
    team_name: str = Field(description="Team name")
    player_id: str = Field(description="Player ID")
    player_name: str = Field(description="Player full name")
    shirt_number: Optional[str] = Field(default=None, description="Player shirt number")
    position_id: Optional[str] = Field(default=None, description="FotMob position code")
    is_starter: bool = Field(description="True if starter, False if substitute")
    rating: Optional[float] = Field(default=None, description="FotMob match rating")
    age: Optional[int] = Field(default=None, description="Player age")
    country: Optional[str] = Field(default=None, description="Player nationality")

# 6. Fact Team Stats Schema
class FactStats(BaseModel):
    """Schema representing team match statistics (fact_stats table)."""
    id: Optional[int] = Field(default=None)
    match_id: str = Field(description="FotMob match identifier")
    period: str = Field(description="Match period: All | FirstHalf | SecondHalf")
    group: str = Field(description="Stat group, e.g., Top stats, Shots, Passes")
    stat_key: str = Field(description="Machine key, e.g., BallPossesion, expected_goals")
    stat_title: str = Field(description="Human-readable stat title")
    home_value: Optional[str] = Field(default=None, description="Home team stat value")
    away_value: Optional[str] = Field(default=None, description="Away team stat value")

# 7. Fact Player Stats Schema
class FactPlayerStats(BaseModel):
    """Schema representing individual player statistics per match (fact_player_stats table)."""
    id: Optional[int] = Field(default=None)
    match_id: str = Field(description="FotMob match identifier")
    player_id: str = Field(description="Player ID")
    player_name: str = Field(description="Player name")
    team_id: str = Field(description="Team ID")
    team_name: str = Field(description="Team name")
    group: str = Field(description="Stat group, e.g., Top stats, Attack, Defence")
    stat_key: str = Field(description="Machine key, e.g., goals, accurate_passes")
    stat_title: str = Field(description="Human-readable stat title")
    value: str = Field(description="Primary numeric/stat value as string")
    value_total: Optional[str] = Field(default=None, description="Total/denominator for fraction stats")

# 8. Combined Match Detail Container Schema
class MatchDetailBundle(BaseModel):
    """Container holding all fact tables for a match detail payload."""
    match: Optional[DimMatch] = None
    teams: List[DimTeam] = Field(default_factory=list)
    players: List[DimPlayer] = Field(default_factory=list)
    events: List[FactEvent] = Field(default_factory=list)
    lineup: List[FactLineup] = Field(default_factory=list)
    stats: List[FactStats] = Field(default_factory=list)
    player_stats: List[FactPlayerStats] = Field(default_factory=list)

