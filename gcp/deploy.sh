#!/usr/bin/env bash
# deploy.sh — Deploy all HydraStream services to GCP production.
#
# Prerequisites (provisioned by WI-1/2/3):
#   - GKE cluster running (terraform applied, kubeconfig configured)
#   - Artifact Registry repository exists
#   - Cloud SQL + Memorystore provisioned
#   - Secret Manager secrets created for DB URL, OIDC, session key
#   - gcloud authenticated with sufficient IAM roles
#
# Usage:
#   export PROJECT_ID=hydrastream-prod
#   export DOMAIN=hydrastream.example.com   # your DNS domain
#   export GIT_SHA=$(git rev-parse --short HEAD)
#   ./gcp/deploy.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────
PROJECT_ID="${PROJECT_ID:-hydrastream-prod}"
REGION="${REGION:-us-central1}"
ZONE="${ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-hydrastream-cluster}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo "latest")}"
NAMESPACE="hydrastream"
DOMAIN="${DOMAIN:-hydrastream.example.com}"
API_DOMAIN="api.${DOMAIN}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== HydraStream Production Deploy ==="
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo "  Cluster : ${CLUSTER_NAME}"
echo "  Registry: ${REGISTRY}"
echo "  Git SHA : ${GIT_SHA}"
echo "  Domain  : ${DOMAIN}"
echo ""

# ── Step 1: Authenticate Docker to Artifact Registry ─────────────
echo "[1/8] Configuring Docker auth for Artifact Registry..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# ── Step 2: Build and push all container images ───────────────────
echo "[2/8] Building and pushing container images via Cloud Build..."
gcloud builds submit "${REPO_ROOT}" \
  --project="${PROJECT_ID}" \
  --config="${SCRIPT_DIR}/cloudbuild.yaml" \
  --substitutions="_REGION=${REGION},SHORT_SHA=${GIT_SHA}"

echo "  Images pushed to ${REGISTRY}/"

# ── Step 3: Configure kubectl to target the GKE cluster ──────────
echo "[3/8] Fetching GKE credentials..."
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}"

kubectl config set-context --current --namespace="${NAMESPACE}"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# ── Step 4: Install External Secrets Operator (idempotent) ───────
echo "[4/9] Installing External Secrets Operator..."
helm repo add external-secrets https://charts.external-secrets.io 2>/dev/null || true
helm repo update
helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets-system \
  --create-namespace \
  --wait --timeout=3m

# ── Step 5: Install cert-manager (idempotent) ────────────────────
echo "[5/9] Installing cert-manager..."
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
echo "  Waiting for cert-manager webhooks to be ready..."
kubectl rollout status deployment/cert-manager -n cert-manager --timeout=120s
kubectl rollout status deployment/cert-manager-webhook -n cert-manager --timeout=120s

# ── Step 6: Deploy Flink Kubernetes Operator ─────────────────────
echo "[6/9] Deploying Flink Kubernetes Operator..."
helm repo add flink-operator-repo \
  https://downloads.apache.org/flink/flink-kubernetes-operator-1.9.0/ 2>/dev/null || true
helm repo update
helm upgrade --install flink-kubernetes-operator \
  flink-operator-repo/flink-kubernetes-operator \
  --namespace flink-operator \
  --create-namespace \
  --set "watchNamespaces={${NAMESPACE}}" \
  --wait

# ── Step 7: Deploy core infrastructure via Helm ──────────────────
echo "[7/9] Deploying hydrastream-infra (Kafka)..."
helm upgrade --install hydrastream-infra \
  "${REPO_ROOT}/streaming_infra/charts/hydrastream-infra" \
  --namespace="${NAMESPACE}" \
  --create-namespace \
  --values="${SCRIPT_DIR}/values-prod.yaml" \
  --wait --timeout=5m

# ── Step 8: Deploy tenant services (Flink, Proxy) via Helm ───────
echo "[8/9] Deploying hydrastream-tenant (Flink + Proxy)..."
helm upgrade --install hydrastream-tenant \
  "${REPO_ROOT}/streaming_infra/charts/hydrastream-tenant" \
  --namespace="${NAMESPACE}" \
  --values="${SCRIPT_DIR}/values-prod.yaml" \
  --set "proxy.image.tag=proxy-${GIT_SHA}" \
  --set "flink.image=${REGISTRY}/engine:flink1.19.1" \
  --set "podAnnotations.deploy-timestamp=$(date -u +%Y%m%d%H%M%S)" \
  --wait --timeout=10m

# ── Step 9: Apply control-plane + Flink + Kafka + Ingress k8s manifests
echo "[9/9] Applying Kubernetes manifests (control-plane, Flink, Kafka, Ingress)..."

# Substitute image tags in control-plane manifest
sed "s|:latest|:${GIT_SHA}|g" "${SCRIPT_DIR}/k8s/control-plane.yaml" \
  | kubectl apply -f -

kubectl apply -f "${SCRIPT_DIR}/k8s/kafka.yaml"
kubectl apply -f "${SCRIPT_DIR}/k8s/pdb.yaml"
kubectl apply -f "${SCRIPT_DIR}/k8s/flink.yaml"

# Wait for Kafka to be ready, then create production topics
echo "  Waiting for Kafka..."
kubectl rollout status statefulset/kafka -n "${NAMESPACE}" --timeout=5m
kubectl apply -f "${SCRIPT_DIR}/k8s/kafka-topics.yaml"

# Apply ingress after substituting domain
sed -e "s|hydrastream.example.com|${DOMAIN}|g" \
    -e "s|api.hydrastream.example.com|${API_DOMAIN}|g" \
    "${SCRIPT_DIR}/k8s/ingress.yaml" \
  | kubectl apply -f -

# ── Verification ──────────────────────────────────────────────────
echo ""
echo "=== Waiting for rollouts to complete ==="
kubectl rollout status deployment/control-plane-backend  -n "${NAMESPACE}" --timeout=5m
kubectl rollout status deployment/control-plane-frontend -n "${NAMESPACE}" --timeout=5m
kubectl rollout status deployment/flink-jobmanager       -n "${NAMESPACE}" --timeout=5m
kubectl rollout status deployment/flink-taskmanager      -n "${NAMESPACE}" --timeout=5m

echo ""
echo "=== Pod status ==="
kubectl get pods -n "${NAMESPACE}"

echo ""
echo "=== Ingress ==="
kubectl get ingress -n "${NAMESPACE}"

echo ""
echo "=== Deploy complete ==="
echo "  Frontend : https://${DOMAIN}"
echo "  API      : https://${API_DOMAIN}"
echo ""
echo "Next: verify DNS points to the Ingress LoadBalancer IP, then"
echo "      test OIDC login at https://${DOMAIN}/api/auth/login"
