import duckdb
from typing import Optional
from pyiceberg.catalog import Catalog
from src.api.repositories.match_repository import _table_to_arrow

class DashboardRepository:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def get_dashboard_stats(self, league: Optional[str] = None, from_season: Optional[str] = None, to_season: Optional[str] = None) -> dict:
        dim_match = _table_to_arrow(self.catalog, 'football', 'dim_match')
        if dim_match is None:
            return {}
            
        dim_team = _table_to_arrow(self.catalog, 'football', 'dim_team')
        
        con = duckdb.connect()
        con.register('dim_match', dim_match)
        if dim_team is not None:
            con.register('dim_team', dim_team)
        
        # Build dynamic WHERE clause
        where_clauses = []
        if league:
            where_clauses.append(f"league_slug = '{league}'")
        if from_season:
            where_clauses.append(f"season >= '{from_season}'")
        if to_season:
            where_clauses.append(f"season <= '{to_season}'")
            
        where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        win_where = where_str + " AND home_score IS NOT NULL" if where_str else "WHERE home_score IS NOT NULL"
        
        stats = {}
        
        # Total matches
        stats['total_matches'] = con.execute(f"SELECT COUNT(*) FROM dim_match {where_str}").fetchone()[0]
        
        # Total teams
        if where_str or dim_team is None:
            stats['total_teams'] = con.execute(f"""
                SELECT COUNT(DISTINCT team_id) 
                FROM (
                    SELECT home_team_id as team_id FROM dim_match {where_str}
                    UNION
                    SELECT away_team_id as team_id FROM dim_match {where_str}
                )
            """).fetchone()[0]
        else:
            stats['total_teams'] = con.execute("SELECT COUNT(*) FROM dim_team").fetchone()[0]
        
        # Goals Stats
        goals = con.execute(f"""
            SELECT SUM(home_score + away_score), AVG(home_score + away_score)
            FROM dim_match
            {win_where}
        """).fetchone()
        stats['total_goals'] = goals[0] or 0
        stats['avg_goals'] = goals[1] or 0.0

        # Match Outcomes
        outcomes = con.execute(f"""
            SELECT 
                SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END),
                SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END),
                SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END),
                COUNT(*)
            FROM dim_match
            {win_where}
        """).fetchone()
        stats['home_wins'] = outcomes[0] or 0
        stats['away_wins'] = outcomes[1] or 0
        stats['draws'] = outcomes[2] or 0
        stats['played_with_score'] = outcomes[3] or 0
        
        # Most Goals Team
        stats['most_goals_team'] = con.execute(f"""
            SELECT team_name, SUM(goals) as total_goals
            FROM (
                SELECT home_team_name as team_name, home_score as goals FROM dim_match {win_where}
                UNION ALL
                SELECT away_team_name as team_name, away_score as goals FROM dim_match {win_where}
            )
            GROUP BY team_name
            ORDER BY total_goals DESC
            LIMIT 1
        """).fetchone()
        
        # Most Wins Team
        stats['most_wins_team'] = con.execute(f"""
            SELECT team_name, COUNT(*) as wins
            FROM (
                SELECT home_team_name as team_name FROM dim_match 
                {("WHERE " + " AND ".join(where_clauses + ["home_score IS NOT NULL AND home_score > away_score"])) if where_clauses else "WHERE home_score IS NOT NULL AND home_score > away_score"}
                UNION ALL
                SELECT away_team_name as team_name FROM dim_match 
                {("WHERE " + " AND ".join(where_clauses + ["home_score IS NOT NULL AND away_score > home_score"])) if where_clauses else "WHERE home_score IS NOT NULL AND away_score > home_score"}
            )
            GROUP BY team_name
            ORDER BY wins DESC
            LIMIT 1
        """).fetchone()

        # Matches by league
        stats['matches_by_league'] = con.execute(f"""
            SELECT league_slug, COUNT(*) as count 
            FROM dim_match 
            {where_str}
            GROUP BY league_slug 
            ORDER BY count DESC
        """).fetchall()
        
        # Biggest wins
        stats['biggest_wins'] = con.execute(f"""
            SELECT season, home_team_name, away_team_name, home_score, away_score, ABS(home_score - away_score) as gd 
            FROM dim_match 
            {win_where} 
            ORDER BY gd DESC 
            LIMIT 5
        """).fetchall()
        
        # Highest scoring matches
        stats['highest_scoring'] = con.execute(f"""
            SELECT season, home_team_name, away_team_name, home_score, away_score, (home_score + away_score) as tg 
            FROM dim_match 
            {win_where} 
            ORDER BY tg DESC 
            LIMIT 5
        """).fetchall()
        
        # Data coverage
        cov = con.execute(f"""
            SELECT MIN(kickoff_utc), MAX(kickoff_utc) 
            FROM dim_match
            {where_str}
        """).fetchone()
        stats['coverage_start'] = cov[0]
        stats['coverage_end'] = cov[1]
        
        return stats