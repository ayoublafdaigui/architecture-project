# Livrable 7 — Démonstration Fonctionnelle du Pipeline

## Fichiers

| Fichier | Contenu |
|---------|---------|
| [`01_guide_demonstration.md`](01_guide_demonstration.md) | Guide pas à pas pour la démonstration live |
| [`02_scenarios_test.md`](02_scenarios_test.md) | Scénarios de test et cas limites |
| [`03_resultats_attendus.md`](03_resultats_attendus.md) | Captures d'écran décrites et métriques attendues |

## Démarrage rapide pour la démo

```powershell
# 1. Démarrer le stack avec données pré-remplies
cd mediapulse
docker compose --profile demo up --build demo-seed

# 2. Ouvrir Grafana
start http://localhost:3001

# 3. Ouvrir Airflow
start http://localhost:8080
```

La démo est prête en ~5 minutes.
