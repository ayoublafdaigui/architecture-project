"""Kafka consumer that writes streamed raw article events to Bronze."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from mediapulse.core.config import get_kafka_settings, get_minio_settings
from mediapulse.core.logging import configure_logging

logger = logging.getLogger(__name__)


class ArticleKafkaConsumer:
    """Consume raw article events and persist them as Bronze JSON objects."""

    def __init__(self, batch_size: int = 50, poll_timeout_ms: int = 1000) -> None:
        """Create the Kafka consumer and Bronze writer."""

        try:
            from kafka import KafkaConsumer
            from mediapulse.datalake.bronze_writer import BronzeWriter

            self.kafka_settings = get_kafka_settings()
            self.batch_size = batch_size
            self.poll_timeout_ms = poll_timeout_ms
            self.consumer = KafkaConsumer(
                self.kafka_settings.raw_articles_topic,
                bootstrap_servers=self.kafka_settings.bootstrap_servers,
                group_id=self.kafka_settings.consumer_group_id,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                value_deserializer=lambda value: json.loads(value.decode("utf-8")),
                key_deserializer=lambda key: key.decode("utf-8") if key else None,
            )
            self.bronze_writer = BronzeWriter(get_minio_settings())
        except Exception:
            logger.exception("Failed to initialize Kafka article consumer")
            raise

    def run_forever(self) -> None:
        """Continuously consume messages and write micro-batches to Bronze."""

        logger.info("Starting Kafka Bronze consumer for topic %s", self.kafka_settings.raw_articles_topic)
        try:
            buffer: list[Article] = []
            while True:
                polled = self.consumer.poll(timeout_ms=self.poll_timeout_ms, max_records=self.batch_size)
                for messages in polled.values():
                    for message in messages:
                        article = self._message_to_article(message.value)
                        if article is not None:
                            buffer.append(article)
                if len(buffer) >= self.batch_size:
                    self.flush(buffer)
                    buffer.clear()
                if polled and buffer:
                    self.flush(buffer)
                    buffer.clear()
        except KeyboardInterrupt:
            logger.info("Kafka Bronze consumer interrupted")
        except Exception:
            logger.exception("Kafka Bronze consumer failed")
            raise
        finally:
            self.consumer.close()

    def flush(self, articles: list[Article]) -> None:
        """Write a buffered batch to Bronze and commit Kafka offsets."""

        try:
            self.bronze_writer.write_articles(articles)
            self.consumer.commit()
            logger.info("Committed %s streamed article(s) to Bronze", len(articles))
        except Exception:
            logger.exception("Failed to flush streamed articles to Bronze")
            raise

    @staticmethod
    def _message_to_article(payload: Any) -> Article | None:
        """Convert a Kafka message payload into an Article."""

        try:
            from mediapulse.models.article import Article

            if not isinstance(payload, dict):
                logger.warning("Skipping non-object Kafka payload: %s", type(payload))
                return None
            clean_payload = dict(payload)
            clean_payload.pop("url_hash", None)
            return Article.model_validate(clean_payload)
        except Exception:
            logger.exception("Skipping invalid article payload from Kafka")
            return None


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Consume Kafka raw articles into Bronze")
        parser.add_argument("--batch-size", type=int, default=50)
        parser.add_argument("--poll-timeout-ms", type=int, default=1000)
        return parser
    except Exception:
        logger.exception("Failed to build Kafka consumer argument parser")
        raise


def main() -> None:
    """Run the Kafka Bronze consumer."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        ArticleKafkaConsumer(
            batch_size=args.batch_size,
            poll_timeout_ms=args.poll_timeout_ms,
        ).run_forever()
    except Exception:
        logger.exception("Kafka consumer CLI failed")
        raise


if __name__ == "__main__":
    main()
