import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import dateutil.parser
from datetime import datetime, timezone, timedelta
from src.extract.match_detail_crawler import crawl_match_detail
from dags.utils.fixture_utils import get_fixtures, is_match_crawled
from src.kafka.producer import BaseKafkaProducer
from src.config import KAFKA_BOOTSTRAP_SERVERS, MATCH_BUFFER_HOURS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_missing_historical_matches(days_back: int = 0) -> list:
    """
    Returns a list of historical matches that need to be crawled.
    Matches are included if their target time (kickoff + buffer) is before (now - days_back).
    """
    fixtures = get_fixtures()
    if not fixtures:
        logging.warning("No fixtures found. Run crawl_fixtures first.")
        return []

    now_utc = datetime.now(timezone.utc)
    threshold_date = now_utc - timedelta(days=days_back)
    
    missing_matches = []
    
    for match in fixtures:
        match_id = str(match.get("match_id", ""))
        utc_str = match.get("kickoff_utc", "")
        if not match_id or not utc_str:
            continue
            
        kickoff = dateutil.parser.parse(utc_str)
        target_time = kickoff + timedelta(hours=MATCH_BUFFER_HOURS)
        
        if target_time < threshold_date:
            if not is_match_crawled(match_id):
                missing_matches.append({
                    "match_id": match_id,
                    "season": match.get("season"),
                    "league": match.get("league_slug"),
                    "kickoff": kickoff
                })
                
    missing_matches.sort(key=lambda x: x["kickoff"])
    return missing_matches

def crawl_historical_matches(days_back: int = 0):
    """
    Crawls missing historical matches that occurred in the past days_back days.
    """
    missing_matches = get_missing_historical_matches(days_back)
    
    if not missing_matches:
        logging.info(f"All historical matches older than {days_back} days have already been crawled!")
        return
        
    logging.info(f"Found {len(missing_matches)} missing historical matches to crawl.")
    
    producer = BaseKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    
    for i, m in enumerate(missing_matches, 1):
        logging.info(f"[{i}/{len(missing_matches)}] Crawling match {m['match_id']} (Kickoff: {m['kickoff']})")
        try:
            crawl_match_detail(
                match_id=m["match_id"],
                season=m["season"],
                league_slug=m["league"],
                kafka_producer=producer,
                force_refresh=False
            )
        except Exception as e:
            logging.error(f"Failed to crawl match {m['match_id']}: {e}")
            
    producer.flush()
    producer.close()
    logging.info("Historical catchup completed successfully!")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Catchup missing historical match details")
    parser.add_argument("--days", type=int, default=5, help="Number of days back to check (default: 5)")
    args = parser.parse_args()
    
    crawl_historical_matches(days_back=args.days)
