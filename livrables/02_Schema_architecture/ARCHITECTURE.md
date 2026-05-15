# Schéma d'Architecture — MediaPulse

## Diagramme 1 — Architecture globale

```mermaid
flowchart LR
    subgraph SOURCES["🌐 Sources d'actualité (8)"]
        direction TB
        S1[Hespress\nMA · ar]
        S2[Akhbarona\nMA · ar]
        S3[Barlamane\nMA · ar]
        S4[Lakom\nMA · ar]
        S5[Al Jazeera\nQA · en]
        S6[BBC News\nGB · en]
        S7[CNN\nUS · en]
        S8[Reuters\nGB · en]
    end

    subgraph INGESTION["⚙️ Ingestion"]
        SCR[Scraper Service\nPython · BeautifulSoup\nPydantic Article]
        KP[Kafka Producer\ntopic: raw-articles]
    end

    subgraph STREAMING["⚡ Streaming"]
        KF[Apache Kafka\nConfluentinc 7.6\nZookeeper]
        KC[Kafka Consumer\nmicro-batch=50]
    end

    subgraph DATALAKE["🪣 Data Lake — MinIO"]
        BR[🥉 Bronze\nbronze/source=X/\ndate=D/hash.json]
        BTS[BronzeToSilver\nHTML strip · Unicode\nlangdetect · SHA-256\n6 règles qualité]
        SL[🥈 Silver\nsilver/source=X/\ndate=D/hash.json]
        REJ[🗑️ _rejected/\nQualityIssue traçable]
        STG[SilverToGold\nTF-IDF keywords\ndaily trends\nsource counts]
        GD[🥇 Gold\ngold/table=X/\nrun_date=D/data.json]
    end

    subgraph WAREHOUSE["🗄️ Warehouse — PostgreSQL 16"]
        DIM[dim_source\ndim_date\ndim_category]
        FACT[fact_articles\nfact_keyword_frequency\nfact_daily_trends]
        QR[quality_report]
    end

    subgraph VISU["📊 Visualisation & Monitoring"]
        GR[Grafana 11\nPort 3001]
        MB[Metabase\nPort 3000]
        PR[Prometheus\nPort 9090]
    end

    subgraph ORCH["🌀 Orchestration — Airflow 2.9"]
        D1[dag_batch_scrape]
        D2[dag_bronze_to_silver]
        D3[dag_silver_to_gold]
        D4[dag_load_warehouse]
        D5[dag_data_quality]
    end

    SOURCES --> SCR
    SCR --> KP
    KP --> KF
    KF --> KC
    KC --> BR
    BR --> BTS
    BTS -->|accepted| SL
    BTS -->|rejected| REJ
    SL --> STG
    STG --> GD
    GD --> FACT
    DIM --> FACT
    FACT --> GR
    FACT --> MB
    PR --> GR
    ORCH -.->|schedule| SCR
    ORCH -.->|schedule| BTS
    ORCH -.->|schedule| STG
    ORCH -.->|schedule| FACT
```

---

## Diagramme 2 — Architecture Medallion (zoom couches)

```mermaid
flowchart TD
    subgraph BRONZE["🥉 BRONZE — Données brutes (immuables)"]
        B1["Article JSON brut\n{title, content, url, source,\n published_at, scraped_at,\n language, country, url_hash}"]
    end

    subgraph SILVER["🥈 SILVER — Données nettoyées et validées"]
        direction LR
        T1[strip_html_tags\nBeautifulSoup4]
        T2[normalize_encoding\nNFKC · html.unescape]
        T3[detect_language\nlangdetect seed=0]
        T4[compute_url_hash\nSHA-256]
        T5[parse_datetime_utc\npython-dateutil]
        V1{validate_silver_record\n6 règles}
        S_OK[✅ Silver valide\nsource=X/date=D/hash.json]
        S_KO[❌ _rejected/\nQualityIssue list]
    end

    subgraph GOLD["🥇 GOLD — Agrégats analytiques"]
        G1[top_keywords\nTF-IDF · top 50]
        G2[daily_trends\ntopic · trend_score]
        G3[source_counts\npar source / pays]
    end

    B1 --> T1 --> T2 --> T3 --> T4 --> T5 --> V1
    V1 -->|0 issue| S_OK
    V1 -->|1+ issues| S_KO
    S_OK --> G1 & G2 & G3
```

---

## Diagramme 3 — Flux temps réel (Kafka)

```mermaid
sequenceDiagram
    participant SC as Scraper
    participant KP as Kafka Producer
    participant KF as Kafka Broker
    participant KC as Kafka Consumer
    participant MN as MinIO Bronze

    SC->>SC: scrape() → Article (Pydantic)
    SC->>KP: send(article.json())
    KP->>KF: produce(raw-articles, key=url_hash)
    KF-->>KC: poll(batch_size=50)
    loop Pour chaque message du lot
        KC->>MN: put_object(bronze/source=X/date=D/hash.json)
    end
    KC-->>KF: commit_offsets()
    Note over KF,KC: Consumer group: mediapulse-bronze-writer
```

---

## Stack technologique

| Composant | Technologie | Version | Port |
|-----------|------------|---------|------|
| Scraping | Python + BeautifulSoup4 + Pydantic | 3.11 / 4.12 / 2.8 | — |
| Message Broker | Apache Kafka (Confluent) | 7.6.1 | 9092 |
| Coordination | Zookeeper | 7.6.1 | 2181 |
| Data Lake | MinIO | 2024-07 | 9000/9001 |
| Orchestration | Apache Airflow + Celery | 2.9.3 | 8080 |
| Broker Celery | Redis | 7-alpine | 6379 |
| Entrepôt | PostgreSQL | 16 | 5432 |
| Visualisation | Grafana | 11.1.0 | 3001 |
| Analytics | Metabase | v0.50.18 | 3000 |
| Monitoring | Prometheus | 2.53.1 | 9090 |
| Containerisation | Docker Compose | v2.20+ | — |
