"""
Controller Layer: HTTP endpoints for matches.

Responsibilities:
- Accept and validate HTTP request parameters.
- Call MatchService.
- Return HTTP responses or raise HTTPException.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.responses import (
    EventItem,
    MatchDetailResponse,
    MatchListResponse,
    TeamLineup,
    StatItem,
)
from src.api.services.match_service import MatchService
from src.api.deps import get_match_service

router = APIRouter(prefix="/api/v1/matches", tags=["Matches"])


@router.get("/", response_model=MatchListResponse, summary="List matches")
async def list_matches(
    league_id: Optional[int] = Query(None, description="Filter by league ID, e.g. 47 for Premier League"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    status: Optional[str] = Query(None, description="Filter by status: upcoming | ongoing | finished"),
    matchweek: Optional[str] = Query(None, description="Filter by matchweek/round"),
    season: Optional[str] = Query(None, description="Filter by season (e.g. 2023/2024)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=2000, description="Items per page"),
    service: MatchService = Depends(get_match_service),
):
    league_slug = None
    if league_id is not None:
        try:
            league_slug = service.resolve_league_slug(league_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return service.list_matches(league_slug=league_slug, team_id=team_id, status=status, round=matchweek, season=season, page=page, page_size=page_size)




from typing import Optional
@router.get("/h2h", response_model=list, summary="Head-to-Head matches")
async def get_h2h(
    team1_id: int = Query(..., description="First team ID"),
    team2_id: Optional[int] = Query(None, description="Second team ID"),
    vs_league_slug: Optional[str] = Query(None, description="Or against teams from this league"),
    limit: int = Query(20, ge=1, le=500, description="Number of recent matches"),
    service: MatchService = Depends(get_match_service),
):
    return service.get_h2h(team1_id=team1_id, team2_id=team2_id, vs_league_slug=vs_league_slug, limit=limit)

@router.get("/{match_id}", response_model=MatchDetailResponse, summary="Get match detail")
async def get_match_detail(match_id: str, service: MatchService = Depends(get_match_service)):
    result = service.get_match_detail(match_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id!r} not found.")
    return result


@router.get("/{match_id}/events", response_model=list[EventItem], summary="Get match events")
async def get_match_events(match_id: str, service: MatchService = Depends(get_match_service)):
    result = service.get_match_events(match_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id!r} not found.")
    return result


@router.get("/{match_id}/lineup", response_model=list[TeamLineup], summary="Get match lineup")
async def get_match_lineup(match_id: str, service: MatchService = Depends(get_match_service)):
    result = service.get_match_lineup(match_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id!r} not found.")
    return result


@router.get("/{match_id}/stats", response_model=list[StatItem], summary="Get match stats")
async def get_match_stats(match_id: str, service: MatchService = Depends(get_match_service)):
    result = service.get_match_stats(match_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id!r} not found.")
    return result
