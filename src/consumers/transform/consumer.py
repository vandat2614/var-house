"""
Stream Transformer.

Listens to the 'raw-match-details' Kafka topic, transforms the raw JSON
payload into structured fact records, then publishes the result to
'transformed-match-details' for the Stream Loader to consume.
"""

import logging
import os
from typing import Any, Dict

from src.kafka import BaseKafkaConsumer, BaseKafkaProducer
from src.etl.transform import TransformService
from src.config import KAFKA_BOOTSTRAP_SERVERS, TRANSFORMED_DIR
from src.utils import save_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("StreamTransformer")


class StreamTransformer:
    """
    Stateless Kafka-to-Kafka transformation stage.

    Consumes raw match content from the 'raw-match-details' topic,
    applies transform_match_detail(), persists the result as a local
    Silver-layer JSON file, then publishes the structured bundle to the
    'transformed-match-details' topic for downstream loading.
    """

    def __init__(self, bootstrap_servers: str = None):
        self.producer = BaseKafkaProducer(bootstrap_servers=bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS)
        self.consumer = BaseKafkaConsumer(
            group_id="football-transformer-group",
            topics=["raw-match-details"],
            bootstrap_servers=bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,
        )
        self.transform_service = TransformService()

    def process_raw_match(self, match_id: str, payload: Dict[str, Any]) -> None:
        """Callback: transform one raw match payload and forward it downstream."""
        try:
            # 1. Transform raw payload -> structured dict
            result_dict = self.transform_service.transform_match_detail(match_id, payload)

            # 2. Persist Silver-layer JSON to disk (orchestrator responsibility)
            match_info = result_dict.get("match") or {}
            season = (match_info.get("season") or "unknown").replace("/", "_").replace("-", "_")
            league = match_info.get("league_slug") or "unknown"
            out_path = os.path.join(TRANSFORMED_DIR, "match-details", season, league, f"{match_id}.json")
            save_json(result_dict, out_path)
            logger.info("    Saved Silver JSON -> %s", out_path)

            # 3. Publish clean data to the next topic for the Loader
            self.producer.produce_message(
                topic="transformed-match-details",
                key=match_id,
                value=result_dict,
            )
            logger.info("Successfully transformed and published match %s.", match_id)

        except Exception as exc:
            logger.error("Failed to transform match %s: %s", match_id, exc)
            raise  # Re-raise so the Consumer does not commit the offset

    def start(self) -> None:
        """Start the consumer loop. Blocks until interrupted or error."""
        logger.info("Starting Stream Transformer...")
        try:
            self.consumer.consume_stream(self.process_raw_match, idle_timeout=120.0)
        except KeyboardInterrupt:
            pass
        finally:
            self.producer.flush()


if __name__ == "__main__":
    StreamTransformer().start()
