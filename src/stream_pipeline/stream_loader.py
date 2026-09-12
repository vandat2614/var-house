"""
Stream Loader.

Listens to the 'transformed-match-details' Kafka topic and idempotently
loads each MatchDetailBundle into the Iceberg Data Lake.
"""

import logging
from typing import Any, Dict

from src.kafka import BaseKafkaConsumer
from src.config import KAFKA_BOOTSTRAP_SERVERS
from src.load.service import MatchLoadService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("StreamLoader")


class StreamLoader:
    """
    Terminal Kafka consumer stage that persists match facts to the database.

    Consumes structured ``MatchDetailBundle`` payloads from the
    'transformed-match-details' topic, validates them through the Pydantic
    schema, then delegates to :func:`load_match_detail` for an idempotent
    database upsert.
    """

    def __init__(self, bootstrap_servers: str = None):
        self.consumer = BaseKafkaConsumer(
            group_id="football-loader-group",
            topics=["transformed-match-details"],
            bootstrap_servers=bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,
        )
        self.load_service = MatchLoadService()

    def process_transformed_match(self, match_id: str, payload: Dict[str, Any]) -> None:
        """Callback: delegate validation and persistence to the load service."""
        try:
            self.load_service.process_and_load(match_id, payload)
        except Exception as exc:
            logger.error("Failed to load match %s: %s", match_id, exc)
            raise  # Re-raise so the Consumer does not commit the offset

    def start(self) -> None:
        """Start the consumer loop. Blocks until interrupted or error."""
        logger.info("Starting Stream Loader...")
        try:
            self.consumer.consume_stream(self.process_transformed_match)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    StreamLoader().start()


