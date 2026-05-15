"""Operator command line interface for MediaPulse."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import runpy
import subprocess
import sys
from pathlib import Path

from mediapulse.core.logging import configure_logging

logger = logging.getLogger(__name__)


def run_module(module_name: str, args: list[str]) -> None:
    """Run a Python module with delegated CLI arguments."""

    try:
        original_argv = sys.argv[:]
        sys.argv = [module_name, *args]
        runpy.run_module(module_name, run_name="__main__")
    except Exception:
        logger.exception("MediaPulse delegated command failed: %s", module_name)
        raise
    finally:
        sys.argv = original_argv


def command_doctor(_: argparse.Namespace) -> None:
    """Run local project health checks."""

    try:
        required_modules = [
            "pydantic",
            "kafka",
            "minio",
            "psycopg",
            "bs4",
            "langdetect",
            "spacy",
        ]
        print("MediaPulse doctor")
        for module_name in required_modules:
            status = "ok" if importlib.util.find_spec(module_name) else "missing"
            print(f"  dependency {module_name}: {status}")

        project_root = Path(__file__).resolve().parent
        compose_file = project_root / "docker-compose.yml"
        env_example = project_root / ".env.example"
        print(f"  compose file: {'ok' if compose_file.exists() else 'missing'}")
        print(f"  env example: {'ok' if env_example.exists() else 'missing'}")

        if compose_file.exists():
            result = subprocess.run(
                ["docker", "compose", "--env-file", ".env.example", "config"],
                cwd=project_root,
                check=False,
                capture_output=True,
                text=True,
            )
            print(f"  docker compose config: {'ok' if result.returncode == 0 else 'failed'}")
            if result.returncode != 0:
                print(result.stderr.strip())
    except Exception:
        logger.exception("Doctor command failed")
        raise


def command_seed_demo(args: argparse.Namespace) -> None:
    """Seed demo data."""

    run_module(
        "mediapulse.demo.seed_demo",
        [
            "--days",
            str(args.days),
            "--articles-per-day",
            str(args.articles_per_day),
            "--seed",
            str(args.seed),
        ],
    )


def command_scrape(args: argparse.Namespace) -> None:
    """Run batch scraping."""

    delegated_args: list[str] = []
    for source in args.source or []:
        delegated_args.extend(["--source", source])
    if args.limit is not None:
        delegated_args.extend(["--limit", str(args.limit)])
    run_module("mediapulse.ingestion.run_batch_scrape", delegated_args)


def command_bronze_to_silver(args: argparse.Namespace) -> None:
    """Run Bronze to Silver transformation."""

    delegated_args: list[str] = []
    if args.source:
        delegated_args.extend(["--source", args.source])
    if args.limit is not None:
        delegated_args.extend(["--limit", str(args.limit)])
    run_module("mediapulse.transform.bronze_to_silver", delegated_args)


def command_silver_to_gold(args: argparse.Namespace) -> None:
    """Run Silver to Gold aggregation."""

    delegated_args: list[str] = []
    if args.source:
        delegated_args.extend(["--source", args.source])
    if args.limit is not None:
        delegated_args.extend(["--limit", str(args.limit)])
    run_module("mediapulse.transform.silver_to_gold", delegated_args)


def command_load_warehouse(args: argparse.Namespace) -> None:
    """Load the PostgreSQL warehouse."""

    delegated_args: list[str] = []
    if args.silver_limit is not None:
        delegated_args.extend(["--silver-limit", str(args.silver_limit)])
    if args.skip_gold:
        delegated_args.append("--skip-gold")
    run_module("mediapulse.warehouse.load_warehouse", delegated_args)


def command_apply_schema(_: argparse.Namespace) -> None:
    """Apply warehouse schema files."""

    run_module("mediapulse.warehouse.apply_schema", [])


def command_quality(args: argparse.Namespace) -> None:
    """Run data quality checks."""

    delegated_args = ["--layer", args.layer]
    if args.no_write_db:
        delegated_args.append("--no-write-db")
    run_module("mediapulse.quality.data_quality", delegated_args)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the MediaPulse operator CLI parser."""

    try:
        parser = argparse.ArgumentParser(description="MediaPulse operator CLI")
        subparsers = parser.add_subparsers(dest="command", required=True)

        doctor = subparsers.add_parser("doctor", help="Check local environment health")
        doctor.set_defaults(func=command_doctor)

        seed_demo = subparsers.add_parser("seed-demo", help="Seed warehouse demo data")
        seed_demo.add_argument("--days", type=int, default=14)
        seed_demo.add_argument("--articles-per-day", type=int, default=16)
        seed_demo.add_argument("--seed", type=int, default=42)
        seed_demo.set_defaults(func=command_seed_demo)

        scrape = subparsers.add_parser("scrape", help="Run batch scraping")
        scrape.add_argument("--source", action="append")
        scrape.add_argument("--limit", type=int, default=None)
        scrape.set_defaults(func=command_scrape)

        bronze_to_silver = subparsers.add_parser("bronze-to-silver", help="Run Bronze to Silver")
        bronze_to_silver.add_argument("--source", default=None)
        bronze_to_silver.add_argument("--limit", type=int, default=None)
        bronze_to_silver.set_defaults(func=command_bronze_to_silver)

        silver_to_gold = subparsers.add_parser("silver-to-gold", help="Run Silver to Gold")
        silver_to_gold.add_argument("--source", default=None)
        silver_to_gold.add_argument("--limit", type=int, default=None)
        silver_to_gold.set_defaults(func=command_silver_to_gold)

        load = subparsers.add_parser("load-warehouse", help="Load PostgreSQL warehouse")
        load.add_argument("--silver-limit", type=int, default=None)
        load.add_argument("--skip-gold", action="store_true")
        load.set_defaults(func=command_load_warehouse)

        apply_schema = subparsers.add_parser("apply-schema", help="Apply warehouse schema files")
        apply_schema.set_defaults(func=command_apply_schema)

        quality = subparsers.add_parser("quality", help="Run data quality checks")
        quality.add_argument("--layer", choices=["silver", "gold"], default="silver")
        quality.add_argument("--no-write-db", action="store_true")
        quality.set_defaults(func=command_quality)

        return parser
    except Exception:
        logger.exception("Failed to build MediaPulse CLI parser")
        raise


def main() -> None:
    """Run the MediaPulse operator CLI."""

    configure_logging()
    try:
        args = build_arg_parser().parse_args()
        args.func(args)
    except Exception:
        logger.exception("MediaPulse CLI failed")
        raise


if __name__ == "__main__":
    main()
