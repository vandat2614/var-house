import logging
import pytz
from datetime import datetime

# Import Kafka producer and Match detail crawler
from src.extract.match_detail_crawler import crawl_match_detail
from src.kafka.producer import BaseKafkaProducer
from src.config import KAFKA_BOOTSTRAP_SERVERS

# Import the fixture utils that we saved
from archive.airflow_legacy.dags.utils.fixture_utils import get_active_matches

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting active matches crawl...")
    active_matches = get_active_matches()
    
    if not active_matches:
        logger.info("No active matches found for the next 7 days.")
        return

    now = datetime.now(pytz.UTC)
    matches_to_crawl = []
    
    for match in active_matches:
        if now >= match['target_time']:
            matches_to_crawl.append(match)
            
    if not matches_to_crawl:
        logger.info(f"Found {len(active_matches)} active matches, but none are ready to be crawled yet (target_time > now).")
        return
        
    logger.info(f"Found {len(matches_to_crawl)} matches ready to be crawled.")
    
    producer = BaseKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        for match in matches_to_crawl:
            match_id = match['match_id']
            logger.info(f"Crawling match {match_id} ({match['task_name']})")
            
            try:
                crawl_match_detail(
                    match_id=match_id, 
                    force_refresh=False, 
                    kafka_producer=producer,
                    season=match.get('season'), 
                    league_slug=match.get('league_slug')
                )
                logger.info(f"Successfully extracted raw data for match {match_id}")
            except Exception as e:
                logger.error(f"Failed to crawl match {match_id}: {e}", exc_info=True)
                
    finally:
        producer.flush(timeout=5.0)
        logger.info("Flushed Kafka producer and finished active matches crawl.")

if __name__ == '__main__':
    main()
