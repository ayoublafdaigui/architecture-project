CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_source (
    source_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    country_code CHAR(2) NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
    country_name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('moroccan', 'international')),
    base_url TEXT,
    language_hint CHAR(2) CHECK (language_hint ~ '^[a-z]{2}$'),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year_number SMALLINT NOT NULL,
    quarter_number SMALLINT NOT NULL CHECK (quarter_number BETWEEN 1 AND 4),
    month_number SMALLINT NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name TEXT NOT NULL,
    day_of_month SMALLINT NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name TEXT NOT NULL,
    week_of_year SMALLINT NOT NULL CHECK (week_of_year BETWEEN 1 AND 53),
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.dim_category (
    category_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse.fact_articles (
    article_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url_hash CHAR(64) NOT NULL UNIQUE,
    source_key BIGINT NOT NULL REFERENCES warehouse.dim_source(source_key),
    published_date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    scraped_date_key INTEGER REFERENCES warehouse.dim_date(date_key),
    category_key BIGINT REFERENCES warehouse.dim_category(category_key),
    title TEXT NOT NULL CHECK (BTRIM(title) <> ''),
    author TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    language_code CHAR(2) NOT NULL CHECK (language_code ~ '^[a-z]{2}$'),
    country_code CHAR(2) CHECK (country_code ~ '^[A-Z]{2}$'),
    url TEXT NOT NULL UNIQUE,
    content_text TEXT NOT NULL,
    content_length INTEGER NOT NULL CHECK (content_length > 100),
    sentiment_score NUMERIC(6, 5) CHECK (sentiment_score BETWEEN -1 AND 1),
    topic_tags TEXT[],
    silver_object_path TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warehouse.fact_keyword_frequency (
    keyword_frequency_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    source_key BIGINT REFERENCES warehouse.dim_source(source_key),
    keyword TEXT NOT NULL CHECK (BTRIM(keyword) <> ''),
    frequency_count INTEGER NOT NULL CHECK (frequency_count >= 0),
    tf_idf_score NUMERIC(12, 8) NOT NULL DEFAULT 0,
    rank_position INTEGER CHECK (rank_position > 0),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (date_key, source_key, keyword)
);

CREATE TABLE IF NOT EXISTS warehouse.fact_daily_trends (
    daily_trend_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    source_key BIGINT REFERENCES warehouse.dim_source(source_key),
    topic TEXT NOT NULL CHECK (BTRIM(topic) <> ''),
    article_count INTEGER NOT NULL CHECK (article_count >= 0),
    trend_score NUMERIC(12, 6) NOT NULL DEFAULT 0,
    window_start_at TIMESTAMPTZ NOT NULL,
    window_end_at TIMESTAMPTZ NOT NULL,
    top_keywords TEXT[],
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (date_key, source_key, topic, window_start_at, window_end_at)
);

CREATE TABLE IF NOT EXISTS warehouse.quality_report (
    quality_report_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL DEFAULT gen_random_uuid(),
    pipeline_step TEXT NOT NULL,
    layer_name TEXT NOT NULL CHECK (layer_name IN ('bronze', 'silver', 'gold', 'warehouse')),
    source_key BIGINT REFERENCES warehouse.dim_source(source_key),
    article_url TEXT,
    url_hash CHAR(64),
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'error' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    status TEXT NOT NULL DEFAULT 'failed' CHECK (status IN ('passed', 'failed')),
    failure_reason TEXT,
    object_path TEXT,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_articles_published_date
    ON warehouse.fact_articles (published_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_articles_source_date
    ON warehouse.fact_articles (source_key, published_date_key);

CREATE INDEX IF NOT EXISTS idx_fact_articles_language
    ON warehouse.fact_articles (language_code);

CREATE INDEX IF NOT EXISTS idx_fact_keyword_frequency_keyword
    ON warehouse.fact_keyword_frequency (keyword);

CREATE INDEX IF NOT EXISTS idx_fact_daily_trends_topic
    ON warehouse.fact_daily_trends (topic);

CREATE INDEX IF NOT EXISTS idx_quality_report_detected_at
    ON warehouse.quality_report (detected_at);

CREATE INDEX IF NOT EXISTS idx_quality_report_rule_status
    ON warehouse.quality_report (rule_name, status);

CREATE OR REPLACE VIEW warehouse.daily_article_counts AS
SELECT
    d.full_date,
    s.source_name,
    s.country_code,
    COUNT(a.article_key) AS article_count
FROM warehouse.fact_articles AS a
JOIN warehouse.dim_date AS d
    ON d.date_key = a.published_date_key
JOIN warehouse.dim_source AS s
    ON s.source_key = a.source_key
GROUP BY d.full_date, s.source_name, s.country_code;

CREATE OR REPLACE VIEW warehouse.language_distribution AS
SELECT
    language_code,
    COUNT(*) AS article_count
FROM warehouse.fact_articles
GROUP BY language_code;

CREATE OR REPLACE VIEW warehouse.data_quality_score AS
SELECT
    pipeline_step,
    layer_name,
    DATE_TRUNC('day', detected_at)::DATE AS report_date,
    COUNT(*) FILTER (WHERE status = 'passed') AS passed_checks,
    COUNT(*) FILTER (WHERE status = 'failed') AS failed_checks,
    CASE
        WHEN COUNT(*) = 0 THEN 100
        ELSE ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'passed') / COUNT(*), 2)
    END AS quality_score
FROM warehouse.quality_report
GROUP BY pipeline_step, layer_name, DATE_TRUNC('day', detected_at)::DATE;

INSERT INTO warehouse.dim_source (
    source_name,
    country_code,
    country_name,
    source_type,
    base_url,
    language_hint
)
VALUES
    ('Hespress', 'MA', 'Morocco', 'moroccan', 'https://www.hespress.com/', 'ar'),
    ('Akhbarona', 'MA', 'Morocco', 'moroccan', 'https://www.akhbarona.com/', 'ar'),
    ('Barlamane', 'MA', 'Morocco', 'moroccan', 'https://www.barlamane.com/', 'ar'),
    ('Lakom', 'MA', 'Morocco', 'moroccan', 'https://lakome2.com/', 'ar'),
    ('Al Jazeera', 'QA', 'Qatar', 'international', 'https://www.aljazeera.com/', 'en'),
    ('BBC News', 'GB', 'United Kingdom', 'international', 'https://www.bbc.com/news', 'en'),
    ('CNN', 'US', 'United States', 'international', 'https://www.cnn.com/', 'en'),
    ('Reuters', 'GB', 'United Kingdom', 'international', 'https://www.reuters.com/', 'en')
ON CONFLICT (source_name) DO UPDATE SET
    country_code = EXCLUDED.country_code,
    country_name = EXCLUDED.country_name,
    source_type = EXCLUDED.source_type,
    base_url = EXCLUDED.base_url,
    language_hint = EXCLUDED.language_hint,
    updated_at = NOW();
