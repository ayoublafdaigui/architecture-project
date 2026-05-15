# Metabase — Analytics Self-Service

## Accès et configuration initiale

1. Ouvrir **http://localhost:3000**
2. Suivre le wizard de premier démarrage
3. À l'étape "Add your data" → choisir **PostgreSQL**
4. Paramètres de connexion :

| Champ | Valeur |
|-------|--------|
| Host | `postgres` (dans Docker) ou `localhost` (en local) |
| Port | `5432` |
| Database | `mediapulse` |
| Username | `mediapulse` |
| Password | (valeur de `.env` → `POSTGRES_PASSWORD`) |

## Questions suggérées à explorer

### Volume d'articles
```
Table : warehouse.fact_articles
→ Grouper par : published_at (jour), source_key
→ Métrique : COUNT(article_key)
→ Visualisation : Line chart
```

### Top sources par langue
```
Table : warehouse.fact_articles
→ Jointure : dim_source (source_name), fact_articles (language_code)
→ Grouper par : source_name, language_code
→ Métrique : COUNT(*)
→ Visualisation : Bar chart groupé
```

### Évolution des tendances
```
Table : warehouse.fact_daily_trends
→ Jointure : dim_date (full_date)
→ Filtrer : topic = "Maroc" (par exemple)
→ Grouper par : full_date
→ Métrique : SUM(article_count)
→ Visualisation : Area chart
```

### Rapport de qualité
```
Table : warehouse.quality_report
→ Grouper par : layer_name, rule_name
→ Filtrer : status = 'failed'
→ Métrique : COUNT(*)
→ Visualisation : Horizontal bar
```

## Avantages de Metabase pour les équipes métier

- **Aucun SQL requis** — interface point-and-click
- **Partage facile** — liens publics ou intégration iframe
- **Alertes** — notification par email si un chiffre dépasse un seuil
- **Exports** — CSV, Excel, PDF en un clic
