"""Tests for Silver to Gold aggregation functions."""

from __future__ import annotations

from datetime import datetime, timezone

from mediapulse.transform.silver_to_gold import (
    build_articles_by_source_country,
    build_daily_article_counts,
    build_top_keywords,
    build_trending_topics,
    tokenize_keywords,
)


def sample_records() -> list[dict[str, object]]:
    """Build sample Silver-like records for Gold aggregation tests."""

    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "title": "Media policy and economy",
            "content": "economy policy market growth media analysis " * 5,
            "published_at": now,
            "source": "Hespress",
            "country": "MA",
            "url_hash": "a",
        },
        {
            "title": "Economy growth outlook",
            "content": "economy growth investment market policy " * 5,
            "published_at": now,
            "source": "Reuters",
            "country": "GB",
            "url_hash": "b",
        },
    ]


def test_tokenize_keywords_filters_stopwords() -> None:
    """Tokenization should keep useful terms and remove common stopwords."""

    assert tokenize_keywords("The economy and policy growth") == ["economy", "policy", "growth"]


def test_build_daily_article_counts_groups_by_day_source_country() -> None:
    """Daily counts should group records by date, source, and country."""

    rows = build_daily_article_counts(sample_records())

    assert len(rows) == 2
    assert sum(row["article_count"] for row in rows) == 2


def test_build_articles_by_source_country_counts_sources() -> None:
    """Source-country aggregation should count articles."""

    rows = build_articles_by_source_country(sample_records())

    assert {"source": "Hespress", "country": "MA", "article_count": 1} in rows


def test_build_top_keywords_returns_ranked_keywords() -> None:
    """Top keyword aggregation should return ranked terms."""

    rows = build_top_keywords(sample_records(), top_n=5)

    assert rows
    assert rows[0]["rank_position"] == 1


def test_build_trending_topics_uses_recent_articles() -> None:
    """Trending topics should include recent article keywords."""

    rows = build_trending_topics(sample_records(), top_n=5)

    assert rows
