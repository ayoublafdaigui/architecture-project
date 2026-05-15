"""Hourly batch scraping DAG for MediaPulse."""

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
    dag_id="dag_batch_scrape",
    description="Scrape configured news sources every hour and ingest raw articles.",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2026, 5, 8),
    schedule="0 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["mediapulse", "scraping", "bronze", "kafka"],
) as dag:
    scrape_sources = BashOperator(
        task_id="scrape_sources_to_bronze_and_kafka",
        bash_command="cd /opt && python -m mediapulse.ingestion.run_batch_scrape",
        env={"PYTHONPATH": "/opt"},
        append_env=True,
    )

    trigger_bronze_to_silver = TriggerDagRunOperator(
        task_id="trigger_bronze_to_silver",
        trigger_dag_id="dag_bronze_to_silver",
        wait_for_completion=False,
    )

    scrape_sources >> trigger_bronze_to_silver
