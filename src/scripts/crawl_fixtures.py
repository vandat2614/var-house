"""
Script: Crawl Fixtures

Crawls fixture schedules for all configured leagues across one or more seasons.
Handles caching, transform, team extraction, and loading.

Orchestration responsibilities (moved out of ETL layer):
  - Loop over all leagues
  - Cache raw JSON to disk
  - Enrich match records with league_slug and season
  - Call TransformService then LoadService
"""

import logging
import os
import time
import random
import argparse

from src.config import CRAWL_CURRENT_SEASON, FOTMOB_OLDEST_SEASON, LEAGUES, RAW_FIXTURES_DIR
from src.etl.extract import ExtractService
from src.etl.transform import TransformService
from src.etl.load import LoadService
from src.utils import save_json, load_json, file_exists, get_season_safe

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FixtureCrawlerScript")
logging.getLogger("pyiceberg").setLevel(logging.WARNING)

extract = ExtractService()
transform = TransformService()
load = LoadService()


def _cache_path(league_slug: str, season: str) -> str:
    return os.path.join(RAW_FIXTURES_DIR, get_season_safe(season), f"{league_slug}.json")


def generate_seasons(start: str, end: str) -> list:
    start_yr = int(start.split("-")[0])
    end_yr = int(end.split("-")[0])
    return [f"{y}-{y+1}" for y in range(start_yr, end_yr + 1)]


def run_season(season: str) -> tuple:
    """Crawl, transform, and return (all_matches, all_teams) for all leagues in a season."""
    all_matches = []
    all_teams = []

    for league_slug in LEAGUES:
        if league_slug == 'conference_league':
            # UEFA Conference League started in 2021-2022
            start_yr = int(season[:4])
            if start_yr < 2021:
                continue
        try:
            cache_path = _cache_path(league_slug, season)

            # Cache check: skip re-crawl for past seasons
            if file_exists(cache_path) and season != CRAWL_CURRENT_SEASON:
                logger.info(f"  [Cache] {league_slug} {season}")
                raw_list = load_json(cache_path)
            else:
                raw_list = extract.crawl_fixtures(league_slug, season)
                save_json(raw_list, cache_path)
                logger.info(f"  [Crawled] {league_slug} {season} -> {len(raw_list)} matches")

            # Transform fixtures and enrich with league_slug + season
            matches = transform.transform_fixtures(raw_list)
            for m in matches:
                m["league_slug"] = league_slug
                m["season"] = season

            # Extract unique teams
            teams = transform.extract_teams(raw_list)

            all_matches.extend(matches)
            all_teams.extend(teams)

        except Exception as e:
            logger.error(f"  [Error] {league_slug} {season}: {e}")

    return all_matches, all_teams


def main():
    parser = argparse.ArgumentParser(description="FotMob Fixture Crawler")
    parser.add_argument("--season", type=str, help="Crawl a specific season (e.g., 2023-2024)")
    parser.add_argument("--all", action="store_true", help="Crawl from oldest to current season")
    args = parser.parse_args()

    all_matches = []
    all_teams = []

    if args.all:
        logger.info(f"Running Historical Crawl from {FOTMOB_OLDEST_SEASON} to {CRAWL_CURRENT_SEASON}")
        for season in generate_seasons(FOTMOB_OLDEST_SEASON, CRAWL_CURRENT_SEASON):
            m, t = run_season(season)
            all_matches.extend(m)
            all_teams.extend(t)
            time.sleep(random.uniform(2.0, 5.0))
    elif args.season:
        logger.info(f"Running Single Season Crawl for {args.season}")
        m, t = run_season(args.season)
        all_matches.extend(m)
        all_teams.extend(t)
    else:
        logger.info(f"Running Current Season Crawl ({CRAWL_CURRENT_SEASON})")
        m, t = run_season(CRAWL_CURRENT_SEASON)
        all_matches.extend(m)
        all_teams.extend(t)

    logger.info(f"Aggregated {len(all_matches)} matches and {len(all_teams)} teams. Loading to Iceberg...")
    load.load_fixtures(all_matches)
    load.load_teams(all_teams)
    logger.info("Fixture Crawl Complete!")


if __name__ == "__main__":
    main()
