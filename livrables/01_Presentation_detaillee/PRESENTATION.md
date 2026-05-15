# MediaPulse — Présentation Détaillée du Projet

**Module :** Architecture des Données  
**Auteur :** Ayoub Lafdaigui  
**Date de rendu :** 15 Mai 2026  
**Dépôt :** https://github.com/ayoublafdaigui/architecture-project  

---

## 1. Contexte

Le paysage médiatique marocain compte des dizaines de sites publiant chaque jour des centaines
d'articles en arabe, français et anglais. S'y ajoutent les grands médias internationaux
(Al Jazeera, BBC, CNN, Reuters) qui couvrent les mêmes événements sous un angle différent.

**Problème :** il n'existe pas d'outil unifié pour collecter, normaliser, comparer et visualiser
cette information de manière automatisée. Un analyste doit aujourd'hui :
- Visiter 8 sites manuellement
- Lire en 3 langues
- Consolider dans Excel

**Solution : MediaPulse** automatise tout ce processus en un pipeline Big Data de bout en bout.

---

## 2. Objectifs

| # | Objectif | Indicateur de succès |
|---|----------|---------------------|
| 1 | Collecte automatisée | 8 sources scrapées sans intervention humaine |
| 2 | Conservation de l'historique | Architecture Medallion Bronze/Silver/Gold immuable |
| 3 | Métriques quotidiennes | Comptages, top-keywords TF-IDF, tendances par jour |
| 4 | Visualisation | Dashboards Grafana provisionnés automatiquement |
| 5 | Qualité des données | 6 règles de validation, rejet traçable |
| 6 | Santé de la plateforme | Alertes Prometheus, métriques Kafka + PostgreSQL |

---

## 3. Sources couvertes (8)

### Sources marocaines
| Source | URL | Langue | Pays |
|--------|-----|--------|------|
| Hespress | hespress.com | Arabe | 🇲🇦 |
| Akhbarona | akhbarona.com | Arabe | 🇲🇦 |
| Barlamane | barlamane.com | Arabe | 🇲🇦 |
| Lakom (Lakome2) | lakome2.com | Arabe | 🇲🇦 |

### Sources internationales
| Source | URL | Langue | Pays |
|--------|-----|--------|------|
| Al Jazeera | aljazeera.com | Anglais | 🇶🇦 |
| BBC News | bbc.com/news | Anglais | 🇬🇧 |
| CNN | cnn.com | Anglais | 🇺🇸 |
| Reuters | reuters.com | Anglais | 🇬🇧 |

---

## 4. Architecture — Vue d'ensemble

MediaPulse implémente le pattern **Architecture Medallion** sur 7 couches :

```
Sources → Scraper → Kafka → Bronze → Silver → Gold → Warehouse → Dashboards
```

### Couches de données (Medallion)
| Couche | Rôle | Stockage |
|--------|------|---------|
| 🥉 **Bronze** | Données brutes immuables | MinIO `bronze/source=X/date=D/` |
| 🥈 **Silver** | Nettoyées, validées, dédupliquées | MinIO `silver/source=X/date=D/` |
| 🥇 **Gold** | Agrégats analytiques (TF-IDF, tendances) | MinIO `gold/table=X/run_date=D/` |
| 🗄️ **Warehouse** | Schéma en étoile PostgreSQL | `warehouse.fact_*`, `warehouse.dim_*` |

---

## 5. Choix technologiques

### Pourquoi Python + BeautifulSoup ?
→ Riche écosystème web scraping. Pydantic pour la validation stricte dès l'ingestion.
Chaque Article est validé (URL, langue ISO 639-1, timestamp UTC) avant d'entrer dans le pipeline.

### Pourquoi Apache Kafka ?
→ Découplage producteur/consommateur. Durabilité des messages (replay possible).
Indispensable pour un pipeline haute fréquence : le scraper n'attend pas que MinIO soit disponible.

### Pourquoi MinIO ?
→ API S3-compatible, déployable on-premise. Partitionnement `source/date` pour scans sélectifs.
Remplace AWS S3 sans changer une ligne de code (même API boto3/minio).

### Pourquoi l'Architecture Medallion ?
→ Chaque couche est immuable et rejouable. Si une transformation échoue, on peut la relancer
sans perdre les données brutes. Traçabilité complète de la data lineage.

### Pourquoi Apache Airflow ?
→ 5 DAGs versionnés dans le repo Git. CeleryExecutor pour scalabilité horizontale.
Interface visuelle pour le monitoring, les logs et le re-run des tâches échouées.

### Pourquoi PostgreSQL ?
→ Schéma en étoile avec contraintes d'intégrité (FK, CHECK). Vues SQL pré-calculées pour
les dashboards. Extension pgcrypto pour les UUIDs de qualité.

