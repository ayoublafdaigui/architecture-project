"""Triggered Bronze to Silver transformation DAG for MediaPulse."""

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
    dag_id="dag_bronze_to_silver",
    description="Clean, validate, and deduplicate Bronze articles into Silver.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 8),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["mediapulse", "silver", "quality"],
) as dag:
    transform_bronze_to_silver = BashOperator(
        task_id="bronze_to_silver",
        bash_command="cd /opt && python -m mediapulse.transform.bronze_to_silver",
        env={"PYTHONPATH": "/opt"},
        append_env=True,
    )

    trigger_silver_quality = TriggerDagRunOperator(
        task_id="trigger_silver_quality",
        trigger_dag_id="dag_data_quality",
        conf={"layer": "silver"},
        wait_for_completion=False,
    )

    transform_bronze_to_silver >> trigger_silver_quality
