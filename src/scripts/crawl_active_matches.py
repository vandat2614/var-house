"""
Script: Crawl Active Matches

Fetches raw match detail for upcoming/ongoing matches that are ready
(kickoff + buffer has passed). Caches raw JSON locally, then publishes
to Kafka for downstream transform/load consumers.

Orchestration responsibilities (moved out of ETL layer):
  - Check local cache before fetching
  - Check if match is ready to crawl (buffer time check)
  - Publish raw content to Kafka
"""

import logging
import os
from datetime import datetime, timezone, timedelta

from src.etl.extract import ExtractService
from src.kafka.producer import BaseKafkaProducer
from src.config import KAFKA_BOOTSTRAP_SERVERS, RAW_MATCHES_DIR, CRAWL_MATCH_BUFFER_HOURS, CRAWL_CURRENT_SEASON
from src.utils import save_json, load_json, file_exists, list_dir, get_season_safe
import dateutil.parser
from src.config import RAW_FIXTURES_DIR


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

extract = ExtractService()


def _cache_path(match_id: str, season: str, league_slug: str) -> str:
    season_safe = (season or CRAWL_CURRENT_SEASON).replace("/", "_").replace("-", "_")
    return os.path.join(RAW_MATCHES_DIR, season_safe, league_slug or "unknown", f"{match_id}.json")






def _get_pending_matches_to_crawl() -> list:
    season_safe = get_season_safe(CRAWL_CURRENT_SEASON)
    season_path = f"{RAW_FIXTURES_DIR}/{season_safe}".replace("s3://", "s3://").replace("\\", "/")
    
    logger.info(f"Listing raw fixtures directory: {season_path}")
    filenames = list_dir(season_path)
    if not filenames:
        logger.warning(f"No raw fixture files found in {season_path}")
        return []

    now_utc = datetime.now(timezone.utc)
    pending = []

    for filename in filenames:
        if not filename.endswith(".json"):
            continue
            
        league_slug = filename.replace(".json", "")
        
        # Lọc chỉ chạy Premier League và Champions League theo yêu cầu
        if league_slug not in ["premier_league", "champions_league"]:
            logger.info(f"Skipping league {league_slug} (Not in filter list)")
            continue
            
        file_path = f"{season_path}/{filename}"
        
        logger.info(f"Processing league: {league_slug}")
        
        # Optimize: Get all already crawled matches for this league in ONE network call!
        league_cache_dir = os.path.join(RAW_MATCHES_DIR, season_safe, league_slug).replace("\\", "/")
        crawled_files = list_dir(league_cache_dir)
        crawled_match_ids = {f.replace(".json", "") for f in crawled_files}
        logger.info(f"  -> Found {len(crawled_match_ids)} already crawled matches in {league_cache_dir}")
        
        try:
            logger.info(f"  -> Loading fixtures from {file_path}")
            raw_list = load_json(file_path)
            logger.info(f"  -> Parsing {len(raw_list)} matches for {league_slug}")
            
            for item in raw_list:
                match_id = str(item.get("id", ""))
                status = item.get("status", {})
                utc_str = status.get("utcTime", "")
                
                if not match_id or not utc_str:
                    continue
                    
                kickoff = dateutil.parser.parse(utc_str)
                target_time = kickoff + timedelta(hours=CRAWL_MATCH_BUFFER_HOURS)
                
                if target_time <= now_utc:
                    # Check our local set instead of making a network call to R2 for every match!
                    if match_id not in crawled_match_ids:
                        home = item.get("home", {})
                        away = item.get("away", {})
                        pending.append({
                            "match_id": match_id,
                            "kickoff_utc": utc_str,
                            "home": home.get("name", "Home"),
                            "away": away.get("name", "Away"),
                            "league_slug": league_slug,
                            "season": CRAWL_CURRENT_SEASON
                        })
        except Exception as e:
            logger.error(f"Failed to parse {filename}: {e}")

    return pending

def main():
    logger.info("Starting active matches crawl...")
    matches_to_crawl = _get_pending_matches_to_crawl()[:5]

    if not matches_to_crawl:
        logger.info("No pending matches found to crawl.")
        return

    logger.info(f"Found {len(matches_to_crawl)} matches ready to be crawled.")

    producer = BaseKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        for match in matches_to_crawl:
            match_id = match["match_id"]
            season = match.get("season")
            league_slug = match.get("league_slug")

            try:
                cache_path = _cache_path(match_id, season, league_slug)

                # Cache check (orchestrator responsibility)
                if file_exists(cache_path):
                    logger.info(f"  [Cache] Match {match_id} already crawled, publishing from cache.")
                    content = load_json(cache_path)
                else:
                    content = extract.crawl_match_detail(match_id)
                    save_json(content, cache_path)
                    logger.info(f"  [Crawled] Match {match_id} -> saved to {cache_path}")

                # Publish to Kafka (orchestrator responsibility)
                producer.produce_message(
                    topic="raw-match-details",
                    key=match_id,
                    value=content,
                )
                logger.info(f"  [Published] Match {match_id} -> raw-match-details")

            except Exception as e:
                logger.error(f"Failed to crawl match {match_id}: {e}", exc_info=True)
    finally:
        producer.flush()
        logger.info("Flushed Kafka producer and finished active matches crawl.")


if __name__ == "__main__":
    main()
