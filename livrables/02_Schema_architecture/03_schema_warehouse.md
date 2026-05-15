# Schéma de l'Entrepôt de Données — PostgreSQL

## Modèle en étoile (Star Schema)

```
                          ┌──────────────────┐
                          │   dim_category   │
                          │──────────────────│
                          │ category_key  PK │
                          │ category_name    │
                          │ normalized_name  │
                          │ created_at       │
                          └────────┬─────────┘
                                   │ FK
┌─────────────────┐                │              ┌───────────────────────┐
│   dim_source    │                │              │       dim_date        │
│─────────────────│                │              │───────────────────────│
│ source_key   PK │                │              │ date_key  PK (YYYYMMDD│
│ source_name     │                │              │ full_date             │
│ country_code    │                │              │ year_number           │
│ country_name    │                │              │ quarter_number        │
│ source_type     │                │              │ month_number          │
│ base_url        │                │              │ month_name            │
│ language_hint   │                │              │ day_of_month          │
│ is_active       │                │              │ day_of_week           │
│ created_at      │                │              │ day_name              │
│ updated_at      │                │              │ week_of_year          │
└────────┬────────┘                │              │ is_weekend            │
         │ FK                      │              └──────────┬────────────┘
         │                         │                         │ FK
         │              ┌──────────▼──────────────────────────▼──────────┐
         │              │              fact_articles  (CENTRE)            │
         └─────────────►│──────────────────────────────────────────────── │
                        │ article_key          PK (IDENTITY)              │
                        │ url_hash             UNIQUE CHAR(64)            │
                        │ source_key           FK → dim_source            │
                        │ published_date_key   FK → dim_date              │
                        │ scraped_date_key     FK → dim_date              │
                        │ category_key         FK → dim_category          │
                        │ title                TEXT NOT NULL              │
                        │ author               TEXT                       │
                        │ published_at         TIMESTAMPTZ NOT NULL       │
                        │ scraped_at           TIMESTAMPTZ NOT NULL       │
                        │ language_code        CHAR(2)                    │
                        │ country_code         CHAR(2)                    │
                        │ url                  TEXT UNIQUE                │
                        │ content_text         TEXT                       │
                        │ content_length       INTEGER (>100)             │
                        │ sentiment_score      NUMERIC(6,5) [-1..1]       │
                        │ topic_tags           TEXT[]                     │
                        │ silver_object_path   TEXT                       │
                        │ loaded_at            TIMESTAMPTZ                │
                        └─────────────────────────────────────────────────┘
                                       │
             ┌─────────────────────────┴──────────────────────────┐
             │                                                      │
┌────────────▼────────────────────┐        ┌────────────────────────▼──────────┐
│    fact_keyword_frequency       │        │       fact_daily_trends            │
│─────────────────────────────────│        │────────────────────────────────────│
│ keyword_frequency_key  PK       │        │ daily_trend_key  PK               │
│ date_key               FK       │        │ date_key          FK               │
│ source_key             FK       │        │ source_key        FK               │
│ keyword                TEXT     │        │ topic             TEXT             │
│ frequency_count        INTEGER  │        │ article_count     INTEGER          │
│ tf_idf_score           NUMERIC  │        │ trend_score       NUMERIC          │
│ rank_position          INTEGER  │        │ window_start_at   TIMESTAMPTZ     │
│ loaded_at              TIMESTAMPTZ│       │ window_end_at     TIMESTAMPTZ     │
│ UNIQUE(date,source,keyword)     │        │ top_keywords      TEXT[]           │
└─────────────────────────────────┘        │ loaded_at         TIMESTAMPTZ     │
                                           │ UNIQUE(date,src,topic,window)     │
                                           └────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         quality_report (traçabilité)                          │
│──────────────────────────────────────────────────────────────────────────────│
│ quality_report_key  PK │ run_id UUID │ pipeline_step │ layer_name            │
│ source_key  FK         │ article_url │ url_hash       │ rule_name             │
│ severity (info/warn/error/critical)  │ status (passed/failed)                │
│ failure_reason         │ object_path │ detected_at TIMESTAMPTZ               │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Vues pré-calculées pour dashboards

```sql
-- Comptages journaliers par source
warehouse.daily_article_counts
→ full_date, source_name, country_code, article_count

-- Répartition linguistique
warehouse.language_distribution
→ language_code, article_count

-- Score qualité par couche
warehouse.data_quality_score
→ pipeline_step, layer_name, report_date, passed_checks, failed_checks, quality_score%

-- Vues dashboard (03-dashboard-views.sql)
warehouse.dashboard_daily_volume
warehouse.dashboard_top_keywords
warehouse.dashboard_source_breakdown
warehouse.dashboard_quality_trend
```

## Index de performance

```sql
idx_fact_articles_published_date  → (published_date_key)
idx_fact_articles_source_date     → (source_key, published_date_key)
idx_fact_articles_language        → (language_code)
idx_fact_keyword_frequency_keyword→ (keyword)
idx_fact_daily_trends_topic       → (topic)
idx_quality_report_detected_at    → (detected_at)
idx_quality_report_rule_status    → (rule_name, status)
```
