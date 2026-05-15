# Déploiement Kubernetes — MediaPulse

## Ordre de déploiement

```bash
# 1. Namespace
kubectl apply -f 00-namespace.yaml

# 2. Configuration et secrets
kubectl apply -f 01-config.yaml
kubectl apply -f 02-secret.yaml

# 3. Base de données
kubectl apply -f 10-postgres.yaml

# 4. Scraper et consumer
kubectl apply -f 20-scraper.yaml

# 5. Monitoring (Prometheus + Grafana)
kubectl apply -f 40-monitoring.yaml

# Vérifier
kubectl get all -n mediapulse
```

## Manifestes

| Fichier | Ressources |
|---------|-----------|
| `00-namespace.yaml` | Namespace `mediapulse` |
| `01-config.yaml` | ConfigMap (URLs, variables non-sensibles) |
| `02-secret.yaml` | Secret (mots de passe MinIO, PostgreSQL, Grafana) |
| `10-postgres.yaml` | PostgreSQL StatefulSet + PVC 10Gi + Service |
| `20-scraper.yaml` | CronJob scraper (toutes les 6h) + Deployment stream-consumer |
| `40-monitoring.yaml` | Grafana Deployment + Service LoadBalancer + Ingress |

## Accès aux services (port-forward)

```bash
# Grafana
kubectl port-forward -n mediapulse svc/grafana-service 3001:3000

# PostgreSQL
kubectl port-forward -n mediapulse svc/postgres-service 5432:5432
```

## Prérequis
- Kubernetes 1.28+
- kubectl configuré
- Image publiée : `ghcr.io/ayoublafdaigui/mediapulse-scraper:latest`
