# HydraStream Production Deployment Guide

**Version:** 1.0.0
**Date:** 2026-11-17
**Author:** Product Manager (BLUAA-296, WI-4)
**Status:** Ready for review — pending DevOps Engineer technical accuracy review

---

## Overview

This guide covers deploying HydraStream to a production GCP/GKE environment. It assumes all Sprint 1 P0 fixes are merged (BLUAA-288 through BLUAA-292) and Sprint 2 frontend auth (BLUAA-300) is complete.

**Architecture summary:**

```
Internet → Ingress (TLS) → Control Plane Frontend (Next.js :3000)
                          → Control Plane Backend (FastAPI :8000) → PostgreSQL
                          → Flink Proxy Gateway (:8080) → Flink SQL Gateway (:8083)

Shared Infra:    Kafka (KRaft :9092), PostgreSQL (:5432)
Per-Tenant:      Flink JobManager + TaskManagers, Proxy Gateway, SQL Gateway
Data Pipeline:   Simulator → Kafka → Flink → ClickHouse
Transformations: dbt Worker pods (ephemeral)
```

---

## 1. GCP Prerequisites

> **Terraform alternative:** Sections 1 and 2 can be provisioned via Terraform instead of manual `gcloud` commands. See `gcp/terraform/` — `main.tf` provisions Artifact Registry, GCS bucket, VPC, GKE cluster, Cloud Run, and Cloud Build trigger. Run with `terraform apply -var="project_id=hydrastream-prod"`. The manual steps below are equivalent and shown for clarity.

### 1.1 Project Setup

```bash
export PROJECT_ID="hydrastream-prod"
export REGION="us-central1"
export ZONE="us-central1-a"

gcloud projects create $PROJECT_ID --name="HydraStream Production"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

### 1.2 Artifact Registry

```bash
gcloud artifacts repositories create hydrastream \
  --repository-format=docker \
  --location=$REGION \
  --description="HydraStream container images"

# Authenticate Docker
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

### 1.3 Service Accounts

| Service Account | Purpose | Roles |
|----------------|---------|-------|
| `hydrastream-gke-nodes` | GKE node pool | `roles/artifactregistry.reader`, `roles/logging.logWriter`, `roles/monitoring.metricWriter` |
| `hydrastream-cloudbuild` | Cloud Build CI | `roles/artifactregistry.writer`, `roles/cloudbuild.builds.builder` |
| `hydrastream-control-plane` | Control plane workload identity | `roles/secretmanager.secretAccessor` |

```bash
# GKE node SA
gcloud iam service-accounts create hydrastream-gke-nodes \
  --display-name="HydraStream GKE Nodes"

for ROLE in roles/artifactregistry.reader roles/logging.logWriter roles/monitoring.metricWriter; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:hydrastream-gke-nodes@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Cloud Build SA
gcloud iam service-accounts create hydrastream-cloudbuild \
  --display-name="HydraStream Cloud Build"

for ROLE in roles/artifactregistry.writer roles/cloudbuild.builds.builder; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:hydrastream-cloudbuild@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE"
done
```

### 1.4 VPC Network

```bash
gcloud compute networks create hydrastream-vpc --subnet-mode=custom

gcloud compute networks subnets create hydrastream-subnet \
  --network=hydrastream-vpc \
  --region=$REGION \
  --range=10.0.0.0/20 \
  --secondary-range=pods=10.4.0.0/14,services=10.8.0.0/20

# Allow internal traffic
gcloud compute firewall-rules create hydrastream-internal \
  --network=hydrastream-vpc \
  --allow=tcp,udp,icmp \
  --source-ranges=10.0.0.0/8
```

---

## 2. GKE Cluster Setup

### 2.1 Create Cluster

```bash
gcloud container clusters create hydrastream-prod \
  --zone=$ZONE \
  --network=hydrastream-vpc \
  --subnetwork=hydrastream-subnet \
  --cluster-secondary-range-name=pods \
  --services-secondary-range-name=services \
  --enable-ip-alias \
  --enable-network-policy \
  --workload-pool="${PROJECT_ID}.svc.id.goog" \
  --service-account="hydrastream-gke-nodes@${PROJECT_ID}.iam.gserviceaccount.com" \
  --release-channel=regular \
  --num-nodes=3 \
  --machine-type=e2-standard-4 \
  --disk-size=100 \
  --enable-autorepair \
  --enable-autoupgrade

gcloud container clusters get-credentials hydrastream-prod --zone=$ZONE
```

