"""Bronze layer writer backed by MinIO object storage."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from io import BytesIO

from minio import Minio

from mediapulse.core.config import MinioSettings
from mediapulse.models.article import Article

logger = logging.getLogger(__name__)


class BronzeWriter:
    """Write raw article JSON records to the Bronze data lake prefix."""

    def __init__(self, settings: MinioSettings) -> None:
        """Create a MinIO client and ensure the target bucket exists."""

        try:
            self.bucket_name = settings.bucket_name
            self.bronze_prefix = settings.bronze_prefix.strip("/")
            self.client = Minio(
                endpoint=settings.endpoint,
                access_key=settings.access_key,
                secret_key=settings.secret_key,
                secure=settings.secure,
            )
            self._ensure_bucket()
        except Exception:
            logger.exception("Failed to initialize Bronze writer")
            raise

    def write_article(self, article: Article) -> str:
        """Write one article JSON file and return its object path."""

        try:
            object_name = self._object_name(article)
            payload = article.model_dump_json(indent=2).encode("utf-8")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=BytesIO(payload),
                length=len(payload),
                content_type="application/json",
            )
            logger.info("Wrote Bronze object s3://%s/%s", self.bucket_name, object_name)
            return object_name
        except Exception:
            logger.exception("Failed to write article to Bronze layer: %s", article.url)
            raise

    def write_articles(self, articles: Iterable[Article]) -> list[str]:
        """Write many articles to the Bronze layer."""

        object_names: list[str] = []
        try:
            for article in articles:
                object_names.append(self.write_article(article))
            logger.info("Wrote %s Bronze object(s)", len(object_names))
            return object_names
        except Exception:
            logger.exception("Failed while writing article batch to Bronze layer")
            raise

    def _ensure_bucket(self) -> None:
        """Create the configured bucket when it does not already exist."""

        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket %s", self.bucket_name)
        except Exception:
            logger.exception("Failed to ensure MinIO bucket exists: %s", self.bucket_name)
            raise

    def _object_name(self, article: Article) -> str:
        """Build a medallion Bronze object path partitioned by source and date."""

        try:
            partition_date = article.scraped_at.date().isoformat()
            source_partition = article.source.lower().replace(" ", "_")
            return (
                f"{self.bronze_prefix}/source={source_partition}/"
                f"date={partition_date}/{article.url_hash}.json"
            )
        except Exception:
            logger.exception("Failed to build Bronze object path")
            raise
