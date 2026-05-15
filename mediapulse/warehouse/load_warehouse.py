"""Load Silver and Gold data lake outputs into the PostgreSQL warehouse."""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Any

from mediapulse.core.config import (
    MinioSettings,
    PostgresSettings,
    get_minio_settings,
    get_postgres_settings,
)
from mediapulse.core.logging import configure_logging
from mediapulse.transform.bronze_to_silver import parse_datetime_to_utc_iso

logger = logging.getLogger(__name__)

CATEGORY_NORMALIZER = re.compile(r"[^a-z0-9\u0600-\u06FF]+", re.IGNORECASE)


def parse_utc_datetime(value: Any) -> datetime:
    """Parse a datetime-like value to UTC, defaulting to now when missing."""

    try:
        parsed = parse_datetime_to_utc_iso(value)
        if parsed is None:
            return datetime.now(timezone.utc)
        return datetime.fromisoformat(parsed).astimezone(timezone.utc)
    except Exception:
        logger.warning("Failed to parse datetime for warehouse load: %s", value)
        return datetime.now(timezone.utc)


def date_key(value: date) -> int:
    """Build a YYYYMMDD integer date key."""

    try:
        return int(value.strftime("%Y%m%d"))
    except Exception:
        logger.exception("Failed to build date key")
        raise


def normalize_category(value: str | None) -> tuple[str, str]:
    """Normalize a category into display and key-friendly names."""

    try:
        display_name = (value or "Uncategorized").strip() or "Uncategorized"
        normalized = CATEGORY_NORMALIZER.sub("_", display_name.lower()).strip("_")
        return display_name, normalized or "uncategorized"
    except Exception:
        logger.exception("Failed to normalize category")
        raise


