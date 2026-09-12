import logging

from src.config import KAFKA_BOOTSTRAP_SERVERS


def crawl_match_task(match_id: str, season: str = None, league_slug: str = None, **kwargs):
    """
    The actual worker task that runs after the Sensor releases it.
    """
    logging.getLogger(__name__).info(
        f"Sensor released! It has been 2 hours since kickoff for Match {match_id}. Crawling now..."
    )
    from src.extract.match_detail_crawler import crawl_match_detail
    from src.kafka.producer import BaseKafkaProducer

    producer = BaseKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        crawl_match_detail(
            match_id=match_id, force_refresh=False, kafka_producer=producer,
            season=season, league_slug=league_slug
        )
        logging.getLogger(__name__).info(f"Successfully extracted raw data for match {match_id}")
    finally:
        producer.flush(timeout=5.0)
