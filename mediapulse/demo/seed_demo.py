"""Seed the MediaPulse warehouse with realistic demo data."""

from __future__ import annotations

import argparse
import hashlib
import logging
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from mediapulse.core.config import PostgresSettings, get_postgres_settings
from mediapulse.core.logging import configure_logging
from mediapulse.warehouse.load_warehouse import date_key, normalize_category

logger = logging.getLogger(__name__)

SOURCES = [
    ("Hespress", "MA", "Morocco", "moroccan", "ar"),
    ("Akhbarona", "MA", "Morocco", "moroccan", "ar"),
    ("Barlamane", "MA", "Morocco", "moroccan", "ar"),
    ("Lakom", "MA", "Morocco", "moroccan", "ar"),
    ("Al Jazeera", "QA", "Qatar", "international", "en"),
    ("BBC News", "GB", "United Kingdom", "international", "en"),
    ("CNN", "US", "United States", "international", "en"),
    ("Reuters", "GB", "United Kingdom", "international", "en"),
]
CATEGORIES = ["Politics", "Economy", "World", "Technology", "Sport", "Culture"]
TOPICS = [
    "elections",
    "inflation",
    "energy",
    "education",
    "climate",
    "migration",
    "football",
    "startups",
    "diplomacy",
    "healthcare",
]
ARABIC_WORDS = ["المغرب", "الحكومة", "الاقتصاد", "الطاقة", "التعليم", "الرياضة", "الصحة"]
ENGLISH_WORDS = ["morocco", "policy", "economy", "energy", "education", "sport", "health"]


@dataclass(frozen=True)
class DemoArticle:
    """Synthetic article record for demo seeding."""

    source_name: str
    country_code: str
    category: str
    language_code: str
    title: str
    content: str
    published_at: datetime
    scraped_at: datetime
    url: str
    url_hash: str


def build_demo_articles(days: int, articles_per_day: int, seed: int) -> list[DemoArticle]:
    """Generate deterministic demo articles."""

    try:
        random.seed(seed)
        now = datetime.now(timezone.utc)
        articles: list[DemoArticle] = []
        for day_offset in range(days):
            published_day = now.date() - timedelta(days=day_offset)
            for index in range(articles_per_day):
                source = random.choice(SOURCES)
                topic = random.choice(TOPICS)
                category = random.choice(CATEGORIES)
                hour = random.randint(6, 22)
                minute = random.randint(0, 59)
                published_at = datetime.combine(
                    published_day,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                ).replace(hour=hour, minute=minute)
                title_words = ARABIC_WORDS if source[4] == "ar" else ENGLISH_WORDS
                title = f"{source[0]}: {topic.title()} {random.choice(title_words)} pulse"
                content = " ".join(
                    [
                        f"{topic} {random.choice(title_words)} analysis",
                        "MediaPulse demo article with enough detail for quality rules",
                        "market public policy newsroom trend source context",
                    ]
                    * 5
                )
                url = (
                    f"https://demo.mediapulse.local/{source[0].lower().replace(' ', '-')}/"
                    f"{published_day.isoformat()}/{topic}-{index}"
                )
                url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
                articles.append(
                    DemoArticle(
                        source_name=source[0],
                        country_code=source[1],
                        category=category,
                        language_code=source[4],
                        title=title,
                        content=content,
                        published_at=published_at,
                        scraped_at=published_at + timedelta(minutes=random.randint(2, 45)),
                        url=url,
                        url_hash=url_hash,
                    )
                )
        return articles
    except Exception:
        logger.exception("Failed to build demo articles")
        raise


