"""Tests for demo data generation."""

from __future__ import annotations

from mediapulse.demo.seed_demo import build_demo_articles


def test_build_demo_articles_is_deterministic() -> None:
    """Demo generation should be deterministic for the same seed."""

    first = build_demo_articles(days=2, articles_per_day=3, seed=7)
    second = build_demo_articles(days=2, articles_per_day=3, seed=7)

    assert len(first) == 6
    assert [article.url_hash for article in first] == [article.url_hash for article in second]
    assert all(len(article.content) > 100 for article in first)
