#!/usr/bin/env bash
# bootstrap-db.sh — Run once after `terraform apply` to inject database
# credentials from Secret Manager into GKE as Kubernetes Secrets, then
# apply the sink schema and run the control-plane migration.
#
# Usage:
#   ./gcp/bootstrap-db.sh <project-id> <gke-cluster> <region>
#
# Example:
#   ./gcp/bootstrap-db.sh hydrastream-prod hydrastream-cluster us-central1

set -euo pipefail

PROJECT=${1:?Usage: $0 <project-id> <gke-cluster> <region>}
CLUSTER=${2:?Usage: $0 <project-id> <gke-cluster> <region>}
REGION=${3:?Usage: $0 <project-id> <gke-cluster> <region>}

echo "→ Connecting to GKE cluster..."
gcloud container clusters get-credentials "$CLUSTER" \
  --region "$REGION" --project "$PROJECT"

echo "→ Ensuring namespace hydrastream exists..."
kubectl create namespace hydrastream --dry-run=client -o yaml | kubectl apply -f -

echo "→ Fetching credentials from Secret Manager..."
CP_DB_URL=$(gcloud secrets versions access latest \
  --secret=hydrastream-cp-database-url --project="$PROJECT")
REDIS_URL=$(gcloud secrets versions access latest \
  --secret=hydrastream-redis-url --project="$PROJECT")
SINK_JDBC=$(gcloud secrets versions access latest \
  --secret=hydrastream-sink-jdbc-url --project="$PROJECT")

# Parse sink JDBC URL for psql env vars
PGHOST=$(echo "$SINK_JDBC" | grep -oP '(?<=jdbc:postgresql://)[^:/]+')
PGPASSWORD=$(echo "$SINK_JDBC" | grep -oP '(?<=password=)[^&]+')
PGUSER=$(echo "$SINK_JDBC" | grep -oP '(?<=user=)[^&]+')
PGDATABASE=$(echo "$SINK_JDBC" | grep -oP '(?<=5432/)[^?]+')

echo "→ Creating hydrastream-credentials Secret (control-plane)..."
kubectl create secret generic hydrastream-credentials \
  --namespace hydrastream \
  --from-literal=DATABASE_URL="$CP_DB_URL" \
  --from-literal=REDIS_URL="$REDIS_URL" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "→ Creating hydrastream-sink-credentials Secret (Flink sink)..."
kubectl create secret generic hydrastream-sink-credentials \
  --namespace hydrastream \
  --from-literal=PGHOST="$PGHOST" \
  --from-literal=PGUSER="$PGUSER" \
  --from-literal=PGDATABASE="$PGDATABASE" \
  --from-literal=PGPASSWORD="$PGPASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "→ Applying sink schema job..."
kubectl apply -f gcp/k8s/sink-schema.yaml

echo "→ Applying control-plane manifests (migration + deployment)..."
kubectl apply -f gcp/k8s/control-plane.yaml

echo ""
echo "✓ Bootstrap complete."
echo "  Monitor migration: kubectl logs -n hydrastream job/control-plane-migrate -f"
echo "  Monitor sink schema: kubectl logs -n hydrastream job/sink-schema-setup -f"
