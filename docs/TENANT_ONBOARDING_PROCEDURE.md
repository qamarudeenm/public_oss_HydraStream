# HydraStream: First Tenant Onboarding Procedure

**Version:** 1.0.0
**Date:** 2026-11-21
**Author:** DevOps Engineer (BLUAA-328)
**Depends on:** Production Deployment Guide v1.0.2 (BLUAA-316), WI-4 Deploy All Services (BLUAA-326)

---

## Overview

This runbook covers onboarding the first production tenant into a live HydraStream deployment on GKE.
It is meant to be executed after all shared infrastructure and services are running (WI-4 / BLUAA-326 complete).

Expected time to complete: **60–90 minutes** (first run); 15–20 minutes for subsequent tenants.

---

## Prerequisites

Verify the following are true before starting:

```bash
export KUBECONFIG=~/.kube/config   # or project kubeconfig path
export PROJECT_ID="hydrastream-prod"
export REGION="us-central1"
export CONTROL_PLANE_URL="https://hydrastream.example.com"  # production ingress
export TENANT_ID="tenant-1"
export TENANT_NS="$TENANT_ID"

# Shared infra healthy
kubectl get pods -n default | grep -E "kafka|postgres|control-plane"

# Control plane API reachable
curl -sf "$CONTROL_PLANE_URL/health"
# Expected: {"status":"healthy","database":"healthy"}
```

If any check fails, resolve WI-4 blockers before proceeding.

---

## Step 1: Obtain an OIDC Access Token

The Control Plane API requires a valid OIDC JWT.  Replace the placeholders with your provider's values.

```bash
# Example using curl + client_credentials (service account / CI use case).
# For a human operator using a browser, log in at $CONTROL_PLANE_URL and
# extract the hs_session cookie — or use a provider CLI (e.g. gcloud, okta-cli).

export OIDC_ISSUER_URL="https://your-oidc-provider.example.com"
export OIDC_CLIENT_ID="hydrastream-control-plane"
export OIDC_CLIENT_SECRET="<secret>"   # rotate immediately after onboarding

TOKEN=$(curl -s -X POST "$OIDC_ISSUER_URL/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$OIDC_CLIENT_ID&client_secret=$OIDC_CLIENT_SECRET&audience=hydrastream-control-plane" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtained: ${TOKEN:0:30}..."
```

> **Note:** If `CONTROL_PLANE_AUTH_DISABLED=true` is set (dev only), skip this step and
> omit the `-H "Authorization: Bearer $TOKEN"` header from all API calls below.

---

## Step 2: Create the Tenant via Control Plane API

```bash
# Adjust kafka.bootstrap_servers and sink fields to your production values
CREATE_RESP=$(curl -sf -X POST "$CONTROL_PLANE_URL/tenants" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"$TENANT_ID\",
    \"name\": \"First Production Tenant\",
    \"description\": \"Onboarded via BLUAA-328 on $(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"kafka\": {
      \"bootstrap_servers\": \"hydrastream-infra-kafka.default:9092\",
      \"topic\": \"clickstream-$TENANT_ID\",
      \"group_id\": \"$TENANT_ID-consumer-group\"
    },
    \"sink\": {
      \"jdbc_url\": \"jdbc:postgresql://hydrastream-infra-postgres.default:5432/hydrastream\",
      \"user\": \"hydra\",
      \"password\": \"<postgres-password>\",
      \"summary_table\": \"${TENANT_ID}_summary\",
      \"metrics_table\": \"${TENANT_ID}_metrics\"
    },
    \"flink_version\": \"1.19.1\",
    \"dbt_version\": \"1.7.0\",
    \"status\": \"provisioning\"
  }")

echo "$CREATE_RESP" | python3 -m json.tool
TENANT_STATUS=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))")
echo "Tenant created with status: $TENANT_STATUS"
```

Verify it persisted:

```bash
curl -sf "$CONTROL_PLANE_URL/tenants/$TENANT_ID" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Step 3: Configure Tenant-Specific Kafka Topic

HydraStream uses per-tenant Kafka topics for isolation. Create the topic on the shared Kafka broker:

```bash
# Port-forward to Kafka (or run from inside a kafka pod)
kubectl port-forward -n default svc/hydrastream-infra-kafka 9092:9092 &
sleep 2

# Create tenant topic (retention: 7 days, 3 partitions for throughput)
kafka-topics.sh --bootstrap-server localhost:9092 \
  --create \
  --topic "clickstream-$TENANT_ID" \
  --partitions 3 \
  --replication-factor 1 \
  --config retention.ms=604800000 \
  --if-not-exists

