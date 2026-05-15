# Guide d'Utilisation — CLI Opérateur MediaPulse

## Commandes disponibles

Toutes les commandes s'exécutent depuis le répertoire `architecture-project/` :

```
python -m mediapulse <commande> [options]
```

---

## `doctor` — Diagnostic de connectivité

```powershell
python -m mediapulse doctor
```

Vérifie que MinIO, Kafka et PostgreSQL sont accessibles. À exécuter après chaque démarrage.

---

## `apply-schema` — Initialiser le warehouse

```powershell
python -m mediapulse apply-schema
```

Exécute les scripts SQL :
1. `01-create-service-databases.sql` — crée les bases airflow et metabase
2. `02-warehouse-schema.sql` — crée le schéma en étoile + peuple dim_source
3. `03-dashboard-views.sql` — crée les vues pour Grafana

> À exécuter une seule fois. Idempotent (IF NOT EXISTS).

---

## `scrape` — Lancer le scraping

```powershell
# Toutes les sources (8 sources en parallèle)
python -m mediapulse scrape

# Une source spécifique
python -m mediapulse scrape --source hespress
python -m mediapulse scrape --source bbc
python -m mediapulse scrape --source aljazeera

# Sources disponibles :
# hespress, akhbarona, barlamane, lakom, aljazeera, bbc, cnn, reuters
```

Le scraper écrit les articles dans MinIO Bronze :
`bronze/source={source}/date={YYYY-MM-DD}/{url_hash}.json`

---

## `bronze-to-silver` — Nettoyage et validation

```powershell
# Toutes les sources
python -m mediapulse bronze-to-silver

# Une source spécifique
python -m mediapulse bronze-to-silver --source hespress

# Limiter le nombre d'objets traités
python -m mediapulse bronze-to-silver --limit 100
```

**Sortie console :**
```
INFO  Found 47 Bronze object(s) under bronze/source=hespress
INFO  Wrote Silver object s3://mediapulse/silver/source=hespress/date=2026-05-15/a3f8...json
WARN  Rejected Bronze object bronze/.../b7c2...json into silver/_rejected/...
INFO  Bronze to Silver run complete: scanned=47, accepted=43, rejected=4, duplicate=2
```

---

## `silver-to-gold` — Agrégation analytique

```powershell
python -m mediapulse silver-to-gold
```

Lit tous les fichiers Silver et produit :
- `gold/table=keyword_frequency/run_date={date}/data.json` — top-50 keywords TF-IDF
- `gold/table=daily_trends/run_date={date}/data.json` — tendances quotidiennes
- `gold/table=source_counts/run_date={date}/data.json` — comptages par source

---

## `load-warehouse` — Charger le warehouse PostgreSQL

```powershell
python -m mediapulse load-warehouse
```

Lit les fichiers Gold et charge :
- Dimensions : `dim_source`, `dim_date`, `dim_category` (UPSERT)
- Faits : `fact_articles`, `fact_keyword_frequency`, `fact_daily_trends` (INSERT)

---

## `quality` — Rapport de qualité

```powershell
# Qualité de la couche Silver
python -m mediapulse quality --layer silver

# Qualité de la couche Gold
python -m mediapulse quality --layer gold
```

Affiche le taux d'acceptation, les règles les plus souvent violées et écrit dans `warehouse.quality_report`.

---

## `seed-demo` — Données de démonstration

```powershell
# 14 jours, 16 articles par jour par source
python -m mediapulse seed-demo --days 14 --articles-per-day 16

# Personnaliser
python -m mediapulse seed-demo --days 30 --articles-per-day 8
```

Génère des données réalistes directement dans le warehouse PostgreSQL pour une démo immédiate sans scraper de vrais sites.

---

## Pipeline complet (ordre des étapes)

```powershell
# 1. Initialiser
python -m mediapulse doctor
python -m mediapulse apply-schema

# 2. Collecter
python -m mediapulse scrape

# 3. Nettoyer
python -m mediapulse bronze-to-silver

# 4. Agréger
python -m mediapulse silver-to-gold

# 5. Charger
python -m mediapulse load-warehouse

# 6. Vérifier la qualité
python -m mediapulse quality --layer silver
python -m mediapulse quality --layer gold

# → Ouvrir Grafana : http://localhost:3001
```

---

## Exécution des tests

```powershell
# Tous les tests
python -m pytest mediapulse/tests/ -v

# Un module spécifique
python -m pytest mediapulse/tests/test_bronze_to_silver.py -v

# Avec coverage
python -m pytest mediapulse/tests/ --cov=mediapulse --cov-report=term-missing
```

| Test | Ce qui est vérifié |
|------|-------------------|
| `test_article_model.py` | Validation Pydantic, URL, langue ISO, timezone UTC, url_hash |
| `test_bronze_to_silver.py` | Strip HTML, normalization Unicode, déduplication, 6 règles qualité |
| `test_silver_to_gold.py` | TF-IDF, agrégation tendances, comptages Gold |
| `test_demo_seed.py` | Cohérence des données générées (dates, sources, langues) |

---

## Airflow — Interface Web

URL : **http://localhost:8080** — identifiants : `admin` / `admin`

| DAG | Description | Schedule suggéré |
|-----|-------------|-----------------|
| `mediapulse_batch_scrape` | Scraping de toutes les sources | `0 */6 * * *` (toutes les 6h) |
| `mediapulse_bronze_to_silver` | Nettoyage et validation | `30 */6 * * *` (30min après scrape) |
| `mediapulse_silver_to_gold` | Agrégation TF-IDF | `0 2 * * *` (2h du matin) |
| `mediapulse_load_warehouse` | Chargement PostgreSQL | `30 2 * * *` (2h30) |
| `mediapulse_data_quality` | Rapport qualité | `0 3 * * *` (3h du matin) |
