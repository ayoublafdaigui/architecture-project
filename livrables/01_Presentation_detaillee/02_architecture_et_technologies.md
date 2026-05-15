# Architecture et Choix Technologiques — MediaPulse

## 1. Vue d'ensemble de l'architecture

MediaPulse implémente le pattern **Architecture Medallion** (Bronze / Silver / Gold)
sur un data lake MinIO, avec un bus de messages Kafka pour le streaming,
Apache Airflow pour l'orchestration et PostgreSQL comme entrepôt analytique.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOURCES EXTERNES                          │
│  Hespress  Akhbarona  Barlamane  Lakom  AlJazeera  BBC  CNN  Reuters │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / HTML
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     COUCHE INGESTION                             │
│  Scraper Service (Python/BeautifulSoup)  ──►  Kafka Producer    │
│  Pydantic Article Model (validation)          topic: raw-articles│
└───────────────────────────┬─────────────────────────────────────┘
                            │ Kafka messages
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  COUCHE STREAMING (Kafka)                        │
│  Apache Kafka (Confluent 7.6)  ──►  Kafka Consumer              │
│  Zookeeper (coordination)             (micro-batch writer)       │
└───────────────────────────┬─────────────────────────────────────┘
                            │ JSON objects
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               DATA LAKE — MinIO (S3-compatible)                  │
│                                                                   │
│  🥉 BRONZE   bronze/source=X/date=YYYY-MM-DD/<url_hash>.json    │
│     ↓  (HTML strip, Unicode normalization, langdetect, dedup)    │
│  🥈 SILVER   silver/source=X/date=YYYY-MM-DD/<url_hash>.json    │
│              silver/_rejected/  ← records invalides              │
│     ↓  (TF-IDF keywords, daily trends, source counts)            │
│  🥇 GOLD     gold/table=X/run_date=YYYY-MM-DD/data.json         │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Gold aggregates
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│             ENTREPÔT DE DONNÉES — PostgreSQL 16                  │
│  dim_source  dim_date  dim_category                              │
│  fact_articles  fact_keyword_frequency  fact_daily_trends        │
│  quality_report                                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          ▼                 ▼                  ▼
   ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
   │   Grafana   │  │  Metabase   │  │  Prometheus  │
   │  Dashboards │  │  Analytics  │  │  + Alerting  │
   └─────────────┘  └─────────────┘  └──────────────┘

         Orchestration : Apache Airflow (5 DAGs)
```

---

## 2. Choix technologiques justifiés

### Ingestion et Streaming

| Technologie | Version | Justification |
|-------------|---------|---------------|
| **Python** | 3.11 | Riche écosystème scraping, NLP, data. Typage strict avec Pydantic. |
| **Apache Kafka** | Confluent 7.6 | Découplage producteur/consommateur, durabilité, replay possible. Indispensable pour haute fréquence. |
| **Pydantic v2** | 2.8.2 | Validation stricte dès l'ingestion : URL, ISO 639-1, timestamps UTC, longueur contenu. |
| **BeautifulSoup4 + lxml** | 4.12 / 5.2 | Parsing HTML robuste, tolérant aux malformations fréquentes sur les sites d'info. |
| **requests** | 2.32 | Client HTTP simple, timeout configurable, headers personnalisables par source. |

### Stockage des Données

| Technologie | Version | Justification |
|-------------|---------|---------------|
| **MinIO** | 2024-07 | Compatible API S3, on-premise, partitionnement par `source` et `date` pour scans sélectifs. |
| **PostgreSQL** | 16 | Schéma en étoile, extension `pgcrypto`, vues SQL pré-calculées pour dashboards. |
| **Redis** | 7-alpine | Broker léger pour Celery Executor Airflow. Faible latence en développement. |

### Pipeline de Transformation

| Technologie | Version | Justification |
|-------------|---------|---------------|
| **langdetect** | 1.0.9 | Détection automatique arabe/anglais/français. Seed fixe pour reproductibilité. |
| **spaCy** | 3.7.5 | Tokenisation multilingue, support bloc Unicode arabe (U+0600–U+06FF). |
| **pandas** | 2.2.2 | Agrégation Silver→Gold : comptages, TF-IDF, tendances journalières. |
| **python-dateutil** | 2.9 | Parsing de dates tous formats, conversion systématique en UTC. |

### Orchestration et Visualisation

| Technologie | Version | Justification |
|-------------|---------|---------------|
| **Apache Airflow** | 2.9.3 | 5 DAGs versionnés dans le repo. CeleryExecutor pour scalabilité horizontale. |
| **Grafana** | 11.1.0 | Dashboard provisionné automatiquement en JSON. Datasource PostgreSQL + Prometheus. |
| **Prometheus** | 2.53.1 | Scrape postgres-exporter + kafka-exporter. Alertes pour données périmées et baisses de qualité. |
| **Metabase** | 0.50.18 | Interface no-code pour équipes métier non-techniques. |

---

## 3. Architecture Medallion — Détail des couches

| Couche | Chemin MinIO | Format | Rôle |
|--------|-------------|--------|------|
| 🥉 **Bronze** | `bronze/source=X/date=YYYY-MM-DD/<hash>.json` | JSON brut | Donnée telle que scrapée, immuable. Source de vérité. |
| 🥈 **Silver** | `silver/source=X/date=YYYY-MM-DD/<hash>.json` | JSON nettoyé | HTML strippé, encodage normalisé, langue détectée, dédupliqué. |
| 🥇 **Gold** | `gold/table=X/run_date=YYYY-MM-DD/data.json` | JSON agrégé | Top keywords TF-IDF, tendances, comptages journaliers. |

---

## 4. Modèle de données Article (Pydantic)

```python
class Article(BaseModel):
    title: str                    # Titre de l'article (min 1 char)
    author: str | None            # Auteur ou agence
    published_at: datetime | None # Timestamp de publication (UTC)
    category: str | None          # Rubrique / section
    content: str                  # Corps de l'article (min 1 char)
    source: str                   # Nom de l'éditeur
    url: AnyHttpUrl               # URL canonique (validée)
    language: str | None          # Code ISO 639-1 (ex: "ar", "en")
    scraped_at: datetime          # Timestamp de scraping (UTC, auto)
    country: str | None           # Code ISO 3166-1 alpha-2 (ex: "MA")
```
