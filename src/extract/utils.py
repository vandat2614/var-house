import logging
"""
Shared utilities for FotMob crawlers.

Provides:
  - HTTP fetching with retry & exponential backoff
  - __NEXT_DATA__ JSON extraction from FotMob HTML pages
  - Local JSON cache read/write helpers
"""

import json
import os
import time
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str, delay: float = 0.5, max_retries: int = 3) -> str:
    """Fetch raw HTML from URL with rate limiting and exponential backoff retry."""
    time.sleep(delay)
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            res.raise_for_status()
            return res.text
        except Exception as exc:
            if attempt == max_retries:
                raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts: {exc}")
            wait = delay * (2 ** attempt)
            logger.info(f"  [Retry {attempt}/{max_retries}] {exc} — retrying in {wait:.1f}s")
            time.sleep(wait)


def extract_next_data(html: str, url: str) -> Dict[str, Any]:
    """Parse and return the __NEXT_DATA__ JSON payload from a FotMob page."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        raise ValueError(f"__NEXT_DATA__ script tag not found in: {url}")
    return json.loads(tag.string)






