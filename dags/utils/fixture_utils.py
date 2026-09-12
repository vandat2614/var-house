import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import dateutil.parser

from src.config import CURRENT_SEASON, TRANSFORMED_DIR
from src.utils import get_season_safe


def is_match_crawled(match_id: str) -> bool:
    season_safe = get_season_safe(CURRENT_SEASON)
    season_dir = os.path.join(TRANSFORMED_DIR, "match-details", season_safe)

    if not os.path.exists(season_dir):
        return False

    for _l_dir in os.listdir(season_dir):
        league_dir = os.path.join(season_dir, _l_dir)
        if os.path.isdir(league_dir) and os.path.exists(
            os.path.join(league_dir, f"{match_id}.json")
        ):
            return True
    return False


def get_fixtures():
    season_safe = get_season_safe(CURRENT_SEASON)
    season_path = os.path.join(TRANSFORMED_DIR, "fixtures", season_safe)
    all_fixtures = []

    if not os.path.exists(season_path):
        return all_fixtures

    for filename in os.listdir(season_path):
        # Only read the matches file
        if not filename.endswith("_matches.json"):
            continue
        file_path = os.path.join(season_path, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_fixtures.extend(data)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to parse {filename}: {e}")

    return all_fixtures


def get_active_matches() -> list:
    """
    Finds uncrawled matches within the active [-3 days, +3 days] window.
    """
    fixtures = get_fixtures()
    active_uncrawled = []
    now_utc = datetime.now(timezone.utc)

    for match in fixtures:
        match_id = str(match.get("match_id", ""))
        utc_str = match.get("kickoff_utc", "")
        if not match_id or not utc_str:
            continue

        kickoff = dateutil.parser.parse(utc_str)
        target_time = kickoff + timedelta(hours=2)

        if abs((now_utc - target_time).days) <= 3 and not is_match_crawled(match_id):
            home_name = match.get("home_team_name", "Home")
            away_name = match.get("away_team_name", "Away")
            home_safe = re.sub(r"[^a-zA-Z0-9]", "_", home_name)
            away_safe = re.sub(r"[^a-zA-Z0-9]", "_", away_name)
            match_date = kickoff.strftime("%Y_%m_%d")
            match_label = f"{match_date}_{home_safe}_vs_{away_safe}_{match_id}"

            active_uncrawled.append(
                {
                    "match_id": match_id,
                    "target_time": target_time,
                    "task_name": match_label,
                    "kickoff": kickoff,
                    "season": match.get("season"),
                    "league_slug": match.get("league_slug"),
                }
            )

    active_uncrawled.sort(key=lambda x: x["kickoff"])
    return active_uncrawled
