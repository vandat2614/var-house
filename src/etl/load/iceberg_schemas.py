"""
PyIceberg Schema definitions corresponding to the SQLModel schemas.
"""
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType, IntegerType, DoubleType, BooleanType

DIM_MATCH_SCHEMA = Schema(
    NestedField(field_id=1, name="match_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="league_slug", field_type=StringType(), required=True),
    NestedField(field_id=3, name="season", field_type=StringType(), required=True),
    NestedField(field_id=4, name="round", field_type=LongType(), required=True),
    NestedField(field_id=5, name="home_team_id", field_type=StringType(), required=True),
    NestedField(field_id=6, name="home_team_name", field_type=StringType(), required=True),
    NestedField(field_id=7, name="away_team_id", field_type=StringType(), required=True),
    NestedField(field_id=8, name="away_team_name", field_type=StringType(), required=True),
    NestedField(field_id=9, name="kickoff_utc", field_type=StringType(), required=True),
    NestedField(field_id=10, name="status", field_type=StringType(), required=True),
    NestedField(field_id=11, name="home_score", field_type=LongType(), required=False),
    NestedField(field_id=12, name="away_score", field_type=LongType(), required=False),
)

DIM_TEAM_SCHEMA = Schema(
    NestedField(field_id=1, name="team_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="team_name", field_type=StringType(), required=True),
    NestedField(field_id=3, name="short_name", field_type=StringType(), required=False),
)

DIM_PLAYER_SCHEMA = Schema(
    NestedField(field_id=1, name="player_id", field_type=StringType(), required=True),
    NestedField(field_id=2, name="player_name", field_type=StringType(), required=True),
    NestedField(field_id=3, name="current_team_id", field_type=StringType(), required=False),
    NestedField(field_id=4, name="current_team_name", field_type=StringType(), required=False),
    NestedField(field_id=5, name="age", field_type=LongType(), required=False),
    NestedField(field_id=6, name="country", field_type=StringType(), required=False),
)

FACT_EVENT_SCHEMA = Schema(
    NestedField(field_id=1, name="id", field_type=LongType(), required=False),
    NestedField(field_id=2, name="match_id", field_type=StringType(), required=True),
    NestedField(field_id=3, name="event_type", field_type=StringType(), required=True),
    NestedField(field_id=4, name="minute", field_type=LongType(), required=False),
    NestedField(field_id=5, name="is_home", field_type=BooleanType(), required=False),
    NestedField(field_id=6, name="player_id", field_type=StringType(), required=False),
    NestedField(field_id=7, name="player_name", field_type=StringType(), required=False),
    NestedField(field_id=8, name="assist_player_id", field_type=StringType(), required=False),
    NestedField(field_id=9, name="assist_player_name", field_type=StringType(), required=False),
    NestedField(field_id=10, name="is_own_goal", field_type=BooleanType(), required=False),
    NestedField(field_id=11, name="card_type", field_type=StringType(), required=False),
    NestedField(field_id=12, name="player_in_id", field_type=StringType(), required=False),
    NestedField(field_id=13, name="player_in_name", field_type=StringType(), required=False),
    NestedField(field_id=14, name="player_out_id", field_type=StringType(), required=False),
    NestedField(field_id=15, name="player_out_name", field_type=StringType(), required=False),
    NestedField(field_id=16, name="added_time", field_type=LongType(), required=False),
    NestedField(field_id=17, name="new_score_home", field_type=LongType(), required=False),
    NestedField(field_id=18, name="new_score_away", field_type=LongType(), required=False),
)

FACT_LINEUP_SCHEMA = Schema(
    NestedField(field_id=1, name="id", field_type=LongType(), required=False),
    NestedField(field_id=2, name="match_id", field_type=StringType(), required=True),
    NestedField(field_id=3, name="team_id", field_type=StringType(), required=True),
    NestedField(field_id=4, name="team_name", field_type=StringType(), required=True),
    NestedField(field_id=5, name="player_id", field_type=StringType(), required=True),
    NestedField(field_id=6, name="player_name", field_type=StringType(), required=True),
    NestedField(field_id=7, name="shirt_number", field_type=StringType(), required=False),
    NestedField(field_id=8, name="position_id", field_type=StringType(), required=False),
    NestedField(field_id=9, name="is_starter", field_type=BooleanType(), required=True),
    NestedField(field_id=10, name="rating", field_type=DoubleType(), required=False),
    NestedField(field_id=11, name="age", field_type=LongType(), required=False),
    NestedField(field_id=12, name="country", field_type=StringType(), required=False),
)

# We can skip FACT_STATS and FACT_PLAYER_STATS schemas since they are FROZEN for now.
