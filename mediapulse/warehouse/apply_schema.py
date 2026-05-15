"""Apply MediaPulse warehouse schema files to an existing PostgreSQL database."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from mediapulse.core.config import PostgresSettings, get_postgres_settings
from mediapulse.core.logging import configure_logging

logger = logging.getLogger(__name__)

SCHEMA_FILES = (
    "02-warehouse-schema.sql",
    "03-dashboard-views.sql",
)


class WarehouseSchemaApplier:
    """Apply idempotent warehouse SQL files."""

    def __init__(self, settings: PostgresSettings, retries: int = 20, retry_delay_seconds: int = 3) -> None:
        """Create a warehouse schema applier."""

        try:
            import psycopg

            self.psycopg = psycopg
            self.settings = settings
            self.retries = retries
            self.retry_delay_seconds = retry_delay_seconds
            self.schema_dir = Path(__file__).resolve().parent / "init"
        except Exception:
            logger.exception("Failed to initialize warehouse schema applier")
            raise

    def run(self) -> None:
        """Apply all schema files in order."""

        try:
            with self.connect_with_retry() as connection:
                for file_name in SCHEMA_FILES:
                    sql_path = self.schema_dir / file_name
                    logger.info("Applying warehouse schema file: %s", sql_path)
                    connection.execute(sql_path.read_text(encoding="utf-8"))
                connection.commit()
            logger.info("Warehouse schema apply complete")
        except Exception:
            logger.exception("Warehouse schema apply failed")
            raise

    def connect_with_retry(self):
        """Connect to PostgreSQL with startup retries."""

        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                return self.psycopg.connect(self.settings.dsn)
            except Exception as exc:
                last_error = exc
                logger.warning("PostgreSQL not ready for schema apply, attempt %s/%s", attempt, self.retries)
                time.sleep(self.retry_delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Could not connect to PostgreSQL")


def build_arg_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""

    try:
        parser = argparse.ArgumentParser(description="Apply MediaPulse warehouse schema")
        parser.add_argument("--retries", type=int, default=20)
        parser.add_argument("--retry-delay-seconds", type=int, default=3)
        return parser
    except Exception:
        logger.exception("Failed to build warehouse schema argument parser")
        raise


def main() -> None:
    """Run the warehouse schema applier."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        WarehouseSchemaApplier(
            settings=get_postgres_settings(),
            retries=args.retries,
            retry_delay_seconds=args.retry_delay_seconds,
        ).run()
    except Exception:
        logger.exception("Warehouse schema CLI failed")
        raise


if __name__ == "__main__":
    main()
