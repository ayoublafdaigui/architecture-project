# Contexte et Objectifs — MediaPulse

## 1. Contexte

Le paysage médiatique marocain est riche et fragmenté : des dizaines de sites d'information publient
chaque jour des centaines d'articles en **arabe**, **français** et **anglais**.
À côté de ces sources locales, les grandes chaînes internationales (Al Jazeera, BBC, CNN, Reuters)
couvrent les mêmes événements avec un regard extérieur.

Il n'existait pas d'outil unifié permettant de **collecter, normaliser, comparer et visualiser**
cette information de manière automatisée.

### Problème résolu

> Un analyste qui veut savoir « quels sujets dominent l'actualité marocaine cette semaine ? »
> devait visiter manuellement 8 sites, lire des articles en 3 langues et consolider ses notes dans Excel.
> **MediaPulse automatise tout ce processus en quelques minutes.**

---

## 2. Sources couvertes

| Source | Pays | Langue | Type |
|--------|------|--------|------|
| Hespress | 🇲🇦 Maroc | Arabe | Nationale |
| Akhbarona | 🇲🇦 Maroc | Arabe | Nationale |
| Barlamane | 🇲🇦 Maroc | Arabe | Nationale |
| Lakom (Lakome2) | 🇲🇦 Maroc | Arabe | Nationale |
| Al Jazeera | 🇶🇦 Qatar | Anglais | Internationale |
| BBC News | 🇬🇧 Royaume-Uni | Anglais | Internationale |
| CNN | 🇺🇸 États-Unis | Anglais | Internationale |
| Reuters | 🇬🇧 Royaume-Uni | Anglais | Internationale |

---

## 3. Objectifs techniques

| Objectif | Critère de succès |
|----------|-------------------|
| **Collecte automatisée** | Scraper 8 sources sans intervention humaine via Airflow DAGs |
| **Streaming fiable** | Articles transmis via Kafka (topic `raw-articles`) avec garantie de livraison |
| **Qualité des données** | Pipeline Bronze→Silver avec 6 règles de validation, rejet traçable |
| **Agrégation analytique** | Couche Gold : top-keywords TF-IDF, tendances, comptages journaliers |
| **Entrepôt de données** | Schéma en étoile PostgreSQL (dim_source, dim_date, fact_articles…) |
| **Visualisation** | Dashboards Grafana provisionnés automatiquement, métriques Prometheus |

---

## 4. Indicateurs clés du projet

| Indicateur | Valeur |
|------------|--------|
| Sources d'actualité | **8** |
| Couches de données (Medallion) | **3** (Bronze, Silver, Gold) |
| DAGs Apache Airflow | **5** |
| Services Docker | **18** |
| Règles de qualité Silver | **6** |
| Langues supportées | **3** (arabe, anglais, français) |
| Tables warehouse | **7** (4 faits + 3 dimensions) |