# Verify topic exists
kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic "clickstream-$TENANT_ID"
```

Expected output: topic details showing 3 partitions.

---

## Step 4: Create Tenant User Account in OIDC Provider

Each tenant operator needs a user account. Steps vary by provider.

### Google Identity Platform / Firebase Auth

```bash
gcloud identity platform users create \
  --email "operator@tenant1.example.com" \
  --display-name "Tenant 1 Operator" \
  --project "$PROJECT_ID"
```

### Keycloak

```bash
# Via admin-cli (replace KEYCLOAK_URL and credentials)
kcadm.sh create users -r hydrastream \
  -s username="tenant1-operator" \
  -s email="operator@tenant1.example.com" \
  -s enabled=true

kcadm.sh set-password -r hydrastream \
  --username "tenant1-operator" \
  --new-password "<temp-password>" \
  --temporary
```

### Auth0 (via Management API)

```bash
curl -s -X POST "https://your-auth0-tenant.auth0.com/api/v2/users" \
  -H "Authorization: Bearer $MGMT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connection": "Username-Password-Authentication",
    "email": "operator@tenant1.example.com",
    "password": "<temp-password>",
    "verify_email": true
  }'
```

> Record the user ID; update the tenant record if needed.

---

## Step 5: Deploy Tenant Infrastructure (Helm)

```bash
# Get the proxy image SHA (must be a git-SHA tag, e.g. proxy-abc1234)
# This was published during WI-4 (BLUAA-326) image build.
PROXY_TAG="proxy-<SHORT_SHA>"   # replace with actual SHA from BLUAA-326

# Create namespace
kubectl create namespace "$TENANT_NS" --dry-run=client -o yaml | kubectl apply -f -

# Deploy using the production values override
cd /path/to/public_oss_HydraStream/streaming_infra

helm install "$TENANT_ID" ./charts/hydrastream-tenant \
  --namespace "$TENANT_NS" \
  --values values-tenant-prod-example.yaml \
  --set proxy.image.tag="$PROXY_TAG" \
  --set kafka.bootstrapServers="hydrastream-infra-kafka.default:9092" \
  --set kafka.topic="clickstream-$TENANT_ID" \
  --wait --timeout 10m

echo "Helm install complete"
```

Watch pod startup:

```bash
kubectl get pods -n "$TENANT_NS" -w
```

Expected pods (all `Running`):

| Pod | Description |
|-----|-------------|
| `tenant-1-hydrastream-tenant-flink-jm-*` | Flink JobManager |
| `tenant-1-hydrastream-tenant-flink-tm-*` (×2) | Flink TaskManagers |
| `tenant-1-hydrastream-tenant-sql-gateway-*` | Flink SQL Gateway |
| `tenant-1-hydrastream-tenant-proxy-*` | Flink Proxy Gateway |

---

## Step 6: Verify Tenant Isolation

Confirm the tenant namespace is isolated from others:

```bash
# Check no cross-namespace service leakage
kubectl get networkpolicies -n "$TENANT_NS"

# Verify RBAC scope: tenant SA only has access to its namespace
kubectl auth can-i list pods --namespace default \
  --as="system:serviceaccount:${TENANT_NS}:${TENANT_ID}-hydrastream-tenant"
# Expected: "no"

kubectl auth can-i list pods --namespace "$TENANT_NS" \
  --as="system:serviceaccount:${TENANT_NS}:${TENANT_ID}-hydrastream-tenant"
# Expected: "yes"

# SQL Gateway health
kubectl port-forward -n "$TENANT_NS" \
  svc/${TENANT_ID}-hydrastream-tenant-sql-gateway 8083:8083 &
sleep 2
curl -sf http://localhost:8083/v1/info | python3 -m json.tool

# Proxy health (unauthenticated → 401)
kubectl port-forward -n "$TENANT_NS" \
  svc/${TENANT_ID}-hydrastream-tenant-proxy 8080:8080 &
sleep 2
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
echo "Unauthenticated /health → $HTTP_STATUS (expect 200 or 401)"

# Proxy rejects unauthenticated SQL calls
HTTP_SQL=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  http://localhost:8080/v1/sessions \
  -H "Content-Type: application/json" -d '{}')
echo "Unauthenticated SQL → $HTTP_SQL (expect 401)"
```

---

## Step 7: Run E2E Data Flow Validation

Use the production E2E script (`prod-e2e-validate.sh`) which covers the full pipeline:
Simulator → Kafka → Flink → PostgreSQL sink → Control Plane API.

```bash
export FLINK_GATEWAY_URL="http://localhost:8083"  # or ingress URL
export CONTROL_PLANE_URL="https://hydrastream.example.com"
export CONTROL_PLANE_TOKEN="$TOKEN"
export KAFKA_BOOTSTRAP="hydrastream-infra-kafka.default:9092"
export TENANT_ID="tenant-1"
export KAFKA_TOPIC="clickstream-$TENANT_ID"
export POSTGRES_HOST="hydrastream-infra-postgres.default"
export POSTGRES_DB="hydrastream"
export POSTGRES_USER="hydra"
export POSTGRES_PASSWORD="<password>"

