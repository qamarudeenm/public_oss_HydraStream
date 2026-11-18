# ☸️ HydraStream: Kubernetes Migration Guide

This guide describes how to migrate the HydraStream infrastructure from Docker Compose to Kubernetes.

## 🏗️ Architecture on Kubernetes

The Kubernetes deployment follows a **Multi-Tenant** architecture:

1.  **Control Plane**: Shared services (UI, Backend, Database).
2.  **Shared Infrastructure**: Shared services like Kafka.
3.  **Data Plane (Tenants)**: Isolated environments per tenant, each in their own namespace.
    *   **Flink Kubernetes Operator**: Manages Flink clusters.
    *   **Tenant Flink Cluster**: JobManager and TaskManagers managed by the operator.
    *   **Flink SQL Gateway**: Tenant-specific SQL Gateway.
    *   **Flink Proxy Gateway**: Bridges dbt to the SQL Gateway.

---

## 🚀 Deployment Steps

### 1. Prerequisites
Ensure you have `kubectl` and `helm` installed and connected to your cluster.

### 2. Deploy Apache Flink Kubernetes Operator
The operator is required to manage Flink clusters via the `FlinkDeployment` CRD.

```bash
cd streaming_infra/k8s-operator
./deploy-operator.sh
```

### 3. Deploy Shared Infrastructure (Kafka)
Install the shared Kafka cluster.

```bash
cd streaming_infra
helm install hydrastream-infra ./charts/hydrastream-infra --namespace default
```

### 4. Deploy a Tenant
Each tenant gets their own isolated environment.

```bash
./deploy-tenant.sh tenant-a
```

---

## 📦 Helm Charts

### `hydrastream-infra`
Deploys shared infrastructure.
- **Components**: Kafka (StatefulSet).
- **Configuration**: See `charts/hydrastream-infra/values.yaml`.

### `hydrastream-tenant`
Deploys an isolated data plane for a tenant.
- **Components**:
    - `FlinkDeployment`: Managed by the Flink Operator.
    - `sql-gateway`: Deployment + Service.
    - `proxy-gateway`: Deployment + Service.
    - `RBAC`: ServiceAccount, Role, and RoleBinding for the tenant pods.
- **Configuration**: See `charts/hydrastream-tenant/values.yaml`.

---

## 🛠️ Running dbt Jobs on Kubernetes

When a user triggers a `dbt run`, the Control Plane should launch an ephemeral Kubernetes Pod.

**Pod Configuration Requirements:**
- **Image**: `blue2berry/hydrastream:dbt-latest`
- **Environment Variables**:
    - `FLINK_PROXY_HOST`: `<tenant-id>-proxy.<tenant-namespace>`
    - `FLINK_PROXY_PORT`: `8080`
- **Profiles**: The pod should have a `profiles.yml` pointing to the proxy.

Example `profiles.yml` for dbt in K8s:
```yaml
hydrastream:
  outputs:
    dev:
      type: confluent
      host: tenant-a-proxy.tenant-a
      port: 8080
      # ... other settings
  target: dev
```

---

## 🔍 Monitoring
- **Flink Dashboard**: Access the JobManager REST API via `kubectl port-forward`.
- **Operator Logs**: `kubectl logs -n flink-operator -l app=flink-kubernetes-operator`.
- **Tenant Status**: `kubectl get flinkdeployment -n <tenant-namespace>`.

---

## 🔐 Cybersecurity Gate

Before production rollout, run the cybersecurity gate from repo root:

```bash
./streaming_infra/security/cybersecurity-gate.sh
```

The gate validates:
- Proxy authentication mode is enforced (`oidc_jwt`) in Kubernetes and Helm defaults.
- Proxy runtime hardening (`runAsNonRoot`, dropped capabilities, read-only root filesystem).
- Basic secret hygiene in sample/values files.

If the script exits non-zero, deployment is not release-ready and must be remediated first.