### 2.2 Node Pool Sizing

| Component | CPU Request | Memory Request | Min Nodes |
|-----------|------------|----------------|-----------|
| Kafka (StatefulSet) | 1 CPU | 2 Gi | 1 (3 for HA) |
| PostgreSQL | 1 CPU | 1 Gi | 1 |
| Control Plane Backend | 500m | 512 Mi | 2 |
| Control Plane Frontend | 500m | 512 Mi | 2 |
| Flink JobManager (per tenant) | 1 CPU | 2 Gi | 1 |
| Flink TaskManager (per tenant) | 1 CPU | 2 Gi | 2 |
| Flink SQL Gateway (per tenant) | 500m | 1 Gi | 1 |
| Flink Proxy Gateway (per tenant) | 500m | 512 Mi | 1 |
| Flink Kubernetes Operator | 500m | 512 Mi | 1 |

**Recommendation:** Start with 3x `e2-standard-4` nodes (4 vCPU, 16 GiB each = 12 vCPU, 48 GiB total). This supports shared infra + 2 tenants. Enable cluster autoscaler for growth:

```bash
gcloud container clusters update hydrastream-prod --zone=$ZONE \
  --enable-autoscaling --min-nodes=3 --max-nodes=10
```

---

## 3. Secrets Management

### 3.1 Create Kubernetes Secrets

All secrets must be created before Helm deployment. Never store secrets in `values.yaml` or git.

```bash
# PostgreSQL credentials
kubectl create secret generic hydrastream-postgres-credentials \
  --from-literal=postgres-password="$(openssl rand -base64 32)" \
  --from-literal=password="$(openssl rand -base64 32)" \
  --from-literal=replication-password="$(openssl rand -base64 32)"

# Control plane database URL (after PostgreSQL is running)
kubectl create secret generic hydrastream-db-url \
  --from-literal=url="postgresql+asyncpg://hydra:<password>@hydrastream-infra-postgresql:5432/hydrastream"

# OIDC configuration
kubectl create secret generic hydrastream-oidc \
  --from-literal=issuer-url="https://your-oidc-provider.example.com" \
  --from-literal=audience="hydrastream-control-plane" \
  --from-literal=proxy-audience="flink-proxy"

# ClickHouse credentials (for tenant data sinks)
kubectl create secret generic hydrastream-clickhouse \
  --from-literal=password="<clickhouse-password>" \
  --from-literal=jdbc-url="jdbc:mysql://<clickhouse-host>:9004/clickstream"

# TLS certificate (if not using cert-manager)
kubectl create secret tls hydrastream-tls \
  --cert=path/to/tls.crt \
  --key=path/to/tls.key
```

### 3.2 GCP Secret Manager (Optional)

For enhanced secret rotation, use GCP Secret Manager with Workload Identity:

```bash
# Create secret in GCP
echo -n "<db-password>" | gcloud secrets create hydrastream-db-password \
  --data-file=- --replication-policy=automatic

# Grant access to control plane SA
gcloud secrets add-iam-policy-binding hydrastream-db-password \
  --member="serviceAccount:hydrastream-control-plane@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 4. Build and Push Images

### 4.1 Using GCP Cloud Build

```bash
cd streaming_infra

gcloud builds submit \
  --config=../gcp/cloudbuild.yaml \
  --substitutions=_REGION=$REGION \
  .
