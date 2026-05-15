# Guide de Déploiement — MediaPulse

## Option A — Docker Compose (Développement / Démo)

### Prérequis
- Docker Desktop 24+
- Docker Compose v2.20+
- 8 Go de RAM disponible

### Démarrage complet

```powershell
# 1. Cloner le dépôt
git clone https://github.com/ayoublafdaigui/architecture-project.git
cd architecture-project

# 2. Configurer l'environnement
Copy-Item mediapulse\.env.example mediapulse\.env
# Éditer mediapulse\.env (changer les mots de passe si besoin)

# 3. Démarrer le stack
cd mediapulse
docker compose up --build

# 4. Vérifier que tous les services sont UP
docker compose ps
```

### Mode démonstration (warehouse pré-rempli)

```powershell
cd mediapulse
docker compose --profile demo up --build demo-seed
# Génère 14 jours × 16 articles dans le warehouse
# Grafana est immédiatement utilisable avec des données réelles
```

### Arrêt et nettoyage

```powershell
docker compose down           # Arrêt (volumes conservés)
docker compose down -v        # Arrêt + suppression des volumes
docker compose down --rmi all # Arrêt + suppression des images
```

---

## Option B — Kubernetes (Production)

### Prérequis
- Kubernetes 1.28+ (k3s, minikube, ou cluster cloud)
- kubectl configuré
- Image Docker publiée dans un registry (GHCR, Docker Hub)

### Déploiement pas à pas

```bash
# 1. Créer le namespace
kubectl apply -f kubernetes/namespace.yaml

# 2. Créer les secrets (modifier d'abord les valeurs !)
kubectl apply -f kubernetes/secret.yaml

# 3. Appliquer la ConfigMap
kubectl apply -f kubernetes/configmap.yaml

# 4. Déployer PostgreSQL
kubectl apply -f kubernetes/postgres.yaml

# 5. Déployer le scraper (CronJob) + consumer (Deployment)
kubectl apply -f kubernetes/scraper.yaml

# 6. Déployer Grafana
kubectl apply -f kubernetes/grafana.yaml

# 7. Vérifier l'état
kubectl get all -n mediapulse
kubectl get pods -n mediapulse -w
```

### Vérifier les logs

```bash
# Logs du scraper (dernier job)
kubectl logs -n mediapulse -l app=mediapulse-scraper --tail=50

# Logs du stream consumer
kubectl logs -n mediapulse deployment/stream-consumer -f

# Logs Grafana
kubectl logs -n mediapulse deployment/grafana
```

### Accès aux services (avec port-forward)

```bash
# Grafana
kubectl port-forward -n mediapulse svc/grafana-service 3001:3000

# PostgreSQL
kubectl port-forward -n mediapulse svc/postgres-service 5432:5432
```

---

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `KAFKA_BOOTSTRAP_SERVERS` | Adresse Kafka | `kafka:29092` |
| `KAFKA_RAW_ARTICLES_TOPIC` | Nom du topic | `raw-articles` |
| `MINIO_ENDPOINT` | Endpoint MinIO | `minio:9000` |
| `MINIO_BUCKET` | Bucket principal | `mediapulse` |
| `POSTGRES_HOST` | Hôte PostgreSQL | `postgres` |
| `POSTGRES_DB` | Base de données | `mediapulse` |
| `SCRAPER_MAX_ARTICLES_PER_RUN` | Articles max/run | `25` |
| `SCRAPER_REQUEST_TIMEOUT_SECONDS` | Timeout HTTP | `20` |
| `GF_SECURITY_ADMIN_PASSWORD` | Mot de passe Grafana | (à définir) |
| `AIRFLOW__CORE__FERNET_KEY` | Clé Airflow | (générer avec `fernet_key`) |

### Générer les clés Airflow

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## Santé du système

```powershell
# Vérifier la connectivité de tous les services
python -m mediapulse doctor

# Exemple de sortie attendue :
# ✓ MinIO    : connecté (bucket mediapulse OK)
# ✓ Kafka    : connecté (broker kafka:29092)
# ✓ PostgreSQL: connecté (db mediapulse)
```
