"""Run one Hespress scrape, then publish to Kafka and write Bronze JSON."""

from __future__ import annotations

import logging

from mediapulse.core.config import get_kafka_settings, get_minio_settings, get_scraper_settings
from mediapulse.core.logging import configure_logging
from mediapulse.datalake.bronze_writer import BronzeWriter
from mediapulse.ingestion.kafka_producer import ArticleKafkaProducer
from mediapulse.scrapers.hespress import HespressScraper

logger = logging.getLogger(__name__)


def main() -> None:
    """Execute a single Hespress ingestion run."""

    configure_logging()
    producer: ArticleKafkaProducer | None = None
    try:
        scraper_settings = get_scraper_settings()
        scraper = HespressScraper(
            request_timeout_seconds=scraper_settings.request_timeout_seconds,
        )
        articles = scraper.scrape(limit=scraper_settings.max_articles_per_run)
        if not articles:
            logger.warning("No Hespress articles were scraped")
            return

        bronze_writer = BronzeWriter(get_minio_settings())
        bronze_writer.write_articles(articles)

        producer = ArticleKafkaProducer(get_kafka_settings())
        producer.send_articles(articles)
        logger.info("Completed Hespress ingestion run with %s article(s)", len(articles))
    except Exception:
        logger.exception("Hespress ingestion run failed")
        raise
    finally:
        if producer is not None:
            producer.close()


if __name__ == "__main__":
    main()
