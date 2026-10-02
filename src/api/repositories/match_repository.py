"""
Repository Layer: Data Access via DuckDB + PyIceberg.

Responsibilities:
- Open Iceberg tables via PyIceberg catalog.
- Run analytical SQL queries using DuckDB on PyArrow data.
- Return raw list[dict] — no business logic here.
"""

import logging
import time
from typing import Optional

import duckdb
from pyiceberg.catalog import Catalog

logger = logging.getLogger(__name__)

_TRANSIENT_ERRORS = (
    "Unexpected end of stream",
    "end of stream",
    "Connection reset",
    "timed out",
    "branch main has changed",
)

def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(e.lower() in msg for e in _TRANSIENT_ERRORS)


_ARROW_CACHE_TTL = 1800  # 30 minutes caching for PyArrow tables in memory
_arrow_cache = {}

def _table_to_arrow(catalog: Catalog, namespace: str, table_name: str, max_retries: int = 4):
    """
    Load an Iceberg table as a PyArrow dataset.
    Caches the PyArrow table in memory to avoid S3 re-downloads on every API request.
    Retries on transient errors (e.g. concurrent write causing 'Unexpected end of stream').
    """
    key = f"{namespace}.{table_name}"
    now = time.monotonic()
    
    if key in _arrow_cache:
        cached_arrow, created_at = _arrow_cache[key]
        if now - created_at < _ARROW_CACHE_TTL:
            return cached_arrow

    for attempt in range(1, max_retries + 1):
        try:
            table = catalog.load_table(f"{namespace}.{table_name}")
            arrow_table = table.scan().to_arrow()
            _arrow_cache[key] = (arrow_table, now)
            return arrow_table
        except Exception as e:
            if _is_transient(e) and attempt < max_retries:
                wait = 2 ** attempt  # 2, 4, 8 seconds
                logger.warning(
                    "Transient error loading %s.%s (attempt %d/%d): %s - retrying in %ds",
                    namespace, table_name, attempt, max_retries, e, wait
                )
                time.sleep(wait)
            else:
                logger.warning("Could not load table %s.%s: %s", namespace, table_name, e)
                return None
    return None
    return None




def warm_arrow_cache(catalog: Catalog):
    """Pre-load dim_match into the in-process Arrow cache at startup."""
    import logging
    _log = logging.getLogger(__name__)
    _log.info("Warming up Arrow cache for football.dim_match ...")
    result = _table_to_arrow(catalog, "football", "dim_match")
    if result is not None:
        _log.info("Arrow cache warm — %d rows loaded.", result.num_rows)
    else:
        _log.warning("Arrow cache warm-up failed.")
