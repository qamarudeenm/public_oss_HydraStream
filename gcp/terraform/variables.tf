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
