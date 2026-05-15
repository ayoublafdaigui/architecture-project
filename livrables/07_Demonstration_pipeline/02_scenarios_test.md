# Scénarios de Test — Validation du Pipeline

## Test 1 — Validation du modèle Article (Pydantic)

```powershell
python -m pytest mediapulse/tests/test_article_model.py -v
```

| Cas testé | Résultat attendu |
|-----------|-----------------|
| Article valide (tous champs) | Création réussie |
| Titre vide `""` | `ValidationError` |
| URL invalide `"not-a-url"` | `ValidationError` |
| Langue invalide `"francais"` | `ValidationError` (pas ISO 639-1) |
| `published_at` sans timezone | Converti en UTC automatiquement |
| `url_hash` | SHA-256 stable et reproductible |

## Test 2 — Pipeline Bronze → Silver

```powershell
python -m pytest mediapulse/tests/test_bronze_to_silver.py -v
```

| Cas testé | Résultat attendu |
|-----------|-----------------|
| Article HTML avec `<p>`, `<strong>` | Tags supprimés, texte conservé |
| Entités HTML `&amp;`, `&eacute;` | Décodées correctement |
| Caractères zéro-width `​` | Supprimés |
| Même URL vue 2 fois | Deuxième → rejeté (rule: `url_unique`) |
| Contenu 50 caractères | Rejeté (rule: `content_length_gt_100`) |
| Date `"2026-05-15T10:00:00"` (sans tz) | Assumé UTC |
| Langue `"ar-MA"` | Normalisé en `"ar"` |

## Test 3 — Agrégation Silver → Gold

```powershell
python -m pytest mediapulse/tests/test_silver_to_gold.py -v
```

| Cas testé | Résultat attendu |
|-----------|-----------------|
| 10 articles, 3 sources | Comptages corrects par source |
| Stopwords EN/FR/AR filtrés | Absents du top-keywords |
| Mots < 3 caractères | Filtrés par TOKEN_PATTERN |
| TF-IDF > 0 pour mots fréquents | Score calculé correctement |

## Test 4 — Données de démonstration

```powershell
python -m pytest mediapulse/tests/test_demo_seed.py -v
```

| Cas testé | Résultat attendu |
|-----------|-----------------|
| `seed_demo(days=7)` | 7 × 16 articles générés |
| Dates dans la plage demandée | Toutes dans [today-7, today] |
| Sources variées | 8 sources différentes représentées |
| Langues cohérentes avec source | Hespress → `ar`, BBC → `en` |

## Exécution de la suite complète

```powershell
python -m pytest mediapulse/tests/ -v --tb=short

# Avec rapport de couverture
python -m pytest mediapulse/tests/ --cov=mediapulse --cov-report=html
# Ouvrir htmlcov/index.html
```
