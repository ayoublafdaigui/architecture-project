"""Base classes and helpers for source-specific news scrapers."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from mediapulse.models.article import Article

logger = logging.getLogger(__name__)

USER_AGENT = (
    "MediaPulseBot/0.1 (+https://example.local/mediapulse; "
    "research and analytics pipeline)"
)
WHITESPACE_PATTERN = re.compile(r"\s+")


class BaseNewsScraper(ABC):
    """Shared scraper behavior for source-specific article extractors."""

    source_name: str
    base_url: str
    country: str | None = None
    language_hint: str | None = None

    def __init__(self, request_timeout_seconds: int = 20) -> None:
        """Create a scraper with a reusable HTTP session."""

        try:
            self.request_timeout_seconds = request_timeout_seconds
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": USER_AGENT})
        except Exception:
            logger.exception("Failed to initialize scraper")
            raise

    def fetch(self, url: str) -> str:
        """Fetch a URL and return its response body."""

        try:
            response = self.session.get(url, timeout=self.request_timeout_seconds)
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"
            logger.info("Fetched URL %s with status %s", url, response.status_code)
            return response.text
        except Exception:
            logger.exception("Failed to fetch URL: %s", url)
            raise

    def scrape(self, limit: int = 25) -> list[Article]:
        """Discover and parse article URLs from this source."""

        articles: list[Article] = []
        try:
            urls = self.discover_article_urls(limit=limit)
            for url in urls:
                try:
                    html = self.fetch(url)
                    articles.append(self.parse_article(html=html, url=url))
                except Exception:
                    logger.exception("Failed to scrape article URL: %s", url)
            logger.info("Scraped %s article(s) from %s", len(articles), self.source_name)
            return articles
        except Exception:
            logger.exception("Failed to run scraper for %s", self.source_name)
            raise

    @abstractmethod
    def discover_article_urls(self, limit: int = 25) -> list[str]:
        """Discover article URLs for the source."""

    @abstractmethod
    def parse_article(self, html: str, url: str) -> Article:
        """Parse an article page into an Article object."""

    def absolute_url(self, href: str) -> str:
        """Build an absolute URL from a source-relative link."""

        try:
            return urljoin(self.base_url, href)
        except Exception:
            logger.exception("Failed to build absolute URL from href: %s", href)
            raise

    @staticmethod
    def clean_text(value: str | None) -> str | None:
        """Normalize whitespace in extracted text."""

        try:
            if value is None:
                return None
            normalized = WHITESPACE_PATTERN.sub(" ", value).strip()
            return normalized or None
        except Exception:
            logger.exception("Failed to clean extracted text")
            raise

    @staticmethod
    def first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
        """Return text from the first selector that matches non-empty content."""

        try:
            for selector in selectors:
                node = soup.select_one(selector)
                if node is None:
                    continue
                text = BaseNewsScraper.clean_text(node.get_text(" ", strip=True))
                if text:
                    return text
            return None
        except Exception:
            logger.exception("Failed to extract first matching text")
            raise

    @staticmethod
    def meta_content(soup: BeautifulSoup, *names: str) -> str | None:
        """Read the first matching meta tag by property or name."""

        try:
            for name in names:
                node = soup.find("meta", attrs={"property": name}) or soup.find(
                    "meta", attrs={"name": name}
                )
                if node and node.get("content"):
                    return BaseNewsScraper.clean_text(str(node["content"]))
            return None
        except Exception:
            logger.exception("Failed to extract meta content")
            raise

    @staticmethod
    def json_ld_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract JSON-LD objects from a page."""

        objects: list[dict[str, Any]] = []
        try:
            for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
                raw_json = node.string or node.get_text()
                if not raw_json:
                    continue
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    graph = parsed.get("@graph")
                    if isinstance(graph, list):
                        objects.extend(item for item in graph if isinstance(item, dict))
                    else:
                        objects.append(parsed)
                elif isinstance(parsed, list):
                    objects.extend(item for item in parsed if isinstance(item, dict))
            return objects
        except Exception:
            logger.exception("Failed to parse JSON-LD metadata")
            return objects

    @staticmethod
    def first_json_ld_value(objects: Iterable[dict[str, Any]], *keys: str) -> Any | None:
        """Return the first JSON-LD value found for any requested key."""

        try:
            for obj in objects:
                for key in keys:
                    value = obj.get(key)
                    if value:
                        return value
            return None
        except Exception:
            logger.exception("Failed to extract JSON-LD value")
            raise
