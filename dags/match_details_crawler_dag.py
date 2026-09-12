"""
Match Details Crawler DAG

This DAG orchestrates the extraction of football match details.
It uses dynamic DateTimeSensors to wait for matches to finish (kickoff + 2 hours).
"""

import logging
from datetime import timedelta

try:
    from airflow import DAG
    from airflow.operators.empty import EmptyOperator
    from airflow.operators.python import PythonOperator
    from airflow.sensors.date_time import DateTimeSensor
    from airflow.utils.dates import days_ago
except ImportError:
    logging.getLogger(__name__).warning(
        "Apache Airflow is not installed. This file is for review purposes."
    )

from dags.tasks.match_tasks import crawl_match_task
from dags.utils.fixture_utils import get_active_matches

default_args = {
    "owner": "data_engineer",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

try:
    with DAG(
        dag_id="match_details_crawler",
        default_args=default_args,
        description="Daily DAG using DateTimeSensors for active window",
        schedule_interval="@daily",
        start_date=days_ago(1),
        catchup=False,
        tags=["football", "etl", "dynamic"],
    ) as dag:
        # Dynamic Sensors for Active Window
        active_matches = get_active_matches()

        if not active_matches:
            no_active_task = EmptyOperator(task_id="no_active_matches_today")
        else:
            for match in active_matches:
                match_id = match["match_id"]
                target_time = match["target_time"]
                task_name = match.get("task_name", match_id)

                wait_for_kickoff = DateTimeSensor(
                    task_id=f"timer_{task_name}",
                    target_time=target_time,
                    mode="reschedule",
                    poke_interval=60 * 5,
                )

                crawl_task = PythonOperator(
                    task_id=f"extract_{task_name}",
                    python_callable=crawl_match_task,
                    op_kwargs={"match_id": match_id, "season": match.get("season"), "league_slug": match.get("league_slug")},
                )

                wait_for_kickoff >> crawl_task

except NameError:
    pass
