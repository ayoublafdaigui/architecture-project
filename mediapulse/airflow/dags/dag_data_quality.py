"""Triggered data quality DAG for MediaPulse transformations."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "mediapulse",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="dag_data_quality",
    description="Run layer-specific data quality checks and log to PostgreSQL.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 8),
    schedule=None,
    catchup=False,
    max_active_runs=4,
    tags=["mediapulse", "quality"],
) as dag:
    run_quality_checks = BashOperator(
        task_id="run_quality_checks",
        bash_command=(
            "cd /opt && python -m mediapulse.quality.data_quality "
            "--layer {{ dag_run.conf.get('layer', 'silver') if dag_run else 'silver' }}"
        ),
        env={"PYTHONPATH": "/opt"},
        append_env=True,
    )

    run_quality_checks
