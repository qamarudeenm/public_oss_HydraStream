terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# ─────────────────────────────────────────────────────────────────
# Provider — MiniSky mode: override all endpoints to localhost:2080
# Real GCP mode: leave minisky_endpoint empty
# ─────────────────────────────────────────────────────────────────
locals {
  minisky = var.minisky_endpoint != "" ? var.minisky_endpoint : null

  # MiniSky routes GCP API calls by path prefix on its gateway
  ar_endpoint         = local.minisky != null ? "${local.minisky}/artifactregistry/" : null
  build_endpoint      = local.minisky != null ? "${local.minisky}/cloudbuild/" : null
  compute_endpoint    = local.minisky != null ? "${local.minisky}/compute/" : null
  container_endpoint  = local.minisky != null ? "${local.minisky}/container/" : null
  run_endpoint        = local.minisky != null ? "${local.minisky}/run/" : null
  storage_endpoint    = local.minisky != null ? "${local.minisky}/storage/v1/" : null
  iam_endpoint        = local.minisky != null ? "${local.minisky}/iam/" : null
  logging_endpoint    = local.minisky != null ? "${local.minisky}/logging/" : null
  monitoring_endpoint = local.minisky != null ? "${local.minisky}/monitoring/" : null
}

provider "google" {
  project = var.project_id
  region  = var.region

  # Custom endpoints — only set when using MiniSky
  artifact_registry_custom_endpoint = local.ar_endpoint
  cloud_build_custom_endpoint       = local.build_endpoint
  compute_custom_endpoint           = local.compute_endpoint
  container_custom_endpoint         = local.container_endpoint
  cloud_run_v2_custom_endpoint      = local.run_endpoint
  storage_custom_endpoint           = local.storage_endpoint
  iam_credentials_custom_endpoint   = local.iam_endpoint
  logging_custom_endpoint           = local.logging_endpoint
  monitoring_custom_endpoint        = local.monitoring_endpoint
}

# ─────────────────────────────────────────────────────────────────
# 1. Artifact Registry — Docker image repository
# ─────────────────────────────────────────────────────────────────
resource "google_artifact_registry_repository" "hydrastream" {
  location      = var.region
  repository_id = var.artifact_registry_repo
  description   = "HydraStream Docker images (Flink engine, proxy, dbt worker)"
  format        = "DOCKER"
}

# ─────────────────────────────────────────────────────────────────
# 2. GCS Bucket — Flink state checkpoints
# ─────────────────────────────────────────────────────────────────
resource "google_storage_bucket" "flink_state" {
  name          = "${var.project_id}-${var.flink_checkpoint_bucket}"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 30 }
    action    { type = "Delete" }
  }
}

# ─────────────────────────────────────────────────────────────────
# 3. VPC — Private network for GKE and Cloud Run
# ─────────────────────────────────────────────────────────────────
resource "google_compute_network" "hydrastream_vpc" {
  name                    = "hydrastream-vpc"
  auto_create_subnetworks = false

  lifecycle {
    # MiniSky compute shim returns 405 on PATCH; this field is a computed default
    ignore_changes = [network_firewall_policy_enforcement_order]
  }
}

resource "google_compute_subnetwork" "hydrastream_subnet" {
  count         = local.minisky == null ? 1 : 0
  name          = "hydrastream-subnet"
  ip_cidr_range = "10.0.0.0/16"
  network       = google_compute_network.hydrastream_vpc.id
  region        = var.region

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/16"
  }
}

# ─────────────────────────────────────────────────────────────────
# 4. GKE Cluster — Stateful services: Kafka + full Flink cluster
#    (JobManager, TaskManager, SQL Gateway)
#    Workload Identity enabled for Secret Manager access
# ─────────────────────────────────────────────────────────────────
resource "google_container_cluster" "hydrastream" {
  name     = var.gke_cluster_name
  location = var.zone

  network    = google_compute_network.hydrastream_vpc.name
  subnetwork = length(google_compute_subnetwork.hydrastream_subnet) > 0 ? google_compute_subnetwork.hydrastream_subnet[0].name : null

  # Separate node pool; remove default
  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = length(google_compute_subnetwork.hydrastream_subnet) > 0 ? "pods" : null
    services_secondary_range_name = length(google_compute_subnetwork.hydrastream_subnet) > 0 ? "services" : null
  }

  # Workload Identity — allows GKE pods to authenticate as GCP service accounts
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }
}

