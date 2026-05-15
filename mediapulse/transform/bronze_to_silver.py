"""Bronze to Silver cleaning, validation, and deduplication pipeline."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

from mediapulse.core.config import MinioSettings, get_minio_settings
from mediapulse.core.logging import configure_logging

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover - exercised only in minimal local envs.
    BeautifulSoup = None  # type: ignore[assignment]

try:
    from dateutil import parser as date_parser
except ImportError:  # pragma: no cover - dateutil is included in requirements.
    date_parser = None  # type: ignore[assignment]

try:
    from langdetect import DetectorFactory, LangDetectException, detect

    DetectorFactory.seed = 0
except ImportError:  # pragma: no cover - exercised only in minimal local envs.
    detect = None  # type: ignore[assignment]

    class LangDetectException(Exception):
        """Fallback exception when langdetect is unavailable."""


logger = logging.getLogger(__name__)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b\u200c\u200d\ufeff]")
VALID_ISO_639_1_CODES = frozenset(
    {
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    }
)


@dataclass(frozen=True)
class QualityIssue:
    """A validation failure captured during Bronze to Silver transformation."""

    rule_name: str
    message: str
    layer: str = "silver"
    severity: str = "error"
    source: str | None = None
    url: str | None = None
    url_hash: str | None = None
    object_path: str | None = None


@dataclass(frozen=True)
class TransformResult:
    """Result for transforming one Bronze record."""

    accepted: bool
    record: dict[str, Any] | None
    issues: list[QualityIssue] = field(default_factory=list)


@dataclass(frozen=True)
class SilverRunSummary:
    """Aggregate metrics for a Bronze to Silver run."""

    scanned: int
    accepted: int
    rejected: int
    duplicate: int
    silver_objects: list[str]
    rejected_objects: list[str]


def strip_html_tags(value: str | None) -> str:
    """Remove HTML markup from a text field."""

    try:
        if value is None:
            return ""
        raw_text = str(value)
        if BeautifulSoup is None:
            return WHITESPACE_PATTERN.sub(" ", HTML_TAG_PATTERN.sub(" ", raw_text)).strip()
        return BeautifulSoup(raw_text, "html.parser").get_text(" ", strip=True)
    except Exception:
        logger.exception("Failed to strip HTML tags")
        raise


def normalize_encoding_and_whitespace(value: str | None) -> str:
    """Normalize Unicode, HTML entities, zero-width chars, and whitespace."""

    try:
        if value is None:
            return ""
        decoded = html.unescape(str(value))
        normalized = unicodedata.normalize("NFKC", decoded)
        normalized = ZERO_WIDTH_PATTERN.sub("", normalized)
        normalized = normalized.replace("\x00", "")
        normalized = normalized.encode("utf-8", errors="ignore").decode("utf-8")
        return WHITESPACE_PATTERN.sub(" ", normalized).strip()
    except Exception:
        logger.exception("Failed to normalize text encoding and whitespace")
        raise


def normalize_language_code(value: str | None) -> str | None:
    """Normalize and validate an ISO 639-1 language code."""

    try:
        if value is None:
            return None
        candidate = str(value).strip().lower().split("-", maxsplit=1)[0]
        if candidate in VALID_ISO_639_1_CODES:
            return candidate
        return None
    except Exception:
        logger.exception("Failed to normalize language code: %s", value)
        raise


def detect_article_language(
    title: str | None,
    content: str | None,
    fallback: str | None = None,
) -> str | None:
    """Detect article language with langdetect and return an ISO 639-1 code."""

    try:
        fallback_code = normalize_language_code(fallback)
        sample = normalize_encoding_and_whitespace(f"{title or ''} {content or ''}")
        if len(sample) < 20 or detect is None:
            return fallback_code
        detected = normalize_language_code(detect(sample))
        return detected or fallback_code
    except LangDetectException:
        logger.warning("Language detection failed; using fallback language")
        return fallback_code
    except Exception:
        logger.exception("Failed to detect article language")
        raise


def compute_url_hash(url: str) -> str:
    """Compute a stable SHA-256 hash for a URL."""

    try:
        normalized_url = normalize_encoding_and_whitespace(url)
        return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("Failed to compute URL hash")
        raise


def parse_datetime_to_utc_iso(value: Any) -> str | None:
    """Parse a datetime-like value and return an ISO UTC timestamp."""

    try:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            parsed = value
        elif date_parser is not None:
            parsed = date_parser.parse(str(value))
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        logger.warning("Failed to parse datetime value: %s", value)
        return None


def validate_silver_record(
    record: dict[str, Any],
    seen_url_hashes: set[str] | None = None,
) -> list[QualityIssue]:
    """Validate a Silver candidate record and return all quality failures."""

    try:
        seen_hashes = seen_url_hashes if seen_url_hashes is not None else set()
        issues: list[QualityIssue] = []
        title = str(record.get("title") or "").strip()
        content = str(record.get("content") or "").strip()
        url = str(record.get("url") or "").strip()
        url_hash = str(record.get("url_hash") or "").strip()
        language = normalize_language_code(record.get("language"))
        parsed_url = urlparse(url)
        issue_context = {
            "source": record.get("source"),
            "url": url or None,
            "url_hash": url_hash or None,
            "object_path": record.get("bronze_object_path"),
        }

        if not title:
            issues.append(
                QualityIssue(
                    rule_name="title_not_empty",
                    message="Article title is empty",
                    **issue_context,
                )
            )
        if not record.get("published_at"):
            issues.append(
                QualityIssue(
                    rule_name="published_at_not_null",
                    message="Article published_at is missing or invalid",
                    **issue_context,
                )
            )
        if len(content) <= 100:
            issues.append(
                QualityIssue(
                    rule_name="content_length_gt_100",
                    message="Article content length must be greater than 100 characters",
                    **issue_context,
                )
            )
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            issues.append(
                QualityIssue(
                    rule_name="url_valid",
                    message="Article URL is missing or invalid",
                    **issue_context,
                )
            )
        if not url_hash:
            issues.append(
                QualityIssue(
                    rule_name="url_hash_not_empty",
                    message="Article URL hash is missing",
                    **issue_context,
                )
            )
        elif url_hash in seen_hashes:
            issues.append(
                QualityIssue(
                    rule_name="url_unique",
                    message="Article URL hash already appeared in this run",
                    **issue_context,
                )
            )
        if language is None:
            issues.append(
                QualityIssue(
                    rule_name="language_iso_639_1",
                    message="Article language is not a valid ISO 639-1 code",
                    **issue_context,
                )
            )
        return issues
    except Exception:
        logger.exception("Failed to validate Silver record")
        raise


def transform_bronze_record(
    record: dict[str, Any],
    seen_url_hashes: set[str] | None = None,
    bronze_object_path: str | None = None,
) -> TransformResult:
    """Clean and validate one Bronze article record into a Silver candidate."""

    try:
        raw_url = normalize_encoding_and_whitespace(str(record.get("url") or ""))
        title = normalize_encoding_and_whitespace(strip_html_tags(record.get("title")))
        content = normalize_encoding_and_whitespace(strip_html_tags(record.get("content")))
        url_hash = compute_url_hash(raw_url) if raw_url else ""
        published_at = parse_datetime_to_utc_iso(record.get("published_at"))
        scraped_at = parse_datetime_to_utc_iso(record.get("scraped_at"))
        language = detect_article_language(
            title=title,
            content=content,
            fallback=record.get("language"),
        )

        silver_record: dict[str, Any] = {
            "title": title,
            "author": normalize_encoding_and_whitespace(strip_html_tags(record.get("author"))),
            "published_at": published_at,
            "category": normalize_encoding_and_whitespace(strip_html_tags(record.get("category"))),
            "content": content,
            "source": normalize_encoding_and_whitespace(record.get("source")),
            "url": raw_url,
            "language": language,
            "scraped_at": scraped_at or datetime.now(timezone.utc).isoformat(),
            "country": normalize_encoding_and_whitespace(record.get("country")),
            "url_hash": url_hash,
            "content_length": len(content),
            "bronze_object_path": bronze_object_path,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        issues = validate_silver_record(silver_record, seen_url_hashes)
        if issues:
            return TransformResult(accepted=False, record=silver_record, issues=issues)
        return TransformResult(accepted=True, record=silver_record, issues=[])
    except Exception:
        logger.exception("Failed to transform Bronze record")
        raise


class BronzeToSilverPipeline:
    """MinIO-backed Bronze to Silver transformation pipeline."""

    def __init__(self, settings: MinioSettings) -> None:
        """Create a pipeline using MinIO data lake settings."""

        try:
            from minio import Minio

            self.settings = settings
            self.bucket_name = settings.bucket_name
            self.bronze_prefix = settings.bronze_prefix.strip("/")
            self.silver_prefix = settings.silver_prefix.strip("/")
            self.rejected_prefix = f"{self.silver_prefix}/_rejected"
            self.client = Minio(
                endpoint=settings.endpoint,
                access_key=settings.access_key,
                secret_key=settings.secret_key,
                secure=settings.secure,
            )
            self._ensure_bucket()
        except Exception:
            logger.exception("Failed to initialize Bronze to Silver pipeline")
            raise

    def run(self, source: str | None = None, limit: int | None = None) -> SilverRunSummary:
        """Run the Bronze to Silver pipeline and return a summary."""

        try:
            seen_url_hashes: set[str] = set()
            scanned = 0
            accepted = 0
            duplicate = 0
            silver_objects: list[str] = []
            rejected_objects: list[str] = []
            object_names = self.list_bronze_objects(source=source)

            for object_name in object_names:
                if limit is not None and scanned >= limit:
                    break
                scanned += 1
                try:
                    bronze_record = self.read_json_object(object_name)
                    result = transform_bronze_record(
                        bronze_record,
                        seen_url_hashes=seen_url_hashes,
                        bronze_object_path=object_name,
                    )
                    if result.accepted and result.record is not None:
                        seen_url_hashes.add(str(result.record["url_hash"]))
                        silver_objects.append(self.write_silver_record(result.record))
                        accepted += 1
                    else:
                        if any(issue.rule_name == "url_unique" for issue in result.issues):
                            duplicate += 1
                        rejected_objects.append(
                            self.write_rejected_record(
                                bronze_record=bronze_record,
                                result=result,
                                bronze_object_path=object_name,
                            )
                        )
                except Exception:
                    logger.exception("Failed to process Bronze object: %s", object_name)

            summary = SilverRunSummary(
                scanned=scanned,
                accepted=accepted,
                rejected=scanned - accepted,
                duplicate=duplicate,
                silver_objects=silver_objects,
                rejected_objects=rejected_objects,
            )
            logger.info("Bronze to Silver run complete: %s", summary)
            return summary
        except Exception:
            logger.exception("Bronze to Silver pipeline run failed")
            raise

    def list_bronze_objects(self, source: str | None = None) -> list[str]:
        """List Bronze JSON object names, optionally filtered by source."""

        try:
            prefix = self.bronze_prefix
            if source:
                prefix = f"{prefix}/source={source.strip().lower().replace(' ', '_')}"
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=prefix,
                recursive=True,
            )
            object_names = sorted(
                item.object_name
                for item in objects
                if item.object_name and item.object_name.endswith(".json")
            )
            logger.info("Found %s Bronze object(s) under %s", len(object_names), prefix)
            return object_names
        except Exception:
            logger.exception("Failed to list Bronze objects")
            raise

    def read_json_object(self, object_name: str) -> dict[str, Any]:
        """Read a JSON object from MinIO."""

        response = None
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            payload = response.read().decode("utf-8")
            loaded = json.loads(payload)
            if not isinstance(loaded, dict):
                raise ValueError(f"Bronze object is not a JSON object: {object_name}")
            return loaded
        except Exception:
            logger.exception("Failed to read JSON object: %s", object_name)
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def write_silver_record(self, record: dict[str, Any]) -> str:
        """Write an accepted Silver record to MinIO."""

        try:
            object_name = self._silver_object_name(record)
            self._write_json(object_name, record)
            logger.info("Wrote Silver object s3://%s/%s", self.bucket_name, object_name)
            return object_name
        except Exception:
            logger.exception("Failed to write Silver record")
            raise

    def write_rejected_record(
        self,
        bronze_record: dict[str, Any],
        result: TransformResult,
        bronze_object_path: str,
    ) -> str:
        """Write a rejected record with quality issues for later inspection."""

        try:
            candidate = result.record or {}
            url_hash = candidate.get("url_hash") or compute_url_hash(bronze_object_path)
            object_name = (
                f"{self.rejected_prefix}/date={datetime.now(timezone.utc).date().isoformat()}/"
                f"{url_hash}.json"
            )
            payload = {
                "bronze_object_path": bronze_object_path,
                "bronze_record": bronze_record,
                "silver_candidate": candidate,
                "issues": [issue.__dict__ for issue in result.issues],
                "rejected_at": datetime.now(timezone.utc).isoformat(),
            }
            self._write_json(object_name, payload)
            logger.warning("Rejected Bronze object %s into %s", bronze_object_path, object_name)
            return object_name
        except Exception:
            logger.exception("Failed to write rejected Silver record")
            raise

    def _ensure_bucket(self) -> None:
        """Ensure the configured MinIO bucket exists."""

        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket %s", self.bucket_name)
        except Exception:
            logger.exception("Failed to ensure MinIO bucket exists: %s", self.bucket_name)
            raise

    def _write_json(self, object_name: str, payload: dict[str, Any]) -> None:
        """Write a JSON payload to MinIO."""

        try:
            raw_payload = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=BytesIO(raw_payload),
                length=len(raw_payload),
                content_type="application/json",
            )
        except Exception:
            logger.exception("Failed to write JSON object: %s", object_name)
            raise

    def _silver_object_name(self, record: dict[str, Any]) -> str:
        """Build a partitioned Silver object path."""

        try:
            source = str(record.get("source") or "unknown").lower().replace(" ", "_")
            published_at = parse_datetime_to_utc_iso(record.get("published_at"))
            partition_date = (
                datetime.fromisoformat(str(published_at)).date().isoformat()
                if published_at
                else datetime.now(timezone.utc).date().isoformat()
            )
            return (
                f"{self.silver_prefix}/source={source}/date={partition_date}/"
                f"{record['url_hash']}.json"
            )
        except Exception:
            logger.exception("Failed to build Silver object path")
            raise


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Run Bronze to Silver transformation")
        parser.add_argument("--source", default=None, help="Optional source partition filter")
        parser.add_argument("--limit", default=None, type=int, help="Optional object processing limit")
        return parser
    except Exception:
        logger.exception("Failed to build argument parser")
        raise


def main() -> None:
    """Run the Bronze to Silver pipeline from the command line."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        pipeline = BronzeToSilverPipeline(get_minio_settings())
        pipeline.run(source=args.source, limit=args.limit)
    except Exception:
        logger.exception("Bronze to Silver CLI failed")
        raise


if __name__ == "__main__":
    main()
