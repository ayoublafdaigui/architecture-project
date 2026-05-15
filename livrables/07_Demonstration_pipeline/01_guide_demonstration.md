# Guide de Démonstration — Pipeline Bout en Bout

## Durée estimée : 15-20 minutes

---

## Étape A — Démarrer le stack (5 min)

```powershell
cd architecture-project\mediapulse
docker compose --profile demo up --build demo-seed
```

Pendant le démarrage, expliquer :
- **Kafka + Zookeeper** : bus de messages pour le streaming
- **MinIO** : data lake compatible S3 (Bronze / Silver / Gold)
- **PostgreSQL** : entrepôt analytique en schéma étoile
- **Airflow** : orchestration des DAGs
- **Grafana** : dashboards provisionnés automatiquement

---

## Étape B — Montrer le scraping en temps réel (3 min)

```powershell
# Dans un nouveau terminal
cd architecture-project
python -m mediapulse scrape --source hespress
```

**Points à montrer :**
- Les URLs détectées par pattern regex : `hespress.com/.+/\d+/`
- La validation Pydantic (articles rejetés si titre vide, URL invalide…)
- Les articles écrits dans MinIO : `bronze/source=hespress/date=.../`

**Dans MinIO Console (http://localhost:9001) :**
- Naviguer dans `mediapulse` → `bronze/` → `source=hespress/`
- Ouvrir un fichier JSON pour montrer la structure brute

---

## Étape C — Pipeline Bronze → Silver (3 min)

```powershell
python -m mediapulse bronze-to-silver --source hespress
```

**Output console à commenter :**
```
INFO  Found 23 Bronze object(s) under bronze/source=hespress
INFO  Wrote Silver object s3://mediapulse/silver/source=hespress/...
WARN  Rejected Bronze object ... (rule: content_length_gt_100)
INFO  Run complete: scanned=23, accepted=20, rejected=2, duplicate=1
```

**Points à expliquer :**
- **Nettoyage HTML** : balises `<p>`, `<span>`, `<br>` supprimées
- **Normalisation** : Unicode NFKC, entités HTML (`&amp;` → `&`)
- **Détection langue** : `langdetect` → `ar`, `en`, `fr`
- **Déduplication** : SHA-256 de l'URL, doublons mis en quarantaine
- **Enregistrements rejetés** : naviguer dans `silver/_rejected/` sur MinIO

---

## Étape D — Agrégation Silver → Gold (2 min)

```powershell
python -m mediapulse silver-to-gold
```

**Points à montrer :**
- Top-50 keywords avec score TF-IDF
- Tendances quotidiennes groupées par topic
- Fichiers Gold dans MinIO : `gold/table=keyword_frequency/run_date=.../`

---

## Étape E — Chargement du Warehouse (1 min)

```powershell
python -m mediapulse load-warehouse
```

**Vérifier dans PostgreSQL (via psql ou Metabase) :**
```sql
-- Nombre d'articles chargés
SELECT COUNT(*) FROM warehouse.fact_articles;

-- Répartition par source
SELECT s.source_name, COUNT(*) as articles
FROM warehouse.fact_articles a
JOIN warehouse.dim_source s ON s.source_key = a.source_key
GROUP BY s.source_name ORDER BY articles DESC;
```

---

## Étape F — Dashboards Grafana (3 min)

1. Ouvrir **http://localhost:3001** → Dashboards → MediaPulse
2. Montrer panel par panel :

| Panel | Point à expliquer |
|-------|------------------|
| Volume par jour | Pipeline Airflow planifié toutes les 6h |
| Répartition linguistique | 4 sources arabes + 4 sources anglaises |
| Top Keywords | TF-IDF calculé en Python, pas de service externe |
| Score de qualité | 87% d'acceptation = signe d'un pipeline sain |
| Consumer lag | Kafka stream en quasi temps-réel |

---

## Étape G — Orchestration Airflow (2 min)

1. Ouvrir **http://localhost:8080** (admin/admin)
2. Montrer les 5 DAGs :
   - `mediapulse_batch_scrape` — déclencher manuellement
   - `mediapulse_bronze_to_silver` — voir les logs de task
   - `mediapulse_data_quality` — rapport qualité automatique

3. Montrer le **Graph View** d'un DAG pour illustrer les dépendances

---

## Points forts à mettre en avant

1. **Architecture Medallion** : chaque couche est immuable et rejouable
2. **100% containerisé** : `docker compose up` suffit, aucune installation manuelle
3. **Multilingue** : arabe + anglais + français, détection automatique
4. **Qualité traçable** : chaque record rejeté est archivé avec la raison
5. **Dashboards prêts à l'emploi** : provisionnement automatique Grafana
6. **Code testé** : 4 fichiers de tests, pipeline de bout en bout
