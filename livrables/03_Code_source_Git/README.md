# Livrable 3 — Code Source Versionné sur Git

## Dépôt GitHub

**URL :** https://github.com/ayoublafdaigui/architecture-project  
**Branche principale :** `main`  
**Commits :** 2 (initial + documentation)  
**Fichiers :** 59 fichiers Python, SQL, YAML, JSON, Dockerfile  
**Lignes de code :** ~5 800 lignes  

---

## Structure du code source

```
architecture-project/
│
├── mediapulse/                          # Package Python principal
│   │
│   ├── models/
│   │   └── article.py                  # Modèle Pydantic Article (validation)
│   │
│   ├── scrapers/
│   │   ├── base.py                     # Classe abstraite BaseScraper
│   │   ├── generic.py                  # GenericArticleScraper (crawl + parse)
│   │   ├── hespress.py                 # Scraper spécifique Hespress
│   │   └── sources.py                  # Registry des 8 scrapers + SCRAPER_REGISTRY
│   │
│   ├── ingestion/
│   │   ├── kafka_producer.py           # Producteur Kafka (topic raw-articles)
│   │   ├── kafka_consumer.py           # Consommateur Kafka → Bronze MinIO
│   │   ├── run_batch_scrape.py         # Entrée CLI scrape batch
│   │   └── run_hespress_pipeline.py    # Pipeline Hespress standalone
│   │
│   ├── datalake/
│   │   └── bronze_writer.py            # Écriture partitionnée dans MinIO
│   │
│   ├── transform/
│   │   ├── bronze_to_silver.py         # Pipeline B→S (nettoyage + validation)
│   │   └── silver_to_gold.py           # Pipeline S→G (agrégation TF-IDF)
│   │
│   ├── warehouse/
│   │   ├── apply_schema.py             # Application du DDL PostgreSQL
│   │   ├── load_warehouse.py           # Chargement Gold → warehouse
│   │   └── init/
│   │       ├── 01-create-service-databases.sql  # Création BDs (airflow, metabase)
│   │       ├── 02-warehouse-schema.sql           # DDL schéma en étoile
│   │       └── 03-dashboard-views.sql            # Vues SQL pour Grafana
│   │
│   ├── quality/
│   │   └── data_quality.py             # Rapport de qualité par couche
│   │
│   ├── airflow/dags/
│   │   ├── dag_batch_scrape.py         # DAG scraping batch
│   │   ├── dag_bronze_to_silver.py     # DAG transformation B→S
│   │   ├── dag_silver_to_gold.py       # DAG agrégation S→G
│   │   ├── dag_load_warehouse.py       # DAG chargement warehouse
│   │   └── dag_data_quality.py         # DAG contrôle qualité
│   │
│   ├── demo/
│   │   └── seed_demo.py                # Générateur de données de démonstration
│   │
│   ├── dashboard/
│   │   ├── prometheus.yml              # Config scrape Prometheus
│   │   ├── prometheus-alerts.yml       # Règles d'alerte
│   │   └── grafana/provisioning/
│   │       ├── datasources/datasources.yml
│   │       ├── dashboards/dashboards.yml
│   │       └── dashboards/mediapulse-overview.json  # Dashboard JSON
│   │
│   ├── core/
│   │   ├── config.py                   # Settings (Kafka, MinIO, Postgres, Scraper)
│   │   └── logging.py                  # Configuration logging
│   │
│   ├── web/
│   │   └── app.py                      # Application web légère
│   │
│   ├── tests/
│   │   ├── test_article_model.py
│   │   ├── test_bronze_to_silver.py
│   │   ├── test_silver_to_gold.py
│   │   └── test_demo_seed.py
│   │
│   ├── cli.py                          # CLI operator (python -m mediapulse <cmd>)
│   ├── __main__.py                     # Point d'entrée python -m mediapulse
│   ├── requirements.txt                # Dépendances Python
│   ├── Dockerfile                      # Image scraper/pipeline
│   ├── Dockerfile.airflow              # Image Airflow custom
│   ├── docker-compose.yml              # Stack complet 18 services
│   ├── .env.example                    # Template variables d'environnement
│   └── README.md                       # Documentation utilisateur
│
├── livrables/                          # Ce dossier (livrables du projet)
├── MediaPulse_Documentation.html       # Documentation complète (→ PDF)
├── Projet_architecture_de_donnee.pdf   # PDF architecture initial
└── .gitignore                          # .venv, __pycache__, .env exclus
```

---

## Modules clés — Description

### `models/article.py`
Modèle Pydantic central. Valide tous les champs dès l'ingestion :
- `url` : AnyHttpUrl
- `language` : regex ISO 639-1 (`^[a-z]{2}$`)
- `published_at` / `scraped_at` : timezone-aware UTC
- `url_hash` : property SHA-256 pour partitionnement

### `scrapers/generic.py`
Scraper générique basé sur des patterns regex d'URL. Chaque source hérite de `GenericArticleScraper` et définit `source_name`, `base_url`, `country`, `language_hint`, `article_url_patterns`.

### `transform/bronze_to_silver.py`
Pipeline de nettoyage avec 6 fonctions pures testables :
`strip_html_tags`, `normalize_encoding_and_whitespace`, `detect_article_language`, `compute_url_hash`, `parse_datetime_to_utc_iso`, `validate_silver_record`

### `transform/silver_to_gold.py`
Tokenisation multilingue avec support arabe (`[\w؀-ۿ]{3,}`), calcul TF-IDF maison, agrégation pandas.

### `cli.py`
CLI opérateur avec 8 commandes : `doctor`, `apply-schema`, `scrape`, `bronze-to-silver`, `silver-to-gold`, `load-warehouse`, `quality`, `seed-demo`.
