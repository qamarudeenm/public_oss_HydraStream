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

# ── Database outputs (WI-3) ───────────────────────────────────────

output "cloudsql_private_ip" {
  description = "Cloud SQL private IP — reachable only from within hydrastream-vpc"
  value       = google_sql_database_instance.hydrastream.private_ip_address
}

output "cloudsql_connection_name" {
  description = "Cloud SQL connection name — for Cloud SQL Auth Proxy if needed"
  value       = google_sql_database_instance.hydrastream.connection_name
}

output "redis_host" {
  description = "Memorystore Redis host — reachable only from within hydrastream-vpc"
  value       = google_redis_instance.hydrastream.host
}

output "redis_port" {
  description = "Memorystore Redis port"
  value       = google_redis_instance.hydrastream.port
}

output "secret_cp_database_url" {
  description = "Secret Manager secret ID for the control-plane DATABASE_URL"
  value       = google_secret_manager_secret.cp_database_url.secret_id
}

output "secret_sink_jdbc_url" {
  description = "Secret Manager secret ID for the Flink sink JDBC URL"
  value       = google_secret_manager_secret.sink_jdbc_url.secret_id
}

output "secret_redis_url" {
  description = "Secret Manager secret ID for the Redis URL"
  value       = google_secret_manager_secret.redis_url.secret_id
}
