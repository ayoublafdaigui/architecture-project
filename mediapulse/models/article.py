"""Canonical article schema for scraped news records."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

# pyrefly: ignore [missing-import]
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

ISO_639_1_PATTERN = re.compile(r"^[a-z]{2}$")
WHITESPACE_PATTERN = re.compile(r"\s+")


class Article(BaseModel):
    """Validated representation of a press article moving through the pipeline."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    title: str = Field(..., min_length=1, description="Article headline.")
    author: str | None = Field(default=None, description="Article author or agency.")
    published_at: datetime | None = Field(default=None, description="Source publication timestamp.")
    category: str | None = Field(default=None, description="Source category or section.")
    content: str = Field(..., min_length=1, description="Article body text.")
    source: str = Field(..., min_length=1, description="Publisher name.")
    url: AnyHttpUrl = Field(..., description="Canonical article URL.")
    language: str | None = Field(default=None, description="ISO 639-1 language code.")
    scraped_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when MediaPulse scraped the article.",
    )
    country: str | None = Field(default=None, description="ISO 3166-1 alpha-2 source country.")

    @field_validator("title", "content", "source")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Normalize required text fields and reject empty normalized values."""

        try:
            normalized = WHITESPACE_PATTERN.sub(" ", value).strip()
            if not normalized:
                raise ValueError("required article text field cannot be empty")
            return normalized
        except Exception:
            logger.exception("Failed to normalize required article text field")
            raise

    @field_validator("author", "category", "country")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields while preserving missing values."""

        try:
            if value is None:
                return None
            normalized = WHITESPACE_PATTERN.sub(" ", value).strip()
            return normalized or None
        except Exception:
            logger.exception("Failed to normalize optional article text field")
            raise

    @field_validator("language")
    @classmethod
    def validate_language_code(cls, value: str | None) -> str | None:
        """Validate language as an ISO 639-1-like two-letter code when present."""

        try:
            if value is None:
                return None
            normalized = value.strip().lower()
            if not ISO_639_1_PATTERN.match(normalized):
                raise ValueError("language must be a two-letter ISO 639-1 code")
            return normalized
        except Exception:
            logger.exception("Invalid article language code: %s", value)
            raise

    @field_validator("published_at", "scraped_at")
    @classmethod
    def ensure_timezone(cls, value: datetime | None) -> datetime | None:
        """Ensure datetime values are timezone-aware."""

        try:
            if value is None:
                return None
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        except Exception:
            logger.exception("Failed to normalize article datetime")
            raise

    @property
    def url_hash(self) -> str:
        """Return a stable SHA-256 hash of the article URL for partition-safe keys."""

        try:
            return hashlib.sha256(str(self.url).encode("utf-8")).hexdigest()
        except Exception:
            logger.exception("Failed to generate article URL hash")
            raise

    def to_bronze_dict(self) -> dict[str, Any]:
        """Serialize the article as a JSON-ready Bronze layer record."""

        try:
            payload = self.model_dump(mode="json")
            payload["url_hash"] = self.url_hash
            return payload
        except Exception:
            logger.exception("Failed to serialize article for Bronze layer")
            raise
