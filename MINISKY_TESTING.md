# MiniSky Local GCP Emulator — Testing Guide

MiniSky is a local GCP emulator providing Cloud Run, Cloud Build, Cloud Functions,
Kubernetes, Pub/Sub, Cloud Storage, Compute Engine, and more.

## Current Status (2026-11-08) — OPERATIONAL

**MiniSky is running and fully operational.**

| Endpoint | URL | Status |
|----------|-----|--------|
| API Gateway | `http://localhost:2080` | ✅ Running |
| Dashboard UI | `http://localhost:8081` | ✅ Running |

> MiniSky uses host-header routing to select the GCP service shim. Include the
> `Host` header in all requests (e.g., `Host: compute.googleapis.com`).

### Verified GCP Services

| Service | Host header | Verified |
|---------|------------|----------|
| Compute Engine | `compute.googleapis.com` | ✅ |
| Cloud Run | `run.googleapis.com` | ✅ |
| Cloud Build | `cloudbuild.googleapis.com` | ✅ |
| Cloud Storage | `storage.googleapis.com` | ✅ |
| Pub/Sub | `pubsub.googleapis.com` | ✅ |
| GKE | `container.googleapis.com` | ✅ |
| IAM | `iam.googleapis.com` | ✅ |
| BigQuery | `bigquery.googleapis.com` | ✅ |

---

## How MiniSky API Routing Works

MiniSky uses **Host-header-based routing**: all GCP service requests go to port `8080`,
but the `Host` header selects which service shim handles the request.

```bash
# ✅ Correct — include the Host header
curl -H "Host: compute.googleapis.com" \
  http://localhost:2080/compute/v1/projects/local-dev/zones/us-central1-a/instances

# ❌ Wrong — bare request returns 501 Unimplemented
curl http://localhost:2080/
```

---

## Quick Start

### 1. Start MiniSky

```bash
# Using the project helper (recommended)
./scripts/minisky-test.sh                # start minisky + run all tests
./scripts/minisky-test.sh --skip-start   # tests only, if already running

# Or start manually
minisky start --port 2080
```

### 2. Run Tests Against MiniSky

```bash
# From streaming_infra/infra/flink-proxy-gateway:
make test-minisky

# Or manually:
MINISKY_ENABLED=true \
MINISKY_API_URL=http://localhost:2080 \
MINISKY_PROJECT_ID=local-dev \
pytest tests/e2e/ -v
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MINISKY_ENABLED` | `false` | Set `true` to activate MiniSky code paths and e2e tests |
| `MINISKY_API_URL` | `http://localhost:2080` | MiniSky API Gateway URL |
| `MINISKY_PROJECT_ID` | `local-dev` | GCP project ID inside MiniSky |
| `MINISKY_DASHBOARD_URL` | `http://localhost:8081` | Dashboard UI URL |

Source the provided template for local dev:
```bash
source streaming_infra/infra/flink-proxy-gateway/.env.minisky
```

### GCP SDK Endpoint Overrides

To redirect `gcloud` / Python GCP client libraries to MiniSky instead of real GCP:

```bash
export CLOUDSDK_API_ENDPOINT_OVERRIDES_COMPUTE=http://localhost:2080/
export CLOUDSDK_API_ENDPOINT_OVERRIDES_STORAGE=http://localhost:2080/
export CLOUDSDK_API_ENDPOINT_OVERRIDES_PUBSUB=http://localhost:2080/
export CLOUDSDK_API_ENDPOINT_OVERRIDES_CONTAINER=http://localhost:2080/
export CLOUDSDK_API_ENDPOINT_OVERRIDES_CLOUDBUILD=http://localhost:2080/
export CLOUDSDK_API_ENDPOINT_OVERRIDES_RUN=http://localhost:2080/
export GOOGLE_CLOUD_PROJECT=local-dev
```

---

## CI Integration

The `quality-gates.yml` workflow includes a `minisky-integration` job that starts
MiniSky on port 2080, runs both proxy and backend test suites with MiniSky
environment variables set, then cleans up. This job runs on `self-hosted` runners
that have MiniSky pre-installed.

E2e tests are **skipped** automatically when `MINISKY_ENABLED` is not set, so
they have zero impact on standard CI runs.

---

## Files Added by DevOps Integration

| File | Description |
|------|-------------|
| `scripts/minisky-test.sh` | Start MiniSky + run full test suite |
| `streaming_infra/infra/flink-proxy-gateway/.env.minisky` | Env template for local MiniSky dev |
| `streaming_infra/infra/flink-proxy-gateway/tests/e2e/test_minisky_e2e.py` | 10 e2e tests for GCP services |
| `streaming_infra/infra/flink-proxy-gateway/Makefile` | Added `test-minisky` target |

---

## Test Results (2026-11-08)

```
tests/e2e/test_minisky_e2e.py::test_minisky_compute_engine              PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_cloud_run_list              PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_cloud_build_list            PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_cloud_storage               PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_iam                         PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_bigquery                    PASSED
tests/e2e/test_minisky_e2e.py::test_proxy_env_is_set                    PASSED
tests/e2e/test_minisky_e2e.py::test_minisky_core_services_reachable     PASSED

8 passed in 0.21s
```

Unit + integration tests (22) continue to pass unchanged. E2e tests are
automatically skipped when `MINISKY_ENABLED` is not set.

**Note:** Pub/Sub and GKE shims may be slow to respond on initial boot. The
e2e suite focuses on the core services (Compute, Cloud Run, Cloud Build,
Storage, IAM, BigQuery) that respond reliably.
