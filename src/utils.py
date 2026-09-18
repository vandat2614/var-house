import os
import json
import logging
import re
from datetime import datetime, timedelta, timezone
import dateutil.parser
from src.config import CRAWL_CURRENT_SEASON, TRANSFORMED_DIR

from typing import Any, List

logger = logging.getLogger(__name__)

def _get_fs_and_path(path: str):
    path = path.replace("\\", "/")
    if path.startswith("s3://"):
        import s3fs
        from src.config import R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
        fs = s3fs.S3FileSystem(
            client_kwargs={
                "endpoint_url": R2_ENDPOINT,
                "aws_access_key_id": R2_ACCESS_KEY_ID,
                "aws_secret_access_key": R2_SECRET_ACCESS_KEY
            }
        )
        # s3fs expects path without s3:// prefix for some operations, but open() supports it.
        return fs, path
    return None, path

def save_json(data: Any, path: str) -> None:
    """Persist data as JSON to local path or Cloudflare R2."""
    fs, path = _get_fs_and_path(path)
    if fs:
        with fs.open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path: str) -> Any:
    """Load and return JSON from local path or Cloudflare R2."""
    fs, path = _get_fs_and_path(path)
    if fs:
        with fs.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

def file_exists(path: str) -> bool:
    """Check if a file exists locally or on R2."""
    fs, path = _get_fs_and_path(path)
    if fs:
        return fs.exists(path)
    return os.path.exists(path)

def list_dir(path: str) -> List[str]:
    """List files/directories in a path. Returns base names."""
    fs, clean_path = _get_fs_and_path(path)
    if fs:
        try:
            items = fs.ls(clean_path)
            # fs.ls returns full paths like 'bucket/data/raw/matches'
            return [os.path.basename(item) for item in items]
        except FileNotFoundError:
            return []
    else:
        if not os.path.exists(path):
            return []
        return os.listdir(path)

def get_season_safe(season: str) -> str:
    """Convert season string like '2023/2024' to a safe folder name '2023_2024'."""
    return season.replace('/', '_').replace('-', '_')

def is_match_crawled(match_id: str) -> bool:
    season_safe = get_season_safe(CRAWL_CURRENT_SEASON)
    season_dir = os.path.join(TRANSFORMED_DIR, "match-details", season_safe).replace("\\", "/")

    if not file_exists(season_dir):
        return False

    for _l_dir in list_dir(season_dir):
        league_dir = os.path.join(season_dir, _l_dir).replace("\\", "/")
        if file_exists(os.path.join(league_dir, f"{match_id}.json").replace("\\", "/")):
            return True
    return False

def get_fixtures():
    season_safe = get_season_safe(CRAWL_CURRENT_SEASON)
    season_path = os.path.join(TRANSFORMED_DIR, "fixtures", season_safe).replace("\\", "/")
    all_fixtures = []

    if not file_exists(season_path):
        return all_fixtures

    for filename in list_dir(season_path):
        if not filename.endswith("_matches.json"):
            continue
        file_path = os.path.join(season_path, filename).replace("\\", "/")
        try:
            data = load_json(file_path)
            all_fixtures.extend(data)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to parse {filename}: {e}")

    return all_fixtures

def get_pending_matches_to_crawl() -> list:
    fixtures = get_fixtures()
    pending_matches = []
    now_utc = datetime.now(timezone.utc)

    for match in fixtures:
        match_id = str(match.get("match_id", ""))
        utc_str = match.get("kickoff_utc", "")
        if not match_id or not utc_str:
            continue

        kickoff = dateutil.parser.parse(utc_str)
        target_time = kickoff + timedelta(hours=2)

        if target_time <= now_utc and not is_match_crawled(match_id):
            home_name = match.get("home_team_name", "Home")
            away_name = match.get("away_team_name", "Away")
            home_safe = re.sub(r"[^a-zA-Z0-9]", "_", home_name)
            away_safe = re.sub(r"[^a-zA-Z0-9]", "_", away_name)
            match_date = kickoff.strftime("%Y_%m_%d")
            match_label = f"{match_date}_{home_safe}_vs_{away_safe}_{match_id}"

            pending_matches.append({
                "match_id": match_id,
                "target_time": target_time,
                "task_name": match_label,
                "kickoff": kickoff,
                "season": match.get("season"),
                "league_slug": match.get("league_slug"),
            })

    pending_matches.sort(key=lambda x: x["kickoff"])
    return pending_matches
