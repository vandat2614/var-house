import json
import os

_config_path = os.path.join(os.path.dirname(__file__), "llm_config.json")

with open(_config_path, "r", encoding="utf-8") as f:
    LLM_CONFIG = json.load(f)
