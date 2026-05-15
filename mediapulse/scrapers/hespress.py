"""Hespress scraper implementation."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from mediapulse.models.article import Article
from mediapulse.scrapers.base import BaseNewsScraper

logger = logging.getLogger(__name__)

HESPRESS_ARTICLE_PATTERN = re.compile(r"^https?://(www\.)?hespress\.com/.+\.html$")


class HespressScraper(BaseNewsScraper):
    """Scrape article metadata and body content from Hespress."""

    source_name = "Hespress"
    base_url = "https://www.hespress.com/"
    country = "MA"
    language_hint = "ar"

    def discover_article_urls(self, limit: int = 25) -> list[str]:
        """Discover Hespress article URLs from the homepage."""

        try:
            html = self.fetch(self.base_url)
            soup = BeautifulSoup(html, "lxml")
            discovered: list[str] = []
            seen: set[str] = set()
            for anchor in soup.select("a[href]"):
                href = str(anchor.get("href", "")).strip()
                if not href:
                    continue
                url = self.absolute_url(href).split("#", maxsplit=1)[0]
                if url in seen or not HESPRESS_ARTICLE_PATTERN.match(url):
                    continue
                seen.add(url)
                discovered.append(url)
                if len(discovered) >= limit:
                    break
            logger.info("Discovered %s Hespress article URL(s)", len(discovered))
            return discovered
        except Exception:
            logger.exception("Failed to discover Hespress article URLs")
            raise

    def parse_article(self, html: str, url: str) -> Article:
        """Parse a Hespress article page."""

        try:
            soup = BeautifulSoup(html, "lxml")
            json_ld = self.json_ld_objects(soup)

            title = self._extract_title(soup, json_ld)
            content = self._extract_content(soup, json_ld)
            author = self._extract_author(soup, json_ld)
            published_at = self._extract_published_at(soup, json_ld)
            category = self._extract_category(soup)

            if not title:
                raise ValueError(f"Hespress article has no title: {url}")
            if not content:
                raise ValueError(f"Hespress article has no content: {url}")

            return Article(
                title=title,
                author=author,
                published_at=published_at,
                category=category,
                content=content,
                source=self.source_name,
                url=url,
                language=self.language_hint,
                country=self.country,
            )
        except Exception:
            logger.exception("Failed to parse Hespress article: %s", url)
            raise

    def _extract_title(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract the article title from JSON-LD, metadata, or heading tags."""

        try:
            json_title = self.first_json_ld_value(json_ld, "headline", "name")
            if isinstance(json_title, str) and json_title.strip():
                return self.clean_text(json_title)
            return (
                self.meta_content(soup, "og:title", "twitter:title")
                or self.first_text(
                    soup,
                    (
                        "h1.article-title",
                        "h1.entry-title",
                        "article h1",
                        "h1",
                    ),
                )
            )
        except Exception:
            logger.exception("Failed to extract Hespress title")
            raise

    def _extract_author(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract the article author or publisher label."""

        try:
            author = self.first_json_ld_value(json_ld, "author")
            if isinstance(author, dict):
                author_name = author.get("name")
                if isinstance(author_name, str):
                    return self.clean_text(author_name)
            if isinstance(author, list):
                names = [item.get("name") for item in author if isinstance(item, dict)]
                joined_names = ", ".join(name for name in names if isinstance(name, str))
                if joined_names:
                    return self.clean_text(joined_names)
            if isinstance(author, str):
                return self.clean_text(author)
            return self.meta_content(soup, "author") or self.first_text(
                soup,
                (
                    ".author",
                    ".post-author",
                    ".article-author",
                    "[rel='author']",
                ),
            )
        except Exception:
            logger.exception("Failed to extract Hespress author")
            raise

    def _extract_published_at(
        self,
        soup: BeautifulSoup,
        json_ld: list[dict[str, Any]],
    ) -> datetime | None:
        """Extract the publication timestamp when available."""

        try:
            candidate = self.first_json_ld_value(json_ld, "datePublished", "dateCreated")
            if not candidate:
                candidate = self.meta_content(
                    soup,
                    "article:published_time",
                    "datePublished",
                    "pubdate",
                )
            if not candidate:
                time_node = soup.select_one("time[datetime]")
                candidate = str(time_node.get("datetime")) if time_node else None
            if isinstance(candidate, str) and candidate.strip():
                return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return None
        except ValueError:
            logger.warning("Could not parse Hespress published_at value: %s", candidate)
            return None
        except Exception:
            logger.exception("Failed to extract Hespress published_at")
            raise

    def _extract_category(self, soup: BeautifulSoup) -> str | None:
        """Extract the article category from metadata or breadcrumbs."""

        try:
            metadata_category = self.meta_content(soup, "article:section")
            if metadata_category:
                return metadata_category
            breadcrumb_links = soup.select(".breadcrumb a, nav[aria-label='breadcrumb'] a")
            for node in reversed(breadcrumb_links):
                text = self.clean_text(node.get_text(" ", strip=True))
                href = str(node.get("href", "")).rstrip("/")
                if text and href != self.base_url.rstrip("/"):
                    return text
            return None
        except Exception:
            logger.exception("Failed to extract Hespress category")
            raise

    def _extract_content(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract and normalize article body content."""

        try:
            article_body = self.first_json_ld_value(json_ld, "articleBody")
            if isinstance(article_body, str) and article_body.strip():
                return self.clean_text(article_body)

            selectors = (
                "article .article-content p",
                "article .entry-content p",
                "article .post-content p",
                ".article-content p",
                ".entry-content p",
                ".post-content p",
                "article p",
            )
            for selector in selectors:
                paragraphs = [
                    self.clean_text(node.get_text(" ", strip=True))
                    for node in soup.select(selector)
                ]
                content = " ".join(text for text in paragraphs if text)
                normalized = self.clean_text(content)
                if normalized:
                    return normalized
            return None
        except Exception:
            logger.exception("Failed to extract Hespress content")
            raise
