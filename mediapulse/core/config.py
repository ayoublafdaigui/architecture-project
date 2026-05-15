"""Environment-driven settings for MediaPulse services."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KafkaSettings:
    """Kafka connection settings."""

    bootstrap_servers: str
    raw_articles_topic: str
    consumer_group_id: str


@dataclass(frozen=True)
class MinioSettings:
    """MinIO connection settings for the data lake."""

    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str
    bronze_prefix: str
    silver_prefix: str
    gold_prefix: str
    secure: bool


@dataclass(frozen=True)
class ScraperSettings:
    """Generic scraper execution settings."""

    request_timeout_seconds: int
    max_articles_per_run: int


@dataclass(frozen=True)
class PostgresSettings:
    """PostgreSQL connection settings."""

    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def dsn(self) -> str:
        """Build a psycopg-compatible DSN."""

        try:
            return (
                f"host={self.host} port={self.port} dbname={self.database} "
                f"user={self.user} password={self.password}"
            )
        except Exception:
            logger.exception("Failed to build PostgreSQL DSN")
            raise


def get_kafka_settings() -> KafkaSettings:
    """Load Kafka settings from environment variables."""

    try:
        return KafkaSettings(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            raw_articles_topic=os.getenv("KAFKA_RAW_ARTICLES_TOPIC", "raw-articles"),
            consumer_group_id=os.getenv("KAFKA_CONSUMER_GROUP_ID", "mediapulse-bronze-writer"),
        )
    except Exception:
        logger.exception("Failed to load Kafka settings")
        raise


def get_minio_settings() -> MinioSettings:
    """Load MinIO settings from environment variables."""

    try:
        secure_value = os.getenv("MINIO_SECURE", "false").strip().lower()
        return MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
            bucket_name=os.getenv("MINIO_BUCKET", "mediapulse"),
            bronze_prefix=os.getenv("MINIO_BRONZE_PREFIX", "bronze"),
            silver_prefix=os.getenv("MINIO_SILVER_PREFIX", "silver"),
            gold_prefix=os.getenv("MINIO_GOLD_PREFIX", "gold"),
            secure=secure_value in {"1", "true", "yes"},
        )
    except Exception:
        logger.exception("Failed to load MinIO settings")
        raise


def get_scraper_settings() -> ScraperSettings:
    """Load scraper execution settings from environment variables."""

    try:
        return ScraperSettings(
            request_timeout_seconds=int(os.getenv("SCRAPER_REQUEST_TIMEOUT_SECONDS", "20")),
            max_articles_per_run=int(os.getenv("SCRAPER_MAX_ARTICLES_PER_RUN", "25")),
        )
    except Exception:
        logger.exception("Failed to load scraper settings")
        raise


def get_postgres_settings(database: str | None = None) -> PostgresSettings:
    """Load PostgreSQL settings from environment variables."""

    try:
        return PostgresSettings(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "mediapulse"),
            password=os.getenv("POSTGRES_PASSWORD", "mediapulse"),
            database=database or os.getenv("POSTGRES_DB", "mediapulse"),
        )
    except Exception:
        logger.exception("Failed to load PostgreSQL settings")
        raise
