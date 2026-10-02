from typing import Optional
from fastapi import APIRouter, Depends, Query
from src.api.services.dashboard_service import DashboardService
from src.api.deps import get_dashboard_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/stats")
def get_dashboard_stats(
    league: Optional[str] = Query(None),
    from_season: Optional[str] = Query(None),
    to_season: Optional[str] = Query(None),
    service: DashboardService = Depends(get_dashboard_service)
):
    return service.get_dashboard_stats(league, from_season, to_season)