class MatchRepository:
    def __init__(self, catalog: Catalog, season: str = "2026-2027"):
        self._catalog = catalog
        self._dim_ns = "football"
        self._fact_ns = f"football_{season.replace('-', '_').replace('/', '_')}"

    def _get_dim_match_arrow(self):
        return _table_to_arrow(self._catalog, self._dim_ns, "dim_match")

    def _get_fact_events_arrow(self):
        return _table_to_arrow(self._catalog, self._fact_ns, "fact_event")

    def _get_fact_lineup_arrow(self):
        return _table_to_arrow(self._catalog, self._fact_ns, "fact_lineup")

    def _get_fact_stats_arrow(self):
        return _table_to_arrow(self._catalog, self._fact_ns, "fact_stats")

    def get_matches(
        self,
        league_slug: Optional[str] = None,
        team_id: Optional[str] = None,
        status: Optional[str] = None,
        round: Optional[str] = None,
        season: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[dict]]:
        """Return (total_count, paginated list of match dicts)."""
        arrow = self._get_dim_match_arrow()
        if arrow is None:
            return 0, []

        con = duckdb.connect()
        con.register("dim_match", arrow)

        where_clauses = []
        if league_slug:
            where_clauses.append(f"league_slug = '{league_slug}'")
        if team_id:
            where_clauses.append(f"(home_team_id = '{team_id}' OR away_team_id = '{team_id}')")
        if status:
            where_clauses.append(f"status = '{status}'")
        if round is not None:
            where_clauses.append(f"round = '{round}'")
        if season:
            where_clauses.append(f"season = '{season.replace('/', '-')}'")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        total = con.execute(f"SELECT COUNT(*) FROM dim_match {where_sql}").fetchone()[0]
        rows = con.execute(
            f"""SELECT * FROM dim_match {where_sql}
                ORDER BY kickoff_utc DESC
                LIMIT {limit} OFFSET {offset}"""
        ).fetchdf().replace({float("nan"): None}).to_dict(orient="records")

        con.close()
        return total, rows

    def get_seasons(self, league_slug: Optional[str] = None) -> list[str]:
        """Return distinct seasons available in dim_match, sorted newest-first."""
        arrow = self._get_dim_match_arrow()
        if arrow is None:
            return []

        con = duckdb.connect()
        con.register("dim_match", arrow)

        where_sql = f"WHERE league_slug = '{league_slug}'" if league_slug else ""
        rows = con.execute(
            f"SELECT DISTINCT season FROM dim_match {where_sql} ORDER BY season DESC"
        ).fetchdf()
        con.close()
        return rows["season"].tolist()

    def get_teams(self, season: Optional[str] = None, league_slug: Optional[str] = None) -> list[dict]:
        arrow = self._get_dim_match_arrow()
        if arrow is None:
            return []
            
        import duckdb
        con = duckdb.connect()
        con.register("dim_match", arrow)
        
        where_sql = "WHERE 1=1"
        if season:
            where_sql += f" AND season = '{season.replace('/', '-')}'"
        if league_slug:
            where_sql += f" AND league_slug = '{league_slug}'"
            
        # Get unique teams with their most frequent domestic league
        # Domestic leagues = exclude European competitions
        EUROPEAN = ('champions_league', 'europa_league', 'conference_league')
        european_list = ', '.join(f"'{s}'" for s in EUROPEAN)
        
        query = f"""
            WITH all_teams AS (
                SELECT home_team_id as team_id, home_team_name as team_name, league_slug FROM dim_match {where_sql}
                UNION ALL
                SELECT away_team_id as team_id, away_team_name as team_name, league_slug FROM dim_match {where_sql}
            ),
            domestic_counts AS (
                SELECT team_id, team_name, league_slug,
                       COUNT(*) as cnt,
                       ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY COUNT(*) DESC) as rn
                FROM all_teams
                WHERE league_slug NOT IN ({european_list})
                GROUP BY team_id, team_name, league_slug
            ),
            domestic_league AS (
                SELECT team_id, league_slug as domestic_league
                FROM domestic_counts
                WHERE rn = 1
            )
            SELECT DISTINCT t.team_id, t.team_name, COALESCE(d.domestic_league, 'other') as domestic_league
            FROM all_teams t
            LEFT JOIN domestic_league d ON t.team_id = d.team_id
            ORDER BY domestic_league, t.team_name
        """
        
        rows = con.execute(query).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()
        return rows

    def get_match_by_id(self, match_id: str) -> Optional[dict]:
        arrow = self._get_dim_match_arrow()
        if arrow is None:
            return None

        con = duckdb.connect()
        con.register("dim_match", arrow)
        rows = con.execute(
            "SELECT * FROM dim_match WHERE match_id = ? LIMIT 1", [match_id]
        ).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()

        return rows[0] if rows else None

    def get_match_events(self, match_id: str) -> list[dict]:
        arrow = self._get_fact_events_arrow()
        if arrow is None:
            return []

        con = duckdb.connect()
        con.register("fact_event", arrow)
        rows = con.execute(
            "SELECT * FROM fact_event WHERE match_id = ? ORDER BY minute ASC NULLS LAST",
            [match_id],
        ).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()
        return rows

    def get_match_lineup(self, match_id: str) -> list[dict]:
        arrow = self._get_fact_lineup_arrow()
        if arrow is None:
            return []

        con = duckdb.connect()
        con.register("fact_lineup", arrow)
        rows = con.execute(
            """SELECT * FROM fact_lineup
               WHERE match_id = ?
               ORDER BY team_id, is_starter DESC, shirt_number ASC""",
            [match_id],
        ).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()
        return rows

    def get_match_stats(self, match_id: str) -> list[dict]:
        arrow = self._get_fact_stats_arrow()
        if arrow is None:
            return []

        con = duckdb.connect()
        con.register("fact_stats", arrow)
        rows = con.execute(
            "SELECT * FROM fact_stats WHERE match_id = ? ORDER BY period, group, stat_key",
            [match_id],
        ).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()
        return rows

    def get_h2h(self, team1_id: int, team2_id: Optional[int] = None, vs_league_slug: Optional[str] = None, limit: int = 20) -> list[dict]:
        """Return last N matches of team1 against team2 OR against any team whose domestic league is vs_league_slug."""
        arrow = self._get_dim_match_arrow()
        if arrow is None:
            return []

        con = duckdb.connect()
        con.register("dim_match", arrow)
        
        EUROPEAN = ('champions_league', 'europa_league', 'conference_league')
        european_list = ', '.join(f"'{s}'" for s in EUROPEAN)
        
        if team2_id:
            query = f"""
                SELECT * FROM dim_match
                WHERE
                  (home_team_id = {team1_id} AND away_team_id = {team2_id})
                  OR (home_team_id = {team2_id} AND away_team_id = {team1_id})
                ORDER BY kickoff_utc DESC
                LIMIT {limit}
            """
        elif vs_league_slug:
            # Find teams whose primary domestic league is vs_league_slug
            query = f"""
                WITH all_teams AS (
                    SELECT home_team_id as team_id, league_slug FROM dim_match
                    UNION ALL
                    SELECT away_team_id as team_id, league_slug FROM dim_match
                ),
                domestic_counts AS (
                    SELECT team_id, league_slug,
                           COUNT(*) as cnt,
                           ROW_NUMBER() OVER (PARTITION BY team_id ORDER BY COUNT(*) DESC) as rn
                    FROM all_teams
                    WHERE league_slug NOT IN ({european_list})
                    GROUP BY team_id, league_slug
                ),
                league_teams AS (
                    SELECT team_id
                    FROM domestic_counts
                    WHERE rn = 1 AND league_slug = '{vs_league_slug}'
                )
                SELECT m.* 
                FROM dim_match m
                WHERE 
                  (m.home_team_id = {team1_id} AND m.away_team_id IN (SELECT team_id FROM league_teams))
                  OR (m.away_team_id = {team1_id} AND m.home_team_id IN (SELECT team_id FROM league_teams))
                ORDER BY m.kickoff_utc DESC
                LIMIT {limit}
            """
        else:
            query = f"""
                SELECT * FROM dim_match
                WHERE home_team_id = {team1_id} OR away_team_id = {team1_id}
                ORDER BY kickoff_utc DESC
                LIMIT {limit}
            """
            
        rows = con.execute(query).fetchdf().replace({float("nan"): None}).to_dict(orient="records")
        con.close()
        return rows

    def get_rounds(self, league_slug: str, season: Optional[str] = None) -> list[str]:
        arrow_tbl = _table_to_arrow(self._catalog, "football", "dim_match")
        con = duckdb.connect()
        con.register("tbl", arrow_tbl)
        
        where_clauses = [f"league_slug = '{league_slug}'"]
        if season:
            where_clauses.append(f"season = '{season}'")
            
        q = f"SELECT DISTINCT round FROM tbl WHERE {' AND '.join(where_clauses)} AND round IS NOT NULL"
        df = con.execute(q).df()
        
        rounds = [r for r in df['round'].tolist() if r and str(r).strip()]
        
        # Sort rounds safely (integers first, then strings)
        def sort_key(r):
            try:
                return (0, int(r))
            except:
                return (1, r)
        
        rounds.sort(key=sort_key)
        return [str(r) for r in rounds]
