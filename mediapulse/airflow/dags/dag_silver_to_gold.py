"""Six-hour Silver to Gold aggregation DAG for MediaPulse."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

DEFAULT_ARGS = {
    "owner": "mediapulse",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="dag_silver_to_gold",
    description="Aggregate Silver articles into Gold analytical tables every 6 hours.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 8),
    schedule="0 */6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["mediapulse", "gold", "analytics"],
) as dag:
    aggregate_silver_to_gold = BashOperator(
        task_id="silver_to_gold",
        bash_command="cd /opt && python -m mediapulse.transform.silver_to_gold",
        env={"PYTHONPATH": "/opt"},
        append_env=True,
    )

    trigger_gold_quality = TriggerDagRunOperator(
        task_id="trigger_gold_quality",
        trigger_dag_id="dag_data_quality",
        conf={"layer": "gold"},
        wait_for_completion=False,
    )

    aggregate_silver_to_gold >> trigger_gold_quality
