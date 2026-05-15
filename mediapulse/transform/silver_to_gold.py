"""Silver to Gold analytical aggregation pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from mediapulse.core.config import MinioSettings, get_minio_settings
from mediapulse.core.logging import configure_logging
from mediapulse.transform.bronze_to_silver import parse_datetime_to_utc_iso

logger = logging.getLogger(__name__)

TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]{3,}", re.UNICODE)
STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "are",
        "was",
        "were",
        "dans",
        "avec",
        "pour",
        "des",
        "les",
        "une",
        "sur",
        "par",
        "إلى",
        "على",
        "عن",
        "من",
        "في",
        "هذا",
        "هذه",
        "ذلك",
        "التي",
        "الذي",
        "بعد",
        "قبل",
        "كان",
        "كانت",
    }
)


@dataclass(frozen=True)
class GoldRunSummary:
    """Summary of a Silver to Gold aggregation run."""

    scanned: int
    written_tables: dict[str, str]


def parse_utc_datetime(value: Any) -> datetime | None:
    """Parse a datetime value into UTC."""

    try:
        parsed = parse_datetime_to_utc_iso(value)
        if parsed is None:
            return None
        return datetime.fromisoformat(parsed).astimezone(timezone.utc)
    except Exception:
        logger.warning("Failed to parse UTC datetime for Gold aggregation: %s", value)
        return None


def tokenize_keywords(text: str | None) -> list[str]:
    """Tokenize article text into normalized keyword candidates."""

    try:
        if not text:
            return []
        tokens = [token.lower() for token in TOKEN_PATTERN.findall(text)]
        return [token for token in tokens if token not in STOPWORDS and not token.isdigit()]
    except Exception:
        logger.exception("Failed to tokenize keywords")
        raise


def build_daily_article_counts(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate daily article counts by source and country."""

    try:
        counts: Counter[tuple[str, str, str]] = Counter()
        for record in records:
            published_at = parse_utc_datetime(record.get("published_at"))
            if published_at is None:
                continue
            key = (
                published_at.date().isoformat(),
                str(record.get("source") or "unknown"),
                str(record.get("country") or "unknown"),
            )
            counts[key] += 1
        return [
            {
                "published_date": published_date,
                "source": source,
                "country": country,
                "article_count": count,
            }
            for (published_date, source, country), count in sorted(counts.items())
        ]
    except Exception:
        logger.exception("Failed to build daily article counts")
        raise


def build_articles_by_source_country(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate total articles by source and country."""

    try:
        counts: Counter[tuple[str, str]] = Counter()
        for record in records:
            counts[(str(record.get("source") or "unknown"), str(record.get("country") or "unknown"))] += 1
        return [
            {"source": source, "country": country, "article_count": count}
            for (source, country), count in sorted(counts.items())
        ]
    except Exception:
        logger.exception("Failed to build source-country article counts")
        raise


def build_top_keywords(records: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
    """Compute top keyword scores using a compact TF-IDF implementation."""

    try:
        term_frequencies: Counter[str] = Counter()
        document_frequencies: Counter[str] = Counter()
        document_count = 0

        for record in records:
            tokens = tokenize_keywords(f"{record.get('title') or ''} {record.get('content') or ''}")
            if not tokens:
                continue
            document_count += 1
            token_counts = Counter(tokens)
            term_frequencies.update(token_counts)
            document_frequencies.update(token_counts.keys())

        scored_keywords = []
        for keyword, frequency in term_frequencies.items():
            idf = math.log((1 + document_count) / (1 + document_frequencies[keyword])) + 1
            scored_keywords.append((keyword, frequency, round(frequency * idf, 8)))

        scored_keywords.sort(key=lambda item: (-item[2], item[0]))
        return [
            {
                "keyword": keyword,
                "frequency_count": frequency,
                "tf_idf_score": score,
                "rank_position": index + 1,
            }
            for index, (keyword, frequency, score) in enumerate(scored_keywords[:top_n])
        ]
    except Exception:
        logger.exception("Failed to build top keywords")
        raise


def build_trending_topics(
    records: list[dict[str, Any]],
    window_hours: int = 24,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Build trending topics for the most recent rolling time window."""

    try:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=window_hours)
        topic_counts: Counter[str] = Counter()
        article_sets: defaultdict[str, set[str]] = defaultdict(set)

        for record in records:
            published_at = parse_utc_datetime(record.get("published_at"))
            if published_at is None or published_at < window_start:
                continue
            article_id = str(record.get("url_hash") or record.get("url") or "")
            tokens = tokenize_keywords(f"{record.get('title') or ''} {record.get('content') or ''}")
            top_tokens = [token for token, _ in Counter(tokens).most_common(5)]
            for token in top_tokens:
                topic_counts[token] += 1
                article_sets[token].add(article_id)

        ranked = topic_counts.most_common(top_n)
        return [
            {
                "topic": topic,
                "article_count": len(article_sets[topic]),
                "trend_score": round(count / max(1, window_hours), 6),
                "window_start_at": window_start.isoformat(),
                "window_end_at": now.isoformat(),
            }
            for topic, count in ranked
        ]
    except Exception:
        logger.exception("Failed to build trending topics")
        raise


