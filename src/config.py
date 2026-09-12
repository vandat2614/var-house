import os
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- Paths ---
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
# Fallback to 2 levels up if PROJECT_ROOT is not set or empty
PROJECT_ROOT = os.getenv("PROJECT_ROOT") or os.path.abspath(os.path.join(_SRC_DIR, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_FIXTURES_DIR = os.path.join(DATA_DIR, "raw", "fixtures")
RAW_MATCHES_DIR = os.path.join(DATA_DIR, "raw", "matches")
TRANSFORMED_DIR = os.path.join(DATA_DIR, "transformed")

ICEBERG_WAREHOUSE_DIR = os.path.join(DATA_DIR, "iceberg", "warehouse")
ICEBERG_CATALOG_DB = os.path.join(DATA_DIR, "iceberg", "iceberg_catalog.db")

# --- Kafka ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# --- Crawler Configs ---
CURRENT_SEASON = os.getenv("CURRENT_SEASON", "2026-2027")
MATCH_BUFFER_HOURS = int(os.getenv("MATCH_BUFFER_HOURS", 2))

LEAGUES: Dict[str, Dict[str, Any]] = {
    "premier_league": {"fotmob_id": 47, "name": "Premier League"},
}
