"""Generic source scraper for news sites with JSON-LD/OpenGraph metadata."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from mediapulse.models.article import Article
from mediapulse.scrapers.base import BaseNewsScraper

logger = logging.getLogger(__name__)


class GenericArticleScraper(BaseNewsScraper):
    """Reusable scraper for news sites that expose standard article metadata."""

    article_url_patterns: tuple[re.Pattern[str], ...] = ()
    excluded_path_fragments: tuple[str, ...] = (
        "/tag/",
        "/tags/",
        "/category/",
        "/categories/",
        "/author/",
        "/authors/",
        "/video/",
        "/videos/",
        "/live/",
        "/privacy",
        "/terms",
        "/about",
        "/contact",
    )

    def discover_article_urls(self, limit: int = 25) -> list[str]:
        """Discover article URLs from the source homepage."""

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
                if url in seen or not self._looks_like_article_url(url):
                    continue
                seen.add(url)
                discovered.append(url)
                if len(discovered) >= limit:
                    break
            logger.info("Discovered %s article URL(s) for %s", len(discovered), self.source_name)
            return discovered
        except Exception:
            logger.exception("Failed to discover article URLs for %s", self.source_name)
            raise

    def parse_article(self, html: str, url: str) -> Article:
        """Parse an article page into the canonical Article model."""

        try:
            soup = BeautifulSoup(html, "lxml")
            json_ld = self.json_ld_objects(soup)
            title = self._extract_title(soup, json_ld)
            content = self._extract_content(soup, json_ld)
            if not title:
                raise ValueError(f"{self.source_name} article has no title: {url}")
            if not content:
                raise ValueError(f"{self.source_name} article has no content: {url}")

            return Article(
                title=title,
                author=self._extract_author(soup, json_ld),
                published_at=self._extract_published_at(soup, json_ld),
                category=self._extract_category(soup, json_ld),
                content=content,
                source=self.source_name,
                url=url,
                language=self.language_hint,
                country=self.country,
            )
        except Exception:
            logger.exception("Failed to parse article for %s: %s", self.source_name, url)
            raise

    def _looks_like_article_url(self, url: str) -> bool:
        """Heuristically decide whether a URL is likely an article page."""

        try:
            parsed_base = urlparse(self.base_url)
            parsed_url = urlparse(url)
            if parsed_base.netloc.replace("www.", "") != parsed_url.netloc.replace("www.", ""):
                return False
            path = parsed_url.path.rstrip("/")
            if not path or any(fragment in path for fragment in self.excluded_path_fragments):
                return False
            if self.article_url_patterns and any(pattern.search(url) for pattern in self.article_url_patterns):
                return True
            return bool(re.search(r"/(20\d{2}|news|article|world|business|politics|sport|culture)/", path))
        except Exception:
            logger.exception("Failed to evaluate article URL: %s", url)
            raise

    def _extract_title(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract article title."""

        try:
            json_title = self.first_json_ld_value(json_ld, "headline", "name")
            if isinstance(json_title, str) and json_title.strip():
                return self.clean_text(json_title)
            return self.meta_content(soup, "og:title", "twitter:title") or self.first_text(
                soup,
                ("article h1", "main h1", "h1"),
            )
        except Exception:
            logger.exception("Failed to extract title for %s", self.source_name)
            raise

    def _extract_author(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract article author."""

        try:
            author = self.first_json_ld_value(json_ld, "author", "creator")
            if isinstance(author, dict):
                return self.clean_text(str(author.get("name") or "")) or None
            if isinstance(author, list):
                names = [item.get("name") for item in author if isinstance(item, dict)]
                return self.clean_text(", ".join(str(name) for name in names if name)) or None
            if isinstance(author, str):
                return self.clean_text(author)
            return self.meta_content(soup, "author", "article:author") or self.first_text(
                soup,
                (".author", "[rel='author']", "[data-testid*='author']"),
            )
        except Exception:
            logger.exception("Failed to extract author for %s", self.source_name)
            raise

    def _extract_published_at(
        self,
        soup: BeautifulSoup,
        json_ld: list[dict[str, Any]],
    ) -> datetime | None:
        """Extract publication timestamp."""

        try:
            candidate = self.first_json_ld_value(json_ld, "datePublished", "dateCreated")
            if not candidate:
                candidate = self.meta_content(
                    soup,
                    "article:published_time",
                    "datePublished",
                    "pubdate",
                    "sailthru.date",
                )
            if not candidate:
                time_node = soup.select_one("time[datetime]")
                candidate = str(time_node.get("datetime")) if time_node else None
            if isinstance(candidate, str) and candidate.strip():
                return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return None
        except ValueError:
            logger.warning("Could not parse publication timestamp for %s: %s", self.source_name, candidate)
            return None
        except Exception:
            logger.exception("Failed to extract published_at for %s", self.source_name)
            raise

    def _extract_category(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract source article category."""

        try:
            section = self.first_json_ld_value(json_ld, "articleSection")
            if isinstance(section, str):
                return self.clean_text(section)
            return self.meta_content(soup, "article:section", "section") or self.first_text(
                soup,
                (".breadcrumb a:last-child", "nav[aria-label='breadcrumb'] a:last-child"),
            )
        except Exception:
            logger.exception("Failed to extract category for %s", self.source_name)
            raise

    def _extract_content(self, soup: BeautifulSoup, json_ld: list[dict[str, Any]]) -> str | None:
        """Extract article content text."""

        try:
            article_body = self.first_json_ld_value(json_ld, "articleBody")
            if isinstance(article_body, str) and article_body.strip():
                return self.clean_text(article_body)

            selectors = (
                "article [data-component='text-block'] p",
                "article [data-testid*='paragraph']",
                "article .article-body p",
                "article .entry-content p",
                "article .post-content p",
                "main article p",
                "article p",
                "main p",
            )
            for selector in selectors:
                paragraphs = [
                    self.clean_text(node.get_text(" ", strip=True))
                    for node in soup.select(selector)
                ]
                content = self.clean_text(" ".join(text for text in paragraphs if text))
                if content and len(content) > 100:
                    return content
            return None
        except Exception:
            logger.exception("Failed to extract content for %s", self.source_name)
            raise
