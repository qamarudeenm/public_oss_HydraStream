# ─────────────────────────────────────────────────────────────────
# WI-3: Production Database Provisioning
# Cloud SQL PostgreSQL + Memorystore Redis + Secret Manager
#
# Note: Cloud SQL and Memorystore use real GCP APIs; they cannot be
# tested through MiniSky. Only provision against hydrastream-prod.
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# Required GCP APIs
# ─────────────────────────────────────────────────────────────────
resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking" {
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "redis" {
  service            = "redis.googleapis.com"
  disable_on_destroy = false
}

# google_project_service.secretmanager is declared in main.tf with a MiniSky count guard.

# ─────────────────────────────────────────────────────────────────
# VPC Private Service Access
# Allocates a /20 block from hydrastream-vpc for Google-managed
# services (Cloud SQL private IP, Memorystore).
# ─────────────────────────────────────────────────────────────────
resource "google_compute_global_address" "private_service_access" {
  name          = "hydrastream-private-service-access"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.hydrastream_vpc.id

  depends_on = [google_project_service.servicenetworking]
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.hydrastream_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access.name]

  depends_on = [google_project_service.servicenetworking]
}

# ─────────────────────────────────────────────────────────────────
# Random passwords for database users
# ─────────────────────────────────────────────────────────────────
resource "random_password" "hydra_cp" {
  length  = 32
  special = false
}

resource "random_password" "hydra_sink" {
  length  = 32
  special = false
}

# ─────────────────────────────────────────────────────────────────
# Cloud SQL PostgreSQL 15 — REGIONAL HA, private IP only
# ─────────────────────────────────────────────────────────────────
resource "google_sql_database_instance" "hydrastream" {
  name             = var.cloudsql_instance_name
  database_version = "POSTGRES_15"
  region           = var.region

  # Keep deletion protection on; use `terraform destroy` with caution
  deletion_protection = true

  settings {
    tier              = var.cloudsql_tier
    availability_type = "REGIONAL"
    disk_autoresize   = true
    disk_autoresize_limit = 100
    disk_type         = "PD_SSD"
    disk_size         = 20

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.hydrastream_vpc.id
      require_ssl     = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    maintenance_window {
      day          = 7
      hour         = 3
      update_track = "stable"
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }

    insights_config {
      query_insights_enabled = true
      query_string_length    = 1024
    }
  }

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.sqladmin,
  ]
}

# Control-plane database — used by HydraStream API
resource "google_sql_database" "hydrastream_cp" {
  name     = "hydrastream"
  instance = google_sql_database_instance.hydrastream.name
}

# Flink sink database — Flink JDBC connector writes results here
resource "google_sql_database" "hydrastream_sink" {
  name     = "hydrastream_sink"
  instance = google_sql_database_instance.hydrastream.name
}

resource "google_sql_user" "hydra_cp" {
  name     = "hydra_cp"
  instance = google_sql_database_instance.hydrastream.name
  password = random_password.hydra_cp.result
}

resource "google_sql_user" "hydra_sink" {
  name     = "hydra_sink"
  instance = google_sql_database_instance.hydrastream.name
  password = random_password.hydra_sink.result
}

# ─────────────────────────────────────────────────────────────────
# Memorystore Redis 7 — STANDARD_HA for Flink Proxy state
# ─────────────────────────────────────────────────────────────────
resource "google_redis_instance" "hydrastream" {
  name           = var.redis_instance_name
  tier           = "STANDARD_HA"
  memory_size_gb = var.redis_memory_gb
  region         = var.region

  authorized_network = google_compute_network.hydrastream_vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  reserved_ip_range  = google_compute_global_address.private_service_access.name

  redis_version = "REDIS_7_0"
  display_name  = "HydraStream Flink Proxy State"

  persistence_config {
    persistence_mode    = "RDB"
    rdb_snapshot_period = "TWENTY_FOUR_HOURS"
  }

  maintenance_policy {
    weekly_maintenance_window {
      day = "SUNDAY"
      start_time {
        hours   = 3
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.redis,
  ]
}

# ─────────────────────────────────────────────────────────────────
# Secret Manager — store all database credentials
# ─────────────────────────────────────────────────────────────────
resource "google_secret_manager_secret" "cp_database_url" {
  secret_id = "hydrastream-cp-database-url"
  replication {
    auto {
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "cp_database_url" {
  secret = google_secret_manager_secret.cp_database_url.id
  secret_data = join("", [
    "postgresql+asyncpg://",
    google_sql_user.hydra_cp.name, ":",
    random_password.hydra_cp.result, "@",
    google_sql_database_instance.hydrastream.private_ip_address,
    ":5432/",
    google_sql_database.hydrastream_cp.name,
  ])
}

resource "google_secret_manager_secret" "sink_jdbc_url" {
  secret_id = "hydrastream-sink-jdbc-url"
  replication {
    auto {
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "sink_jdbc_url" {
  secret = google_secret_manager_secret.sink_jdbc_url.id
  secret_data = join("", [
    "jdbc:postgresql://",
    google_sql_database_instance.hydrastream.private_ip_address,
    ":5432/",
    google_sql_database.hydrastream_sink.name,
    "?user=", google_sql_user.hydra_sink.name,
    "&password=", random_password.hydra_sink.result,
    "&sslmode=require",
  ])
}

resource "google_secret_manager_secret" "redis_url" {
  secret_id = "hydrastream-redis-url"
  replication {
    auto {
    }
  }
  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "redis_url" {
  secret      = google_secret_manager_secret.redis_url.id
  secret_data = "redis://${google_redis_instance.hydrastream.host}:${google_redis_instance.hydrastream.port}"
}
