#!/usr/bin/env bash
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Local equivalent of the GitHub Actions "Quality Gates" workflow.
# Runs all quality checks directly on this machine — no GitHub Actions credits required.
#
# Usage:
#   ./scripts/run-quality-gates.sh              # run all gates
#   ./scripts/run-quality-gates.sh hygiene       # repository hygiene only
#   ./scripts/run-quality-gates.sh proxy         # flink proxy lint + unit tests only
#   ./scripts/run-quality-gates.sh frontend      # frontend lint only
#   ./scripts/run-quality-gates.sh security      # cybersecurity gate only

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE="${1:-all}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}==> $*${NC}"; }

# ── 1. Repository Hygiene ─────────────────────────────────────────────────────
gate_hygiene() {
  header "Repository Hygiene"
  tracked_artifacts="$(git -C "$REPO_DIR" ls-files \
    'streaming_infra/dbt/target/**' \
    'streaming_infra/dbt/logs/**' 2>/dev/null || true)"
  if [ -n "$tracked_artifacts" ]; then
    echo "Tracked dbt artifacts detected:"
    echo "$tracked_artifacts"
    fail "Generated dbt artifacts must not be tracked in git"
  fi
  pass "No tracked dbt artifacts found"
}

# ── 2. Flink Proxy Quality ────────────────────────────────────────────────────
gate_proxy() {
  header "Flink Proxy Quality (lint + unit tests)"
  PROXY_DIR="$REPO_DIR/streaming_infra/infra/flink-proxy-gateway"

  if ! command -v uv &>/dev/null; then
    fail "'uv' not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
  fi

  (
    cd "$PROXY_DIR"
    echo "Installing dependencies..."
    uv sync --all-extras

    echo "Running lint and type check..."
    make lint

    echo "Running unit tests..."
    make test-unit
  )
  pass "Flink proxy quality checks passed"
}

# ── 3. Frontend Lint ──────────────────────────────────────────────────────────
gate_frontend() {
  header "Frontend Lint"
  FRONTEND_DIR="$REPO_DIR/control_plane/frontend"

  if ! command -v node &>/dev/null; then
    fail "'node' not found. Install Node.js 22+: https://nodejs.org"
  fi

  (
    cd "$FRONTEND_DIR"
    echo "Installing npm dependencies..."
    npm ci

    echo "Running ESLint..."
    npm run lint
  )
  pass "Frontend lint passed"
}

# ── 4. Cybersecurity Gate ─────────────────────────────────────────────────────
gate_security() {
  header "Cybersecurity Release Gate"

  if ! command -v rg &>/dev/null; then
    echo -e "${YELLOW}[INFO]${NC} ripgrep not found, attempting install via apt..."
    sudo apt-get update -qq && sudo apt-get install -y ripgrep
  fi

  "$REPO_DIR/streaming_infra/security/cybersecurity-gate.sh"
  pass "Cybersecurity gate passed"
}

# ── Run gates ─────────────────────────────────────────────────────────────────
echo -e "${BOLD}HydraStream Quality Gates — local run${NC}"
echo "Repo: $REPO_DIR"
echo "Gate: $GATE"

case "$GATE" in
  hygiene)  gate_hygiene ;;
  proxy)    gate_proxy ;;
  frontend) gate_frontend ;;
  security) gate_security ;;
  all)
    gate_hygiene
    gate_proxy
    gate_frontend
    gate_security
    ;;
  *)
    echo "Unknown gate: $GATE"
    echo "Valid options: all | hygiene | proxy | frontend | security"
    exit 1
    ;;
esac

echo -e "\n${GREEN}${BOLD}All quality gates passed.${NC}"
