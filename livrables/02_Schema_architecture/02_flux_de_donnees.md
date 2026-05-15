# Flux de Données — MediaPulse

## Flux principal (bout en bout)

```
Article web
    │
    ▼
[1] SCRAPING ─────────────────────────────────────────────────────────────
    │  GenericArticleScraper.scrape()
    │  • Télécharge la page d'index (requests)
    │  • Identifie les URLs d'articles (regex patterns)
    │  • Télécharge et parse chaque article (BeautifulSoup)
    │  • Instancie Article (Pydantic) → rejet immédiat si invalide
    │
    ├──► Mode streaming : KafkaProducer.send("raw-articles", article.json())
    └──► Mode batch     : BronzeWriter.write(article) → MinIO direct
    │
    ▼
[2] STREAMING KAFKA ──────────────────────────────────────────────────────
    │  Producer → Topic raw-articles → Consumer
    │  • Sérialisation JSON (ensure_ascii=False)
    │  • Consumer lit par micro-lots de 50 messages
    │  • Chaque lot → BronzeWriter
    │
    ▼
[3] STOCKAGE BRONZE ──────────────────────────────────────────────────────
    │  MinIO : s3://mediapulse/bronze/
    │  Path  : bronze/source={source}/date={YYYY-MM-DD}/{url_hash}.json
    │
    │  Exemple :
    │  bronze/source=hespress/date=2026-05-15/a3f8b2c1...sha256...json
    │
    │  Contenu : article brut + url_hash calculé
    │
    ▼
[4] TRANSFORMATION BRONZE → SILVER ───────────────────────────────────────
    │  BronzeToSilverPipeline.run()
    │
    │  Pour chaque objet Bronze :
    │  ┌─────────────────────────────────────────────────────────────┐
    │  │  strip_html_tags()          → supprime balises HTML         │
    │  │  normalize_encoding()       → NFKC, html.unescape, UTF-8   │
    │  │  detect_article_language()  → langdetect (seed=0)          │
    │  │  compute_url_hash()         → SHA-256(normalize(url))      │
    │  │  parse_datetime_to_utc()    → tous formats → UTC ISO       │
    │  └─────────────────────────────────────────────────────────────┘
    │
    │  validate_silver_record() — 6 règles :
    │  ┌─────────────────────────────────────────────────────────────┐
    │  │  ✓ title_not_empty          → titre non vide après clean   │
    │  │  ✓ published_at_not_null    → date de publication valide   │
    │  │  ✓ content_length_gt_100   → contenu > 100 caractères     │
    │  │  ✓ url_valid               → scheme http/https + domaine  │
    │  │  ✓ url_hash_not_empty      → hash présent                 │
    │  │  ✓ url_unique              → pas déjà vu dans cette run   │
    │  └─────────────────────────────────────────────────────────────┘
    │
    ├──► Accepté → silver/source=X/date=D/{url_hash}.json
    └──► Rejeté  → silver/_rejected/date=D/{url_hash}.json
                   (avec liste des QualityIssue et bronze_object_path)
    │
    ▼
[5] AGRÉGATION SILVER → GOLD ─────────────────────────────────────────────
    │  SilverToGoldPipeline.run()
    │
    │  Lit tous les fichiers Silver de la période :
    │  ┌─────────────────────────────────────────────────────────────┐
    │  │  Tokenisation multilingue (TOKEN_PATTERN: \w + Arabic)     │
    │  │  Filtrage stopwords (EN + FR + AR)                         │
    │  │  Calcul TF-IDF → top-50 keywords par source et par jour   │
    │  │  Agrégation tendances quotidiennes par topic               │
    │  │  Comptages article_count par source / pays / langue        │
    │  └─────────────────────────────────────────────────────────────┘
    │
    │  Écriture Gold :
    │  gold/table=keyword_frequency/run_date={date}/data.json
    │  gold/table=daily_trends/run_date={date}/data.json
    │  gold/table=source_counts/run_date={date}/data.json
    │
    ▼
[6] CHARGEMENT WAREHOUSE ─────────────────────────────────────────────────
    │  WarehouseLoader
    │
    │  Pour chaque article Gold :
    │  1. UPSERT dim_source       (source_name, country_code, type)
    │  2. UPSERT dim_date         (full_date → date_key YYYYMMDD)
    │  3. UPSERT dim_category     (category_name normalisé)
    │  4. INSERT fact_articles    (si url_hash absent, sinon skip)
    │  5. INSERT fact_keyword_frequency  (top keywords du jour)
    │  6. INSERT fact_daily_trends       (tendances du jour)
    │
    ▼
[7] VISUALISATION ────────────────────────────────────────────────────────
    │
    ├──► Grafana (port 3001)
    │    Requête SQL → views warehouse.daily_article_counts,
    │    warehouse.language_distribution, warehouse.data_quality_score
    │
    ├──► Metabase (port 3000)
    │    Exploration libre sur schéma warehouse.*
    │
    └──► Prometheus (port 9090)
         postgres-exporter (9187) + kafka-exporter (9308)
         → alertes sur données périmées, rejection rate, consumer lag
```

## Flux de données qualité (rejet)

```
Bronze record
    │
    ▼ validate_silver_record()
    │
    ├── PASS (0 issues) ──► Silver valide ──► fact_articles
    │
    └── FAIL (1+ issues) ──► silver/_rejected/
                              {
                                "bronze_object_path": "bronze/...",
                                "issues": [
                                  {
                                    "rule_name": "content_length_gt_100",
                                    "message": "Article content ≤ 100 chars",
                                    "severity": "error"
                                  }
                                ],
                                "rejected_at": "2026-05-15T10:30:00Z"
                              }
                              └──► warehouse.quality_report (traçabilité)
```
