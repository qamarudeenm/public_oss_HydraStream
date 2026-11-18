#!/usr/bin/env bash
# minisky-test.sh — Start MiniSky and run the HydraStream test suite locally.
#
# Usage:
#   ./scripts/minisky-test.sh [--skip-start] [pytest-args...]
#
# Options:
#   --skip-start   Skip the minisky start step (assume it's already running).
#
# Examples:
#   ./scripts/minisky-test.sh                 # Start minisky + run all tests
#   ./scripts/minisky-test.sh --skip-start    # Tests only, minisky already up
#   ./scripts/minisky-test.sh -k test_unit    # Pass extra args to pytest

set -euo pipefail

MINISKY_BIN="${MINISKY_BIN:-minisky}"
MINISKY_API="http://localhost:2080"
MINISKY_DASHBOARD="http://localhost:8081"
MINISKY_PROJECT="${MINISKY_PROJECT:-local-dev}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROXY_DIR="$REPO_ROOT/streaming_infra/infra/flink-proxy-gateway"
BACKEND_DIR="$REPO_ROOT/control_plane/backend"

SKIP_START=false
EXTRA_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --skip-start) SKIP_START=true ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

# ── 1. Start minisky if needed ────────────────────────────────────────────────
start_minisky() {
  if ! curl -sf -H "Host: compute.googleapis.com" \
       "${MINISKY_API}/compute/v1/projects/${MINISKY_PROJECT}/zones/us-central1-a/instances" \
       > /dev/null 2>&1; then
    echo "MiniSky not responding — starting daemon..."
    if [ ! -x "$MINISKY_BIN" ]; then
      echo "ERROR: minisky binary not found at $MINISKY_BIN"
      echo "Install from: https://minisky.bmics.com.ng"
      exit 1
    fi
    "$MINISKY_BIN" start --port 2080 &
    MINISKY_PID=$!
    echo "Started minisky (PID $MINISKY_PID)"

    # Wait up to 30 seconds for the API to become ready
    for i in $(seq 1 30); do
      if curl -sf -H "Host: compute.googleapis.com" \
           "${MINISKY_API}/compute/v1/projects/${MINISKY_PROJECT}/zones/us-central1-a/instances" \
           > /dev/null 2>&1; then
        echo "MiniSky API ready (${MINISKY_API})"
        break
      fi
      if [ "$i" -eq 30 ]; then
        echo "ERROR: MiniSky did not become ready within 30 seconds"
        exit 1
      fi
      sleep 1
    done
  else
    echo "MiniSky already running at ${MINISKY_API}"
  fi
}

# ── 2. Verify key GCP services ────────────────────────────────────────────────
verify_services() {
  echo ""
  echo "Verifying MiniSky GCP services..."

  check_service() {
    local label="$1"
    local host="$2"
    local path="$3"
    if curl -sf -H "Host: ${host}" "${MINISKY_API}${path}" > /dev/null 2>&1; then
      echo "  ✓ ${label}"
    else
      echo "  ✗ ${label} — not responding"
    fi
  }

  check_service "Compute Engine"  "compute.googleapis.com"  "/compute/v1/projects/${MINISKY_PROJECT}/zones/us-central1-a/instances"
  check_service "Cloud Run"       "run.googleapis.com"       "/apis/serving.knative.dev/v1/namespaces/${MINISKY_PROJECT}/services"
  check_service "Cloud Build"     "cloudbuild.googleapis.com" "/v1/projects/${MINISKY_PROJECT}/builds"
  check_service "Cloud Storage"   "storage.googleapis.com"   "/storage/v1/b?project=${MINISKY_PROJECT}"
  check_service "Pub/Sub"         "pubsub.googleapis.com"    "/v1/projects/${MINISKY_PROJECT}/topics"
  check_service "GKE"             "container.googleapis.com" "/v1/projects/${MINISKY_PROJECT}/zones/us-central1-a/clusters"
  echo ""
}

# ── 3. Export environment variables for tests ────────────────────────────────
export_env() {
  export MINISKY_ENABLED=true
  export MINISKY_API_URL="${MINISKY_API}"
  export MINISKY_PROJECT_ID="${MINISKY_PROJECT}"
  export MINISKY_ENDPOINT="${MINISKY_API}"

  # GCP SDK overrides — point the SDK at MiniSky instead of real GCP
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_COMPUTE="${MINISKY_API}/"
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE="${MINISKY_API}/"
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_PUBSUB="${MINISKY_API}/"
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_CONTAINER="${MINISKY_API}/"
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_CLOUDBUILD="${MINISKY_API}/"
  export CLOUDSDK_API_ENDPOINT_OVERRIDES_RUN="${MINISKY_API}/"

  # GCLOUD project
  export GCLOUD_PROJECT="${MINISKY_PROJECT}"
  export GOOGLE_CLOUD_PROJECT="${MINISKY_PROJECT}"

  echo "Environment configured for MiniSky (project: ${MINISKY_PROJECT})"
}

# ── 4. Run proxy tests ─────────────────────────────────────────────────────────
run_tests() {
  echo "Running flink-proxy-gateway tests..."
  cd "$PROXY_DIR"
  uv run pytest tests/ -v "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"

  echo ""
  echo "Running control-plane backend tests..."
  cd "$BACKEND_DIR"
  .venv/bin/pytest tests/ -v "${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
}

# ── Main ──────────────────────────────────────────────────────────────────────
echo "=== MiniSky Local Testing Setup ==="
echo "  API Gateway : ${MINISKY_API}"
echo "  Dashboard   : ${MINISKY_DASHBOARD}"
echo "  Project     : ${MINISKY_PROJECT}"
echo ""

if [ "$SKIP_START" = false ]; then
  start_minisky
fi

verify_services
export_env
run_tests
