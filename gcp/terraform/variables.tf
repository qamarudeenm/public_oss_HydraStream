variable "project_id" {
  description = "GCP project ID (use any string for MiniSky)"
  type        = string
  default     = "hydrastream-local"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone for GKE node pool"
  type        = string
  default     = "us-central1-a"
}

# MiniSky endpoint — set to http://localhost:2080 for local testing,
# or leave empty to use real GCP APIs.
variable "minisky_endpoint" {
  description = "MiniSky API gateway base URL (e.g. http://localhost:2080). Empty = use real GCP."
  type        = string
  default     = ""
}

variable "artifact_registry_repo" {
  description = "Name of the Artifact Registry Docker repository"
  type        = string
  default     = "hydrastream"
}

variable "gke_cluster_name" {
  description = "GKE cluster name for Flink and Kafka"
  type        = string
  default     = "hydrastream-cluster"
}

variable "gke_node_count" {
  description = "Number of GKE nodes"
  type        = number
  default     = 2
}

variable "gke_machine_type" {
  description = "GKE node machine type"
  type        = string
  default     = "e2-standard-4"
}

variable "flink_checkpoint_bucket" {
  description = "GCS bucket for Flink state checkpoints"
  type        = string
  default     = "hydrastream-flink-state"
}

variable "github_repo" {
  description = "GitHub repo in owner/name format for Cloud Build trigger"
  type        = string
  default     = "qamarudeenm/agent_company_bluemoon"
}

variable "github_pat" {
  description = "GitHub PAT for Cloud Build to pull source (sensitive)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "k8s_namespace" {
  description = "Kubernetes namespace where HydraStream pods run (used for Workload Identity binding)"
  type        = string
  default     = "hydrastream"
}

variable "production_domain" {
  description = "Production domain for the HydraStream control plane (used in OIDC redirect URI)"
  type        = string
  default     = "control-plane.hydrastream.dev"
}

variable "oidc_client_id" {
  description = "GCP OAuth2 client ID for Google Identity Platform OIDC (create in GCP Console → APIs & Services → Credentials)"
  type        = string
  default     = ""
}

variable "alert_email" {
  description = "Email address for Cloud Monitoring alert notifications"
  type        = string
  default     = "ops@hydrastream.io"
}

variable "frontend_domain" {
  description = "Public domain for the HydraStream frontend (uptime check host)"
  type        = string
  default     = "app.hydrastream.io"
}

variable "api_domain" {
  description = "Public domain for the HydraStream API (uptime check host)"
  type        = string
  default     = "api.hydrastream.io"
}

# ── Database (WI-3) ───────────────────────────────────────────────

variable "cloudsql_instance_name" {
  description = "Cloud SQL PostgreSQL instance name"
  type        = string
  default     = "hydrastream-prod"
}

variable "cloudsql_tier" {
  description = "Cloud SQL machine tier (db-g1-small for staging, db-custom-2-7680 for prod)"
  type        = string
  default     = "db-custom-2-7680"
}

variable "redis_instance_name" {
  description = "Memorystore Redis instance name"
  type        = string
  default     = "hydrastream-redis"
}

variable "redis_memory_gb" {
  description = "Memorystore Redis memory size in GB"
  type        = number
  default     = 1
}
