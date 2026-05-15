# Dashboard Grafana — MediaPulse News Intelligence

## Provisionnement automatique

Le dashboard est **provisionné automatiquement** au démarrage de Grafana,
sans aucune configuration manuelle. Les fichiers de provisionnement :

```
mediapulse/dashboard/grafana/provisioning/
├── datasources/
│   └── datasources.yml         ← Connexion PostgreSQL + Prometheus
└── dashboards/
    ├── dashboards.yml          ← Configuration du provider
    └── mediapulse-overview.json ← Dashboard JSON (versionné dans Git)
```

## Accès

1. Ouvrir **http://localhost:3001**
2. Se connecter avec `admin` / mot de passe du `.env`
3. Menu gauche → **Dashboards** → dossier **MediaPulse** → **MediaPulse News Intelligence**

---

## Panels du dashboard

### Panel 1 — Volume d'articles par jour
- **Type :** Time series
- **Source :** Vue `warehouse.daily_article_counts`
- **Query :**
  ```sql
  SELECT full_date AS time, source_name, article_count
  FROM warehouse.daily_article_counts
  WHERE full_date >= NOW() - INTERVAL '30 days'
  ORDER BY full_date
  ```
- **Indicateur :** Évolution du volume de publication par source sur 30 jours

### Panel 2 — Répartition linguistique
- **Type :** Pie chart
- **Source :** Vue `warehouse.language_distribution`
- **Query :**
  ```sql
  SELECT language_code AS metric, article_count AS value
  FROM warehouse.language_distribution
  ```
- **Indicateur :** Proportion arabe (ar) / anglais (en) / autres

### Panel 3 — Top 10 Keywords du jour
- **Type :** Bar chart (horizontal)
- **Source :** `warehouse.fact_keyword_frequency`
- **Query :**
  ```sql
  SELECT keyword, SUM(frequency_count) AS total
  FROM warehouse.fact_keyword_frequency kf
  JOIN warehouse.dim_date d ON d.date_key = kf.date_key
  WHERE d.full_date = CURRENT_DATE
  GROUP BY keyword
  ORDER BY total DESC
  LIMIT 10
  ```
- **Indicateur :** Mots-clés les plus fréquents aujourd'hui (TF-IDF)

### Panel 4 — Sujets tendance (Trending Topics)
- **Type :** Table
- **Source :** `warehouse.fact_daily_trends`
- **Query :**
  ```sql
  SELECT topic, article_count, trend_score,
         top_keywords[1:3] AS top_3_keywords
  FROM warehouse.fact_daily_trends dt
  JOIN warehouse.dim_date d ON d.date_key = dt.date_key
  WHERE d.full_date = CURRENT_DATE
  ORDER BY trend_score DESC
  LIMIT 10
  ```
- **Indicateur :** Sujets les plus couverts avec leur score de tendance

### Panel 5 — Score de qualité par couche
- **Type :** Gauge / Stat
- **Source :** Vue `warehouse.data_quality_score`
- **Query :**
  ```sql
  SELECT layer_name, quality_score
  FROM warehouse.data_quality_score
  WHERE report_date = CURRENT_DATE
  ```
- **Indicateur :** % de records passant les règles de validation (cible : > 80%)

### Panel 6 — Articles par source/pays
- **Type :** Bar chart (grouped)
- **Source :** `warehouse.fact_articles` + `dim_source`
- **Query :**
  ```sql
  SELECT s.source_name, s.country_code,
         COUNT(*) AS article_count
  FROM warehouse.fact_articles a
  JOIN warehouse.dim_source s ON s.source_key = a.source_key
  JOIN warehouse.dim_date d ON d.date_key = a.published_date_key
  WHERE d.full_date >= NOW() - INTERVAL '7 days'
  GROUP BY s.source_name, s.country_code
  ORDER BY article_count DESC
  ```
- **Indicateur :** Répartition Maroc vs International sur 7 jours

### Panel 7 — Métriques Kafka (Prometheus)
- **Type :** Time series
- **Source :** Prometheus (kafka-exporter port 9308)
- **Métriques :**
  - `kafka_consumer_lag_sum` — Consumer lag total
  - `kafka_topic_partition_current_offset` — Offset courant
- **Indicateur :** Santé du pipeline de streaming en temps réel

### Panel 8 — Métriques PostgreSQL (Prometheus)
- **Type :** Stat / Time series
- **Source :** Prometheus (postgres-exporter port 9187)
- **Métriques :**
  - `pg_stat_activity_count` — Connexions actives
  - `pg_database_size_bytes` — Taille de la base
  - `pg_stat_user_tables_n_live_tup` — Lignes vivantes par table
- **Indicateur :** Santé de l'entrepôt de données

---

## Exportation du dashboard

```bash
# Exporter le dashboard depuis l'API Grafana
curl -u admin:PASSWORD http://localhost:3001/api/dashboards/uid/mediapulse-overview \
  -o mediapulse-dashboard-export.json
```
