"""Run a batch scrape for all configured MediaPulse sources."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable

from mediapulse.core.config import get_kafka_settings, get_minio_settings, get_scraper_settings
from mediapulse.core.logging import configure_logging
from mediapulse.datalake.bronze_writer import BronzeWriter
from mediapulse.ingestion.kafka_producer import ArticleKafkaProducer
from mediapulse.models.article import Article
from mediapulse.scrapers.base import BaseNewsScraper
from mediapulse.scrapers.hespress import HespressScraper
from mediapulse.scrapers.sources import SCRAPER_REGISTRY

logger = logging.getLogger(__name__)

ALL_SCRAPERS = {"hespress": HespressScraper, **SCRAPER_REGISTRY}


def scrape_sources(source_names: Iterable[str], limit: int) -> list[Article]:
    """Scrape a list of configured source names."""

    try:
        scraper_settings = get_scraper_settings()
        articles: list[Article] = []
        for source_name in source_names:
            scraper_class = ALL_SCRAPERS[source_name]
            scraper: BaseNewsScraper = scraper_class(
                request_timeout_seconds=scraper_settings.request_timeout_seconds,
            )
            try:
                source_articles = scraper.scrape(limit=limit)
                articles.extend(source_articles)
            except Exception:
                logger.exception("Source scrape failed and will be skipped: %s", source_name)
        logger.info("Batch scrape produced %s article(s)", len(articles))
        return articles
    except Exception:
        logger.exception("Failed to scrape configured sources")
        raise


def publish_and_write_bronze(articles: list[Article]) -> None:
    """Write scraped articles to Bronze and publish them to Kafka."""

    producer: ArticleKafkaProducer | None = None
    try:
        if not articles:
            logger.warning("No articles to ingest from batch scrape")
            return
        BronzeWriter(get_minio_settings()).write_articles(articles)
        producer = ArticleKafkaProducer(get_kafka_settings())
        producer.send_articles(articles)
    except Exception:
        logger.exception("Failed to publish/write scraped article batch")
        raise
    finally:
        if producer is not None:
            producer.close()


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Run MediaPulse batch scrape")
        parser.add_argument(
            "--source",
            action="append",
            choices=sorted(ALL_SCRAPERS),
            help="Source to scrape. Repeat for multiple sources. Defaults to all.",
        )
        parser.add_argument("--limit", type=int, default=None, help="Per-source article limit")
        return parser
    except Exception:
        logger.exception("Failed to build batch scrape argument parser")
        raise


def main() -> None:
    """Run the batch scrape CLI."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        scraper_settings = get_scraper_settings()
        source_names = args.source or sorted(ALL_SCRAPERS)
        limit = args.limit or scraper_settings.max_articles_per_run
        articles = scrape_sources(source_names=source_names, limit=limit)
        publish_and_write_bronze(articles)
    except Exception:
        logger.exception("Batch scrape CLI failed")
        raise


if __name__ == "__main__":
    main()
