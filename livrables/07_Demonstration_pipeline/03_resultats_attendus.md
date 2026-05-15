# Résultats Attendus — Démonstration

## Métriques pipeline (run complet sur 1 heure de scraping)

| Étape | Métrique | Valeur typique |
|-------|---------|---------------|
| Scraping | Articles scrapés / source | 20–25 (max configuré) |
| Scraping | Durée totale (8 sources) | 30–90 secondes |
| Bronze | Objets écrits dans MinIO | ~160 (8 sources × 20) |
| Silver | Taux d'acceptation | 80–92% |
| Silver | Doublons détectés | 2–5% |
| Silver | Rejetés (qualité) | 5–15% |
| Gold | Keywords uniques extraits | 200–500 |
| Gold | Tendances identifiées | 20–50 topics |
| Warehouse | `fact_articles` chargés | ~140–150 nouvelles lignes |
| Warehouse | `fact_keyword_frequency` | ~400–600 lignes |

## Sortie console attendue — Scrape Hespress

```
INFO  Scraping Hespress (MA, ar) — max 25 articles
INFO  Found 31 article URLs on index page
INFO  Scraped article: "عنوان المقال الأول" — hespress.com/...
INFO  Scraped article: "عنوان المقال الثاني" — hespress.com/...
...
INFO  Scrape complete: 23 articles accepted, 2 skipped (validation)
INFO  Written to Bronze: bronze/source=hespress/date=2026-05-15/
```

## Sortie console attendue — Bronze → Silver

```
INFO  Found 160 Bronze object(s) under bronze/
INFO  Wrote Silver object s3://mediapulse/silver/source=hespress/...
INFO  Wrote Silver object s3://mediapulse/silver/source=bbc/...
WARN  Rejected bronze/source=cnn/.../abc123.json
      → rule: content_length_gt_100 (content: 87 chars — likely nav menu)
WARN  Rejected bronze/source=hespress/.../def456.json
      → rule: url_unique (duplicate URL)
INFO  Bronze to Silver run complete:
      scanned=160, accepted=141, rejected=14, duplicate=5
```

## Score de qualité Grafana attendu

```
Couche Silver :  quality_score = 88.1%
Couche Gold   :  quality_score = 100%  (agrégats toujours valides)
Couche Warehouse: quality_score = 95%+
```

## Structure MinIO après une run complète

```
mediapulse/
├── bronze/
│   ├── source=hespress/date=2026-05-15/    ← 23 JSON
│   ├── source=akhbarona/date=2026-05-15/   ← 21 JSON
│   ├── source=bbc/date=2026-05-15/         ← 20 JSON
│   └── ... (8 sources)
├── silver/
│   ├── source=hespress/date=2026-05-15/    ← 20 JSON (nettoyés)
│   ├── _rejected/date=2026-05-15/          ← 3 JSON (avec raisons)
│   └── ...
└── gold/
    ├── table=keyword_frequency/run_date=2026-05-15/data.json
    ├── table=daily_trends/run_date=2026-05-15/data.json
    └── table=source_counts/run_date=2026-05-15/data.json
```

## Warehouse PostgreSQL après chargement

```sql
SELECT COUNT(*) FROM warehouse.fact_articles;
-- 141

SELECT source_name, COUNT(*) as articles
FROM warehouse.fact_articles a
JOIN warehouse.dim_source s ON s.source_key = a.source_key
GROUP BY source_name ORDER BY articles DESC;
-- Hespress    | 20
-- Akhbarona   | 19
-- BBC News    | 18
-- Reuters     | 17
-- CNN         | 17
-- Al Jazeera  | 16
-- Barlamane   | 17
-- Lakom       | 17

SELECT language_code, COUNT(*) FROM warehouse.fact_articles
GROUP BY language_code;
-- ar | 73
-- en | 68
```
