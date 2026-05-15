# MediaPulse

MediaPulse is a containerized news intelligence platform for scraping, streaming,
storing, transforming, and visualizing press articles from Moroccan and global
news sources.

This first implementation slice includes:

- A Pydantic `Article` model.
- One scraper class per requested source: Hespress, Akhbarona, Barlamane,
  Lakom, Al Jazeera, BBC News, CNN, and Reuters.
- A Kafka producer for the `raw-articles` topic.
- A MinIO Bronze writer with paths like
  `s3://mediapulse/bronze/source=hespress/date=YYYY-MM-DD/<url_hash>.json`.
- A Bronze to Silver transformation pipeline with HTML stripping, whitespace and
  encoding normalization, language detection, URL-hash deduplication, and
  rejected-record capture.
- A Kafka stream consumer that writes micro-batches to Bronze.
- A Silver to Gold aggregation pipeline for daily counts, top keywords,
  trending topics, and source-country counts.
- Airflow DAGs for batch scrape, Bronze to Silver, Silver to Gold, warehouse
  loading, and data quality.
- A PostgreSQL warehouse schema under the `warehouse` schema.
- A warehouse loader and data quality reporter.
- A `docker-compose.yml` skeleton for Kafka, MinIO, Postgres, Airflow,
  Metabase, Prometheus, Grafana, and the scraper service.

## Quick Start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Service URLs:

- MinIO console: http://localhost:9001
- Airflow: http://localhost:8080
- Metabase: http://localhost:3000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## Operator CLI

From the parent `scrapingproject` directory:

```powershell
python -m mediapulse doctor
python -m mediapulse apply-schema
python -m mediapulse scrape --source hespress
python -m mediapulse bronze-to-silver --source hespress
python -m mediapulse silver-to-gold
python -m mediapulse load-warehouse
python -m mediapulse quality --layer silver
```

## Demo Mode

To populate the warehouse with presentation-ready demo data:

```powershell
cd mediapulse
docker compose --profile demo up --build demo-seed
```

Then open Grafana at http://localhost:3001 and use the provisioned
`MediaPulse News Intelligence` dashboard.

## Run Batch Ingestion Once

```powershell
python -m mediapulse.ingestion.run_batch_scrape
```

From the parent `scrapingproject` directory, this compatibility command also
works:

```powershell
python -m ingestion.run_batch_scrape
```

To scrape only one source:

```powershell
python -m mediapulse.ingestion.run_batch_scrape --source hespress
```

From Docker Compose:

```powershell
docker compose run --rm scraper
```

## Run Bronze to Silver

```powershell
python -m mediapulse.transform.bronze_to_silver --source hespress
```

From the parent `scrapingproject` directory, this compatibility command also
works:

```powershell
python -m transform.bronze_to_silver --source hespress
```

Accepted records are written to `silver/source=<source>/date=<YYYY-MM-DD>/`.
Rejected records are written to `silver/_rejected/` with quality-rule details.

## Run Silver to Gold

```powershell
python -m mediapulse.transform.silver_to_gold
```

Gold snapshots are written to `gold/table=<table>/run_date=<YYYY-MM-DD>/`.

## Load PostgreSQL Warehouse

```powershell
python -m mediapulse.warehouse.load_warehouse
```

## Run Data Quality Checks

```powershell
python -m mediapulse.quality.data_quality --layer silver
python -m mediapulse.quality.data_quality --layer gold
```

## Dashboards

Grafana is provisioned with:

- PostgreSQL datasource: `MediaPulse Warehouse`
- Prometheus datasource: `Prometheus`
- Dashboard: `MediaPulse News Intelligence`

The dashboard reads from the `warehouse.dashboard_*` views created by
`warehouse/init/03-dashboard-views.sql`.

Prometheus also scrapes:

- PostgreSQL exporter: http://localhost:9187
- Kafka exporter: http://localhost:9308

Alert rules live in `dashboard/prometheus-alerts.yml`.

## Current Source Coverage

Implemented:

- Hespress
- Akhbarona
- Barlamane
- Lakom
- Al Jazeera
- BBC News
- CNN
- Reuters

## Next Layers

The next production components to add are:

- Source selector hardening against each publisher's latest HTML changes.
- Alert rules for stale data and quality-score drops.