resource "google_container_node_pool" "hydrastream_nodes" {
  name       = "hydrastream-nodes"
  cluster    = google_container_cluster.hydrastream.name
  location   = var.zone
  node_count = var.gke_node_count

  node_config {
    machine_type = var.gke_machine_type
    disk_size_gb = 50

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    # Use GKE metadata server for Workload Identity (required)
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }

  autoscaling {
    min_node_count = 1
    max_node_count = 5
  }
}

# ─────────────────────────────────────────────────────────────────
# 5. Cloud Run — Flink Proxy Gateway (stateless)
# ─────────────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "flink_proxy" {
  name     = "flink-proxy-gateway"
  location = var.region

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}/proxy:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "PROXY_FLINK_GATEWAY_URL"
        # Points to Flink SQL Gateway running in GKE — expose via LoadBalancer or internal ingress
        value = "http://flink-sql-gateway.hydrastream.svc.cluster.local:8083"
      }

      env {
        name  = "PROXY_LISTEN_HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "PROXY_LISTEN_PORT"
        value = "8080"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    dynamic "vpc_access" {
      for_each = local.minisky == null ? [1] : []
      content {
        network_interfaces {
          network    = google_compute_network.hydrastream_vpc.name
          subnetwork = google_compute_subnetwork.hydrastream_subnet[0].name
        }
        egress = "PRIVATE_RANGES_ONLY"
      }
    }
  }

  depends_on = [google_artifact_registry_repository.hydrastream]
}

# Allow unauthenticated access to the proxy from internal services
resource "google_cloud_run_v2_service_iam_member" "flink_proxy_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.flink_proxy.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ─────────────────────────────────────────────────────────────────
# 6. Cloud Build Trigger — builds Docker images on push to main
# ─────────────────────────────────────────────────────────────────
resource "google_cloudbuild_trigger" "hydrastream_build" {
  count       = local.minisky == null ? 1 : 0
  name        = "hydrastream-build-push"
  description = "Build and push HydraStream Docker images on push to main"

  github {
    owner = split("/", var.github_repo)[0]
    name  = split("/", var.github_repo)[1]

    push {
      branch = "^main$"
    }
  }

  filename = "gcp/cloudbuild.yaml"

  substitutions = {
    _REGISTRY = "${var.region}-docker.pkg.dev"
    _REGION   = var.region
  }
}

# ─────────────────────────────────────────────────────────────────
# 7. Required GCP APIs
#    Not provisioned in MiniSky mode (no emulator for these)
# ─────────────────────────────────────────────────────────────────
resource "google_project_service" "secretmanager" {
  count   = local.minisky == null ? 1 : 0
  service = "secretmanager.googleapis.com"

  disable_on_destroy = false
}

resource "google_project_service" "identitytoolkit" {
  count   = local.minisky == null ? 1 : 0
  service = "identitytoolkit.googleapis.com"

  disable_on_destroy = false
}

# ─────────────────────────────────────────────────────────────────
# 8. GCP Service Account — control plane pods (Workload Identity)
# ─────────────────────────────────────────────────────────────────
resource "google_service_account" "control_plane" {
  count        = local.minisky == null ? 1 : 0
  account_id   = "hydrastream-control-plane"
  display_name = "HydraStream Control Plane (Workload Identity)"
}

# Allow the GKE Kubernetes service account to impersonate this GCP SA
resource "google_service_account_iam_member" "control_plane_workload_identity" {
  count              = local.minisky == null ? 1 : 0
  service_account_id = google_service_account.control_plane[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.k8s_namespace}/hydrastream-control-plane]"
}

# Grant the control plane SA access to read secrets from Secret Manager
resource "google_project_iam_member" "control_plane_secretmanager" {
  count   = local.minisky == null ? 1 : 0
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.control_plane[0].email}"

  depends_on = [google_project_service.secretmanager]
}

# ─────────────────────────────────────────────────────────────────
# 9. GCP Secret Manager — sensitive credentials
#    Secrets are created empty; populate values via:
#      gcloud secrets versions add <secret-id> --data-file=-
#    or via the GCP Console before deploying pods.
# ─────────────────────────────────────────────────────────────────
resource "google_secret_manager_secret" "db_password" {
  count     = local.minisky == null ? 1 : 0
  secret_id = "hydrastream-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "redis_password" {
  count     = local.minisky == null ? 1 : 0
  secret_id = "hydrastream-redis-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "oidc_client_secret" {
  count     = local.minisky == null ? 1 : 0
  secret_id = "hydrastream-oidc-client-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "kafka_credentials" {
  count     = local.minisky == null ? 1 : 0
  secret_id = "hydrastream-kafka-credentials"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "database_url" {
  count     = local.minisky == null ? 1 : 0
  secret_id = "hydrastream-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}
