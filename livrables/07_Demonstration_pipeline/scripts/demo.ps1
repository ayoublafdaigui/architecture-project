# demo.ps1 - Démonstration automatisée MediaPulse (Windows PowerShell)
# Usage: .\livrables\07_Demonstration_pipeline\scripts\demo.ps1
# Pré-requis: docker compose up --build (depuis mediapulse/) déjà lancé

$PASS = 0
$FAIL = 0
$BASE_URL_AIRFLOW   = "http://localhost:8080"
$BASE_URL_GRAFANA   = "http://localhost:3001"
$BASE_URL_MINIO     = "http://localhost:9001"
$BASE_URL_PROMETHEUS= "http://localhost:9090"
$PG_CONTAINER       = "mediapulse-postgres-1"

function Write-Pass { param($msg) Write-Host "  [PASS] $msg" -ForegroundColor Green; $script:PASS++ }
function Write-Fail { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red;  $script:FAIL++ }
function Write-Step { param($n, $msg) Write-Host "`n=== Etape $n : $msg ===" -ForegroundColor Cyan }

Write-Host @"
========================================================
  MediaPulse - Demonstration automatisee (PowerShell)
  Auteur : Ayoub Lafdaigui
  Date   : $(Get-Date -Format 'yyyy-MM-dd')
========================================================
"@ -ForegroundColor Yellow

# ─── Étape 1 : Vérification Docker ────────────────────────────────────────────
Write-Step 1 "Verification des conteneurs Docker"

$running = docker ps --format "{{.Names}}" 2>$null
$required = @("postgres","kafka","minio","grafana","airflow-webserver")
foreach ($svc in $required) {
    if ($running -match $svc) { Write-Pass "Conteneur $svc en cours d'execution" }
    else                       { Write-Fail "Conteneur $svc introuvable" }
}

# ─── Étape 2 : Seed des données de démonstration ──────────────────────────────
Write-Step 2 "Chargement des donnees de demonstration (warehouse)"

try {
    $result = docker exec $PG_CONTAINER psql -U mediapulse -d mediapulse -t -c `
        "SELECT COUNT(*) FROM warehouse.fact_articles;" 2>$null
    $count = [int]($result.Trim())
    if ($count -gt 0) { Write-Pass "warehouse.fact_articles contient $count articles" }
    else {
        Write-Host "  Seeding en cours..." -ForegroundColor Yellow
        docker exec $PG_CONTAINER psql -U mediapulse -d mediapulse -c `
            "SELECT COUNT(*) FROM warehouse.fact_articles;" 2>$null | Out-Null
        Write-Fail "Aucun article dans le warehouse (executer seed-demo)"
    }
} catch { Write-Fail "Impossible d'acceder a PostgreSQL" }

# ─── Étape 3 : Vérification MinIO Bronze ──────────────────────────────────────
Write-Step 3 "Verification du Data Lake MinIO (Bronze)"

try {
    $resp = Invoke-WebRequest -Uri "$BASE_URL_MINIO/login" -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { Write-Pass "MinIO Console accessible sur $BASE_URL_MINIO" }
    else                           { Write-Fail "MinIO Console retourne HTTP $($resp.StatusCode)" }
} catch { Write-Fail "MinIO Console inaccessible - verifier que le stack est demarre" }

# ─── Étape 4 : Vérification Airflow ───────────────────────────────────────────
Write-Step 4 "Verification Airflow (orchestration)"

try {
    $resp = Invoke-WebRequest -Uri "$BASE_URL_AIRFLOW/health" -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { Write-Pass "Airflow Webserver sain sur $BASE_URL_AIRFLOW" }
    else                           { Write-Fail "Airflow retourne HTTP $($resp.StatusCode)" }
} catch { Write-Fail "Airflow Webserver inaccessible" }

# ─── Étape 5 : Vérification Grafana ───────────────────────────────────────────
Write-Step 5 "Verification Grafana (dashboards)"

try {
    $resp = Invoke-WebRequest -Uri "$BASE_URL_GRAFANA/api/health" -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { Write-Pass "Grafana accessible sur $BASE_URL_GRAFANA" }
    else                           { Write-Fail "Grafana retourne HTTP $($resp.StatusCode)" }
} catch { Write-Fail "Grafana inaccessible" }

# ─── Étape 6 : Score qualité warehouse ────────────────────────────────────────
Write-Step 6 "Verification score qualite warehouse"

try {
    $result = docker exec $PG_CONTAINER psql -U mediapulse -d mediapulse -t -c `
        "SELECT ROUND(100.0 * COUNT(*) FILTER(WHERE content_length > 100) / COUNT(*), 1)
         FROM warehouse.fact_articles;" 2>$null
    $score = [double]($result.Trim())
    if ($score -ge 80) { Write-Pass "Score qualite : $score% (seuil: 80%)" }
    else               { Write-Fail "Score qualite trop bas : $score%" }
} catch { Write-Fail "Impossible de calculer le score qualite" }

# ─── Étape 7 : Prometheus ─────────────────────────────────────────────────────
Write-Step 7 "Verification Prometheus (monitoring)"

try {
    $resp = Invoke-WebRequest -Uri "$BASE_URL_PROMETHEUS/-/healthy" -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { Write-Pass "Prometheus operationnel sur $BASE_URL_PROMETHEUS" }
    else                           { Write-Fail "Prometheus retourne HTTP $($resp.StatusCode)" }
} catch { Write-Fail "Prometheus inaccessible" }

# ─── Résumé ────────────────────────────────────────────────────────────────────
$TOTAL = $PASS + $FAIL
Write-Host "`n======================================================" -ForegroundColor Yellow
Write-Host "  RESULTAT : $PASS PASS / $FAIL FAIL  (sur $TOTAL verifications)" -ForegroundColor $(if ($FAIL -eq 0) {"Green"} else {"Red"})
Write-Host "======================================================" -ForegroundColor Yellow

if ($FAIL -eq 0) {
    Write-Host @"

  Tous les tests sont PASSES !
  Ouvrir les interfaces :
    Grafana   : $BASE_URL_GRAFANA
    Airflow   : $BASE_URL_AIRFLOW
    MinIO     : $BASE_URL_MINIO
    Metabase  : http://localhost:3000
    Prometheus: $BASE_URL_PROMETHEUS
"@ -ForegroundColor Green
} else {
    Write-Host "`n  Verifier que le stack est demarre : cd mediapulse && docker compose up --build" -ForegroundColor Yellow
}
