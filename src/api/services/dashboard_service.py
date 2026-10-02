from typing import Optional
from src.api.repositories.dashboard_repository import DashboardRepository

class DashboardService:
    def __init__(self, repo: DashboardRepository):
        self.repo = repo
        
    def get_dashboard_stats(self, league: Optional[str] = None, from_season: Optional[str] = None, to_season: Optional[str] = None) -> dict:
        raw = self.repo.get_dashboard_stats(league, from_season, to_season)
        
        played = raw['played_with_score']
        hw_pct = round((raw['home_wins'] / played * 100), 1) if played else 0
        aw_pct = round((raw['away_wins'] / played * 100), 1) if played else 0
        dr_pct = round((raw['draws'] / played * 100), 1) if played else 0
        
        mg_team = raw['most_goals_team']
        mw_team = raw['most_wins_team']
        
        return {
            'overview': {
                'total_matches': raw['total_matches'],
                'total_teams': raw['total_teams'],
                'coverage_start': raw['coverage_start'],
                'coverage_end': raw['coverage_end'],
                'total_goals': raw['total_goals'],
                'avg_goals': round(raw['avg_goals'], 2)
            },
            'outcomes': {
                'home_wins': raw['home_wins'],
                'home_wins_pct': hw_pct,
                'away_wins': raw['away_wins'],
                'away_wins_pct': aw_pct,
                'draws': raw['draws'],
                'draws_pct': dr_pct,
                'total_played': played
            },
            'dominance': {
                'most_goals': {
                    'team': mg_team[0] if mg_team else None,
                    'goals': mg_team[1] if mg_team else 0
                },
                'most_wins': {
                    'team': mw_team[0] if mw_team else None,
                    'wins': mw_team[1] if mw_team else 0
                }
            },
            'biggest_wins': [
                {
                    'season': row[0],
                    'home': row[1],
                    'away': row[2],
                    'home_score': row[3],
                    'away_score': row[4],
                    'goal_diff': row[5]
                } for row in raw['biggest_wins']
            ],
            'highest_scoring': [
                {
                    'season': row[0],
                    'home': row[1],
                    'away': row[2],
                    'home_score': row[3],
                    'away_score': row[4],
                    'total_goals': row[5]
                } for row in raw['highest_scoring']
            ]
        }