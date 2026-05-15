# Référence des Modules — MediaPulse

## `mediapulse.models.article` — Modèle Article

```python
from mediapulse.models.article import Article
from datetime import datetime, timezone

article = Article(
    title="Titre de l'article",
    content="Contenu de l'article (min 1 caractère)",
    source="Hespress",
    url="https://www.hespress.com/article/12345",
    language="ar",
    country="MA",
    published_at=datetime.now(timezone.utc),
)

# Propriété calculée
print(article.url_hash)        # SHA-256 de l'URL
print(article.to_bronze_dict()) # Sérialisation JSON pour Bronze
```

## `mediapulse.core.config` — Configuration

```python
from mediapulse.core.config import (
    get_kafka_settings,
    get_minio_settings,
    get_postgres_settings,
    get_scraper_settings,
)

kafka    = get_kafka_settings()    # bootstrap_servers, topic, group_id
minio    = get_minio_settings()    # endpoint, bucket, prefixes
postgres = get_postgres_settings() # host, port, user, password, db
scraper  = get_scraper_settings()  # timeout, max_articles
```

## `mediapulse.scrapers` — Scrapers

```python
from mediapulse.scrapers.sources import SCRAPER_REGISTRY

# Instancier un scraper
ScraperClass = SCRAPER_REGISTRY["hespress"]
scraper = ScraperClass()
articles = scraper.scrape()  # Retourne list[Article]

# SCRAPER_REGISTRY keys :
# "hespress", "akhbarona", "barlamane", "lakom",
# "aljazeera", "bbc", "cnn", "reuters"
```

## `mediapulse.datalake.bronze_writer` — BronzeWriter

```python
from mediapulse.datalake.bronze_writer import BronzeWriter
from mediapulse.core.config import get_minio_settings

writer = BronzeWriter(get_minio_settings())
object_path = writer.write(article)
# Retourne : "bronze/source=hespress/date=2026-05-15/<hash>.json"
```

## `mediapulse.transform.bronze_to_silver` — Pipeline B→S

```python
from mediapulse.transform.bronze_to_silver import (
    BronzeToSilverPipeline,
    transform_bronze_record,
    validate_silver_record,
    strip_html_tags,
    normalize_encoding_and_whitespace,
    detect_article_language,
    compute_url_hash,
)

# Pipeline complet
pipeline = BronzeToSilverPipeline(get_minio_settings())
summary = pipeline.run(source="hespress", limit=100)
# summary.scanned, summary.accepted, summary.rejected, summary.duplicate

# Transformation unitaire (testable)
result = transform_bronze_record(bronze_dict, seen_url_hashes=set())
# result.accepted : bool
# result.record   : dict | None
# result.issues   : list[QualityIssue]
```

## `mediapulse.transform.silver_to_gold` — Pipeline S→G

```python
from mediapulse.transform.silver_to_gold import SilverToGoldPipeline

pipeline = SilverToGoldPipeline(get_minio_settings())
summary = pipeline.run()
# Écrit gold/table=*/run_date=YYYY-MM-DD/data.json
```

## `mediapulse.ingestion.kafka_producer` — Producteur

```python
from mediapulse.ingestion.kafka_producer import ArticleKafkaProducer

producer = ArticleKafkaProducer(get_kafka_settings())
producer.send(article)
producer.flush()
producer.close()
```

## `mediapulse.ingestion.kafka_consumer` — Consommateur

```python
from mediapulse.ingestion.kafka_consumer import ArticleKafkaConsumer

consumer = ArticleKafkaConsumer(
    kafka_settings=get_kafka_settings(),
    minio_settings=get_minio_settings(),
    batch_size=50,
)
consumer.run()  # Boucle infinie, Ctrl+C pour arrêter
```

## `mediapulse.warehouse.load_warehouse` — Chargement

```python
from mediapulse.warehouse.load_warehouse import WarehouseLoader

loader = WarehouseLoader(
    postgres_settings=get_postgres_settings(),
    minio_settings=get_minio_settings(),
)
loader.run()
```

## `mediapulse.quality.data_quality` — Qualité

```python
from mediapulse.quality.data_quality import DataQualityReporter

reporter = DataQualityReporter(get_postgres_settings())
report = reporter.run(layer="silver")
# report.total_checks, report.passed, report.failed, report.quality_score
```
