import logging
"""
Football Match Detail Crawler

Responsibility: EXTRACT only.
  - Fetch raw HTML from FotMob for a given match_id
  - Parse __NEXT_DATA__ JSON
  - Return raw content dict

Does NOT cache, does NOT check match readiness, does NOT publish.
All orchestration logic (caching, retry scheduling, Kafka) belongs in the caller.
"""

from typing import Any, Dict

from src.etl.extract.utils import fetch_html, extract_next_data

logger = logging.getLogger(__name__)


def crawl_match_detail(match_id: str) -> Dict[str, Any]:
    """
    Fetch raw match content from FotMob for a given match_id.

    Args:
        match_id: FotMob match identifier (e.g. '5868011').

    Returns:
        Raw content dict from FotMob __NEXT_DATA__.
        Returns empty dict if content is missing.
    """
    url = f"https://www.fotmob.com/match/{match_id}"
    logger.info(f"  [Crawl Match] {match_id} -> {url}")

    next_data = extract_next_data(fetch_html(url), url)
    content = next_data.get("props", {}).get("pageProps", {}).get("content", {})

    logger.info(f"  -> Fetched raw content for match {match_id}")
    return content
