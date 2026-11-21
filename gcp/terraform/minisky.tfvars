# ─────────────────────────────────────────────────────────────────
# MiniSky local overrides — use this file when running against the
# local GCP emulator instead of real GCP.
#
# Usage:
#   terraform init
#   terraform apply -var-file="minisky.tfvars"
# ─────────────────────────────────────────────────────────────────

project_id       = "hydrastream-local"
region           = "us-central1"
zone             = "us-central1-a"

# MiniSky API gateway — routes all GCP API calls to local emulators
minisky_endpoint = "http://localhost:2080"

# Smaller resources for local testing
gke_node_count   = 1
gke_machine_type = "e2-standard-2"

# Point to the local GitHub repo (Cloud Build pulls from GitHub via PAT)
github_repo      = "qamarudeenm/agent_company_bluemoon"

# Monitoring
alert_email      = "ops@hydrastream.io"
frontend_domain  = "app.hydrastream.io"
api_domain       = "api.hydrastream.io"
