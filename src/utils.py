import os
import json
from typing import Any

def save_json(data: Any, path: str) -> None:
    """Persist data as JSON to local path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json(path: str) -> Any:
    """Load and return JSON from local path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def get_season_safe(season: str) -> str:
    """Convert season string like '2023/2024' to a safe folder name '2023_2024'."""
    return season.replace('/', '_').replace('-', '_')
