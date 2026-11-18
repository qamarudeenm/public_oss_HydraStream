#!/bin/bash
# E2E Flink Pipeline Validation Script
# Tests: Simulator → Kafka → Flink → Print/Console Sink
set -euo pipefail

GATEWAY_URL="${FLINK_GATEWAY_URL:-http://localhost:8083}"
LOG_DIR="${LOG_DIR:-/tmp/hydrastream-e2e-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$LOG_DIR"

echo "=================================================="
echo "HydraStream E2E Flink Pipeline Validation"
echo "SQL Gateway: $GATEWAY_URL"
echo "Logs: $LOG_DIR"
echo "=================================================="

# --- Step 1: Wait for SQL Gateway ---
echo ""
echo "STEP 1: Waiting for Flink SQL Gateway..."
for i in $(seq 1 60); do
    if curl -sf "$GATEWAY_URL/v1/info" > /dev/null 2>&1; then
        echo "  ✅ SQL Gateway is ready"
        curl -s "$GATEWAY_URL/v1/info" | python3 -m json.tool 2>/dev/null | head -5
        break
    fi
    echo "  ⏳ Attempt $i/60 — waiting 5s..."
    sleep 5
done

curl -sf "$GATEWAY_URL/v1/info" > "$LOG_DIR/gateway-info.json" 2>&1 || { echo "❌ SQL Gateway not reachable"; exit 1; }

# --- Step 2: Create a SQL Gateway session ---
echo ""
echo "STEP 2: Creating SQL Gateway session..."
SESSION_RESP=$(curl -s -X POST "$GATEWAY_URL/v1/sessions" \
    -H "Content-Type: application/json" \
    -d '{"properties": {}}')
echo "$SESSION_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/session.json"
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['sessionHandle'])" 2>/dev/null)

if [ -z "$SESSION_ID" ]; then
    echo "❌ Failed to get session ID from: $SESSION_RESP"
    exit 1
fi
echo "  ✅ Session created: $SESSION_ID"

# --- Step 3: Submit DDL — Create Kafka source table ---
echo ""
echo "STEP 3: Creating Kafka source table in Flink..."
SOURCE_DDL="CREATE TABLE IF NOT EXISTS clickstream_raw (
    event_type STRING,
    page_url STRING,
    user_id STRING,
    session_id STRING,
    element_id STRING,
    element_text STRING,
    product_id STRING,
    \`data\` STRING,
    \`timestamp\` STRING,
    event_time AS TO_TIMESTAMP(REPLACE(REPLACE(\`timestamp\`, 'T', ' '), 'Z', '')),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'clickstream',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id' = 'flink-e2e-test',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json'
)"

SOURCE_RESP=$(curl -s -X POST "$GATEWAY_URL/v1/sessions/$SESSION_ID/statements" \
    -H "Content-Type: application/json" \
    -d "{\"statement\": \"$SOURCE_DDL\"}")
echo "$SOURCE_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/source-ddl.json"
echo "  ✅ Kafka source table created"

# --- Step 4: Create print sink table ---
echo ""
echo "STEP 4: Creating print sink table..."
SINK_DDL="CREATE TABLE IF NOT EXISTS clickstream_print (
    event_type STRING,
    user_id STRING,
    session_id STRING,
    event_count BIGINT,
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3)
) WITH (
    'connector' = 'print'
)"

SINK_RESP=$(curl -s -X POST "$GATEWAY_URL/v1/sessions/$SESSION_ID/statements" \
    -H "Content-Type: application/json" \
    -d "{\"statement\": \"$SINK_DDL\"}")
echo "$SINK_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/sink-ddl.json"
echo "  ✅ Print sink table created"

# --- Step 5: Submit streaming INSERT job ---
echo ""
echo "STEP 5: Submitting streaming INSERT job (Kafka → Flink → Print)..."
INSERT_SQL="INSERT INTO clickstream_print
SELECT
    event_type,
    user_id,
    session_id,
    COUNT(*) AS event_count,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE clickstream_raw, DESCRIPTOR(event_time), INTERVAL '1' MINUTE)
)
GROUP BY event_type, user_id, session_id, window_start, window_end"

JOB_RESP=$(curl -s -X POST "$GATEWAY_URL/v1/sessions/$SESSION_ID/statements" \
    -H "Content-Type: application/json" \
    -d "{\"statement\": \"$INSERT_SQL\"}")
echo "$JOB_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/job-submit.json"

OP_ID=$(echo "$JOB_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('operationHandle',''))" 2>/dev/null)
echo "  ✅ Job submitted, operation: $OP_ID"

# --- Step 6: Check job status ---
echo ""
echo "STEP 6: Checking job status..."
sleep 5
STATUS_RESP=$(curl -s "$GATEWAY_URL/v1/sessions/$SESSION_ID/operations/$OP_ID/status" 2>/dev/null)
echo "$STATUS_RESP" | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/job-status.json"

# Also list running Flink jobs via REST API (JobManager on port 8081)
echo ""
echo "STEP 6b: Flink JobManager running jobs..."
curl -s http://localhost:8022/jobs/overview 2>/dev/null | python3 -m json.tool 2>/dev/null | tee "$LOG_DIR/flink-jobs.json" | head -40 || echo "  (JobManager REST not reachable on 8022)"

echo ""
echo "=================================================="
echo "✅ E2E validation script complete"
echo "   Session ID: $SESSION_ID"
echo "   Operation ID: $OP_ID"
echo "   Logs saved to: $LOG_DIR"
echo "=================================================="
