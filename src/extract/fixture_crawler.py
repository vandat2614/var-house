import logging
"""
Football Fixture Crawler

Crawls fixture schedules for configured leagues.
Raw JSON responses are cached locally under data/raw/fixtures/{season}/.
"""

import os
from src.config import RAW_FIXTURES_DIR, CURRENT_SEASON, LEAGUES, TRANSFORMED_DIR
from typing import Any, Dict, List

from src.extract.utils import fetch_html, extract_next_data
from src.utils import save_json, load_json, get_season_safe

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_DIR = RAW_FIXTURES_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_path(league_slug: str) -> str:
    season_safe = get_season_safe(CURRENT_SEASON)
    path = os.path.join(RAW_DIR, season_safe, f"{league_slug}.json")
    
    return path


def _fetch_raw_fixtures(league_slug: str) -> List[Dict[str, Any]]:
    """Fetches raw fixture data from FotMob for a given league."""
    league = LEAGUES[league_slug]
    url = (
        f"https://www.fotmob.com/leagues/{league['fotmob_id']}/fixtures/{league_slug}"
        f"?season={CURRENT_SEASON}&group=by-date"
    )

    logger.info(f"[Crawl Fixtures] {league['name']} {CURRENT_SEASON}")
    logger.info(f"  URL: {url}")

    next_data = extract_next_data(fetch_html(url), url)

    return (
        next_data
        .get("props", {})
        .get("pageProps", {})
        .get("fixtures", {})
        .get("allMatches", [])
    )


def _process_and_load_dimensions(all_matches: List[Dict[str, Any]], league_slug: str) -> None:
    """Transforms raw fixtures into Match/Team dimensions and loads them into Iceberg."""
    try:
        from src.transform.fixture_transformer import transform_fixtures, transform_teams_from_fixtures
        from src.load.iceberg_loader import load_dim_matches, load_dim_teams

        logger.info(f"  [Transform] Extracting Dimensions for {league_slug}")
        matches = transform_fixtures(all_matches, league_slug)
        teams = transform_teams_from_fixtures(all_matches)

        # Save transformed copies to data/transformed/
        season_safe = get_season_safe(CURRENT_SEASON)
        trans_dir = os.path.join(TRANSFORMED_DIR, "fixtures", season_safe)
        # os.makedirs(trans_dir, exist_ok=True)
        
        matches_data = [m if isinstance(m, dict) else (m.model_dump() if hasattr(m, 'model_dump') else m.dict()) for m in matches]
        # teams_data = [t if isinstance(t, dict) else (t.model_dump() if hasattr(t, 'model_dump') else t.dict()) for t in teams]
        
        save_json(matches_data, os.path.join(trans_dir, f"{league_slug}_matches.json"))
        # save_json(teams_data, os.path.join(trans_dir, f"{league_slug}_teams.json"))
        logger.info(f"  [Transform] Saved transformed JSON to {trans_dir}")

        logger.info(f"  [Load] Upserting {len(matches)} matches and {len(teams)} teams into Iceberg")
        load_dim_matches(matches)
        load_dim_teams(teams)
    except Exception as e:
        logger.error(f"Failed to transform/load fixtures for {league_slug}: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def crawl_fixtures(
    league_slug: str,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """
    Crawl all fixtures for a given league in the current season.
    """
    if league_slug not in LEAGUES:
        raise ValueError(f"Unknown league: '{league_slug}'. Available: {list(LEAGUES)}")

    cache_path = _cache_path(league_slug)

    if not force_refresh and file_exists(cache_path):
        logger.error(f"[Cache] Loaded fixtures from: {cache_path}")
        return load_json(cache_path)

    all_matches = _fetch_raw_fixtures(league_slug)

    save_json(all_matches, cache_path)
    logger.info(f"  Saved {len(all_matches)} raw fixtures -> {cache_path}")

    _process_and_load_dimensions(all_matches, league_slug)

    return all_matches


def crawl_all_fixtures(
    force_refresh: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Crawl fixtures for all 5 leagues in the current season.
    """
    results: Dict[str, List[Dict[str, Any]]] = {}
    for league_slug in LEAGUES:
        try:
            results[league_slug] = crawl_fixtures(
                league_slug,
                force_refresh=force_refresh,
            )
        except Exception as exc:
            logger.info(f"  [Error] {league_slug}: {exc}")
            results[league_slug] = []
    return results
