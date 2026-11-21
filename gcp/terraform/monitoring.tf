# ─────────────────────────────────────────────────────────────────
# HydraStream — Cloud Monitoring: dashboards, alerting, uptime checks
# ─────────────────────────────────────────────────────────────────

locals {
  gke_cluster_id = "projects/${var.project_id}/locations/${var.zone}/clusters/${var.gke_cluster_name}"
}

# ─────────────────────────────────────────────────────────────────
# Notification channels
# ─────────────────────────────────────────────────────────────────

resource "google_monitoring_notification_channel" "email_ops" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream Ops Email"
  type         = "email"

  labels = {
    email_address = var.alert_email
  }
}

# ─────────────────────────────────────────────────────────────────
# Alerting policies
# ─────────────────────────────────────────────────────────────────

resource "google_monitoring_alert_policy" "pod_crash_loop" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: Pod CrashLoopBackOff or OOM"
  combiner     = "OR"

  conditions {
    display_name = "Pod restart rate high (crash loop)"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/container/restart_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 3
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  conditions {
    display_name = "OOMKilled container"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/container/memory/used_bytes\" AND metric.labels.memory_type=\"non-evictable\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1800000000 # 1.8 GB — near limit for typical 2 GB containers
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "A GKE pod is crash-looping or approaching OOM. Check `kubectl logs` and `kubectl describe pod` in the hydrastream namespace."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "high_5xx_error_rate" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: High 5xx Error Rate (>1%)"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run 5xx error rate > 1%"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"flink-proxy-gateway\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      duration        = "120s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.labels.service_name"]
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "Flink Proxy Gateway is returning >1% 5xx responses. Check Cloud Run logs and Flink SQL Gateway connectivity."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "flink_job_failure" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: Flink Job Failure or Checkpoint Failure"
  combiner     = "OR"

  conditions {
    display_name = "Flink JobManager pod restarted"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND resource.labels.container_name=\"flink-jobmanager\" AND metric.type=\"kubernetes.io/container/restart_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
      }
    }
  }

  conditions {
    display_name = "Flink checkpoint failure (log-based)"
    condition_threshold {
      filter          = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"logging.googleapis.com/user/flink_checkpoint_failure\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "A Flink job has failed or checkpointing has stopped. Check Flink JobManager logs and GCS checkpoint bucket."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "cloudsql_connection_exhaustion" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: Cloud SQL Connection Pool Near Exhaustion"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL connections > 80% of max"
    condition_threshold {
      filter          = "resource.type=\"cloudsql_database\" AND resource.labels.database_id=~\"${var.project_id}:.*\" AND metric.type=\"cloudsql.googleapis.com/database/postgresql/num_backends\""
      comparison      = "COMPARISON_GT"
      threshold_value = 80
      duration        = "120s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "Cloud SQL connection count is high. Check application connection pooling settings and query latency."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "gke_node_resource_pressure" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: GKE Node CPU/Memory/Disk Threshold Breach"
  combiner     = "OR"

  conditions {
    display_name = "Node CPU utilization > 85%"
    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/node/cpu/allocatable_utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  conditions {
    display_name = "Node memory utilization > 85%"
    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/node/memory/allocatable_utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  conditions {
    display_name = "Node disk usage > 80%"
    condition_threshold {
      filter          = "resource.type=\"k8s_node\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/node/ephemeral_storage/used_bytes\""
      comparison      = "COMPARISON_GT"
      threshold_value = 42949672960 # 40 GB — 80% of 50 GB node disk
      duration        = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "A GKE node is under CPU/memory/disk pressure. Consider scaling up the node pool."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "ssl_cert_expiry" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: SSL Certificate Expiring Within 30 Days"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check SSL cert expiry < 30 days"
    condition_threshold {
      filter          = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/time_until_ssl_cert_expires\""
      comparison      = "COMPARISON_LT"
      threshold_value = 30
      duration        = "600s"
      aggregations {
        alignment_period   = "600s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "An SSL certificate used by HydraStream expires within 30 days. Renew immediately."
    mime_type = "text/markdown"
  }
}

# ─────────────────────────────────────────────────────────────────
# Uptime checks
# ─────────────────────────────────────────────────────────────────

resource "google_monitoring_uptime_check_config" "frontend" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream Frontend"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.frontend_domain
    }
  }
}

resource "google_monitoring_uptime_check_config" "api_health" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream API Health Endpoint"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true

    accepted_response_status_codes {
      status_class = "STATUS_CLASS_2XX"
    }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = var.api_domain
    }
  }
}

resource "google_monitoring_alert_policy" "uptime_check_failure" {
  count = local.minisky == null ? 1 : 0
  display_name = "HydraStream: Uptime Check Failing"
  combiner     = "OR"

  conditions {
    display_name = "Uptime check failing from multiple regions"
    condition_threshold {
      filter          = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "120s"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.labels.*"]
      }
    }
  }

  notification_channels = length(google_monitoring_notification_channel.email_ops) > 0 ? [google_monitoring_notification_channel.email_ops[0].name] : []

  alert_strategy {
    auto_close = "604800s"
  }

  documentation {
    content   = "An uptime check for HydraStream is failing. Verify service availability and DNS/SSL configuration."
    mime_type = "text/markdown"
  }
}

