"""Daily PostgreSQL warehouse load DAG for MediaPulse."""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

DEFAULT_ARGS = {
    "owner": "mediapulse",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="dag_load_warehouse",
    description="Load Silver article facts and Gold aggregates into PostgreSQL daily.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 8),
    schedule="0 0 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["mediapulse", "warehouse", "postgres"],
) as dag:
    load_warehouse = BashOperator(
        task_id="load_postgres_warehouse",
        bash_command="cd /opt && python -m mediapulse.warehouse.load_warehouse",
        env={"PYTHONPATH": "/opt"},
        append_env=True,
    )

    load_warehouse
