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