### Pourquoi Prometheus + Grafana ?
→ Dashboards provisionnés automatiquement (JSON versionné dans Git). Alertes configurables.
Scrape des exporteurs Kafka et PostgreSQL pour une vue end-to-end.

### Pourquoi Docker Compose ?
→ Déploiement en une commande (`docker compose up --build`). Reproductible sur toute machine.
18 services orchestrés avec leurs volumes et réseaux.

---

## 6. Pipeline de données (7 étapes)

### Étape 1 — Scraping
Le `GenericArticleScraper` crawle les pages d'index, identifie les URLs d'articles par regex,
télécharge et parse le HTML avec BeautifulSoup. Chaque article est validé par Pydantic.

### Étape 2 — Publication Kafka
Le `KafkaProducer` sérialise l'article en JSON (ensure_ascii=False pour l'arabe) et publie
sur le topic `raw-articles`.

### Étape 3 — Stockage Bronze
Le `KafkaConsumer` lit par micro-lots de 50 et écrit dans MinIO :
`bronze/source={src}/date={date}/{url_hash}.json`

### Étape 4 — Transformation Bronze → Silver
Nettoyage HTML, normalisation Unicode NFKC, détection langue (langdetect seed=0),
hash SHA-256 de l'URL, validation 6 règles. Records invalides → `silver/_rejected/`.

### Étape 5 — Agrégation Silver → Gold
Tokenisation multilingue (arabe U+0600-U+06FF + latin), calcul TF-IDF, agrégation
des tendances quotidiennes, comptages par source et pays.

### Étape 6 — Chargement Warehouse
UPSERT dimensions (dim_source, dim_date, dim_category), INSERT faits
(fact_articles, fact_keyword_frequency, fact_daily_trends).

### Étape 7 — Visualisation
Grafana se connecte au warehouse via datasource PostgreSQL. Dashboard provisionné
automatiquement avec 8 panels : volume, langue, top-keywords, tendances, qualité, Kafka, PG.

---

## 7. Qualité des données

### 6 règles de validation Silver

| Règle | Condition |
|-------|-----------|
| `title_not_empty` | Titre non vide après nettoyage HTML |
| `published_at_not_null` | Date de publication parseable |
| `content_length_gt_100` | Contenu > 100 caractères |
| `url_valid` | Scheme http/https + domaine valide |
| `url_hash_not_empty` | Hash SHA-256 présent |
| `url_unique` | URL non vue dans la même run |

### Traçabilité
Chaque record rejeté est archivé avec :
- `bronze_object_path` : chemin exact du fichier source
- `issues` : liste des `QualityIssue` avec `rule_name`, `message`, `severity`
- `rejected_at` : timestamp UTC du rejet

---

## 8. Gouvernance et monitoring

| Mécanisme | Outil | Détail |
|-----------|-------|--------|
| Lineage temporelle | Airflow DAG logs | Chaque run est tracé avec son timestamp et ses métriques |
| Alertes données périmées | Prometheus | Alerte si aucun article depuis > 6h |
| Taux de rejet | Prometheus / Grafana | Alerte si rejection_rate > 20% |
| Consumer lag | Kafka exporter | Alerte si lag > 1000 messages |
| Santé PostgreSQL | postgres-exporter | Connexions, taille, latence requêtes |
| Score qualité | `warehouse.data_quality_score` | Vue SQL : % passed/failed par couche |

---

## 9. Démonstration

### Démarrage en une commande
```powershell
cd architecture-project\mediapulse
docker compose --profile demo up --build demo-seed
```

### URLs des services
| Service | URL | Identifiants |
|---------|-----|-------------|
| Airflow | http://localhost:8080 | admin / admin |
| Grafana | http://localhost:3001 | admin / .env |
| MinIO Console | http://localhost:9001 | mediapulse_minio / .env |
| Metabase | http://localhost:3000 | wizard 1ère connexion |
| Prometheus | http://localhost:9090 | — |

---

## 10. Limites et évolutions

### Limites actuelles
- Sélecteurs HTML sensibles aux changements de structure des sites
- Kafka avec `replication_factor=1` (dev uniquement, pas tolérant aux pannes)
- Pas d'analyse de sentiment (champ `sentiment_score` réservé mais non calculé)

### Évolutions prévues
- Hardening des sélecteurs avec détection automatique des changements
- Analyse de sentiment multilingue (AraBERT pour l'arabe)
- API REST pour interroger le warehouse programmatiquement
- Alertes Slack/email sur les règles Prometheus
- Déploiement Kubernetes en production
