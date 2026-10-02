"""
Service Layer: Business Logic.

Responsibilities:
- Orchestrate calls to MatchRepository.
- Apply business rules (pagination, grouping lineup by team, sorting events).
- Map raw dicts to API response Pydantic schemas.
"""

import math
from typing import Optional

from src.api.repositories.match_repository import MatchRepository
from src.config import LEAGUES
from src.api.schemas.responses import (
    EventItem,
    LineupPlayer,
    MatchDetailResponse,
    MatchListItem,
    MatchListResponse,
    StatItem,
    TeamLineup,
)


class MatchService:
    def __init__(self, repo: MatchRepository):
        self._repo = repo

    # ------------------------------------------------------------------
    def resolve_league_slug(self, fotmob_id: int) -> str:
        """Resolve a fotmob_id to a league_slug. Raises ValueError if not found."""
        for slug, info in LEAGUES.items():
            if info["fotmob_id"] == fotmob_id:
                return slug
        raise ValueError(f"League with fotmob_id={fotmob_id} is not supported.")

    # ------------------------------------------------------------------
    def list_matches(
        self,
        league_slug: Optional[str] = None,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        round: Optional[str] = None,
        season: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MatchListResponse:
        offset = (page - 1) * page_size
        total, rows = self._repo.get_matches(
            league_slug=league_slug, team_id=team_id, status=status, round=round, season=season, limit=page_size, offset=offset
        )
        matches = [MatchListItem(**r) for r in rows]
        return MatchListResponse(total=total, page=page, page_size=page_size, matches=matches)

    # ------------------------------------------------------------------
    def get_seasons(self, league_slug: Optional[str] = None) -> list[str]:
        return self._repo.get_seasons(league_slug=league_slug)

    def get_teams(self, season: Optional[str] = None, league_slug: Optional[str] = None):
        return self._repo.get_teams(season=season, league_slug=league_slug)

    def get_match_detail(self, match_id: str) -> Optional[MatchDetailResponse]:
        match_row = self._repo.get_match_by_id(match_id)
        if not match_row:
            return None

        match = MatchListItem(**match_row)
        events = self._build_events(self._repo.get_match_events(match_id))
        lineup = self._build_lineup(match_id, match_row, self._repo.get_match_lineup(match_id))
        stats = self._build_stats(self._repo.get_match_stats(match_id))

        return MatchDetailResponse(match=match, events=events, lineup=lineup, stats=stats)

    # ------------------------------------------------------------------
    def get_match_events(self, match_id: str) -> list[EventItem]:
        if not self._repo.get_match_by_id(match_id):
            return None
        return self._build_events(self._repo.get_match_events(match_id))

    def get_match_lineup(self, match_id: str) -> Optional[list[TeamLineup]]:
        match_row = self._repo.get_match_by_id(match_id)
        if not match_row:
            return None
        return self._build_lineup(match_id, match_row, self._repo.get_match_lineup(match_id))

    def get_match_stats(self, match_id: str) -> Optional[list[StatItem]]:
        if not self._repo.get_match_by_id(match_id):
            return None
        return self._build_stats(self._repo.get_match_stats(match_id))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_events(rows: list[dict]) -> list[EventItem]:
        return [EventItem(**{k: v for k, v in r.items() if k in EventItem.model_fields}) for r in rows]

    @staticmethod
    def _build_lineup(match_id: str, match_row: dict, rows: list[dict]) -> list[TeamLineup]:
        """Group flat lineup rows into two TeamLineup objects (home/away)."""
        home_id = match_row["home_team_id"]
        away_id = match_row["away_team_id"]
        home_name = match_row["home_team_name"]
        away_name = match_row["away_team_name"]

        teams: dict[str, dict] = {
            home_id: {"team_id": home_id, "team_name": home_name, "is_home": True, "starters": [], "substitutes": []},
            away_id: {"team_id": away_id, "team_name": away_name, "is_home": False, "starters": [], "substitutes": []},
        }

        for r in rows:
            tid = str(r.get("team_id", ""))
            if tid not in teams:
                continue
            player = LineupPlayer(
                player_id=str(r["player_id"]),
                player_name=r["player_name"],
                shirt_number=str(r.get("shirt_number")) if r.get("shirt_number") is not None else None,
                position_id=r.get("position_id"),
                is_starter=bool(r.get("is_starter", False)),
                rating=r.get("rating"),
            )
            if player.is_starter:
                teams[tid]["starters"].append(player)
            else:
                teams[tid]["substitutes"].append(player)

        return [TeamLineup(**t) for t in teams.values()]

    @staticmethod
    def _build_stats(rows: list[dict]) -> list[StatItem]:
        return [
            StatItem(
                period=r["period"],
                group=r["group"],
                stat_title=r["stat_title"],
                home_value=r.get("home_value"),
                away_value=r.get("away_value"),
            )
            for r in rows
        ]

    def get_h2h(self, team1_id: int, team2_id: int | None = None, vs_league_slug: str | None = None, limit: int = 20):
        """Return H2H matches."""
        rows = self._repo.get_h2h(team1_id=team1_id, team2_id=team2_id, vs_league_slug=vs_league_slug, limit=limit)
        return [MatchListItem(**r) for r in rows]


    def get_rounds(self, league_slug: str, season: Optional[str] = None) -> list[str]:
        return self._repo.get_rounds(league_slug, season)
