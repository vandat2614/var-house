"""
Telegram Notifier Consumer.

Listens to the 'transformed-match-details' Kafka topic and sends a
Telegram message for each match using LLM-generated bulletins.
"""

import logging
import os
import requests
from typing import Any, Dict

from src.kafka import BaseKafkaConsumer
from src.config import KAFKA_BOOTSTRAP_SERVERS
from src.llm.service import LLMClient
from src.consumers.notify.utils import format_events, format_stats, build_messages

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    def __init__(self, bootstrap_servers: str = None):
        self.consumer = BaseKafkaConsumer(
            group_id="telegram-notifier-group",
            topics=["transformed-match-details"],
            bootstrap_servers=bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,
        )
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.bot_token or not self.chat_id:
            raise EnvironmentError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")

        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.llm = LLMClient()

    def _send_message(self, text: str, match_id: str = "") -> None:
        """Send a message via the Telegram Bot API."""
        response = requests.post(
            self.api_url,
            json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
        if response.status_code != 200:
            logger.error("Telegram API Error: %s", response.text)
        response.raise_for_status()
        logger.info("Sent Telegram notification for match %s", match_id)

    def process_match_for_telegram(self, match_id: str, payload: Dict[str, Any]) -> None:
        try:
            match_info = payload.get("match") or {}
            home_team = match_info.get("home_team_name", "Unknown Home")
            away_team = match_info.get("away_team_name", "Unknown Away")

            events = payload.get("events") or []
            llm_events, final_home_score, final_away_score = format_events(events)

            stats_text = format_stats(payload.get("stats", []))
            events_text = "\n".join(llm_events) if llm_events else "Không có diễn biến nổi bật."

            messages = build_messages(
                home_team=home_team,
                away_team=away_team,
                home_score=final_home_score,
                away_score=final_away_score,
                events_text=events_text,
                stats_text=stats_text,
            )

            bulletin = self.llm.chat(messages)
            if not bulletin:
                bulletin = f"[LLM Error]: {home_team} {final_home_score} - {final_away_score} {away_team}"

            message = (
                f"<b>KẾT QUẢ TRẬN ĐẤU</b>\n\n"
                f"<b>{home_team} {final_home_score} - {final_away_score} {away_team}</b>\n\n"
                f"{bulletin}"
            )

            self._send_message(message, match_id)

        except Exception as exc:
            logger.error("Failed to process/send match %s to Telegram: %s", match_id, exc)

    def start(self) -> None:
        logger.info("Starting Telegram Notifier...")
        try:
            self.consumer.consume_stream(self.process_match_for_telegram, idle_timeout=120.0)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    TelegramNotifier().start()