```

This builds and pushes three images to Artifact Registry:
- `${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/engine:flink1.19.1`
- `${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/proxy:${SHORT_SHA}`
- `${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/dbt:${SHORT_SHA}`

Record the `SHORT_SHA` from the build output — you will need it for the proxy image tag.

### 4.2 Control Plane Images

The control plane backend and frontend are not yet included in Cloud Build. Build and push manually:

```bash
# Backend
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-backend:${SHORT_SHA} \
  control_plane/backend/
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-backend:${SHORT_SHA}

# Frontend (requires Dockerfile — see Sprint 2 WI-1 BLUAA-300)
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-frontend:${SHORT_SHA} \
  control_plane/frontend/
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-frontend:${SHORT_SHA}
```

---

## 5. Install Prerequisites

### 5.1 Flink Kubernetes Operator

Required for per-tenant Flink deployments (FlinkDeployment CRD):

```bash
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.9.0/
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator \
  --namespace flink-operator \
  --create-namespace \
  --set watchNamespaces="{default}" \
  --version 1.9.0
```

**Production note:** Update `watchNamespaces` to include all tenant namespaces. For dynamic tenants, set `watchNamespaces="{}"` (empty = watch all namespaces) or use a namespace selector.

### 5.2 cert-manager (Recommended)

For automatic TLS certificate provisioning:

```bash
helm repo add jetstack https://charts.jetstack.io
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true
```

### 5.3 NGINX Ingress Controller

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.type=LoadBalancer
```

---

## 6. Deploy Shared Infrastructure

### 6.1 Production values override

Create `values-prod.yaml` for the `hydrastream-infra` chart:

```yaml
# values-prod.yaml — hydrastream-infra overrides for production

postgresql:
  enabled: true
  auth:
    existingSecret: hydrastream-postgres-credentials
    database: hydrastream
    username: hydra
  primary:
    persistence:
      size: 50Gi
      storageClass: premium-rwo    # GKE SSD-backed
    resources:
      requests:
        cpu: "1"
        memory: 2Gi
      limits:
        cpu: "2"
        memory: 4Gi

kafka:
  image: apache/kafka
  imageTag: "3.9.0"
  replicas: 3                      # HA: 3 brokers minimum
  resources:
    requests:
      cpu: "1"
      memory: 4Gi
    limits:
      cpu: "2"
      memory: 8Gi
  persistence:
    size: 100Gi
    storageClass: premium-rwo
  config:
    autoCreateTopics: "false"      # Explicit topic governance
    defaultReplicationFactor: "3"
    minInsyncReplicas: "2"
    logRetentionHours: "168"       # 7 days

controlPlane:
  database:
    urlSecretName: hydrastream-db-url
```

### 6.2 Deploy

```bash
cd streaming_infra/charts/hydrastream-infra

helm dependency build
helm install hydrastream-infra . \
  --namespace default \
  --values values-prod.yaml \
  --wait --timeout 10m
```

### 6.3 Verify

```bash
# All pods running
kubectl get pods -l app.kubernetes.io/instance=hydrastream-infra

# PostgreSQL accessible
kubectl exec -it hydrastream-infra-postgresql-0 -- \
  psql -U hydra -d hydrastream -c "SELECT 1"

# Kafka broker ready
kubectl exec -it hydrastream-infra-kafka-0 -- \
  /opt/kafka/bin/kafka-metadata.sh --snapshot /var/lib/kafka/data/__cluster_metadata-0/00000000000000000000.log --cluster-id $(kubectl exec hydrastream-infra-kafka-0 -- cat /var/lib/kafka/data/meta.properties | grep cluster.id | cut -d= -f2)
```

---

## 7. Deploy Control Plane

The control plane is not yet included in the Helm charts. Deploy via K8s manifests:

### 7.1 Backend Deployment

```yaml
# control-plane-backend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: control-plane-backend
  labels:
    app: control-plane-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: control-plane-backend
  template:
    metadata:
      labels:
        app: control-plane-backend
    spec:
      containers:
      - name: backend
        image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-backend:${SHORT_SHA}
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: hydrastream-db-url
              key: url
        - name: CONTROL_PLANE_OIDC_ISSUER_URL
          valueFrom:
            secretKeyRef:
              name: hydrastream-oidc
              key: issuer-url
        - name: CONTROL_PLANE_OIDC_AUDIENCE
          valueFrom:
            secretKeyRef:
              name: hydrastream-oidc
              key: audience
        - name: CORS_ALLOWED_ORIGINS
          value: "https://hydrastream.example.com"
        - name: CONTROL_PLANE_AUTH_DISABLED
          value: "false"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
        securityContext:
          runAsNonRoot: true
          runAsUser: 10001
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: [ALL]
---
apiVersion: v1
kind: Service
metadata:
  name: control-plane-backend
spec:
  selector:
    app: control-plane-backend
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP
```

### 7.2 Frontend Deployment

```yaml
# control-plane-frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: control-plane-frontend
  labels:
    app: control-plane-frontend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: control-plane-frontend
  template:
    metadata:
      labels:
        app: control-plane-frontend
    spec:
      containers:
      - name: frontend
        image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/control-plane-frontend:${SHORT_SHA}
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_URL
          value: "https://hydrastream.example.com/api"
        - name: NEXT_PUBLIC_OIDC_ISSUER_URL
          valueFrom:
            secretKeyRef:
              name: hydrastream-oidc
              key: issuer-url
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: "1"
            memory: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: control-plane-frontend
spec:
  selector:
    app: control-plane-frontend
  ports:
  - port: 3000
    targetPort: 3000
  type: ClusterIP
```

---

## 8. DNS and TLS/Ingress

### 8.1 Ingress Resource

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hydrastream-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - hydrastream.example.com
    secretName: hydrastream-tls
  rules:
  - host: hydrastream.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: control-plane-backend
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: control-plane-frontend
            port:
              number: 3000
```

### 8.2 cert-manager ClusterIssuer

```yaml
# cluster-issuer.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
    - http01:
        ingress:
          class: nginx
```

### 8.3 DNS Configuration

```bash
# Get the ingress external IP
INGRESS_IP=$(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Create DNS A record:
# hydrastream.example.com → $INGRESS_IP
```

---

## 9. Deploy First Tenant

### 9.1 Create Tenant Namespace

```bash
export TENANT_ID="tenant-1"
export TENANT_NS="$TENANT_ID"

kubectl create namespace $TENANT_NS
```

### 9.2 Production values override for tenant

Create `values-tenant-prod.yaml`:

```yaml
# values-tenant-prod.yaml — hydrastream-tenant overrides

tenantId: tenant-1

flink:
  image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/engine
  imageTag: flink1.19.1
  jobManager:
    replicas: 1
    resources:
      cpu: "2"
      memory: 4Gi
  taskManager:
    replicas: 2
    resources:
      cpu: "2"
      memory: 4Gi
    taskSlots: 2

proxy:
  image:
    repository: ${REGION}-docker.pkg.dev/${PROJECT_ID}/hydrastream/proxy
    tag: "<SHORT_SHA>"           # Must be a git-SHA tag, e.g. abc1234
  auth:
    mode: oidc_jwt
    issuerUrl: "https://your-oidc-provider.example.com"
    audience: flink-proxy
    algorithms: RS256
  resources:
    requests:
      cpu: 500m
      memory: 512Mi
    limits:
      cpu: "1"
      memory: 1Gi

sqlGateway:
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: "1"
      memory: 2Gi

kafka:
  bootstrapServers: "hydrastream-infra-kafka.default:9092"

clickhouse:
  jdbcUrl: "jdbc:mysql://<clickhouse-host>:9004/clickstream"
  user: flink_user
  passwordSecret: hydrastream-clickhouse
```

### 9.3 Deploy Tenant

Use the production deploy script which enforces immutable image tags:

```bash
# Get the proxy image SHA from your build
PROXY_TAG="proxy-abc1234"  # Replace with actual SHORT_SHA

./streaming_infra/deploy-tenant.sh $TENANT_ID $TENANT_NS $PROXY_TAG
```

Or deploy directly with Helm:

```bash
helm install hydrastream-${TENANT_ID} streaming_infra/charts/hydrastream-tenant \
  --namespace $TENANT_NS \
  --values values-tenant-prod.yaml \
  --set proxy.image.tag="$PROXY_TAG" \
  --wait --timeout 10m
```

### 9.4 Verify Tenant

```bash
# All tenant pods running
kubectl get pods -n $TENANT_NS

# Flink cluster healthy
kubectl get flinkdeployment -n $TENANT_NS

# Proxy gateway responding
kubectl port-forward -n $TENANT_NS svc/flink-proxy-gateway 8080:8080 &
curl -s http://localhost:8080/health
# Expected: {"status":"ok"}

# SQL Gateway responding
kubectl port-forward -n $TENANT_NS svc/flink-sql-gateway 8083:8083 &
curl -s http://localhost:8083/v1/info
```

---

## 10. Monitoring and Observability

### 10.1 GKE Built-in Monitoring

GKE integrates with Cloud Monitoring and Cloud Logging by default (enabled by the node SA roles in section 1.3).

Key dashboards to set up in Cloud Monitoring:
- **Pod resource usage** (CPU, memory per pod)
- **Kafka consumer lag** (critical for pipeline health)
- **PostgreSQL connections and query latency**
- **HTTP error rates** (control plane backend 4xx/5xx)

### 10.2 Health Check Endpoints

| Service | Endpoint | Expected Response |
|---------|----------|-------------------|
| Control Plane Backend | `GET /health` | `{"status":"healthy","database":"healthy"}` |
| Flink Proxy Gateway | `GET /health` | `{"status":"ok"}` |
| Flink Proxy Gateway | `GET /ready` | `{"status":"ready"}` |
| Flink Dashboard | `GET :8081/overview` | Flink cluster metrics JSON |

### 10.3 Alerts (Recommended)

| Alert | Condition | Severity |
|-------|-----------|----------|
| Pod CrashLoopBackOff | Pod restart count > 5 in 10 min | Critical |
| Kafka under-replicated partitions | > 0 for 5 min | Critical |
| PostgreSQL connection pool exhausted | Active connections > 80% of pool_size (5) | Warning |
| Control plane 5xx rate | > 1% of requests over 5 min | Warning |
| Flink job failure | FlinkDeployment status != RUNNING | Critical |
| Disk usage > 80% | PVC usage > 80% | Warning |
| Certificate expiry | < 14 days | Warning |

### 10.4 Flink Monitoring

Access the Flink Dashboard for each tenant via port-forward:

```bash
kubectl port-forward -n $TENANT_NS svc/flink-jobmanager 8081:8081
# Open http://localhost:8081
```

Check Flink operator logs:

```bash
kubectl logs -n flink-operator -l app.kubernetes.io/name=flink-kubernetes-operator --tail=100
```

---

## 11. Security Checklist

Run the cybersecurity gate before every production deployment:

```bash
cd streaming_infra
bash security/cybersecurity-gate.sh
```

**All controls must pass (exit code 0).** The gate validates:

- [ ] Proxy auth mode is `oidc_jwt` (not `passthrough`)
- [ ] Container security: `runAsNonRoot`, `readOnlyRootFilesystem`, no privilege escalation
- [ ] No default passwords in Helm values or example.env
- [ ] Proxy image tag is immutable (not `proxy-latest`)

**Additional production checks:**

- [ ] `CONTROL_PLANE_AUTH_DISABLED` is `false`
- [ ] `CORS_ALLOWED_ORIGINS` is set to your domain (not `*`)
- [ ] PostgreSQL password is rotated from defaults
- [ ] ClickHouse password is not `REPLACE_ME_SECURE_SECRET`
- [ ] All container images use Artifact Registry (not Docker Hub)
- [ ] Network policies restrict cross-namespace traffic
- [ ] RBAC is scoped per tenant namespace

---

## 12. Rollback Procedures

### 12.1 Helm Rollback

```bash
# List revisions
helm history hydrastream-infra
helm history hydrastream-${TENANT_ID} -n $TENANT_NS

# Rollback to previous revision
helm rollback hydrastream-infra <REVISION>
helm rollback hydrastream-${TENANT_ID} <REVISION> -n $TENANT_NS
```

### 12.2 Database Rollback

PostgreSQL data is preserved across Helm rollbacks (PVC is retained). For schema rollbacks, use Alembic:

```bash
kubectl exec -it deploy/control-plane-backend -- alembic downgrade -1
```

### 12.3 Emergency: Delete Tenant

```bash
helm uninstall hydrastream-${TENANT_ID} -n $TENANT_NS
kubectl delete namespace $TENANT_NS
```

---

## 13. First-Tenant Onboarding Checklist

Use this checklist when deploying a new production tenant:

### Pre-deployment

- [ ] GCP project created with required APIs enabled
- [ ] GKE cluster running with sufficient node capacity
- [ ] Artifact Registry images built and pushed (record SHORT_SHA: ________)
- [ ] OIDC provider configured with redirect URIs for `hydrastream.example.com`
- [ ] DNS A record pointing to ingress IP
- [ ] TLS certificate provisioned (cert-manager or manual)
- [ ] All K8s secrets created (PostgreSQL, OIDC, ClickHouse, TLS)
- [ ] Flink Kubernetes Operator installed

### Shared Infrastructure

- [ ] `hydrastream-infra` Helm chart deployed
- [ ] PostgreSQL pod Ready, `SELECT 1` succeeds
- [ ] Kafka broker pod Ready, cluster ID available
- [ ] Control plane backend deployed, `/health` returns `{"status":"healthy","database":"healthy"}`
- [ ] Control plane frontend deployed, login page loads
- [ ] Ingress configured, TLS termination working
- [ ] Cybersecurity gate passes (exit code 0)

### Tenant Deployment

- [ ] Tenant namespace created
- [ ] `hydrastream-tenant` Helm chart deployed with immutable proxy tag
- [ ] Flink JobManager and TaskManager pods Running
- [ ] SQL Gateway `/v1/info` responds
- [ ] Proxy Gateway `/health` and `/ready` respond
- [ ] OIDC JWT auth verified on proxy (unauthenticated request returns 401)

### End-to-End Validation

- [ ] Frontend login succeeds via OIDC
- [ ] Create tenant via control plane UI — tenant appears in PostgreSQL
- [ ] Data simulator produces events to Kafka topic
- [ ] Flink job processes events (check Flink Dashboard)
- [ ] Events arrive at ClickHouse sink
- [ ] dbt transformation runs successfully
- [ ] Delete tenant via control plane UI — cleanup confirmed

### Monitoring

- [ ] Pod metrics visible in Cloud Monitoring
- [ ] Logs flowing to Cloud Logging
- [ ] Critical alerts configured (CrashLoop, Kafka under-replicated, Flink job failure)
- [ ] Runbook linked in alert notifications

---

## Appendix A: Environment Variables Reference

### Control Plane Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://hydra:hydra@localhost:5432/hydrastream` | PostgreSQL connection string |
| `CONTROL_PLANE_OIDC_ISSUER_URL` | Yes (prod) | `""` | OIDC provider URL |
| `CONTROL_PLANE_OIDC_AUDIENCE` | No | `hydrastream-control-plane` | JWT audience claim |
| `CONTROL_PLANE_AUTH_DISABLED` | No | `false` | Disable auth (dev only) |
| `CORS_ALLOWED_ORIGINS` | Yes (prod) | `http://localhost:3000` | Comma-separated allowed origins |

### Flink Proxy Gateway

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROXY_FLINK_GATEWAY_URL` | Yes | — | Flink SQL Gateway URL |
| `PROXY_AUTH_MODE` | Yes | `passthrough` | `oidc_jwt` for production |
| `PROXY_OIDC_ISSUER_URL` | Yes (if oidc_jwt) | `""` | OIDC issuer URL |
| `PROXY_JWT_AUDIENCE` | Yes (if oidc_jwt) | `""` | Expected JWT audience |
| `PROXY_JWT_ALGORITHMS` | No | `RS256` | JWT signing algorithms |
| `PROXY_LISTEN_PORT` | No | `8080` | Listen port |
| `PROXY_SESSION_IDLE_TIMEOUT` | No | `600` | Session timeout (seconds) |
| `PROXY_LOG_LEVEL` | No | `info` | Log level |

### Helm Chart Values

| Chart | Key | Production Override |
|-------|-----|-------------------|
| `hydrastream-infra` | `postgresql.auth.existingSecret` | K8s secret name |
| `hydrastream-infra` | `kafka.replicas` | `3` (HA) |
| `hydrastream-infra` | `kafka.config.autoCreateTopics` | `"false"` |
| `hydrastream-tenant` | `proxy.image.tag` | Git SHA tag (required) |
| `hydrastream-tenant` | `proxy.auth.mode` | `oidc_jwt` |
| `hydrastream-tenant` | `proxy.auth.issuerUrl` | OIDC provider URL |

---

## Appendix B: Port Reference

| Service | Port | Protocol | Exposure |
|---------|------|----------|----------|
| Kafka (external) | 9092 | TCP | ClusterIP |
| Kafka (controller) | 9093 | TCP | ClusterIP |
| PostgreSQL | 5432 | TCP | ClusterIP |
| Control Plane Backend | 8000 | HTTP | Ingress `/api` |
| Control Plane Frontend | 3000 | HTTP | Ingress `/` |
| Flink Proxy Gateway | 8080 | HTTP | ClusterIP (per tenant) |
| Flink SQL Gateway | 8083 | HTTP | ClusterIP (per tenant) |
| Flink Dashboard | 8081 | HTTP | Port-forward only |
| ClickHouse (MySQL) | 9004 | TCP | External or ClusterIP |
