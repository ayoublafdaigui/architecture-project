"""Tests for Bronze to Silver transformation functions."""

from __future__ import annotations

from mediapulse.transform.bronze_to_silver import (
    compute_url_hash,
    detect_article_language,
    normalize_encoding_and_whitespace,
    normalize_language_code,
    parse_datetime_to_utc_iso,
    strip_html_tags,
    transform_bronze_record,
    validate_silver_record,
)


def test_strip_html_tags_removes_markup() -> None:
    """HTML markup should be removed from text fields."""

    assert strip_html_tags("<p>Hello <strong>MediaPulse</strong></p>") == "Hello MediaPulse"


def test_normalize_encoding_and_whitespace_collapses_text() -> None:
    """Whitespace, entities, and zero-width chars should normalize cleanly."""

    assert normalize_encoding_and_whitespace("A&nbsp;\u200b  B\n C") == "A B C"


def test_normalize_language_code_accepts_iso_639_1() -> None:
    """Language codes should normalize to lower-case ISO 639-1 values."""

    assert normalize_language_code("EN-us") == "en"


def test_detect_article_language_uses_valid_fallback() -> None:
    """Language detection should return a valid fallback for short samples."""

    assert detect_article_language("Hi", "Short", fallback="AR") == "ar"


def test_compute_url_hash_is_stable() -> None:
    """URL hashes should be deterministic."""

    url = "https://www.hespress.com/example-123.html"
    assert compute_url_hash(url) == compute_url_hash(url)


def test_parse_datetime_to_utc_iso_returns_timezone_aware_value() -> None:
    """Datetime parsing should normalize timestamps to UTC ISO strings."""

    assert parse_datetime_to_utc_iso("2026-05-08T12:30:00+01:00") == "2026-05-08T11:30:00+00:00"


def test_validate_silver_record_reports_quality_failures() -> None:
    """Silver validation should flag required quality rules."""

    issues = validate_silver_record(
        {
            "title": "",
            "published_at": None,
            "content": "too short",
            "url": "not-a-url",
            "url_hash": "abc",
            "language": "bad",
        },
        seen_url_hashes={"abc"},
    )

    assert {issue.rule_name for issue in issues} == {
        "title_not_empty",
        "published_at_not_null",
        "content_length_gt_100",
        "url_valid",
        "url_unique",
        "language_iso_639_1",
    }


def test_transform_bronze_record_accepts_valid_record() -> None:
    """A valid Bronze article should become an accepted Silver record."""

    content = " ".join(["This is a long enough article body for MediaPulse testing."] * 4)
    result = transform_bronze_record(
        {
            "title": "<h1>Clean headline</h1>",
            "author": "Reporter",
            "published_at": "2026-05-08T12:30:00Z",
            "category": "News",
            "content": f"<p>{content}</p>",
            "source": "Hespress",
            "url": "https://www.hespress.com/example-123.html",
            "language": "en",
            "scraped_at": "2026-05-08T13:00:00Z",
            "country": "MA",
        },
        seen_url_hashes=set(),
        bronze_object_path="bronze/source=hespress/date=2026-05-08/example.json",
    )

    assert result.accepted is True
    assert result.record is not None
    assert result.record["title"] == "Clean headline"
    assert result.record["content_length"] > 100
