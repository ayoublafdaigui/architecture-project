# MediaPulse — Livrables du Projet

**Module :** Architecture des Données  
**Auteur :** Ayoub Lafdaigui  
**Date de rendu :** 15 Mai 2026  
**Dépôt GitHub :** https://github.com/ayoublafdaigui/architecture-project  

---

## Validation des livrables

| # | Livrable | Dossier | Fichiers clés | ✅ |
|---|---------|---------|--------------|---|
| 1 | Présentation détaillée (contexte, architecture, choix technos) | [`01_Presentation_detaillee/`](01_Presentation_detaillee/) | `PRESENTATION.md` | ✅ |
| 2 | Schéma d'architecture (couches + flux de données) | [`02_Schema_architecture/`](02_Schema_architecture/) | `ARCHITECTURE.md` (Mermaid) | ✅ |
| 3 | Code source versionné sur Git | [`03_Code_source_Git/`](03_Code_source_Git/) | `LIEN GITHUB.txt` | ✅ |
| 4 | Fichiers de déploiement (Docker + Kubernetes) | [`04_Fichiers_deploiement/`](04_Fichiers_deploiement/) | `docker-compose.yml` · `kubernetes/` | ✅ |
| 5 | Documentation technique d'installation et d'utilisation | [`05_Documentation_technique/`](05_Documentation_technique/) | `INSTALLATION.md` · `guide_utilisation.md` | ✅ |
| 6 | Dashboards de visualisation des indicateurs clés | [`06_Dashboards_visualisation/`](06_Dashboards_visualisation/) | `grafana_dashboards/` · `flask_dashboard/` | ✅ |
| 7 | Démonstration fonctionnelle du pipeline de bout en bout | [`07_Demonstration_pipeline/`](07_Demonstration_pipeline/) | `DEMO.md` · `scripts/demo.ps1` · `scripts/demo.sh` | ✅ |

---

## Démo en une commande

```powershell
# 1. Démarrer le stack avec données de démonstration
cd architecture-project\mediapulse
docker compose --profile demo up --build demo-seed

# 2. Vérification automatisée (7 checks)
.\livrables\07_Demonstration_pipeline\scripts\demo.ps1

# 3. Ouvrir les interfaces
start http://localhost:3001   # Grafana (dashboards)
start http://localhost:8080   # Airflow (orchestration)
start http://localhost:9001   # MinIO Console (data lake)
start http://localhost:3000   # Metabase (analytics)
start http://localhost:9090   # Prometheus (monitoring)
```

---

## Technologies utilisées

| Couche | Technologie | Version |
|--------|------------|---------|
| Scraping | Python + BeautifulSoup4 + Pydantic | 3.11 / 4.12 / 2.8 |
| Streaming | Apache Kafka (Confluent) | 7.6.1 |
| Data Lake | MinIO (S3-compatible) | 2024-07 |
| Orchestration | Apache Airflow + Celery + Redis | 2.9.3 |
| Entrepôt | PostgreSQL | 16 |
| Dashboards | Grafana | 11.1.0 |
| Analytics | Metabase | 0.50.18 |
| Monitoring | Prometheus | 2.53.1 |
| Déploiement | Docker Compose + Kubernetes | v2.20+ |
