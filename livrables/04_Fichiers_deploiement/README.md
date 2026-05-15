# Livrable 4 — Fichiers de Déploiement

## Fichiers

| Fichier | Description |
|---------|-------------|
| [`docker-compose.yml`](docker-compose.yml) | Stack complet Docker Compose (18 services) |
| [`Dockerfile`](Dockerfile) | Image Python scraper/pipeline |
| [`Dockerfile.airflow`](Dockerfile.airflow) | Image Airflow customisée |
| [`kubernetes/`](kubernetes/) | Manifestes Kubernetes (déploiement production) |
| [`guide_deploiement.md`](guide_deploiement.md) | Guide de déploiement Docker et Kubernetes |

---

## Services Docker Compose

| Service | Image | Port | Rôle |
|---------|-------|------|------|
| zookeeper | cp-zookeeper:7.6.1 | 2181 | Coordination Kafka |
| kafka | cp-kafka:7.6.1 | 9092 | Bus de messages |
| minio | minio/minio | 9000, 9001 | Data Lake S3 |
| minio-init | minio/mc | — | Init bucket |
| postgres | postgres:16 | 5432 | Warehouse |
| redis | redis:7-alpine | 6379 | Broker Celery |
| airflow-init | mediapulse-airflow | — | DB migrate + admin |
| airflow-webserver | mediapulse-airflow | 8080 | UI Airflow |
| airflow-scheduler | mediapulse-airflow | — | Planification |
| airflow-worker | mediapulse-airflow | — | Exécution Celery |
| scraper | Dockerfile local | — | Scraping batch |
| stream-consumer | Dockerfile local | — | Consumer Kafka→Bronze |
| warehouse-migrate | Dockerfile local | — | Apply SQL schema |
| metabase | metabase:v0.50.18 | 3000 | Analytics |
| prometheus | prom/prometheus | 9090 | Métriques |
| postgres-exporter | postgres-exporter | 9187 | Export PG metrics |
| kafka-exporter | kafka-exporter | 9308 | Export Kafka metrics |
| grafana | grafana:11.1.0 | 3001 | Dashboards |
