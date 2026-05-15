# Guide d'Installation — MediaPulse

## Prérequis système

| Outil | Version minimale | Vérification |
|-------|-----------------|-------------|
| Docker Desktop | 24.0+ | `docker --version` |
| Docker Compose | v2.20+ | `docker compose version` |
| Python | 3.11+ | `python --version` |
| Git | 2.40+ | `git --version` |
| RAM disponible | 8 Go | Task Manager → Performance |

---

## Étape 1 — Cloner le dépôt

```powershell
git clone https://github.com/ayoublafdaigui/architecture-project.git
cd architecture-project
```

## Étape 2 — Configurer l'environnement

```powershell
Copy-Item mediapulse\.env.example mediapulse\.env
```

Ouvrir `mediapulse\.env` et vérifier/modifier :

```ini
# Scraper
SCRAPER_MAX_ARTICLES_PER_RUN=25
SCRAPER_REQUEST_TIMEOUT_SECONDS=20

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
KAFKA_RAW_ARTICLES_TOPIC=raw-articles

# MinIO
MINIO_ROOT_USER=mediapulse_minio
MINIO_ROOT_PASSWORD=change_me_minio_password   ← CHANGER
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=mediapulse

# PostgreSQL
POSTGRES_USER=mediapulse
POSTGRES_PASSWORD=change_me_postgres_password  ← CHANGER
POSTGRES_DB=mediapulse
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Grafana
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=change_me_grafana_password  ← CHANGER
```

> **Sécurité :** Le fichier `.env` est exclu par `.gitignore` — il ne sera jamais commité.

## Étape 3 — Installer les dépendances Python (optionnel, pour CLI local)

```powershell
# Créer un environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Installer les dépendances
pip install -r mediapulse\requirements.txt
```

Dépendances principales :

| Package | Version | Usage |
|---------|---------|-------|
| pydantic | 2.8.2 | Validation Article model |
| beautifulsoup4 | 4.12.3 | Parsing HTML |
| kafka-python | 2.0.2 | Kafka producer/consumer |
| minio | 7.2.7 | Client MinIO S3 |
| pandas | 2.2.2 | Agrégation Gold |
| langdetect | 1.0.9 | Détection de langue |
| spacy | 3.7.5 | Tokenisation NLP |
| psycopg | 3.2.1 | Client PostgreSQL |
| requests | 2.32.3 | HTTP scraping |

## Étape 4 — Démarrer le stack Docker

```powershell
cd mediapulse
docker compose up --build
```

La première exécution télécharge ~5 Go d'images. Les suivantes démarrent en ~60 secondes.

## Étape 5 — Vérifier le démarrage

```powershell
# Voir l'état de tous les conteneurs
docker compose ps

# Sortie attendue (tous STATUS = running ou exited 0 pour les init)
NAME                        STATUS
mediapulse-zookeeper-1      running
mediapulse-kafka-1          running
mediapulse-minio-1          running
mediapulse-minio-init-1     exited (0)
mediapulse-postgres-1       running
mediapulse-redis-1          running
mediapulse-airflow-init-1   exited (0)
mediapulse-airflow-webserver-1  running
mediapulse-airflow-scheduler-1  running
mediapulse-airflow-worker-1     running
mediapulse-grafana-1        running
mediapulse-prometheus-1     running
mediapulse-metabase-1       running
```

## Étape 6 — Vérifier la connectivité (CLI)

```powershell
# Depuis le répertoire architecture-project/
python -m mediapulse doctor
```

Résultat attendu :
```
✓ MinIO     : OK (bucket mediapulse accessible)
✓ Kafka     : OK (broker kafka:29092 accessible)
✓ PostgreSQL: OK (base mediapulse accessible)
```

## Dépannage courant

| Symptôme | Cause probable | Solution |
|----------|---------------|---------|
| Port 9092 already in use | Kafka local ou autre service | `netstat -ano | findstr 9092` puis arrêter le service |
| Port 5432 already in use | PostgreSQL local | Arrêter le service local ou changer le port dans `.env` |
| airflow-init en erreur | PostgreSQL pas encore prêt | Attendre 30s et relancer avec `docker compose up airflow-init` |
| Minio inaccessible | Démarrage lent | Attendre 60s après `docker compose up` |
| Module not found (python) | Venv non activé | `.\.venv\Scripts\Activate.ps1` |