class WarehouseLoader:
    """Load MediaPulse lake records into PostgreSQL dimensional tables."""

    def __init__(self, minio_settings: MinioSettings, postgres_settings: PostgresSettings) -> None:
        """Create MinIO and PostgreSQL clients."""

        try:
            import psycopg
            from minio import Minio

            self.psycopg = psycopg
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
            logger.exception("Failed to initialize warehouse loader")
            raise

    def run(self, silver_limit: int | None = None, include_gold: bool = True) -> None:
        """Load Silver articles and Gold aggregate snapshots into PostgreSQL."""

        try:
            with self.psycopg.connect(self.postgres_settings.dsn) as connection:
                silver_records = self.read_silver_records(limit=silver_limit)
                self.load_articles(connection, silver_records)
                if include_gold:
                    self.load_gold_tables(connection)
                connection.commit()
            logger.info("Warehouse load complete")
        except Exception:
            logger.exception("Warehouse load failed")
            raise

    def read_silver_records(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Read accepted Silver records from MinIO."""

        try:
            objects = self.minio.list_objects(self.bucket_name, prefix=self.silver_prefix, recursive=True)
            records: list[dict[str, Any]] = []
            for item in sorted(objects, key=lambda obj: obj.object_name or ""):
                if limit is not None and len(records) >= limit:
                    break
                if not item.object_name or not item.object_name.endswith(".json"):
                    continue
                if "/_rejected/" in item.object_name:
                    continue
                record = self.read_json_object(item.object_name)
                record["silver_object_path"] = item.object_name
                records.append(record)
            logger.info("Read %s Silver record(s) for warehouse loading", len(records))
            return records
        except Exception:
            logger.exception("Failed to read Silver records for warehouse")
            raise

    def load_articles(self, connection: Any, records: list[dict[str, Any]]) -> None:
        """Load Silver article records into dimensions and fact_articles."""

        try:
            for record in records:
                source_key = self.upsert_source(connection, record)
                published_at = parse_utc_datetime(record.get("published_at"))
                scraped_at = parse_utc_datetime(record.get("scraped_at"))
                published_date_key = self.upsert_date(connection, published_at.date())
                scraped_date_key = self.upsert_date(connection, scraped_at.date())
                category_key = self.upsert_category(connection, record.get("category"))
                self.upsert_article(
                    connection=connection,
                    record=record,
                    source_key=source_key,
                    published_date_key=published_date_key,
                    scraped_date_key=scraped_date_key,
                    category_key=category_key,
                    published_at=published_at,
                    scraped_at=scraped_at,
                )
            logger.info("Loaded %s article fact row(s)", len(records))
        except Exception:
            logger.exception("Failed to load article records")
            raise

    def upsert_source(self, connection: Any, record: dict[str, Any]) -> int:
        """Upsert a source dimension row and return its key."""

        try:
            source_name = str(record.get("source") or "Unknown")
            country_code = str(record.get("country") or "ZZ").upper()[:2]
            country_name = "Morocco" if country_code == "MA" else "Unknown"
            source_type = "moroccan" if country_code == "MA" else "international"
            language_hint = str(record.get("language") or "en").lower()[:2]
            row = connection.execute(
                """
                INSERT INTO warehouse.dim_source (
                    source_name, country_code, country_name, source_type, language_hint
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_name) DO UPDATE SET
                    country_code = EXCLUDED.country_code,
                    country_name = EXCLUDED.country_name,
                    source_type = EXCLUDED.source_type,
                    language_hint = EXCLUDED.language_hint,
                    updated_at = NOW()
                RETURNING source_key
                """,
                (source_name, country_code, country_name, source_type, language_hint),
            ).fetchone()
            return int(row[0])
        except Exception:
            logger.exception("Failed to upsert source dimension")
            raise

    def upsert_date(self, connection: Any, value: date) -> int:
        """Upsert a date dimension row and return its date key."""

        try:
            key = date_key(value)
            iso_calendar = value.isocalendar()
            connection.execute(
                """
                INSERT INTO warehouse.dim_date (
                    date_key, full_date, year_number, quarter_number, month_number,
                    month_name, day_of_month, day_of_week, day_name, week_of_year, is_weekend
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (date_key) DO NOTHING
                """,
                (
                    key,
                    value,
                    value.year,
                    ((value.month - 1) // 3) + 1,
                    value.month,
                    value.strftime("%B"),
                    value.day,
                    value.isoweekday(),
                    value.strftime("%A"),
                    iso_calendar.week,
                    value.isoweekday() >= 6,
                ),
            )
            return key
        except Exception:
            logger.exception("Failed to upsert date dimension")
            raise

    def upsert_category(self, connection: Any, value: str | None) -> int:
        """Upsert a category dimension row and return its key."""

        try:
            category_name, normalized_name = normalize_category(value)
            row = connection.execute(
                """
                INSERT INTO warehouse.dim_category (category_name, normalized_name)
                VALUES (%s, %s)
                ON CONFLICT (normalized_name) DO UPDATE SET
                    category_name = EXCLUDED.category_name
                RETURNING category_key
                """,
                (category_name, normalized_name),
            ).fetchone()
            return int(row[0])
        except Exception:
            logger.exception("Failed to upsert category dimension")
            raise

    def upsert_article(
        self,
        connection: Any,
        record: dict[str, Any],
        source_key: int,
        published_date_key: int,
        scraped_date_key: int,
        category_key: int,
        published_at: datetime,
        scraped_at: datetime,
    ) -> None:
        """Upsert a fact_articles row."""

        try:
            connection.execute(
                """
                INSERT INTO warehouse.fact_articles (
                    url_hash, source_key, published_date_key, scraped_date_key, category_key,
                    title, author, published_at, scraped_at, language_code, country_code,
                    url, content_text, content_length, sentiment_score, topic_tags, silver_object_path
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (url_hash) DO UPDATE SET
                    source_key = EXCLUDED.source_key,
                    published_date_key = EXCLUDED.published_date_key,
                    scraped_date_key = EXCLUDED.scraped_date_key,
                    category_key = EXCLUDED.category_key,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    published_at = EXCLUDED.published_at,
                    scraped_at = EXCLUDED.scraped_at,
                    language_code = EXCLUDED.language_code,
                    country_code = EXCLUDED.country_code,
                    url = EXCLUDED.url,
                    content_text = EXCLUDED.content_text,
                    content_length = EXCLUDED.content_length,
                    sentiment_score = EXCLUDED.sentiment_score,
                    topic_tags = EXCLUDED.topic_tags,
                    silver_object_path = EXCLUDED.silver_object_path,
                    loaded_at = NOW()
                """,
                (
                    record.get("url_hash"),
                    source_key,
                    published_date_key,
                    scraped_date_key,
                    category_key,
                    record.get("title"),
                    record.get("author") or None,
                    published_at,
                    scraped_at,
                    str(record.get("language") or "en").lower()[:2],
                    str(record.get("country") or "ZZ").upper()[:2],
                    record.get("url"),
                    record.get("content"),
                    int(record.get("content_length") or len(str(record.get("content") or ""))),
                    record.get("sentiment_score"),
                    record.get("topic_tags"),
                    record.get("silver_object_path"),
                ),
            )
        except Exception:
            logger.exception("Failed to upsert article fact")
            raise

    def load_gold_tables(self, connection: Any) -> None:
        """Load latest Gold aggregate snapshots into warehouse facts."""

        try:
            top_keywords = self.read_latest_gold_table("top_keywords")
            if top_keywords:
                self.load_keyword_frequency(connection, top_keywords)
            trending_topics = self.read_latest_gold_table("trending_topics")
            if trending_topics:
                self.load_daily_trends(connection, trending_topics)
        except Exception:
            logger.exception("Failed to load Gold aggregate tables")
            raise

    def load_keyword_frequency(self, connection: Any, payload: dict[str, Any]) -> None:
        """Load top keyword Gold records into fact_keyword_frequency."""

        try:
            generated_at = parse_utc_datetime(payload.get("generated_at"))
            key = self.upsert_date(connection, generated_at.date())
            for record in payload.get("records", []):
                connection.execute(
                    """
                    INSERT INTO warehouse.fact_keyword_frequency (
                        date_key, source_key, keyword, frequency_count, tf_idf_score, rank_position
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    ON CONFLICT (date_key, source_key, keyword) DO NOTHING
                    """,
                    (
                        key,
                        record.get("keyword"),
                        int(record.get("frequency_count") or 0),
                        float(record.get("tf_idf_score") or 0),
                        record.get("rank_position"),
                    ),
                )
        except Exception:
            logger.exception("Failed to load keyword frequency facts")
            raise

    def load_daily_trends(self, connection: Any, payload: dict[str, Any]) -> None:
        """Load trending topic Gold records into fact_daily_trends."""

        try:
            generated_at = parse_utc_datetime(payload.get("generated_at"))
            key = self.upsert_date(connection, generated_at.date())
            for record in payload.get("records", []):
                connection.execute(
                    """
                    INSERT INTO warehouse.fact_daily_trends (
                        date_key, source_key, topic, article_count, trend_score,
                        window_start_at, window_end_at, top_keywords
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date_key, source_key, topic, window_start_at, window_end_at)
                    DO NOTHING
                    """,
                    (
                        key,
                        record.get("topic"),
                        int(record.get("article_count") or 0),
                        float(record.get("trend_score") or 0),
                        parse_utc_datetime(record.get("window_start_at")),
                        parse_utc_datetime(record.get("window_end_at")),
                        [record.get("topic")],
                    ),
                )
        except Exception:
            logger.exception("Failed to load daily trend facts")
            raise

    def read_latest_gold_table(self, table_name: str) -> dict[str, Any] | None:
        """Read the latest Gold table snapshot for a table name."""

        try:
            prefix = f"{self.gold_prefix}/table={table_name}"
            objects = [
                item.object_name
                for item in self.minio.list_objects(self.bucket_name, prefix=prefix, recursive=True)
                if item.object_name and item.object_name.endswith(".json")
            ]
            if not objects:
                return None
            return self.read_json_object(sorted(objects)[-1])
        except Exception:
            logger.exception("Failed to read latest Gold table: %s", table_name)
            raise

    def read_json_object(self, object_name: str) -> dict[str, Any]:
        """Read one JSON object from MinIO."""

        response = None
        try:
            response = self.minio.get_object(self.bucket_name, object_name)
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object in {object_name}")
            return payload
        except Exception:
            logger.exception("Failed to read JSON object: %s", object_name)
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Load MediaPulse data into PostgreSQL")
        parser.add_argument("--silver-limit", type=int, default=None)
        parser.add_argument("--skip-gold", action="store_true")
        return parser
    except Exception:
        logger.exception("Failed to build warehouse loader argument parser")
        raise


def main() -> None:
    """Run the warehouse loader from the command line."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        loader = WarehouseLoader(get_minio_settings(), get_postgres_settings())
        loader.run(silver_limit=args.silver_limit, include_gold=not args.skip_gold)
    except Exception:
        logger.exception("Warehouse loader CLI failed")
        raise


if __name__ == "__main__":
    main()
