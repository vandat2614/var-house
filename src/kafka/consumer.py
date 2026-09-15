"""
Standalone Kafka Consumer wrapper.

Subscribes to Kafka topics and dispatches messages to a caller-supplied
callback. Handles JSON deserialization, manual offset commits, and
graceful shutdown.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from src.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_SECURITY_PROTOCOL, KAFKA_SSL_CA_LOCATION, KAFKA_SSL_CERT_LOCATION, KAFKA_SSL_KEY_LOCATION

from confluent_kafka import Consumer, KafkaException, KafkaError

logger = logging.getLogger(__name__)


class BaseKafkaConsumer:
    """
    Kafka Consumer wrapper built on ``confluent-kafka``.

    Runs a continuous poll loop, deserializing each message value from UTF-8
    JSON and delegating processing to the caller-supplied ``process_callback``.
    Offsets are committed **synchronously** after each successful callback
    invocation so that failed messages are not skipped.

    Args:
        group_id: Consumer group identifier for offset tracking.
        topics: List of Kafka topic names to subscribe to.
        bootstrap_servers: Kafka broker address (``host:port``).
        additional_config: Extra confluent-kafka consumer config keys merged
            over the defaults.
    """

    def __init__(
        self,
        group_id: str,
        topics: List[str],
        bootstrap_servers: str = None,
        additional_config: Optional[Dict[str, Any]] = None,
    ):
        config: Dict[str, Any] = {
            "bootstrap.servers": bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,  # Initial broker address to discover cluster
            "group.id": group_id,                                               # Consumer group ID for load balancing and offset tracking
            "auto.offset.reset": "earliest",                                    # Read from beginning if no committed offset exists
            "enable.auto.commit": False,                                        # Manual commit after successful DB write to prevent data loss
            "session.timeout.ms": 45000,                                        # Max heartbeat wait time before broker triggers rebalance
            "max.poll.interval.ms": 900000,                                     # 15 minutes max for cloud I/O
            "max.poll.interval.ms": 900000,                                     # 15 minutes max for cloud I/O
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
        self.consumer = Consumer(config)
        self.topics = topics
        self.is_running = False

    def consume_stream(
        self,
        process_callback: Callable[[str, Dict[str, Any]], None], # process what we hear from kafka, then deliver to next step
        poll_timeout: float = 1.0,
        idle_timeout: Optional[float] = None,
    ) -> None:
        """
        Continuously poll for messages and dispatch them to ``process_callback``.

        The loop runs until :meth:`stop` is called, a ``KeyboardInterrupt``
        is raised, or an unrecoverable broker error occurs.

        Args:
            process_callback: Callable receiving ``(message_key, message_value)``
                for each delivered message.
            poll_timeout: Seconds to block waiting for a new message per cycle.
            idle_timeout: Seconds to wait for new messages before gracefully shutting down.
        """
        import time
        try:
            self.consumer.subscribe(self.topics)
            self.is_running = True
            logger.info("Subscribed to topics %s. Polling for messages...", self.topics)
            
            last_message_time = time.time()

            while self.is_running:
                msg = self.consumer.poll(timeout=poll_timeout)

                if msg is None:
                    if idle_timeout and (time.time() - last_message_time) > idle_timeout:
                        logger.info(f"Idle timeout of {idle_timeout}s reached. Shutting down gracefully.")
                        break
                    continue  # No message received in this poll cycle
                
                last_message_time = time.time()

                if msg.error():
                    err_code = msg.error().code()
                    if err_code == KafkaError._PARTITION_EOF:
                        # End-of-partition is informational, not an error
                        logger.debug(
                            "End of partition reached: %s [%s] at offset %s",
                            msg.topic(), msg.partition(), msg.offset(),
                        )
                    elif err_code == KafkaError.UNKNOWN_TOPIC_OR_PART:
                        logger.warning("Topic not available yet. Waiting for producer to create it...")
                        import time
                        time.sleep(2.0)
                    else:
                        raise KafkaException(msg.error())
                else:
                    try:
                        key = msg.key().decode("utf-8") if msg.key() else None
                        value_str = msg.value().decode("utf-8") if msg.value() else "{}"
                        payload = json.loads(value_str)

                        process_callback(key, payload)

                        # Synchronous commit — guarantees at-least-once delivery
                        self.consumer.commit(asynchronous=False)

                    except json.JSONDecodeError as exc:
                        logger.error(
                            "Failed to decode message JSON at offset %s: %s",
                            msg.offset(), exc,
                        )
                    except Exception as exc:
                        logger.error(
                            "Error processing message at offset %s: %s",
                            msg.offset(), exc,
                        )
                        # In production, consider routing to a Dead Letter Queue

        except KeyboardInterrupt:
            logger.info("Kafka consumer loop interrupted by user (KeyboardInterrupt).")
        except Exception as exc:
            logger.exception("Unexpected error in Kafka consumer loop: %s", exc)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the consumer gracefully and leave the consumer group."""
        if self.is_running:
            logger.info("Shutting down Kafka Consumer...")
            self.is_running = False
            self.consumer.close()
            logger.info("Kafka Consumer closed successfully.")

