"""
Telegram Notifier.

Listens to the 'transformed-match-details' Kafka topic and sends a
Telegram message for each match, including match events (Goals, Cards).
"""

import logging
import os
import requests
from typing import Any, Dict

from src.kafka import BaseKafkaConsumer
from src.config import KAFKA_BOOTSTRAP_SERVERS
from src.llm_service import NewsGeneratorService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    def __init__(self, bootstrap_servers: str = None):
        self.consumer = BaseKafkaConsumer(
            group_id="telegram-notifier-group",
            topics=["transformed-match-details"],
            bootstrap_servers=bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS,
        )
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID_HERE")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.llm_service = NewsGeneratorService()

    def process_match_for_telegram(self, match_id: str, payload: Dict[str, Any]) -> None:
        try:
            match_info = payload.get("match") or {}
            home_team = match_info.get("home_team_name", "Unknown Home")
            away_team = match_info.get("away_team_name", "Unknown Away")
            
            events = payload.get("events") or []
            
            final_home_score = 0
            final_away_score = 0
            
            llm_events = ["--- BẮT ĐẦU HIỆP 1 ---"]
            half_number = 1
            
            for ev in events:
                minute = ev.get("minute", "?")
                event_type = ev.get("event_type", "")
                player = ev.get("player_name", "")
                
                if event_type == "Goal":
                    h_score = ev.get("new_score_home", final_home_score)
                    a_score = ev.get("new_score_away", final_away_score)
                    final_home_score = h_score if h_score is not None else final_home_score
                    final_away_score = a_score if a_score is not None else final_away_score
                    
                    is_own_goal = ev.get("is_own_goal", False)
                    og_text = " (Own goal)" if is_own_goal else ""
                    llm_events.append(f"[Goal] {minute}' - {player}{og_text} ({final_home_score} - {final_away_score})")
                    
                elif event_type == "Card":
                    card_type = ev.get("card_type", "")
                    if card_type in ["Red", "YellowRed"]:
                        llm_events.append(f"[Red Card] {minute}' - {player}")
                    elif card_type == "Yellow":
                        llm_events.append(f"[Yellow Card] {minute}' - {player}")
                        
                elif event_type == "Substitution":
                    p_in = ev.get("player_in_name", "")
                    p_out = ev.get("player_out_name", "")
                    llm_events.append(f"[Substitution] {minute}' - In: {p_in} | Out: {p_out}")
                
                elif event_type == "Half":
                    llm_events.append(f"--- KẾT THÚC HIỆP {half_number} ---")
                    half_number += 1
                    if half_number <= 2:
                        llm_events.append(f"--- BẮT ĐẦU HIỆP {half_number} ---")

            stats_data = payload.get("stats", [])

            bulletin = self.llm_service.generate_match_bulletin(
                home_team=home_team,
                away_team=away_team,
                home_score=final_home_score,
                away_score=final_away_score,
                events=llm_events,
                stats=stats_data,
            )
            
            message = (
                f"<b>KẾT QUẢ TRẬN ĐẤU</b>\n\n"
                f"<b>{home_team} {final_home_score} - {final_away_score} {away_team}</b>\n\n"
                f"{bulletin}"
            )

            if self.bot_token != "YOUR_BOT_TOKEN_HERE":
                response = requests.post(
                    self.api_url,
                    json={"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"},
                    timeout=5
                )
                if response.status_code != 200:
                    logger.error(f"Telegram API Error: {response.text}")
                response.raise_for_status()
                logger.info("Sent Telegram notification for match %s", match_id)
            else:
                logger.info("[Mock Telegram]\n%s", message)
                
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
