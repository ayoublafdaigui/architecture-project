#!/usr/bin/env bash
# demo.sh - Démonstration automatisée MediaPulse (Linux/WSL/Git Bash)
# Usage: bash livrables/07_Demonstration_pipeline/scripts/demo.sh
# Pré-requis: docker compose up --build (depuis mediapulse/) déjà lancé

set -euo pipefail

PASS=0
FAIL=0
BASE_URL_AIRFLOW="http://localhost:8080"
BASE_URL_GRAFANA="http://localhost:3001"
BASE_URL_MINIO="http://localhost:9001"
BASE_URL_PROMETHEUS="http://localhost:9090"
PG_CONTAINER="mediapulse-postgres-1"

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $1"; ((PASS++)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; ((FAIL++)); }
step() { echo -e "\n${CYAN}=== Etape $1 : $2 ===${NC}"; }

echo -e "${YELLOW}"
echo "========================================================"
echo "  MediaPulse - Demonstration automatisee (bash)"
echo "  Auteur : Ayoub Lafdaigui"
echo "  Date   : $(date +%Y-%m-%d)"
echo "========================================================"
echo -e "${NC}"

# ─── Étape 1 : Vérification Docker ─────────────────────────────────────────────
step 1 "Verification des conteneurs Docker"

for svc in postgres kafka minio grafana airflow-webserver; do
    if docker ps --format '{{.Names}}' | grep -q "$svc"; then
        pass "Conteneur $svc en cours d'execution"
    else
        fail "Conteneur $svc introuvable"
    fi
done

# ─── Étape 2 : Seed des données de démonstration ───────────────────────────────
step 2 "Chargement des donnees de demonstration (warehouse)"

COUNT=$(docker exec "$PG_CONTAINER" psql -U mediapulse -d mediapulse -t \
    -c "SELECT COUNT(*) FROM warehouse.fact_articles;" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$COUNT" -gt 0 ] 2>/dev/null; then
    pass "warehouse.fact_articles contient $COUNT articles"
else
    fail "Aucun article dans le warehouse (executer: python -m mediapulse seed-demo)"
fi

# ─── Étape 3 : Vérification MinIO ──────────────────────────────────────────────
step 3 "Verification du Data Lake MinIO (Bronze)"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL_MINIO/login" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    pass "MinIO Console accessible sur $BASE_URL_MINIO"
else
    fail "MinIO Console inaccessible (HTTP $HTTP_STATUS)"
fi

# ─── Étape 4 : Vérification Airflow ────────────────────────────────────────────
step 4 "Verification Airflow (orchestration)"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL_AIRFLOW/health" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    pass "Airflow Webserver sain sur $BASE_URL_AIRFLOW"
else
    fail "Airflow Webserver inaccessible (HTTP $HTTP_STATUS)"
fi

# ─── Étape 5 : Vérification Grafana ────────────────────────────────────────────
step 5 "Verification Grafana (dashboards)"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL_GRAFANA/api/health" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    pass "Grafana accessible sur $BASE_URL_GRAFANA"
else
    fail "Grafana inaccessible (HTTP $HTTP_STATUS)"
fi

# ─── Étape 6 : Score qualité warehouse ─────────────────────────────────────────
step 6 "Verification score qualite warehouse"

SCORE=$(docker exec "$PG_CONTAINER" psql -U mediapulse -d mediapulse -t \
    -c "SELECT ROUND(100.0 * COUNT(*) FILTER(WHERE content_length > 100) / NULLIF(COUNT(*),0), 1)
        FROM warehouse.fact_articles;" 2>/dev/null | tr -d ' ' || echo "0")

if awk "BEGIN{exit !($SCORE >= 80)}" 2>/dev/null; then
    pass "Score qualite : ${SCORE}% (seuil: 80%)"
else
    fail "Score qualite trop bas : ${SCORE}%"
fi

# ─── Étape 7 : Prometheus ──────────────────────────────────────────────────────
step 7 "Verification Prometheus (monitoring)"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$BASE_URL_PROMETHEUS/-/healthy" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    pass "Prometheus operationnel sur $BASE_URL_PROMETHEUS"
else
    fail "Prometheus inaccessible (HTTP $HTTP_STATUS)"
fi

# ─── Résumé ────────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo ""
echo -e "${YELLOW}======================================================${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}RESULTAT : $PASS PASS / $FAIL FAIL  (sur $TOTAL verifications)${NC}"
else
    echo -e "  ${RED}RESULTAT : $PASS PASS / $FAIL FAIL  (sur $TOTAL verifications)${NC}"
fi
echo -e "${YELLOW}======================================================${NC}"

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}"
    echo "  Tous les tests sont PASSES !"
    echo "  Interfaces disponibles :"
    echo "    Grafana   : $BASE_URL_GRAFANA"
    echo "    Airflow   : $BASE_URL_AIRFLOW"
    echo "    MinIO     : $BASE_URL_MINIO"
    echo "    Metabase  : http://localhost:3000"
    echo "    Prometheus: $BASE_URL_PROMETHEUS"
    echo -e "${NC}"
else
    echo -e "${YELLOW}  Verifier que le stack est demarre :${NC}"
    echo "    cd mediapulse && docker compose up --build"
fi
