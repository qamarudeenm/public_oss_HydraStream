# HydraStream — GCP / MiniSky Deployment

This directory contains everything needed to deploy HydraStream on Google Cloud Platform
(or the MiniSky local GCP emulator).

## GCP Services Required

| Service | Purpose | MiniSky support |
|---------|---------|-----------------|
| **Cloud Build** | CI — builds Docker images on `git push` | ✅ Available |
| **Artifact Registry** | Stores Docker images (replaces Docker Hub) | ✅ Available |
| **GKE (Kubernetes)** | Runs stateful services: Kafka + Flink cluster | ✅ Available |
| **Cloud Run** | Runs stateless Flink Proxy Gateway | ✅ Available |
| **Cloud Storage (GCS)** | Flink state checkpoints & recovery | ✅ Available |
| **VPC / Subnets** | Private network between GKE and Cloud Run | ✅ Available |

### Service Roles in HydraStream

```
Cloud Build  ──builds──►  Artifact Registry  ──images──►  GKE  +  Cloud Run
                                                            │
                                       ┌────────────────────┤
                                       │ Kafka (StatefulSet) │
                                       │ Flink JobManager    │
                                       │ Flink TaskManager   │
                                       │ Flink SQL Gateway   │
                                       └────────────────────┘
                                          ▲          │
                                  Cloud Run          │ state
                             (Proxy Gateway)         ▼
                                   ▲          GCS Bucket
                                   │
                               dbt Worker (Cloud Run Job)
```

## Quick Start — MiniSky (Local)

### Prerequisites
- MiniSky running: `http://localhost:2080` (API), `http://localhost:8081` (Dashboard)
- Terraform ≥ 1.5
- `kubectl` configured
- `gcloud` CLI (optional, for GKE credential fetch)

### 1. Provision infrastructure

```bash
cd gcp/terraform
terraform init
terraform apply -var-file="minisky.tfvars"
```

This creates:
- Artifact Registry repo `hydrastream`
- GCS bucket for Flink state
- VPC + subnet
- GKE cluster (`hydrastream-cluster`, 1 node)
- Cloud Run service for Flink Proxy Gateway
- Cloud Build trigger on `main` branch

### 2. Build Docker images via MiniSky Cloud Build

Trigger a build manually (replace `<PROJECT_ID>` with `hydrastream-local`):

```bash
# Point gcloud at MiniSky
export CLOUDSDK_API_ENDPOINT_OVERRIDES_CLOUDBUILD=http://localhost:2080/cloudbuild/

gcloud builds submit \
  --config=gcp/cloudbuild.yaml \
  --project=hydrastream-local \
  --substitutions=_REGISTRY=localhost:2080,_REGION=us-central1 \
  .
```

Or trigger via Cloud Build GitHub integration (configured by Terraform).

### 3. Deploy services to GKE

```bash
# Get GKE credentials via MiniSky
export CLOUDSDK_API_ENDPOINT_OVERRIDES_CONTAINER=http://localhost:2080/container/
gcloud container clusters get-credentials hydrastream-cluster \
  --zone us-central1-a --project hydrastream-local

# Deploy Kafka
kubectl apply -f gcp/k8s/kafka.yaml

# Deploy Flink cluster
kubectl apply -f gcp/k8s/flink.yaml

# Wait for all pods ready
kubectl wait --for=condition=ready pod -l app=kafka -n hydrastream --timeout=120s
kubectl wait --for=condition=ready pod -l app=flink -n hydrastream --timeout=120s
```

### 4. Run dbt models (submit Flink jobs)

```bash
# The Flink Proxy Gateway runs on Cloud Run — get its URL from Terraform output
PROXY_URL=$(terraform -chdir=gcp/terraform output -raw flink_proxy_url)

docker run --rm \
  -e FLINK_PROXY_HOST=${PROXY_URL} \
  -e FLINK_PROXY_PORT=443 \
  -e KAFKA_TOPIC=clickstream \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka-external.hydrastream.svc.cluster.local:9092 \
  -e CLICKHOUSE_JDBC_URL=${CLICKHOUSE_JDBC_URL} \
  -e CLICKHOUSE_USER=${CLICKHOUSE_USER} \
  -e CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD} \
  -e CLICKHOUSE_TARGET_TABLE=${CLICKHOUSE_TARGET_TABLE} \
  us-central1-docker.pkg.dev/hydrastream-local/hydrastream/dbt:latest \
  dbt run
```

## Quick Start — Real GCP

```bash
cd gcp/terraform
terraform init
terraform apply \
  -var="project_id=YOUR_GCP_PROJECT" \
  -var="region=us-central1" \
  -var="github_repo=qamarudeenm/agent_company_bluemoon"
```

No `minisky_endpoint` → uses real GCP APIs.

## Replacing GitHub Actions

The existing `.github/workflows/build-and-push.yml` pushes to Docker Hub.
`gcp/cloudbuild.yaml` is the Cloud Build equivalent that pushes to Artifact Registry.

Once Cloud Build is wired to the GitHub repo via Terraform trigger, every push to `main`
will automatically build and push all three images — no GitHub Actions or Docker Hub
credentials needed.

## Directory Structure

```
gcp/
├── README.md           ← this file
├── cloudbuild.yaml     ← Cloud Build CI config (replaces .github/workflows/build-and-push.yml)
├── terraform/
│   ├── main.tf         ← all GCP resources
│   ├── variables.tf    ← input variables
│   ├── outputs.tf      ← useful URLs/names after apply
│   └── minisky.tfvars  ← MiniSky-specific overrides (localhost endpoints, smaller nodes)
└── k8s/
    ├── kafka.yaml      ← Kafka StatefulSet + headless service
    └── flink.yaml      ← Flink JobManager, TaskManager, SQL Gateway + ConfigMap
```
