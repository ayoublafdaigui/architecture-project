"""Data quality checks and reporting for MediaPulse lake and warehouse layers."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from mediapulse.core.config import (
    MinioSettings,
    PostgresSettings,
    get_minio_settings,
    get_postgres_settings,
)
from mediapulse.core.logging import configure_logging
from mediapulse.transform.bronze_to_silver import QualityIssue, validate_silver_record

logger = logging.getLogger(__name__)

SILVER_RULES = {
    "title_not_empty",
    "published_at_not_null",
    "content_length_gt_100",
    "url_valid",
    "url_unique",
    "language_iso_639_1",
}


@dataclass(frozen=True)
class QualityCheckResult:
    """One quality check result ready for logging."""

    pipeline_step: str
    layer_name: str
    rule_name: str
    status: str
    severity: str = "error"
    failure_reason: str | None = None
    source: str | None = None
    article_url: str | None = None
    url_hash: str | None = None
    object_path: str | None = None


@dataclass(frozen=True)
class QualityRunSummary:
    """Aggregate quality run result."""

    checked: int
    passed: int
    failed: int
    run_id: str


class DataQualityRunner:
    """Run data quality checks over MediaPulse data lake objects."""

    def __init__(
        self,
        minio_settings: MinioSettings,
        postgres_settings: PostgresSettings | None = None,
    ) -> None:
        """Create a quality runner."""

        try:
            from minio import Minio

            self.minio_settings = minio_settings
            self.postgres_settings = postgres_settings
            self.bucket_name = minio_settings.bucket_name
            self.silver_prefix = minio_settings.silver_prefix.strip("/")
            self.gold_prefix = minio_settings.gold_prefix.strip("/")
            self.minio = Minio(
                endpoint=minio_settings.endpoint,
                access_key=minio_settings.access_key,
                secret_key=minio_settings.secret_key,
                secure=minio_settings.secure,
            )
        except Exception:
            logger.exception("Failed to initialize data quality runner")
            raise

    def run(self, layer: str = "silver", write_db: bool = True) -> QualityRunSummary:
        """Run quality checks for a layer and optionally persist the report."""

        try:
            run_id = str(uuid4())
            if layer == "silver":
                results = self.check_silver()
            elif layer == "gold":
                results = self.check_gold()
            else:
                raise ValueError(f"Unsupported quality layer: {layer}")

            if write_db:
                self.write_results(run_id, results)

            summary = QualityRunSummary(
                checked=len(results),
                passed=sum(1 for result in results if result.status == "passed"),
                failed=sum(1 for result in results if result.status == "failed"),
                run_id=run_id,
            )
            logger.info("Data quality run complete: %s", summary)
            return summary
        except Exception:
            logger.exception("Data quality run failed")
            raise

    def check_silver(self) -> list[QualityCheckResult]:
        """Run Silver article quality checks."""

        try:
            results: list[QualityCheckResult] = []
            seen_url_hashes: set[str] = set()
            for object_path, record in self.iter_json_objects(self.silver_prefix):
                if "/_rejected/" in object_path:
                    continue
                issues = validate_silver_record(record, seen_url_hashes=seen_url_hashes)
                failed_rules = {issue.rule_name: issue for issue in issues}
                for rule_name in SILVER_RULES:
                    issue = failed_rules.get(rule_name)
                    results.append(
                        QualityCheckResult(
                            pipeline_step="bronze_to_silver",
                            layer_name="silver",
                            rule_name=rule_name,
                            status="failed" if issue else "passed",
                            failure_reason=issue.message if issue else None,
                            source=str(record.get("source") or "") or None,
                            article_url=str(record.get("url") or "") or None,
                            url_hash=str(record.get("url_hash") or "") or None,
                            object_path=object_path,
                        )
                    )
                if not issues and record.get("url_hash"):
                    seen_url_hashes.add(str(record["url_hash"]))
            return results
        except Exception:
            logger.exception("Failed to check Silver data quality")
            raise

    def check_gold(self) -> list[QualityCheckResult]:
        """Check that required Gold tables exist and contain records."""

        try:
            required_tables = {
                "daily_article_counts",
                "top_keywords",
                "trending_topics",
                "articles_by_source_country",
            }
            results: list[QualityCheckResult] = []
            for table_name in required_tables:
                latest = self.read_latest_gold_table(table_name)
                passed = bool(latest and latest.get("record_count", 0) >= 0 and "records" in latest)
                results.append(
                    QualityCheckResult(
                        pipeline_step="silver_to_gold",
                        layer_name="gold",
                        rule_name=f"{table_name}_snapshot_exists",
                        status="passed" if passed else "failed",
                        failure_reason=None if passed else f"Missing Gold snapshot for {table_name}",
                        object_path=f"{self.gold_prefix}/table={table_name}",
                    )
                )
            return results
        except Exception:
            logger.exception("Failed to check Gold data quality")
            raise

    def iter_json_objects(self, prefix: str) -> list[tuple[str, dict[str, Any]]]:
        """Read JSON objects under a MinIO prefix."""

        try:
            records: list[tuple[str, dict[str, Any]]] = []
            for item in self.minio.list_objects(self.bucket_name, prefix=prefix, recursive=True):
                if not item.object_name or not item.object_name.endswith(".json"):
                    continue
                records.append((item.object_name, self.read_json_object(item.object_name)))
            return records
        except Exception:
            logger.exception("Failed to iterate JSON objects under prefix: %s", prefix)
            raise

    def read_latest_gold_table(self, table_name: str) -> dict[str, Any] | None:
        """Read the latest Gold table snapshot by table name."""

        try:
            prefix = f"{self.gold_prefix}/table={table_name}"
            object_names = [
                item.object_name
                for item in self.minio.list_objects(self.bucket_name, prefix=prefix, recursive=True)
                if item.object_name and item.object_name.endswith(".json")
            ]
            if not object_names:
                return None
            return self.read_json_object(sorted(object_names)[-1])
        except Exception:
            logger.exception("Failed to read latest Gold quality target: %s", table_name)
            raise

    def read_json_object(self, object_name: str) -> dict[str, Any]:
        """Read a JSON object from MinIO."""

        response = None
        try:
            response = self.minio.get_object(self.bucket_name, object_name)
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object in {object_name}")
            return payload
        except Exception:
            logger.exception("Failed to read JSON object for quality checks: %s", object_name)
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def write_results(self, run_id: str, results: list[QualityCheckResult]) -> None:
        """Persist quality results to the warehouse quality_report table."""

        try:
            if self.postgres_settings is None:
                raise ValueError("PostgreSQL settings are required when write_db=True")
            import psycopg

            with psycopg.connect(self.postgres_settings.dsn) as connection:
                for result in results:
                    source_key = self.lookup_source_key(connection, result.source)
                    connection.execute(
                        """
                        INSERT INTO warehouse.quality_report (
                            run_id, pipeline_step, layer_name, source_key, article_url,
                            url_hash, rule_name, severity, status, failure_reason,
                            object_path, detected_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            result.pipeline_step,
                            result.layer_name,
                            source_key,
                            result.article_url,
                            result.url_hash,
                            result.rule_name,
                            result.severity,
                            result.status,
                            result.failure_reason,
                            result.object_path,
                            datetime.now(timezone.utc),
                        ),
                    )
                connection.commit()
        except Exception:
            logger.exception("Failed to persist quality results")
            raise

    @staticmethod
    def lookup_source_key(connection: Any, source_name: str | None) -> int | None:
        """Resolve a source name to dim_source.source_key."""

        try:
            if not source_name:
                return None
            row = connection.execute(
                "SELECT source_key FROM warehouse.dim_source WHERE source_name = %s",
                (source_name,),
            ).fetchone()
            return int(row[0]) if row else None
        except Exception:
            logger.exception("Failed to look up source key for quality report")
            raise


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Run MediaPulse data quality checks")
        parser.add_argument("--layer", choices=["silver", "gold"], default="silver")
        parser.add_argument("--no-write-db", action="store_true")
        return parser
    except Exception:
        logger.exception("Failed to build data quality argument parser")
        raise


def main() -> None:
    """Run the data quality checker from the command line."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        runner = DataQualityRunner(
            minio_settings=get_minio_settings(),
            postgres_settings=get_postgres_settings(),
        )
        runner.run(layer=args.layer, write_db=not args.no_write_db)
    except Exception:
        logger.exception("Data quality CLI failed")
        raise


if __name__ == "__main__":
    main()
