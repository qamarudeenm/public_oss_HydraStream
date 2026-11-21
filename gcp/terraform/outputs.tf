output "artifact_registry_url" {
  description = "Docker image push/pull URL prefix"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repo}"
}

output "flink_state_bucket" {
  description = "GCS bucket for Flink checkpoints (use as state.checkpoints.dir in Flink config)"
  value       = "gs://${google_storage_bucket.flink_state.name}/checkpoints"
}

output "gke_cluster_name" {
  description = "GKE cluster name — use with: gcloud container clusters get-credentials"
  value       = google_container_cluster.hydrastream.name
}

output "flink_proxy_url" {
  description = "Cloud Run URL for the Flink Proxy Gateway"
  value       = google_cloud_run_v2_service.flink_proxy.uri
}

output "vpc_name" {
  description = "VPC network name"
  value       = google_compute_network.hydrastream_vpc.name
}

output "control_plane_service_account_email" {
  description = "GCP service account email for control plane pods (use in K8s ServiceAccount annotation)"
  value       = length(google_service_account.control_plane) > 0 ? google_service_account.control_plane[0].email : ""
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL for Google Identity Platform — set as CONTROL_PLANE_OIDC_ISSUER_URL on the backend"
  value       = "https://accounts.google.com"
}

output "oidc_audience" {
  description = "OIDC audience (= GCP OAuth2 client ID) — set as CONTROL_PLANE_OIDC_AUDIENCE on the backend and OIDC_CLIENT_ID on the frontend"
  value       = var.oidc_client_id
}

output "oidc_redirect_uri" {
  description = "Production OIDC redirect URI — register this in GCP Console → APIs & Services → Credentials"
  value       = "https://${var.production_domain}/api/auth/callback"
}

output "secret_manager_secrets" {
  description = "Secret Manager secret IDs — populate values before deploying pods"
  value = length(google_secret_manager_secret.db_password) > 0 ? {
    database_url       = google_secret_manager_secret.database_url[0].secret_id
    db_password        = google_secret_manager_secret.db_password[0].secret_id
    redis_password     = google_secret_manager_secret.redis_password[0].secret_id
    oidc_client_secret = google_secret_manager_secret.oidc_client_secret[0].secret_id
    kafka_credentials  = google_secret_manager_secret.kafka_credentials[0].secret_id
  } : {}
}

# ── Database outputs (WI-3) ───────────────────────────────────────

output "cloudsql_private_ip" {
  description = "Cloud SQL private IP — reachable only from within hydrastream-vpc"
  value       = length(google_sql_database_instance.hydrastream) > 0 ? google_sql_database_instance.hydrastream[0].private_ip_address : ""
}

output "cloudsql_connection_name" {
  description = "Cloud SQL connection name — for Cloud SQL Auth Proxy if needed"
  value       = length(google_sql_database_instance.hydrastream) > 0 ? google_sql_database_instance.hydrastream[0].connection_name : ""
}

output "redis_host" {
  description = "Memorystore Redis host — reachable only from within hydrastream-vpc"
  value       = length(google_redis_instance.hydrastream) > 0 ? google_redis_instance.hydrastream[0].host : ""
}

output "redis_port" {
  description = "Memorystore Redis port"
  value       = length(google_redis_instance.hydrastream) > 0 ? google_redis_instance.hydrastream[0].port : 0
}

output "secret_cp_database_url" {
  description = "Secret Manager secret ID for the control-plane DATABASE_URL"
  value       = length(google_secret_manager_secret.cp_database_url) > 0 ? google_secret_manager_secret.cp_database_url[0].secret_id : ""
}

output "secret_sink_jdbc_url" {
  description = "Secret Manager secret ID for the Flink sink JDBC URL"
  value       = length(google_secret_manager_secret.sink_jdbc_url) > 0 ? google_secret_manager_secret.sink_jdbc_url[0].secret_id : ""
}

output "secret_redis_url" {
  description = "Secret Manager secret ID for the Redis URL"
  value       = length(google_secret_manager_secret.redis_url) > 0 ? google_secret_manager_secret.redis_url[0].secret_id : ""
}
