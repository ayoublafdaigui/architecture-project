"""Source-specific scraper classes for MediaPulse target publishers."""

from __future__ import annotations

import re

from mediapulse.scrapers.generic import GenericArticleScraper


class AkhbaronaScraper(GenericArticleScraper):
    """Scraper for Akhbarona."""

    source_name = "Akhbarona"
    base_url = "https://www.akhbarona.com/"
    country = "MA"
    language_hint = "ar"
    article_url_patterns = (re.compile(r"akhbarona\.com/.+\.html$"),)


class BarlamaneScraper(GenericArticleScraper):
    """Scraper for Barlamane."""

    source_name = "Barlamane"
    base_url = "https://www.barlamane.com/"
    country = "MA"
    language_hint = "ar"
    article_url_patterns = (re.compile(r"barlamane\.com/.+/(20\d{2}|[0-9]{4,})"),)


class LakomScraper(GenericArticleScraper):
    """Scraper for Lakom."""

    source_name = "Lakom"
    base_url = "https://lakome2.com/"
    country = "MA"
    language_hint = "ar"
    article_url_patterns = (re.compile(r"lakome2\.com/.+/\d+/?$"),)


class AlJazeeraScraper(GenericArticleScraper):
    """Scraper for Al Jazeera English."""

    source_name = "Al Jazeera"
    base_url = "https://www.aljazeera.com/"
    country = "QA"
    language_hint = "en"
    article_url_patterns = (re.compile(r"aljazeera\.com/(news|features|economy|sports)/20\d{2}/"),)


class BBCNewsScraper(GenericArticleScraper):
    """Scraper for BBC News."""

    source_name = "BBC News"
    base_url = "https://www.bbc.com/news"
    country = "GB"
    language_hint = "en"
    article_url_patterns = (re.compile(r"bbc\.com/news/.+"),)


class CNNScraper(GenericArticleScraper):
    """Scraper for CNN."""

    source_name = "CNN"
    base_url = "https://www.cnn.com/"
    country = "US"
    language_hint = "en"
    article_url_patterns = (re.compile(r"cnn\.com/20\d{2}/\d{2}/\d{2}/"),)


class ReutersScraper(GenericArticleScraper):
    """Scraper for Reuters."""

    source_name = "Reuters"
    base_url = "https://www.reuters.com/"
    country = "GB"
    language_hint = "en"
    article_url_patterns = (re.compile(r"reuters\.com/.+/20\d{2}/"),)


SCRAPER_REGISTRY = {
    "akhbarona": AkhbaronaScraper,
    "barlamane": BarlamaneScraper,
    "lakom": LakomScraper,
    "aljazeera": AlJazeeraScraper,
    "bbc": BBCNewsScraper,
    "cnn": CNNScraper,
    "reuters": ReutersScraper,
}