# ─────────────────────────────────────────────────────────────────
# Dashboards
# ─────────────────────────────────────────────────────────────────

resource "google_monitoring_dashboard" "gke_cluster_health" {
  count = local.minisky == null ? 1 : 0
  dashboard_json = jsonencode({
    displayName = "HydraStream — GKE Cluster Health"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Node CPU Allocatable Utilization"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_node\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/node/cpu/allocatable_utilization\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["resource.labels.node_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Node Memory Allocatable Utilization"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_node\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/node/memory/allocatable_utilization\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["resource.labels.node_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Container Restart Count (Crash Loops)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/container/restart_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.labels.container_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Container Memory Usage"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND metric.type=\"kubernetes.io/container/memory/used_bytes\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["resource.labels.container_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}

resource "google_monitoring_dashboard" "application_metrics" {
  count = local.minisky == null ? 1 : 0
  dashboard_json = jsonencode({
    displayName = "HydraStream — Application Metrics"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — Request Latency (p50/p95/p99)"
            xyChart = {
              dataSets = [
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"flink-proxy-gateway\" AND metric.type=\"run.googleapis.com/request_latencies\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_50"
                        crossSeriesReducer = "REDUCE_MEAN"
                      }
                    }
                  }
                  legendTemplate = "p50"
                  plotType       = "LINE"
                },
                {
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"flink-proxy-gateway\" AND metric.type=\"run.googleapis.com/request_latencies\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_95"
                        crossSeriesReducer = "REDUCE_MEAN"
                      }
                    }
                  }
                  legendTemplate = "p95"
                  plotType       = "LINE"
                }
              ]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — Request Rate by Response Code Class"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"flink-proxy-gateway\" AND metric.type=\"run.googleapis.com/request_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.labels.response_code_class"]
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run — Active Instances"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"flink-proxy-gateway\" AND metric.type=\"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Application Error Rate (log-based)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/hydrastream_app_errors\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_RATE"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}

resource "google_monitoring_dashboard" "flink_metrics" {
  count = local.minisky == null ? 1 : 0
  dashboard_json = jsonencode({
    displayName = "HydraStream — Flink Job Metrics"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Flink Container CPU Usage"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND (resource.labels.container_name=\"flink-jobmanager\" OR resource.labels.container_name=\"flink-taskmanager\") AND metric.type=\"kubernetes.io/container/cpu/request_utilization\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["resource.labels.container_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Flink Container Memory Usage"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"k8s_container\" AND resource.labels.cluster_name=\"${var.gke_cluster_name}\" AND (resource.labels.container_name=\"flink-jobmanager\" OR resource.labels.container_name=\"flink-taskmanager\") AND metric.type=\"kubernetes.io/container/memory/used_bytes\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["resource.labels.container_name"]
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Flink Checkpoint Failures (log-based)"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/flink_checkpoint_failure\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_SUM"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
                plotType = "STACKED_BAR"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "GCS Checkpoint Bucket — Object Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"gcs_bucket\" AND resource.labels.bucket_name=\"${var.project_id}-${var.flink_checkpoint_bucket}\" AND metric.type=\"storage.googleapis.com/storage/object_count\""
                    aggregation = {
                      alignmentPeriod    = "3600s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}

resource "google_monitoring_dashboard" "database_metrics" {
  count = local.minisky == null ? 1 : 0
  dashboard_json = jsonencode({
    displayName = "HydraStream — Database and Cache Metrics"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Cloud SQL — Active Connections"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/postgresql/num_backends\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Cloud SQL — Query Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/postgresql/insights/aggregate/latencies\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_99"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Cloud SQL — Disk Usage"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/disk/bytes_used\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 4
          width  = 6
          height = 4
          widget = {
            title = "Memorystore Redis — Memory Usage"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"redis_instance\" AND metric.type=\"redis.googleapis.com/stats/memory/usage_ratio\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        },
        {
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Memorystore Redis — Cache Hit Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"redis_instance\" AND metric.type=\"redis.googleapis.com/stats/cache_hit_ratio\""
                    aggregation = {
                      alignmentPeriod    = "60s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
                plotType = "LINE"
              }]
              yAxis = { scale = "LINEAR" }
            }
          }
        }
      ]
    }
  })
}