class SilverToGoldPipeline:
    """MinIO-backed Gold aggregation pipeline."""

    def __init__(self, settings: MinioSettings) -> None:
        """Create a Silver to Gold pipeline."""

        try:
            from minio import Minio

            self.settings = settings
            self.bucket_name = settings.bucket_name
            self.silver_prefix = settings.silver_prefix.strip("/")
            self.gold_prefix = settings.gold_prefix.strip("/")
            self.client = Minio(
                endpoint=settings.endpoint,
                access_key=settings.access_key,
                secret_key=settings.secret_key,
                secure=settings.secure,
            )
            self._ensure_bucket()
        except Exception:
            logger.exception("Failed to initialize Silver to Gold pipeline")
            raise

    def run(self, source: str | None = None, limit: int | None = None) -> GoldRunSummary:
        """Run Gold aggregations over Silver records."""

        try:
            records = self.read_silver_records(source=source, limit=limit)
            tables = {
                "daily_article_counts": build_daily_article_counts(records),
                "top_keywords": build_top_keywords(records),
                "trending_topics": build_trending_topics(records),
                "articles_by_source_country": build_articles_by_source_country(records),
            }
            written_tables = {
                table_name: self.write_gold_table(table_name, table_records)
                for table_name, table_records in tables.items()
            }
            summary = GoldRunSummary(scanned=len(records), written_tables=written_tables)
            logger.info("Silver to Gold run complete: %s", summary)
            return summary
        except Exception:
            logger.exception("Silver to Gold pipeline run failed")
            raise

    def read_silver_records(self, source: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """Read Silver JSON records from MinIO."""

        try:
            object_names = self.list_silver_objects(source=source)
            records: list[dict[str, Any]] = []
            for object_name in object_names:
                if limit is not None and len(records) >= limit:
                    break
                records.append(self.read_json_object(object_name))
            logger.info("Read %s Silver record(s)", len(records))
            return records
        except Exception:
            logger.exception("Failed to read Silver records")
            raise

    def list_silver_objects(self, source: str | None = None) -> list[str]:
        """List accepted Silver JSON object names."""

        try:
            prefix = self.silver_prefix
            if source:
                prefix = f"{prefix}/source={source.strip().lower().replace(' ', '_')}"
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)
            return sorted(
                item.object_name
                for item in objects
                if item.object_name
                and item.object_name.endswith(".json")
                and "/_rejected/" not in item.object_name
            )
        except Exception:
            logger.exception("Failed to list Silver objects")
            raise

    def read_json_object(self, object_name: str) -> dict[str, Any]:
        """Read a JSON object from MinIO."""

        response = None
        try:
            response = self.client.get_object(self.bucket_name, object_name)
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

    def write_gold_table(self, table_name: str, records: list[dict[str, Any]]) -> str:
        """Write a Gold analytical table snapshot to MinIO."""

        try:
            generated_at = datetime.now(timezone.utc)
            object_name = (
                f"{self.gold_prefix}/table={table_name}/run_date={generated_at.date().isoformat()}/"
                f"{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}.json"
            )
            payload = {
                "table": table_name,
                "generated_at": generated_at.isoformat(),
                "record_count": len(records),
                "records": records,
            }
            raw_payload = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=BytesIO(raw_payload),
                length=len(raw_payload),
                content_type="application/json",
            )
            logger.info("Wrote Gold table %s to s3://%s/%s", table_name, self.bucket_name, object_name)
            return object_name
        except Exception:
            logger.exception("Failed to write Gold table: %s", table_name)
            raise

    def _ensure_bucket(self) -> None:
        """Ensure the configured MinIO bucket exists."""

        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except Exception:
            logger.exception("Failed to ensure MinIO bucket exists: %s", self.bucket_name)
            raise


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Run Silver to Gold aggregation")
        parser.add_argument("--source", default=None, help="Optional source partition filter")
        parser.add_argument("--limit", default=None, type=int, help="Optional Silver record limit")
        return parser
    except Exception:
        logger.exception("Failed to build argument parser")
        raise


def main() -> None:
    """Run the Silver to Gold pipeline from the command line."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        pipeline = SilverToGoldPipeline(get_minio_settings())
        pipeline.run(source=args.source, limit=args.limit)
    except Exception:
        logger.exception("Silver to Gold CLI failed")
        raise


if __name__ == "__main__":
    main()
