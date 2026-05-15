CREATE OR REPLACE VIEW warehouse.dashboard_articles_per_day AS
SELECT
    d.full_date AS published_date,
    s.source_name,
    COUNT(a.article_key)::INTEGER AS article_count
FROM warehouse.fact_articles AS a
JOIN warehouse.dim_date AS d
    ON d.date_key = a.published_date_key
JOIN warehouse.dim_source AS s
    ON s.source_key = a.source_key
GROUP BY d.full_date, s.source_name
ORDER BY d.full_date, s.source_name;

CREATE OR REPLACE VIEW warehouse.dashboard_articles_by_source_country AS
SELECT
    s.country_code,
    s.country_name,
    s.source_name,
    COUNT(a.article_key)::INTEGER AS article_count
FROM warehouse.fact_articles AS a
JOIN warehouse.dim_source AS s
    ON s.source_key = a.source_key
GROUP BY s.country_code, s.country_name, s.source_name
ORDER BY article_count DESC, s.source_name;

CREATE OR REPLACE VIEW warehouse.dashboard_top_keywords AS
SELECT
    k.keyword,
    k.frequency_count,
    k.tf_idf_score,
    k.rank_position,
    d.full_date AS keyword_date,
    COALESCE(s.source_name, 'All sources') AS source_name
FROM warehouse.fact_keyword_frequency AS k
JOIN warehouse.dim_date AS d
    ON d.date_key = k.date_key
LEFT JOIN warehouse.dim_source AS s
    ON s.source_key = k.source_key
ORDER BY d.full_date DESC, k.rank_position NULLS LAST, k.tf_idf_score DESC
LIMIT 200;

CREATE OR REPLACE VIEW warehouse.dashboard_trending_topics AS
SELECT
    t.topic,
    t.article_count,
    t.trend_score,
    t.window_start_at,
    t.window_end_at,
    COALESCE(s.source_name, 'All sources') AS source_name
FROM warehouse.fact_daily_trends AS t
LEFT JOIN warehouse.dim_source AS s
    ON s.source_key = t.source_key
WHERE t.window_end_at >= NOW() - INTERVAL '48 hours'
ORDER BY t.trend_score DESC, t.article_count DESC, t.topic
LIMIT 100;

CREATE OR REPLACE VIEW warehouse.dashboard_language_distribution AS
SELECT
    language_code,
    COUNT(article_key)::INTEGER AS article_count
FROM warehouse.fact_articles
GROUP BY language_code
ORDER BY article_count DESC, language_code;

CREATE OR REPLACE VIEW warehouse.dashboard_quality_score AS
SELECT
    pipeline_step,
    layer_name,
    DATE_TRUNC('day', detected_at)::DATE AS report_date,
    COUNT(*) FILTER (WHERE status = 'passed')::INTEGER AS passed_checks,
    COUNT(*) FILTER (WHERE status = 'failed')::INTEGER AS failed_checks,
    CASE
        WHEN COUNT(*) = 0 THEN 100.0
        ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'passed') / COUNT(*), 2)
    END AS quality_score
FROM warehouse.quality_report
GROUP BY pipeline_step, layer_name, DATE_TRUNC('day', detected_at)::DATE
ORDER BY report_date DESC, pipeline_step, layer_name;

CREATE OR REPLACE VIEW warehouse.dashboard_latest_articles AS
SELECT
    a.published_at,
    s.source_name,
    a.language_code,
    c.category_name,
    a.title,
    a.author,
    a.url,
    a.content_length
FROM warehouse.fact_articles AS a
JOIN warehouse.dim_source AS s
    ON s.source_key = a.source_key
LEFT JOIN warehouse.dim_category AS c
    ON c.category_key = a.category_key
ORDER BY a.published_at DESC
LIMIT 100;
