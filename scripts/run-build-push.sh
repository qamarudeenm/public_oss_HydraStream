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

# Local equivalent of the GitHub Actions "Build and Push Images" workflow.
# Builds all Docker images and optionally pushes them to Docker Hub.
# Runs entirely on this machine — no GitHub Actions credits required.
#
# Usage:
#   ./scripts/run-build-push.sh                  # build only (no push)
#   ./scripts/run-build-push.sh --push            # build + push to Docker Hub
#   ./scripts/run-build-push.sh --push --tag v1.2.3   # build + push with version tag
#
# Environment variables (required for --push):
#   DOCKERHUB_USERNAME  — Docker Hub account username
#   DOCKERHUB_TOKEN     — Docker Hub access token / password

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DOCKER_REPO="blue2berry/hydrastream"
FLINK_VERSION="flink1.19.1"
VERSION="latest"
PUSH=false

RED='\033[0;31m'
GREEN='\033[0;32m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
header() { echo -e "\n${BOLD}==> $*${NC}"; }

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)    PUSH=true; shift ;;
    --tag)     VERSION="$2"; shift 2 ;;
    *)         echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Preflight ─────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  fail "Docker is not installed or not in PATH."
fi

if $PUSH; then
  if [[ -z "${DOCKERHUB_USERNAME:-}" || -z "${DOCKERHUB_TOKEN:-}" ]]; then
    fail "DOCKERHUB_USERNAME and DOCKERHUB_TOKEN must be set to push images."
  fi
  echo "Logging in to Docker Hub as ${DOCKERHUB_USERNAME}..."
  echo "${DOCKERHUB_TOKEN}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin
fi

# Ensure buildx builder is available
docker buildx inspect local-builder &>/dev/null \
  || docker buildx create --name local-builder --use --bootstrap

echo -e "${BOLD}HydraStream — Build & Push Images — local run${NC}"
echo "Repo:    $DOCKER_REPO"
echo "Version: $VERSION"
echo "Push:    $PUSH"

# ── Build helper ──────────────────────────────────────────────────────────────
build_image() {
  local name="$1"
  local context="$2"
  local dockerfile="$3"
  shift 3
  local tags=("$@")

  header "Build: $name"
  local tag_args=()
  for t in "${tags[@]}"; do
    tag_args+=("--tag" "$t")
  done

  docker buildx build \
    --builder local-builder \
    --file "$REPO_DIR/$dockerfile" \
    "${tag_args[@]}" \
    $(if $PUSH; then echo "--push"; else echo "--load"; fi) \
    "$REPO_DIR/$context"

  pass "$name built successfully"
}

# ── 1. Flink Engine ───────────────────────────────────────────────────────────
build_image "Flink Engine" \
  "streaming_infra/flink" \
  "streaming_infra/flink/Dockerfile" \
  "${DOCKER_REPO}:engine-${FLINK_VERSION}" \
  "${DOCKER_REPO}:engine-${VERSION}"

# ── 2. Flink Proxy Gateway ────────────────────────────────────────────────────
build_image "Flink Proxy Gateway" \
  "streaming_infra/infra/flink-proxy-gateway" \
  "streaming_infra/infra/flink-proxy-gateway/Dockerfile" \
  "${DOCKER_REPO}:proxy-latest" \
  "${DOCKER_REPO}:proxy-${VERSION}"

# ── 3. dbt Worker ────────────────────────────────────────────────────────────
build_image "dbt Worker" \
  "streaming_infra/dbt" \
  "streaming_infra/dbt/Dockerfile" \
  "${DOCKER_REPO}:dbt-latest" \
  "${DOCKER_REPO}:dbt-${VERSION}"

# ── Summary ───────────────────────────────────────────────────────────────────
echo -e "\n${GREEN}${BOLD}HydraStream Images Built${if $PUSH; then echo " & Pushed"; fi}${NC}"
echo ""
echo "| Image       | Tags                                                          |"
echo "| :---------- | :------------------------------------------------------------ |"
echo "| Engine      | ${DOCKER_REPO}:engine-${FLINK_VERSION}, :engine-${VERSION}    |"
echo "| Proxy       | ${DOCKER_REPO}:proxy-latest, :proxy-${VERSION}                |"
echo "| dbt Worker  | ${DOCKER_REPO}:dbt-latest, :dbt-${VERSION}                    |"
if $PUSH; then
  echo ""
  echo "Published: https://hub.docker.com/r/blue2berry/hydrastream/tags"
fi
