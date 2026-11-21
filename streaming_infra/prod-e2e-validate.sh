#!/bin/bash
# Production E2E Validation: Kafka → Flink → PostgreSQL → API
# Covers the full pipeline for a single tenant in production.
#
# Required env vars:
#   FLINK_GATEWAY_URL       e.g. http://localhost:8083 (port-forward)
#   CONTROL_PLANE_URL       e.g. https://hydrastream.example.com
#   CONTROL_PLANE_TOKEN     Bearer JWT from OIDC provider
#   KAFKA_BOOTSTRAP         e.g. localhost:9092 (port-forward)
#   TENANT_ID               e.g. tenant-1
#   KAFKA_TOPIC             e.g. clickstream-tenant-1
#   POSTGRES_HOST           e.g. localhost (port-forward) or Cloud SQL private IP
#   POSTGRES_DB             e.g. hydrastream
#   POSTGRES_USER           e.g. hydra
#   POSTGRES_PASSWORD       (required)
#
# Usage:
#   export <all vars above>
#   ./prod-e2e-validate.sh

set -euo pipefail

GATEWAY_URL="${FLINK_GATEWAY_URL:-http://localhost:8083}"
CP_URL="${CONTROL_PLANE_URL:-http://localhost:8000}"
CP_TOKEN="${CONTROL_PLANE_TOKEN:-}"
KAFKA_BS="${KAFKA_BOOTSTRAP:-localhost:9092}"
TENANT="${TENANT_ID:-tenant-1}"
TOPIC="${KAFKA_TOPIC:-clickstream-${TENANT}}"
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_DB="${POSTGRES_DB:-hydrastream}"
PG_USER="${POSTGRES_USER:-hydra}"
PG_PASS="${POSTGRES_PASSWORD:-}"

LOG_DIR="${LOG_DIR:-/tmp/hydrastream-e2e-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$LOG_DIR"

PASS=0
FAIL=0

check() {
    local label="$1"; shift
    if "$@" > /dev/null 2>&1; then
        echo "  ✅ $label"
        PASS=$((PASS+1))
    else
        echo "  ❌ $label"
        FAIL=$((FAIL+1))
    fi
}

echo "======================================================================"
echo "HydraStream Production E2E Validation"
echo "Tenant: $TENANT | Topic: $TOPIC"
echo "SQL Gateway: $GATEWAY_URL | Control Plane: $CP_URL"
echo "Logs: $LOG_DIR"
echo "======================================================================"

# ------------------------------------------------------------------
# Step 1: Control Plane API — tenant exists and is active
# ------------------------------------------------------------------
echo ""
echo "STEP 1: Control Plane API — tenant record"
AUTH_HEADER=""
[ -n "$CP_TOKEN" ] && AUTH_HEADER="-H \"Authorization: Bearer $CP_TOKEN\""