class DemoSeeder:
    """Seed PostgreSQL warehouse tables with synthetic MediaPulse data."""

    def __init__(self, settings: PostgresSettings, retries: int = 20, retry_delay_seconds: int = 3) -> None:
        """Create a demo seeder."""

        try:
            import psycopg

            self.psycopg = psycopg
            self.settings = settings
            self.retries = retries
            self.retry_delay_seconds = retry_delay_seconds
        except Exception:
            logger.exception("Failed to initialize demo seeder")
            raise

    def run(self, days: int, articles_per_day: int, seed: int) -> None:
        """Seed all dashboard-facing warehouse tables."""

        try:
            articles = build_demo_articles(days=days, articles_per_day=articles_per_day, seed=seed)
            with self.connect_with_retry() as connection:
                self.seed_sources(connection)
                for article in articles:
                    self.seed_article(connection, article)
                self.seed_keywords(connection)
                self.seed_trends(connection)
                self.seed_quality(connection)
                connection.commit()
            logger.info("Seeded %s demo article(s)", len(articles))
        except Exception:
            logger.exception("Demo seed failed")
            raise

    def connect_with_retry(self) -> Any:
        """Connect to PostgreSQL with startup retries."""

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                return self.psycopg.connect(self.settings.dsn)
            except Exception as exc:
                last_error = exc
                logger.warning("PostgreSQL not ready for demo seed, attempt %s/%s", attempt, self.retries)
                time.sleep(self.retry_delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Could not connect to PostgreSQL")

    @staticmethod
    def seed_sources(connection: Any) -> None:
        """Seed source dimension rows."""

        try:
            for source_name, country_code, country_name, source_type, language_hint in SOURCES:
                connection.execute(
                    """
                    INSERT INTO warehouse.dim_source (
                        source_name, country_code, country_name, source_type, language_hint, base_url
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_name) DO UPDATE SET
                        country_code = EXCLUDED.country_code,
                        country_name = EXCLUDED.country_name,
                        source_type = EXCLUDED.source_type,
                        language_hint = EXCLUDED.language_hint,
                        base_url = EXCLUDED.base_url,
                        updated_at = NOW()
                    """,
                    (
                        source_name,
                        country_code,
                        country_name,
                        source_type,
                        language_hint,
                        f"https://demo.mediapulse.local/{source_name.lower().replace(' ', '-')}",
                    ),
                )
        except Exception:
            logger.exception("Failed to seed source dimensions")
            raise

    def seed_article(self, connection: Any, article: DemoArticle) -> None:
        """Seed one article fact row."""

        try:
            source_key = self.source_key(connection, article.source_name)
            published_date_key = self.seed_date(connection, article.published_at.date())
            scraped_date_key = self.seed_date(connection, article.scraped_at.date())
            category_key = self.seed_category(connection, article.category)
            connection.execute(
                """
                INSERT INTO warehouse.fact_articles (
                    url_hash, source_key, published_date_key, scraped_date_key, category_key,
                    title, author, published_at, scraped_at, language_code, country_code,
                    url, content_text, content_length, sentiment_score, topic_tags, silver_object_path
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (url_hash) DO UPDATE SET
                    title = EXCLUDED.title,
                    content_text = EXCLUDED.content_text,
                    content_length = EXCLUDED.content_length,
                    loaded_at = NOW()
                """,
                (
                    article.url_hash,
                    source_key,
                    published_date_key,
                    scraped_date_key,
                    category_key,
                    article.title,
                    "MediaPulse Demo Desk",
                    article.published_at,
                    article.scraped_at,
                    article.language_code,
                    article.country_code,
                    article.url,
                    article.content,
                    len(article.content),
                    round(random.uniform(-0.25, 0.55), 5),
                    random.sample(TOPICS, k=3),
                    f"silver/demo/date={article.published_at.date().isoformat()}/{article.url_hash}.json",
                ),
            )
        except Exception:
            logger.exception("Failed to seed article")
            raise

    @staticmethod
    def source_key(connection: Any, source_name: str) -> int:
        """Return source dimension key."""

        try:
            row = connection.execute(
                "SELECT source_key FROM warehouse.dim_source WHERE source_name = %s",
                (source_name,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Missing source row: {source_name}")
            return int(row[0])
        except Exception:
            logger.exception("Failed to resolve source key")
            raise

    @staticmethod
    def seed_date(connection: Any, value: date) -> int:
        """Seed one date dimension row and return date key."""

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
            logger.exception("Failed to seed date dimension")
            raise

    @staticmethod
    def seed_category(connection: Any, category: str) -> int:
        """Seed one category dimension row and return category key."""

        try:
            category_name, normalized_name = normalize_category(category)
            row = connection.execute(
                """
                INSERT INTO warehouse.dim_category (category_name, normalized_name)
                VALUES (%s, %s)
                ON CONFLICT (normalized_name) DO UPDATE SET category_name = EXCLUDED.category_name
                RETURNING category_key
                """,
                (category_name, normalized_name),
            ).fetchone()
            return int(row[0])
        except Exception:
            logger.exception("Failed to seed category dimension")
            raise

    def seed_keywords(self, connection: Any) -> None:
        """Seed keyword facts from synthetic topic scores."""

        try:
            today_key = self.seed_date(connection, datetime.now(timezone.utc).date())
            for rank, topic in enumerate(TOPICS, start=1):
                connection.execute(
                    """
                    INSERT INTO warehouse.fact_keyword_frequency (
                        date_key, source_key, keyword, frequency_count, tf_idf_score, rank_position
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        today_key,
                        topic,
                        random.randint(8, 80),
                        round(random.uniform(1.5, 12.0), 8),
                        rank,
                    ),
                )
        except Exception:
            logger.exception("Failed to seed keyword facts")
            raise

    def seed_trends(self, connection: Any) -> None:
        """Seed trend facts from synthetic topic scores."""

        try:
            now = datetime.now(timezone.utc)
            today_key = self.seed_date(connection, now.date())
            for topic in TOPICS[:8]:
                connection.execute(
                    """
                    INSERT INTO warehouse.fact_daily_trends (
                        date_key, source_key, topic, article_count, trend_score,
                        window_start_at, window_end_at, top_keywords
                    )
                    VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        today_key,
                        topic,
                        random.randint(4, 35),
                        round(random.uniform(0.3, 9.5), 6),
                        now - timedelta(hours=24),
                        now,
                        random.sample(TOPICS, k=3),
                    ),
                )
        except Exception:
            logger.exception("Failed to seed trend facts")
            raise

    def seed_quality(self, connection: Any) -> None:
        """Seed quality report rows for the dashboard gauge."""

        try:
            run_id = "00000000-0000-0000-0000-000000000001"
            rules = [
                "title_not_empty",
                "published_at_not_null",
                "content_length_gt_100",
                "url_unique",
                "language_iso_639_1",
            ]
            for rule in rules:
                for index in range(20):
                    status = "failed" if index == 0 and rule == "url_unique" else "passed"
                    connection.execute(
                        """
                        INSERT INTO warehouse.quality_report (
                            run_id, pipeline_step, layer_name, rule_name, severity,
                            status, failure_reason, detected_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            run_id,
                            "bronze_to_silver",
                            "silver",
                            rule,
                            "error",
                            status,
                            "Synthetic duplicate demo row" if status == "failed" else None,
                            datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 36)),
                        ),
                    )
        except Exception:
            logger.exception("Failed to seed quality report")
            raise


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Seed MediaPulse warehouse demo data")
        parser.add_argument("--days", type=int, default=14)
        parser.add_argument("--articles-per-day", type=int, default=16)
        parser.add_argument("--seed", type=int, default=42)
        return parser
    except Exception:
        logger.exception("Failed to build demo seed argument parser")
        raise


def main() -> None:
    """Run the demo data seeder."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        DemoSeeder(get_postgres_settings()).run(
            days=args.days,
            articles_per_day=args.articles_per_day,
            seed=args.seed,
        )
    except Exception:
        logger.exception("Demo seed CLI failed")
        raise


if __name__ == "__main__":
    main()
