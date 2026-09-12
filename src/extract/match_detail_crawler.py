import logging
"""
Football Match Detail Crawler

For a given match_id, fetches:
  - Events  : goals, cards, substitutions, VAR (with minute, player, team)
  - Lineups : starters & bench with shirt number, position, age, country, rating

Raw JSON content is cached locally under data/raw/matches/{season}/{league_slug}/{match_id}.json.
"""

import os
from src.config import RAW_MATCHES_DIR, CURRENT_SEASON, MATCH_BUFFER_HOURS, LEAGUES
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.extract.utils import fetch_html, extract_next_data
from src.utils import save_json, load_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


RAW_DIR = RAW_MATCHES_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_path(match_id: str, season: str = None, league_slug: str = None) -> str:
    season = season or CURRENT_SEASON
    season_safe = season.replace("/", "_").replace("-", "_")
    league_slug = league_slug or "unknown"
    path = os.path.join(RAW_DIR, season_safe, league_slug, f"{match_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _is_ready_to_fetch(utc_time_str: str) -> bool:
    """Return True if kickoff + MATCH_BUFFER_HOURS < current UTC time.

    Uses only the stdlib ``datetime`` module — no pandas dependency needed
    for a simple ISO-8601 timestamp comparison.
    """
    if not utc_time_str:
        return False
    try:
        # Normalise the trailing 'Z' that FotMob appends (not valid in Python < 3.11)
        normalised = utc_time_str.replace("Z", "+00:00")
        kickoff = datetime.fromisoformat(normalised)
        return kickoff + timedelta(hours=MATCH_BUFFER_HOURS) < datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def crawl_match_detail(
    match_id: str,
    force_refresh: bool = False,
    kafka_producer: Any = None,
    season: str = None,
    league_slug: str = None,
) -> Dict[str, Any]:
    """
    Crawl events and lineup for a single match.

    Args:
        match_id: FotMob match identifier string (e.g. '5868011').
        force_refresh: Ignore local cache if True.
        kafka_producer: Optional producer; when provided, the raw content dict
            is published to the 'raw-match-details' topic.

    Returns:
        Dict representing raw match details.
    """
    cache_path = _cache_path(match_id, season=season, league_slug=league_slug)

    if not force_refresh and os.path.exists(cache_path):
        logger.info(f"  [Cache] Loaded match {match_id} from: {cache_path}")
        content = load_json(cache_path)
        if kafka_producer:
            kafka_producer.produce_message(
                topic="raw-match-details",
                key=match_id,
                value=content,
            )
        return content

    url = f"https://www.fotmob.com/match/{match_id}"
    logger.info(f"  [Crawl Match] ID: {match_id} - {url}")

    next_data = extract_next_data(fetch_html(url), url)
    content = next_data.get("props", {}).get("pageProps", {}).get("content", {})

    save_json(content, cache_path)
    if kafka_producer:
        kafka_producer.produce_message(
            topic="raw-match-details",
            key=match_id,
            value=content,
        )

    logger.info(f"  -> Successfully extracted raw data. Saved: {cache_path}")
    return content




