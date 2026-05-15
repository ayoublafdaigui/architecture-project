"""News scraper implementations, one class per source."""

from mediapulse.scrapers.hespress import HespressScraper
from mediapulse.scrapers.sources import (
    AkhbaronaScraper,
    AlJazeeraScraper,
    BarlamaneScraper,
    BBCNewsScraper,
    CNNScraper,
    LakomScraper,
    ReutersScraper,
)

__all__ = [
    "AkhbaronaScraper",
    "AlJazeeraScraper",
    "BarlamaneScraper",
    "BBCNewsScraper",
    "CNNScraper",
    "HespressScraper",
    "LakomScraper",
    "ReutersScraper",
]
