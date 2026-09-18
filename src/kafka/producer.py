"""
Standalone Kafka Producer wrapper.

Publishes JSON payloads to Kafka topics. Handles JSON serialization,
asynchronous delivery callbacks, and graceful flushing.
"""

import json
import logging
from typing import Any, Dict, Optional

from src.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL, KAFKA_SSL_CA_LOCATION, KAFKA_SSL_CERT_LOCATION, KAFKA_SSL_KEY_LOCATION

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

logger = logging.getLogger(__name__)


class BaseKafkaProducer:
    """
    Kafka Producer wrapper built on ``confluent-kafka``.

    Serializes message values as UTF-8 JSON. Delivery success/failure is
    reported asynchronously via :meth:`_delivery_report`. Call :meth:`flush`
    (or :meth:`close`) before process exit to ensure all queued messages
    have been acknowledged by the broker.

    Args:
        bootstrap_servers: Kafka broker address (``host:port``).
        additional_config: Extra confluent-kafka producer config keys merged
            over the defaults.
    """

    def __init__(
        self,
        bootstrap_servers: str = None,
        additional_config: Optional[Dict[str, Any]] = None,
    ):
        config: Dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,  # Initial broker address to discover cluster
            "client.id": "fotmob-etl-producer",                                 # Identifier for logging and broker metrics
            "acks": "all",                                                      # Wait for all replicas to commit (prevents data loss)
            "compression.type": "snappy",                                       # Fast compression to reduce network bandwidth
            "retries": 5,                                                       # Auto-retry up to 5 times on transient network errors
        }
        if additional_config:
            config.update(additional_config)

        if KAFKA_SECURITY_PROTOCOL == "SSL":
            config.update({
                'security.protocol': 'SSL',
                'ssl.ca.location': KAFKA_SSL_CA_LOCATION,
                'ssl.certificate.location': KAFKA_SSL_CERT_LOCATION,
                'ssl.key.location': KAFKA_SSL_KEY_LOCATION,
            })
        self._admin_config = {
            "bootstrap.servers": config["bootstrap.servers"]
        }
        if KAFKA_SECURITY_PROTOCOL == "SSL":
            self._admin_config.update({
                'security.protocol': 'SSL',
                'ssl.ca.location': KAFKA_SSL_CA_LOCATION,
                'ssl.certificate.location': KAFKA_SSL_CERT_LOCATION,
                'ssl.key.location': KAFKA_SSL_KEY_LOCATION,
            })
            
        self.producer = Producer(config)
        self._known_topics = set()
        logger.info("Initialized Kafka Producer connected to %s", bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    
    def _ensure_topic_exists(self, topic: str) -> None:
        if topic in self._known_topics:
            return
            
        admin = AdminClient(self._admin_config)
        metadata = admin.list_topics(timeout=10)
        
        if topic not in metadata.topics:
            logger.info("Topic '%s' does not exist. Creating...", topic)
            new_topic = NewTopic(topic, num_partitions=1, replication_factor=1)
            fs = admin.create_topics([new_topic])
            for t, f in fs.items():
                try:
                    f.result()  # wait for completion
                    logger.info("Successfully created topic '%s'", t)
                except Exception as e:
                    logger.error("Failed to create topic '%s': %s", t, e)
                    
        self._known_topics.add(topic)

    @staticmethod
    def _delivery_report(err, msg) -> None:
        """Async callback triggered upon message delivery success or failure."""
        if err is not None:
            logger.error("Message delivery failed for topic %s: %s", msg.topic(), err)
        else:
            logger.debug(
                "Message delivered to %s [partition %s] at offset %s",
                msg.topic(), msg.partition(), msg.offset(),
            )

    def _do_produce(self, topic: str, key: Optional[str], value: Dict[str, Any]) -> None:
        """Encode and enqueue a single message to the Kafka producer buffer.

        Args:
            topic: Target Kafka topic name.
            key: Optional partition key (encoded to UTF-8).
            value: Payload dict serialized to JSON bytes.
        """
        self.producer.produce(
            topic=topic,
            key=key.encode("utf-8") if key else None, # (e.g. match_id) to guarantee ordering, the same match_id events will always go to the same partition
            value=json.dumps(value).encode("utf-8"),
            callback=self._delivery_report,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def produce_message(self, topic: str, key: str, value: Dict[str, Any]) -> None:
        """
        Produce a JSON message to a Kafka topic.

        Polls for pending delivery callbacks first, then enqueues the message.
        On :exc:`BufferError` (local queue full) the queue is flushed before
        retrying once.

        Args:
            topic: Target Kafka topic.
            key: Partition key (e.g. ``match_id``) to guarantee ordering.
            value: Payload dict serialized as JSON.
        """
        self._ensure_topic_exists(topic)
        
        # Drain any pending delivery report callbacks from previous calls
        self.producer.poll(0)

        try:
            self._do_produce(topic, key, value)
        except BufferError:
            logger.warning("Local producer queue is full - flushing and retrying.")
            self.producer.flush() # Block until all buffered messages are sent
            self._do_produce(topic, key, value)
        except Exception as exc:
            logger.error("Exception while producing message to %s: %s", topic, exc)

    def flush(self, timeout: float = 30.0) -> None:
        """Block until all enqueued messages have been delivered (or timeout)."""
        remaining = self.producer.flush(timeout)
        if remaining > 0:
            logger.warning("Failed to flush %d messages before timeout.", remaining)
        else:
            logger.info("Successfully flushed all messages.")

    def close(self) -> None:
        """Alias for :meth:`flush` - ensures safe shutdown."""
        self.flush()

