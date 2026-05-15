# Démonstration Fonctionnelle — MediaPulse

**Durée estimée :** 10-15 minutes  
**Pré-requis :** Docker Desktop démarré

---

## Étape 1 — Démarrer le stack (2 min)

```powershell
cd architecture-project\mediapulse
docker compose --profile demo up --build demo-seed
```

Attendre que tous les services soient `running` :
```powershell
docker compose ps
```

**Vérification automatisée :**
```powershell
.\livrables\07_Demonstration_pipeline\scripts\demo.ps1
```

Résultat attendu : `7 PASS / 0 FAIL`

---

## Étape 2 — Données de démonstration pré-chargées (warehouse)

Le service `demo-seed` a généré **14 jours × 16 articles × 8 sources** dans le warehouse.

Vérifier dans PostgreSQL :
```sql
-- Connecter via: docker exec -it mediapulse-postgres-1 psql -U mediapulse -d mediapulse

SELECT s.source_name, COUNT(*) AS articles
FROM warehouse.fact_articles a
JOIN warehouse.dim_source s ON s.source_key = a.source_key
GROUP BY s.source_name ORDER BY articles DESC;
```

Résultat attendu :
```
 source_name  | articles
--------------+---------
 Hespress     |      224
 BBC News     |      224
 CNN          |      224
 ...          |      ...
```

---

## Étape 3 — Lancer un scraping en temps réel

```powershell
# Depuis architecture-project/
python -m mediapulse scrape --source hespress
```

**Observer :**
- Les URLs détectées par regex
- La validation Pydantic article par article
- Les fichiers JSON écrits dans MinIO Bronze

**Vérifier dans MinIO :**
1. Ouvrir http://localhost:9001
2. Naviguer : `mediapulse` → `bronze/` → `source=hespress/date=2026-05-15/`
3. Cliquer sur un fichier JSON → structure de l'article brut

---

## Étape 4 — Pipeline Bronze → Silver

```powershell
python -m mediapulse bronze-to-silver --source hespress
```

**Observer les logs :**
- Records acceptés vs rejetés
- Règles de qualité violées
- Fichiers dans `silver/_rejected/` (QualityIssue traçables)

---

## Étape 5 — Déclencher via Airflow

1. Ouvrir **http://localhost:8080** (admin / admin)
2. Activer le DAG `mediapulse_batch_scrape`
3. Cliquer ▶ **Trigger DAG**
4. Observer le **Graph View** : chaque nœud passe au vert
5. Cliquer sur une task → **Logs** pour voir les détails

---

## Étape 6 — Dashboards Grafana (point fort)

1. Ouvrir **http://localhost:3001**
2. **Dashboards** → **MediaPulse** → **MediaPulse News Intelligence**

| Panel | Ce qu'il montre |
|-------|----------------|
| Volume par jour | Courbes par source sur 14 jours |
| Répartition linguistique | 50% arabe / 50% anglais |
| Top Keywords | Mots-clés TF-IDF du jour |
| Tendances | Sujets trending avec score |
| Score qualité | ~88% d'acceptation (normal) |
| Consumer lag Kafka | ~0 (pipeline sain) |

---

## Étape 7 — Prometheus & alertes

1. Ouvrir **http://localhost:9090**
2. **Status → Targets** : vérifier `postgres-exporter` et `kafka-exporter` en `UP`
3. Requête PromQL : `pg_database_size_bytes{datname="mediapulse"}`
4. **Alerts** : voir les règles (StaleData, HighRejectionRate, KafkaConsumerLag)

---

## Étape 8 — Qualité des données

```powershell
python -m mediapulse quality --layer silver
```

Affiche :
```
Layer: silver
  Total checks : 160
  Passed       : 141 (88.1%)
  Failed       : 19
  Top violations:
    content_length_gt_100 : 12 occurrences
    published_at_not_null : 5 occurrences
    url_unique            : 2 occurrences
```

---

## Résumé des interfaces à ouvrir simultanément

```
Tab 1 : http://localhost:3001  → Grafana (dashboards)
Tab 2 : http://localhost:8080  → Airflow (DAGs)
Tab 3 : http://localhost:9001  → MinIO Console (data lake)
Tab 4 : http://localhost:3000  → Metabase (analytics self-service)
Tab 5 : http://localhost:9090  → Prometheus (métriques)
```
