import os
import json
import logging
from typing import Any, List

logger = logging.getLogger(__name__)

def _get_fs_and_path(path: str):
    path = path.replace("\\", "/")
    if path.startswith("s3://"):
        import s3fs
        from src.config import S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
        fs = s3fs.S3FileSystem(
            client_kwargs={
                "endpoint_url": S3_ENDPOINT,
                "aws_access_key_id": S3_ACCESS_KEY_ID,
                "aws_secret_access_key": S3_SECRET_ACCESS_KEY
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