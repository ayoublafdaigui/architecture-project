"""Tests for the canonical Article model."""

from __future__ import annotations

from datetime import datetime

import pytest

pytest.importorskip("pydantic")

from mediapulse.models.article import Article


def test_article_normalizes_text_and_language() -> None:
    """Article validation should normalize whitespace and language codes."""

    article = Article(
        title="  A   title  ",
        author="  Reporter  ",
        published_at=datetime(2026, 5, 8, 10, 0, 0),
        category=" News ",
        content="  Body   text with enough detail for a scraped raw article.  ",
        source="Hespress",
        url="https://www.hespress.com/example-123.html",
        language="AR",
        country="MA",
    )

    assert article.title == "A title"
    assert article.language == "ar"
    assert article.url_hash
