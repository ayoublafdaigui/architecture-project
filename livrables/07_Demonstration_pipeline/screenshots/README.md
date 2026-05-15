# Captures d'écran — MediaPulse

## Captures à réaliser pour la démonstration

| Fichier | Interface | URL | Ce qu'il faut capturer |
|---------|-----------|-----|----------------------|
| `01_airflow_dags.png` | Airflow | http://localhost:8080 | Liste des 5 DAGs avec leur statut (vert = succès) |
| `02_grafana_dashboard.png` | Grafana | http://localhost:3001 | Dashboard "MediaPulse News Intelligence" complet |
| `03_kafka_topics.png` | Kafka (logs) | docker logs mediapulse-kafka-1 | Topic `raw-articles` avec messages produits |
| `04_minio_bronze.png` | MinIO Console | http://localhost:9001 | Bucket `mediapulse` → arborescence `bronze/source=*/` |
| `05_postgres_warehouse.png` | pgAdmin / psql | localhost:5432 | Résultat de `SELECT COUNT(*) FROM warehouse.fact_articles` |
| `06_prometheus_metrics.png` | Prometheus | http://localhost:9090 | Targets actifs (postgres-exporter + kafka-exporter) |

## Comment prendre les captures (Windows)

```
1. Appuyer sur Win + Shift + S
2. Sélectionner la zone d'écran
3. Sauvegarder dans ce dossier avec le nom indiqué ci-dessus
```

## Capture automatisée (optionnel)

```powershell
# Lancer le script de démonstration d'abord
.\livrables\07_Demonstration_pipeline\scripts\demo.ps1

# Ensuite capturer manuellement chaque interface
# ou utiliser un outil comme ShareX / Snagit
```

## Résultats attendus sur les captures

**Airflow** : 5 DAGs visibles — `mediapulse_batch_scrape`, `mediapulse_bronze_to_silver`,
`mediapulse_silver_to_gold`, `mediapulse_load_warehouse`, `mediapulse_data_quality`

**Grafana** : 8 panels — volume par jour, répartition linguistique, top keywords, tendances,
score qualité, métriques Kafka, métriques PostgreSQL

**MinIO** : Arborescence `bronze/source=hespress/date=YYYY-MM-DD/` avec fichiers JSON visibles

**Prometheus** : Targets `postgres-exporter:9187` et `kafka-exporter:9308` en état `UP`