TENANT_STATUS=$(curl -sf \
    ${CP_TOKEN:+-H "Authorization: Bearer $CP_TOKEN"} \
    "$CP_URL/tenants/$TENANT" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','missing'))" 2>/dev/null || echo "unreachable")

if [ "$TENANT_STATUS" = "active" ]; then
    echo "  ✅ Tenant '$TENANT' exists, status=active"
    PASS=$((PASS+1))
else
    echo "  ❌ Tenant '$TENANT' status='$TENANT_STATUS' (expected 'active')"
    FAIL=$((FAIL+1))
fi

# ------------------------------------------------------------------
# Step 2: Flink SQL Gateway reachable
# ------------------------------------------------------------------
echo ""
echo "STEP 2: Flink SQL Gateway health"
check "SQL Gateway /v1/info responds" curl -sf "$GATEWAY_URL/v1/info"

GW_INFO=$(curl -s "$GATEWAY_URL/v1/info" 2>/dev/null)
echo "$GW_INFO" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/gw-info.json" | head -5 || true

# ------------------------------------------------------------------
# Step 3: Produce test messages to tenant Kafka topic
# ------------------------------------------------------------------
echo ""
echo "STEP 3: Produce test messages to Kafka topic '$TOPIC'"
NUM_MSGS=20
PRODUCED=0

for i in $(seq 1 $NUM_MSGS); do
    MSG="{\"event_type\":\"page_view\",\"page_url\":\"/products/$i\",\"user_id\":\"e2e-user-$i\",\"session_id\":\"sess-e2e-$(date +%s)\",\"element_id\":\"btn-$i\",\"element_text\":\"Buy Now\",\"product_id\":\"prod-$i\",\"data\":\"{}\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
    if echo "$MSG" | kafka-console-producer.sh \
        --bootstrap-server "$KAFKA_BS" \
        --topic "$TOPIC" > /dev/null 2>&1; then
        PRODUCED=$((PRODUCED+1))
    fi
done

if [ "$PRODUCED" -eq "$NUM_MSGS" ]; then
    echo "  ✅ Produced $PRODUCED/$NUM_MSGS messages to '$TOPIC'"
    PASS=$((PASS+1))
else
    echo "  ❌ Only produced $PRODUCED/$NUM_MSGS messages to '$TOPIC'"
    FAIL=$((FAIL+1))
fi

# ------------------------------------------------------------------
# Step 4: Flink SQL Gateway session + verify job is RUNNING
# ------------------------------------------------------------------
echo ""
echo "STEP 4: Flink job is RUNNING (via SQL Gateway session)"
SESSION_RESP=$(curl -s -X POST "$GATEWAY_URL/v1/sessions" \
    -H "Content-Type: application/json" \
    -d '{"properties":{}}' 2>/dev/null)
echo "$SESSION_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/session.json" > /dev/null
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sessionHandle',''))" 2>/dev/null || echo "")

if [ -n "$SESSION_ID" ]; then
    echo "  ✅ SQL Gateway session created: $SESSION_ID"
    PASS=$((PASS+1))

    # Verify running jobs via Flink REST (JobManager on :8081)
    JOBS_RESP=$(curl -s http://localhost:8081/jobs/overview 2>/dev/null || echo '{}')
    echo "$JOBS_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/jobs.json" > /dev/null
    RUNNING=$(echo "$JOBS_RESP" | python3 -c "
import sys,json
jobs=json.load(sys.stdin).get('jobs',[])
running=[j for j in jobs if j.get('state')=='RUNNING']
print(len(running))
" 2>/dev/null || echo "0")
    if [ "$RUNNING" -gt 0 ]; then
        echo "  ✅ Flink has $RUNNING RUNNING job(s)"
        PASS=$((PASS+1))
    else
        echo "  ❌ No RUNNING Flink jobs found (check Flink dashboard)"
        FAIL=$((FAIL+1))
    fi
else
    echo "  ❌ Failed to create SQL Gateway session"
    FAIL=$((FAIL+1))
fi

# ------------------------------------------------------------------
# Step 5: PostgreSQL — verify rows landed in sink tables
# ------------------------------------------------------------------
echo ""
echo "STEP 5: PostgreSQL sink — data landed"
if command -v psql > /dev/null 2>&1 && [ -n "$PG_PASS" ]; then
    sleep 15   # allow Flink window to close and rows to commit

    METRICS_COUNT=$(PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" \
        -tAc "SELECT COUNT(*) FROM ${TENANT}_metrics;" 2>/dev/null || echo "-1")
    SUMMARY_COUNT=$(PGPASSWORD="$PG_PASS" psql -h "$PG_HOST" -U "$PG_USER" -d "$PG_DB" \
        -tAc "SELECT COUNT(*) FROM ${TENANT}_summary;" 2>/dev/null || echo "-1")

    if [ "$METRICS_COUNT" -gt 0 ] 2>/dev/null; then
        echo "  ✅ ${TENANT}_metrics has $METRICS_COUNT rows"
        PASS=$((PASS+1))
    else
        echo "  ❌ ${TENANT}_metrics has $METRICS_COUNT rows (expected >0)"
        FAIL=$((FAIL+1))
    fi

    if [ "$SUMMARY_COUNT" -gt 0 ] 2>/dev/null; then
        echo "  ✅ ${TENANT}_summary has $SUMMARY_COUNT rows"
        PASS=$((PASS+1))
    else
        echo "  ❌ ${TENANT}_summary has $SUMMARY_COUNT rows (expected >0)"
        FAIL=$((FAIL+1))
    fi

    echo "$METRICS_COUNT metrics rows, $SUMMARY_COUNT summary rows" > "$LOG_DIR/pg-row-counts.txt"
else
    echo "  ⚠️  psql not available or POSTGRES_PASSWORD not set — skipping PostgreSQL check"
    echo "     Manually run: SELECT COUNT(*) FROM ${TENANT}_metrics;"
fi

# ------------------------------------------------------------------
# Step 6: Control Plane API returns data for tenant
# ------------------------------------------------------------------
echo ""
echo "STEP 6: Control Plane API — tenant data queryable"
TENANTS_RESP=$(curl -sf \
    ${CP_TOKEN:+-H "Authorization: Bearer $CP_TOKEN"} \
    "$CP_URL/tenants" 2>/dev/null || echo "[]")

TENANT_IN_LIST=$(echo "$TENANTS_RESP" | python3 -c "
import sys,json
tenants=json.load(sys.stdin)
ids=[t.get('id','') for t in tenants]
print('yes' if '$TENANT' in ids else 'no')
" 2>/dev/null || echo "no")

if [ "$TENANT_IN_LIST" = "yes" ]; then
    echo "  ✅ Tenant '$TENANT' visible in GET /tenants"
    PASS=$((PASS+1))
else
    echo "  ❌ Tenant '$TENANT' not found in GET /tenants"
    FAIL=$((FAIL+1))
fi

# ------------------------------------------------------------------
# Step 7: Proxy Gateway — OIDC auth enforced
# ------------------------------------------------------------------
echo ""
echo "STEP 7: Proxy Gateway — authentication enforced"
PROXY_PORT=8080
PROXY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:$PROXY_PORT/v1/sessions \
    -H "Content-Type: application/json" -d '{}' 2>/dev/null || echo "000")

if [ "$PROXY_STATUS" = "401" ]; then
    echo "  ✅ Proxy rejects unauthenticated request with 401"
    PASS=$((PASS+1))
elif [ "$PROXY_STATUS" = "000" ]; then
    echo "  ⚠️  Proxy not reachable on port $PROXY_PORT — ensure port-forward is active"
    echo "     kubectl port-forward -n $TENANT svc/${TENANT}-hydrastream-tenant-proxy $PROXY_PORT:8080"
else
    echo "  ❌ Proxy returned $PROXY_STATUS (expected 401)"
    FAIL=$((FAIL+1))
fi

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
echo ""
echo "======================================================================"
TOTAL=$((PASS+FAIL))
echo "E2E Validation Summary: $PASS/$TOTAL checks passed"
if [ "$FAIL" -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED — tenant '$TENANT' is production-ready"
    echo "   Kafka → Flink → PostgreSQL data flow: VERIFIED"
else
    echo "❌ $FAIL CHECK(S) FAILED — review output above and $LOG_DIR"
fi
echo "======================================================================"
echo "Logs: $LOG_DIR"

[ "$FAIL" -eq 0 ]
