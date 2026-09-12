import logging
from typing import List, Any
import pyarrow as pa
from pyiceberg.exceptions import TableAlreadyExistsError
from pyiceberg.expressions import In, EqualTo

from src.load.iceberg_catalog import get_catalog, get_namespace_for_season, ensure_namespace
from src.load.iceberg_schemas import (
    DIM_MATCH_SCHEMA, DIM_TEAM_SCHEMA, DIM_PLAYER_SCHEMA,
    FACT_EVENT_SCHEMA, FACT_LINEUP_SCHEMA
)
from src.schemas.match_schemas import MatchDetailBundle

logger = logging.getLogger(__name__)

def _ensure_table(table_name: str, schema, namespace: str = "football") -> Any:
    """Ensure the table exists in the given namespace and return the PyIceberg table object."""
    catalog = get_catalog()
    ensure_namespace(namespace)
    table_identifier = f"{namespace}.{table_name}"
    try:
        table = catalog.create_table(
            identifier=table_identifier,
            schema=schema,
            properties={"format-version": "2"}
        )
        logger.info(f"[Iceberg] Created table {table_identifier}")
    except TableAlreadyExistsError:
        table = catalog.load_table(table_identifier)
    return table

def _bulk_upsert_dimension_iceberg(table_name: str, models: List[Any], schema, primary_key: str, namespace: str = "football"):
    """
    Iceberg doesn't natively support MERGE INTO via simple Python API yet.
    We simulate UPSERT by Deleting existing keys, then Appending.
    """
    if not models:
        return
        
    table = _ensure_table(table_name, schema, namespace)
    
    # 1. Extract IDs to delete
    dicts = [m.model_dump() if hasattr(m, "model_dump") else m for m in models]
    ids_to_upsert = [str(d[primary_key]) for d in dicts]
    
    # 2. Delete existing records with these IDs (Iceberg v2 row-level delete)
    if ids_to_upsert:
        try:
            table.delete(In(term=primary_key, literals=ids_to_upsert))
        except Exception as e:
            logger.debug(f"[Iceberg] Delete on {table_name} skipped/failed: {e}")

    # 3. Append new data
    arrow_schema = schema.as_arrow()
    df = pa.Table.from_pylist(dicts, schema=arrow_schema)
    table.append(df)
    logger.info(f"[Iceberg] Upserted {len(models)} rows into {namespace}.{table_name}")


def _delete_existing_fact_records(match_id: str, namespace: str = "football"):
    """Delete all fact records for a specific match_id to ensure idempotency."""
    t_event = _ensure_table("fact_event", FACT_EVENT_SCHEMA, namespace)
    t_lineup = _ensure_table("fact_lineup", FACT_LINEUP_SCHEMA, namespace)
    
    try:
        t_event.delete(EqualTo(term="match_id", literal=match_id))
    except Exception:
        pass
        
    try:
        t_lineup.delete(EqualTo(term="match_id", literal=match_id))
    except Exception:
        pass

def _insert_fact_records(match_id: str, bundle: MatchDetailBundle, namespace: str = "football"):
    """Append new fact records to Iceberg tables."""
    if bundle.events:
        t_event = _ensure_table("fact_event", FACT_EVENT_SCHEMA, namespace)
        dicts = [e.model_dump() for e in bundle.events]
        df = pa.Table.from_pylist(dicts, schema=FACT_EVENT_SCHEMA.as_arrow())
        t_event.append(df)
        logger.info(f"[Iceberg] Appended {len(bundle.events)} events for match {match_id}")

    if bundle.lineup:
        t_lineup = _ensure_table("fact_lineup", FACT_LINEUP_SCHEMA, namespace)
        dicts = [l.model_dump() for l in bundle.lineup]
        df = pa.Table.from_pylist(dicts, schema=FACT_LINEUP_SCHEMA.as_arrow())
        t_lineup.append(df)
        logger.info(f"[Iceberg] Appended {len(bundle.lineup)} lineup records for match {match_id}")

def load_match_detail_iceberg(match_id: str, bundle: MatchDetailBundle) -> str:
    """
    Load a parsed MatchDetailBundle into Apache Iceberg Tables.
    
    The namespace is determined dynamically from the season field
    in the match info (e.g. "2026-2027" -> namespace "football_2026_2027").
    """
    # Determine namespace from the season in the bundle
    season = "unknown"
    if bundle.match and hasattr(bundle.match, "season"):
        season = bundle.match.season or "unknown"
    namespace = get_namespace_for_season(season)
    
    logger.info(f"--- Loading Match {match_id} into Iceberg namespace '{namespace}' ---")
    
    # 1. Upsert Dimensions
    if bundle.match:
        _bulk_upsert_dimension_iceberg("dim_match", [bundle.match], DIM_MATCH_SCHEMA, "match_id", namespace)
    if bundle.teams:
        _bulk_upsert_dimension_iceberg("dim_team", bundle.teams, DIM_TEAM_SCHEMA, "team_id", namespace)
    if bundle.players:
        _bulk_upsert_dimension_iceberg("dim_player", bundle.players, DIM_PLAYER_SCHEMA, "player_id", namespace)
        
    # 2. Delete existing Facts (Idempotency)
    _delete_existing_fact_records(match_id, namespace)
    
    # 3. Append new Facts
    _insert_fact_records(match_id, bundle, namespace)
    
    result_str = (f"Iceberg Load OK [{namespace}] - 1 match, {len(bundle.teams)} teams, {len(bundle.players)} players, "
                  f"{len(bundle.events)} events, {len(bundle.lineup)} lineups.")
    logger.info(result_str)
    return result_str

def load_dim_matches(matches: List[Any], db_path: str = None):
    """Fallback function name to load matches into Iceberg"""
    if not matches:
        return
    _bulk_upsert_dimension_iceberg("dim_match", matches, DIM_MATCH_SCHEMA, "match_id")

def load_dim_teams(teams: List[Any], db_path: str = None):
    """Fallback function name to load teams into Iceberg"""
    if not teams:
        return
    _bulk_upsert_dimension_iceberg("dim_team", teams, DIM_TEAM_SCHEMA, "team_id")
