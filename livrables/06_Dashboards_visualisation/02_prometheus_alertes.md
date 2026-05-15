# Alertes Prometheus — MediaPulse

Fichier source : `mediapulse/dashboard/prometheus-alerts.yml`

## Règles d'alerte définies

### `StaleData` — Données périmées
```yaml
alert: StaleData
expr: |
  (time() - max(mediapulse_last_scrape_timestamp)) > 21600
for: 5m
labels:
  severity: warning
annotations:
  summary: "Aucun article scraped depuis plus de 6 heures"
  description: "Le pipeline de scraping semble bloqué ou arrêté."
```

### `HighRejectionRate` — Taux de rejet élevé
```yaml
alert: HighRejectionRate
expr: |
  mediapulse_silver_rejection_rate > 0.20
for: 10m
labels:
  severity: critical
annotations:
  summary: "Taux de rejet Bronze→Silver > 20%"
  description: "Plus de 20% des articles sont rejetés. Vérifier les sources."
```

### `KafkaConsumerLag` — Retard Kafka
```yaml
alert: KafkaConsumerLag
expr: |
  kafka_consumer_lag_sum{group="mediapulse-bronze-writer"} > 1000
for: 5m
labels:
  severity: warning
annotations:
  summary: "Consumer Kafka en retard (lag > 1000)"
  description: "Le consumer Bronze n'arrive pas à suivre le rythme de production."
```

### `PostgresDown` — Base indisponible
```yaml
alert: PostgresDown
expr: |
  pg_up == 0
for: 1m
labels:
  severity: critical
annotations:
  summary: "PostgreSQL warehouse inaccessible"
  description: "Le warehouse PostgreSQL ne répond plus."
```

## Exporteurs Prometheus

| Exporteur | Port | Métriques exposées |
|-----------|------|-------------------|
| postgres-exporter | 9187 | Connexions, taille tables, latence requêtes, transactions |
| kafka-exporter | 9308 | Consumer lag, offsets, messages/sec, partitions |

## Accès à l'interface Prometheus

- URL : **http://localhost:9090**
- Vérifier les targets actifs : **Status → Targets**
- Explorer les alertes : **Alerts**
- Exemples de requêtes PromQL :

```promql
# Taille du warehouse PostgreSQL
pg_database_size_bytes{datname="mediapulse"}

# Consumer lag Kafka total
sum(kafka_consumer_lag_sum) by (group)

# Connexions PostgreSQL actives
pg_stat_activity_count{state="active"}
```
