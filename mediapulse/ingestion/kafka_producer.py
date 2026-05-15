"""Kafka producer for publishing scraped article events."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from kafka import KafkaProducer

from mediapulse.core.config import KafkaSettings
from mediapulse.models.article import Article

logger = logging.getLogger(__name__)


class ArticleKafkaProducer:
    """Publish Article records to the raw-articles Kafka topic."""

    def __init__(self, settings: KafkaSettings) -> None:
        """Create a Kafka producer from runtime settings."""

        try:
            self.topic = settings.raw_articles_topic
            self.producer = KafkaProducer(
                bootstrap_servers=settings.bootstrap_servers,
                key_serializer=lambda key: key.encode("utf-8"),
                value_serializer=lambda value: json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8"),
                linger_ms=50,
                retries=5,
            )
            logger.info("Kafka producer initialized for topic %s", self.topic)
        except Exception:
            logger.exception("Failed to initialize Kafka producer")
            raise

    def send_article(self, article: Article) -> None:
        """Send one article to Kafka."""

        try:
            self.producer.send(
                self.topic,
                key=article.url_hash,
                value=article.to_bronze_dict(),
            )
            logger.info("Queued article for Kafka topic %s: %s", self.topic, article.url)
        except Exception:
            logger.exception("Failed to publish article to Kafka: %s", article.url)
            raise

    def send_articles(self, articles: Iterable[Article]) -> int:
        """Send many articles to Kafka and return the number queued."""

        count = 0
        try:
            for article in articles:
                self.send_article(article)
                count += 1
            self.producer.flush(timeout=30)
            logger.info("Published %s article(s) to Kafka topic %s", count, self.topic)
            return count
        except Exception:
            logger.exception("Failed while publishing article batch to Kafka")
            raise

    def close(self) -> None:
        """Flush and close the Kafka producer."""

        try:
            self.producer.flush(timeout=30)
            self.producer.close(timeout=30)
        except Exception:
            logger.exception("Failed to close Kafka producer")
            raise
