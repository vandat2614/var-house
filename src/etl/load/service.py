import logging
from typing import Any, Dict

from src.schemas.match_schemas import MatchDetailBundle
from src.etl.load.iceberg_loader import load_match_detail_iceberg

logger = logging.getLogger(__name__)

class MatchLoadService:
    """
    Service class responsible for validating and loading match facts into the Data Lake.
    """

    def process_and_load(self, match_id: str, payload: Dict[str, Any]) -> None:
        """
        Validates the payload against Pydantic schemas and loads it into Iceberg.
        """
        team_names = list(set(p.get("team_name") for p in payload.get("lineup", []) if p.get("team_name")))
        team_str = " vs ".join(team_names) if team_names else "Unknown Teams"
        
        logger.info(f"Received clean match {match_id} ({team_str}) from Kafka. Loading to DB...")

        # Parse the dict into typed Pydantic models for schema validation
        bundle = MatchDetailBundle.model_validate(payload)

        # Idempotently load into Iceberg
        load_match_detail_iceberg(match_id=match_id, bundle=bundle)
        logger.info(f"Successfully loaded match {match_id} ({team_str}) into Database.")
