# Schéma d'Architecture Globale — MediaPulse

## Vue d'ensemble des composants

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                          MEDIAPULSE — ARCHITECTURE                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │                     SOURCES D'ACTUALITÉ (8)                          │   ║
║  │                                                                      │   ║
║  │  [Hespress]  [Akhbarona]  [Barlamane]  [Lakom]   ← Maroc (AR)       │   ║
║  │  [Al Jazeera]  [BBC News]  [CNN]  [Reuters]       ← International    │   ║
║  └──────────────────────┬───────────────────────────────────────────────┘   ║
║                         │  HTTP GET / HTML parsing                          ║
║  ┌──────────────────────▼───────────────────────────────────────────────┐   ║
║  │                   COUCHE INGESTION                                   │   ║
║  │                                                                      │   ║
║  │  GenericArticleScraper ──► Pydantic Article ──► KafkaProducer       │   ║
║  │  (BeautifulSoup4/lxml)     (validation stricte)   (raw-articles)    │   ║
║  │                                    │                                 │   ║
║  │                                    └──► BronzeWriter (batch direct) │   ║
║  └──────────────────────┬───────────────────────────────────────────────┘   ║
║                         │  JSON messages                                    ║
║  ┌──────────────────────▼───────────────────────────────────────────────┐   ║
║  │                   COUCHE STREAMING                                   │   ║
║  │                                                                      │   ║
║  │  ┌─────────────────────────────────────────────┐                    │   ║
║  │  │  Apache Kafka (Confluent 7.6)               │                    │   ║
║  │  │  Zookeeper ◄── coordination                 │                    │   ║
║  │  │  Topic: raw-articles (replication_factor=1) │                    │   ║
║  │  └──────────────────────┬──────────────────────┘                    │   ║
║  │                         │                                            │   ║
║  │                  KafkaConsumer (micro-batch=50)                      │   ║
║  └──────────────────────┬───────────────────────────────────────────────┘   ║
║                         │  JSON objects                                     ║
║  ┌──────────────────────▼───────────────────────────────────────────────┐   ║
║  │                   DATA LAKE — MinIO (S3-compatible)                  │   ║
║  │                                                                      │   ║
║  │  ┌─────────────────────────────────────────────────────────────┐    │   ║
║  │  │  🥉 BRONZE — Données brutes immuables                        │    │   ║
║  │  │  Path: bronze/source={src}/date={date}/{url_hash}.json      │    │   ║
║  │  └───────────────────────────┬─────────────────────────────────┘    │   ║
║  │                              │  BronzeToSilverPipeline               │   ║
║  │                              │  • HTML strip (BeautifulSoup)         │   ║
║  │                              │  • Unicode NFKC normalization         │   ║
║  │                              │  • langdetect (ar/en/fr)              │   ║
║  │                              │  • SHA-256 URL deduplication          │   ║
║  │                              │  • 6 règles qualité                   │   ║
║  │                              ▼                                        │   ║
║  │  ┌─────────────────────────────────────────────────────────────┐    │   ║
║  │  │  🥈 SILVER — Données nettoyées et validées                   │    │   ║
║  │  │  Path: silver/source={src}/date={date}/{url_hash}.json      │    │   ║
║  │  │  Rejected: silver/_rejected/date={date}/{url_hash}.json     │    │   ║
║  │  └───────────────────────────┬─────────────────────────────────┘    │   ║
║  │                              │  SilverToGoldPipeline                 │   ║
║  │                              │  • TF-IDF top-50 keywords             │   ║
║  │                              │  • Tendances quotidiennes             │   ║
║  │                              │  • Comptages par source/pays          │   ║
║  │                              ▼                                        │   ║
║  │  ┌─────────────────────────────────────────────────────────────┐    │   ║
║  │  │  🥇 GOLD — Agrégats analytiques                              │    │   ║
║  │  │  Path: gold/table={table}/run_date={date}/data.json         │    │   ║
║  │  └─────────────────────────────────────────────────────────────┘    │   ║
║  └──────────────────────┬───────────────────────────────────────────────┘   ║
║                         │  WarehouseLoader                                  ║
║  ┌──────────────────────▼───────────────────────────────────────────────┐   ║
║  │               ENTREPÔT DE DONNÉES — PostgreSQL 16                   │   ║
║  │                                                                      │   ║
║  │  DIMENSIONS          FAITS                    QUALITÉ               │   ║
║  │  ┌──────────┐    ┌──────────────────┐    ┌─────────────────┐        │   ║
║  │  │dim_source│───►│  fact_articles   │    │ quality_report  │        │   ║
║  │  └──────────┘    │  (table centrale)│    └─────────────────┘        │   ║
║  │  ┌──────────┐    └──────────────────┘                               │   ║
║  │  │ dim_date │───►┌────────────────────────┐                         │   ║
║  │  └──────────┘    │ fact_keyword_frequency │                         │   ║
║  │  ┌────────────┐  └────────────────────────┘                         │   ║
║  │  │dim_category│►┌──────────────────┐                                │   ║
║  │  └────────────┘ │fact_daily_trends │                                 │   ║
║  │                 └──────────────────┘                                 │   ║
║  └──────────────────────┬───────────────────────────────────────────────┘   ║
║                         │                                                    ║
║         ┌───────────────┼───────────────────┐                               ║
║         │               │                   │                               ║
║  ┌──────▼──────┐  ┌─────▼──────┐  ┌────────▼────────┐                      ║
║  │   GRAFANA   │  │  METABASE  │  │   PROMETHEUS    │                      ║
║  │  Port 3001  │  │  Port 3000 │  │   Port 9090     │                      ║
║  │  Dashboards │  │ Self-serv. │  │ postgres-export  │                      ║
║  │  provisionnés│  │ analytics  │  │ kafka-exporter  │                      ║
║  └─────────────┘  └────────────┘  └─────────────────┘                      ║
║                                                                              ║
║  ┌──────────────────────────────────────────────────────────────────────┐   ║
║  │              ORCHESTRATION — Apache Airflow 2.9.3                   │   ║
║  │                                                                      │   ║
║  │  dag_batch_scrape ──► dag_bronze_to_silver ──► dag_silver_to_gold   │   ║
║  │         └──────────────────────────────► dag_load_warehouse         │   ║
║  │                                              └──► dag_data_quality  │   ║
║  │                                                                      │   ║
║  │  CeleryExecutor ← Redis broker ← airflow-worker                     │   ║
║  └──────────────────────────────────────────────────────────────────────┘   ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

## Réseaux et volumes Docker

```
Réseau bridge : mediapulse-net (tous les services)

Volumes persistants :
  kafka-data      → /var/lib/kafka/data
  minio-data      → /data
  postgres-data   → /var/lib/postgresql/data
  airflow-logs    → /opt/airflow/logs
  grafana-data    → /var/lib/grafana
  prometheus-data → /prometheus
  metabase-data   → /metabase-data
```