cd /path/to/public_oss_HydraStream/streaming_infra
./prod-e2e-validate.sh
```

All 7 validation steps must pass with green checkmarks.

---

## Step 8: Test Flink Job Recovery

Verify that Flink restarts gracefully when a TaskManager is killed:

```bash
# Record current running jobs
TM_POD=$(kubectl get pods -n "$TENANT_NS" \
  -l component=taskmanager -o name | head -1)
echo "Will kill: $TM_POD"

# Kill the TaskManager
kubectl delete "$TM_POD" -n "$TENANT_NS"

echo "Watching pod recovery..."
kubectl get pods -n "$TENANT_NS" -w &
sleep 60   # Flink restores from latest checkpoint within ~30s

# Confirm Flink job resumed (not in FAILED state)
JM_POD=$(kubectl get pods -n "$TENANT_NS" -l component=jobmanager -o name | head -1)
kubectl exec -n "$TENANT_NS" "$JM_POD" -- \
  curl -s http://localhost:8081/jobs/overview | python3 -m json.tool | grep -E '"state"'
# Expected: "RUNNING"
```

---

## Step 9: Mark Tenant Active in Control Plane

```bash
curl -sf -X PATCH "$CONTROL_PLANE_URL/tenants/$TENANT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}' | python3 -m json.tool
```

---

## Step 10: Verify Monitoring Coverage

```bash
# In Cloud Monitoring console (or gcloud):
gcloud monitoring dashboards list --project="$PROJECT_ID" 2>/dev/null || \
  echo "Check dashboards manually in Cloud Monitoring UI"

# Confirm logs flowing for tenant namespace
gcloud logging read \
  "resource.type=k8s_container AND resource.labels.namespace_name=$TENANT_NS" \
  --limit=5 --project="$PROJECT_ID" 2>/dev/null | head -30 || \
  echo "Verify Cloud Logging manually — expected log entries from $TENANT_NS namespace"
```

---

## Acceptance Criteria Checklist

| # | Criterion | Evidence |
|---|-----------|---------|
| 1 | First tenant created and configured | `GET /tenants/tenant-1` returns `status: active` |
| 2 | Kafka → Flink → PostgreSQL data flow | prod-e2e-validate.sh exits 0, row count in DB |
| 3 | Frontend shows tenant data after OIDC login | Manual browser test — login, see events |
| 4 | Smoke test suite passes against production | 75/75 tests pass |
| 5 | Flink job recovery verified | Job `RUNNING` after TaskManager kill |
| 6 | Tenant onboarding procedure documented | This document |

---

## Production-Specific Configuration Notes

These differ from local/kind development:

| Config | Local Dev | Production GCP |
|--------|-----------|----------------|
| Kafka bootstrap | `kafka:29092` (docker-compose) | `hydrastream-infra-kafka.default:9092` |
| PostgreSQL sink | ClickHouse (local) | Cloud SQL PostgreSQL via private IP |
| Auth | `CONTROL_PLANE_AUTH_DISABLED=true` | OIDC JWT (RS256) mandatory |
| Image registry | `blue2berry/hydrastream` (Docker Hub) | `${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/...` |
| Proxy tag | `proxy-latest` acceptable | Must be `proxy-<git-sha>` — immutable |
| TLS | None | cert-manager or manual cert via K8s secret |
| Flink checkpointing | Disabled | GCS bucket `gs://hydrastream-prod-flink-checkpoints/` |
| Secrets | `.env` files | GCP Secret Manager via K8s external-secrets |

---

## Rollback

If onboarding fails mid-way:

```bash
# Remove tenant Helm release
helm uninstall "$TENANT_ID" -n "$TENANT_NS"
kubectl delete namespace "$TENANT_NS"

# Remove tenant record from Control Plane DB
curl -sf -X DELETE "$CONTROL_PLANE_URL/tenants/$TENANT_ID" \
  -H "Authorization: Bearer $TOKEN"

# Delete Kafka topic
kafka-topics.sh --bootstrap-server localhost:9092 \
  --delete --topic "clickstream-$TENANT_ID"
```

---

## Lessons Learned (Updated after First Run)

> *Fill this section in after executing the procedure against production.*
> Record any deviations, timing issues, or configuration surprises encountered.
> Reference: BLUAA-316 Production Deployment Guide updates.

- [ ] TODO: Record actual timing for each step
- [ ] TODO: Note any GKE-specific nuances observed
- [ ] TODO: Document actual OIDC provider used and any setup gotchas
