import logging
"""
Football Fixture Crawler

Responsibility: EXTRACT only.
  - Fetch raw HTML from FotMob for a given league + season
  - Parse __NEXT_DATA__ JSON
  - Return raw list of match dicts

Does NOT validate inputs, does NOT cache, does NOT transform.
"""

from src.config import LEAGUES
from typing import Any, Dict, List

from src.etl.extract.utils import fetch_html, extract_next_data

logger = logging.getLogger(__name__)


def crawl_fixtures(league_slug: str, season: str) -> List[Dict[str, Any]]:
    """
    Fetch raw fixture list from FotMob for a given league and season.

    Args:
        league_slug: League identifier key from config (e.g. 'premier-league').
        season:      Season string (e.g. '2025-2026').

    Returns:
        Raw list of match dicts from FotMob allMatches payload.
        Returns empty list if no data found.
    """
    league = LEAGUES[league_slug]
    url = (
        f"https://www.fotmob.com/leagues/{league['fotmob_id']}/fixtures/{league_slug}"
        f"?season={season}&group=by-date"
    )

    logger.info(f"[Crawl Fixtures] {league['name']} {season} -> {url}")

    try:
        next_data = extract_next_data(fetch_html(url), url)
        return (
            next_data
            .get("props", {})
            .get("pageProps", {})
            .get("fixtures", {})
            .get("allMatches", [])
        )
    except ValueError:
        logger.warning(f"  [Missing Data] FotMob has no fixture data for {league_slug} {season}.")
        return []
