# ─────────────────────────────────────────────────────────────────
# HydraStream — Cloud Logging: log-based metrics, retention, queries
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# Log retention — override default _Default bucket to 90 days
# ─────────────────────────────────────────────────────────────────

resource "google_logging_project_bucket_config" "default_retention" {
  count          = local.minisky == null ? 1 : 0
  project        = var.project_id
  location       = "global"
  bucket_id      = "_Default"
  retention_days = 90
  description    = "HydraStream production logs — 90-day retention"
}

# ─────────────────────────────────────────────────────────────────
# Log-based metrics
# ─────────────────────────────────────────────────────────────────

resource "google_logging_metric" "app_errors" {
  count       = local.minisky == null ? 1 : 0
  name        = "hydrastream_app_errors"
  description = "Count of ERROR-level log entries from HydraStream GKE containers"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND severity=\"ERROR\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
    labels {
      key         = "container_name"
      value_type  = "STRING"
      description = "Name of the container that emitted the error"
    }
  }

  label_extractors = {
    "container_name" = "EXTRACT(resource.labels.container_name)"
  }
}

resource "google_logging_metric" "flink_checkpoint_failure" {
  count       = local.minisky == null ? 1 : 0
  name        = "flink_checkpoint_failure"
  description = "Count of Flink checkpoint failure log entries"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND textPayload=~\"(?i)(checkpoint.*fail|fail.*checkpoint)\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "oom_kills" {
  count       = local.minisky == null ? 1 : 0
  name        = "hydrastream_oom_kills"
  description = "Count of OOMKilled container events"
  filter      = "resource.type=\"k8s_node\" AND jsonPayload.reason=\"OOMKilling\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "pod_evictions" {
  count       = local.minisky == null ? 1 : 0
  name        = "hydrastream_pod_evictions"
  description = "Count of pod eviction events in HydraStream namespace"
  filter      = "resource.type=\"k8s_cluster\" AND jsonPayload.reason=\"Evicted\" AND jsonPayload.metadata.namespace=\"hydrastream\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

resource "google_logging_metric" "kafka_consumer_lag_errors" {
  count       = local.minisky == null ? 1 : 0
  name        = "hydrastream_kafka_consumer_lag_errors"
  description = "Count of Kafka consumer lag or connection error log entries"
  filter      = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND textPayload=~\"(?i)(kafka.*error|consumer.*lag|connection.*refused.*kafka)\""

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

# ─────────────────────────────────────────────────────────────────
# Saved log queries (stored as a local reference file)
# Cloud Logging saved views are not natively Terraform-managed;
# these queries are documented here for operator use.
# ─────────────────────────────────────────────────────────────────

resource "local_file" "saved_log_queries" {
  filename = "${path.module}/saved_log_queries.md"
  content  = <<-EOT
    # HydraStream — Saved Cloud Logging Queries

    ## All ERROR logs from HydraStream pods
    ```
    resource.type="k8s_container"
    resource.labels.cluster_name="${var.gke_cluster_name}"
    severity="ERROR"
    ```

    ## Flink checkpoint failures
    ```
    resource.type="k8s_container"
    resource.labels.cluster_name="${var.gke_cluster_name}"
    textPayload=~"(?i)(checkpoint.*fail|fail.*checkpoint)"
    ```

    ## Pod OOM kills
    ```
    resource.type="k8s_node"
    jsonPayload.reason="OOMKilling"
    ```

    ## Cloud SQL slow queries (> 1s)
    ```
    resource.type="cloudsql_database"
    textPayload=~"duration: [1-9][0-9]{3,}"
    ```

    ## Flink Proxy Gateway 5xx errors
    ```
    resource.type="cloud_run_revision"
    resource.labels.service_name="flink-proxy-gateway"
    httpRequest.status>=500
    ```

    ## Control plane auth failures
    ```
    resource.type="k8s_container"
    resource.labels.cluster_name="${var.gke_cluster_name}"
    textPayload=~"(?i)(unauthorized|forbidden|auth.*fail|invalid.*token)"
    ```

    ## Kafka consumer group lag
    ```
    resource.type="k8s_container"
    resource.labels.cluster_name="${var.gke_cluster_name}"
    textPayload=~"(?i)(consumer.*lag|lag.*consumer)"
    ```
  EOT
}
