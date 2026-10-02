"""
Controller Layer: HTTP endpoints for leagues.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.schemas.responses import LeagueItem, MatchListResponse
from src.api.services.match_service import MatchService
from src.api.deps import get_match_service
from src.config import LEAGUES

router = APIRouter(prefix="/api/v1/leagues", tags=["Leagues"])


@router.get("/", response_model=list[LeagueItem], summary="List supported leagues")
async def list_leagues():
    return [
        LeagueItem(slug=slug, name=info["name"], fotmob_id=info["fotmob_id"])
        for slug, info in LEAGUES.items()
    ]


@router.get("/{league_id}/matches", response_model=MatchListResponse, summary="List matches in a league")
async def get_league_matches(
    league_id: int,
    status: Optional[str] = Query(None),
    matchweek: Optional[str] = Query(None),
    season: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MatchService = Depends(get_match_service),
):
    try:
        league_slug = service.resolve_league_slug(league_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return service.list_matches(league_slug=league_slug, status=status, round=matchweek, season=season, page=page, page_size=page_size)

@router.get("/teams", summary="List teams by season")
async def get_teams(
    season: Optional[str] = Query(None),
    league_id: Optional[int] = Query(None),
    service: MatchService = Depends(get_match_service),
):
    league_slug = None
    if league_id:
        try:
            league_slug = service.resolve_league_slug(league_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return service.get_teams(season=season, league_slug=league_slug)

@router.get("/seasons", summary="List available seasons for a league")
async def get_seasons(
    league_id: Optional[int] = Query(None),
    service: MatchService = Depends(get_match_service),
):
    league_slug = None
    if league_id:
        try:
            league_slug = service.resolve_league_slug(league_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return service.get_seasons(league_slug=league_slug)


@router.get("/rounds", summary="List available rounds for a league/season")
async def get_rounds(
    league_id: Optional[int] = Query(None),
    season: Optional[str] = Query(None),
    service: MatchService = Depends(get_match_service),
):
    league_slug = None
    if league_id:
        try:
            league_slug = service.resolve_league_slug(league_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return service.get_rounds(league_slug=league_slug, season=season)
