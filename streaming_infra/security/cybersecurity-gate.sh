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

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$ROOT_DIR/.." && pwd)"

pass_count=0
warn_count=0
fail_count=0

passes=()
warnings=()
failures=()

add_pass() {
  passes+=("$1")
  pass_count=$((pass_count + 1))
}

add_warn() {
  warnings+=("$1")
  warn_count=$((warn_count + 1))
}

add_fail() {
  failures+=("$1")
  fail_count=$((fail_count + 1))
}

contains() {
  local file="$1"
  local pattern="$2"
  rg -q --fixed-strings "$pattern" "$file"
}

check_file_exists() {
  local file="$1"
  local control_name="$2"
  if [[ ! -f "$file" ]]; then
    add_fail "$control_name: missing required file $file"
    return 1
  fi
  return 0
}

k8s_configmap="$ROOT_DIR/infra/flink-proxy-gateway/deploy/kubernetes/configmap.yaml"
chart_values="$ROOT_DIR/charts/hydrastream-tenant/values.yaml"
chart_proxy_template="$ROOT_DIR/charts/hydrastream-tenant/templates/proxy-gateway.yaml"
k8s_proxy_deploy="$ROOT_DIR/infra/flink-proxy-gateway/deploy/kubernetes/deployment.yaml"
example_env="$ROOT_DIR/example.env"

# 1) Authentication must be enabled for deployed proxy endpoints.
if check_file_exists "$k8s_configmap" "proxy-auth-config"; then
  if contains "$k8s_configmap" 'PROXY_AUTH_MODE: "oidc_jwt"'; then
    add_pass "proxy-auth-config: Kubernetes proxy ConfigMap enforces OIDC JWT auth mode"
  else
    add_fail "proxy-auth-config: Kubernetes proxy ConfigMap does not enforce OIDC JWT auth mode"
  fi
fi

if check_file_exists "$chart_proxy_template" "proxy-auth-chart-template"; then
  if contains "$chart_proxy_template" 'name: PROXY_AUTH_MODE'; then
    add_pass "proxy-auth-chart-template: Helm template wires PROXY_AUTH_MODE into proxy container"
  else
    add_fail "proxy-auth-chart-template: Helm template is missing PROXY_AUTH_MODE env var"
  fi
fi

if check_file_exists "$chart_values" "proxy-auth-values"; then
  if contains "$chart_values" 'mode: oidc_jwt'; then
    add_pass "proxy-auth-values: Helm defaults require OIDC JWT mode"
  else
    add_fail "proxy-auth-values: Helm defaults still allow passthrough auth"
  fi
fi

# 2) Runtime hardening on proxy pods.
if check_file_exists "$chart_proxy_template" "proxy-security-context-template"; then
  if contains "$chart_proxy_template" 'securityContext:' && contains "$chart_proxy_template" '.Values.proxy.securityContext'; then
    add_pass "proxy-security-context-template: Helm template applies proxy container security context"
  else
    add_fail "proxy-security-context-template: Helm template does not apply proxy container security context"
  fi
fi

if check_file_exists "$k8s_proxy_deploy" "proxy-security-context-k8s"; then
  if contains "$k8s_proxy_deploy" 'runAsNonRoot: true' \
    && contains "$k8s_proxy_deploy" 'allowPrivilegeEscalation: false' \
    && contains "$k8s_proxy_deploy" 'readOnlyRootFilesystem: true'; then
    add_pass "proxy-security-context-k8s: Kubernetes deployment enforces non-root and read-only runtime"
  else
    add_fail "proxy-security-context-k8s: Kubernetes deployment misses one or more runtime hardening controls"
  fi
fi

# 3) Secret hygiene.
if check_file_exists "$chart_values" "clickhouse-secret-hygiene-values"; then
  if contains "$chart_values" 'password: "password"'; then
    add_fail "clickhouse-secret-hygiene-values: Helm values contain default password"
  else
    add_pass "clickhouse-secret-hygiene-values: Helm values no longer ship with default password"
  fi
fi

if check_file_exists "$example_env" "clickhouse-secret-hygiene-example-env"; then
  if rg -q 'CLICKHOUSE_PASSWORD=(12345|password|changeme)$' "$example_env"; then
    add_fail "clickhouse-secret-hygiene-example-env: example.env contains weak sample password"
  else
    add_pass "clickhouse-secret-hygiene-example-env: example.env avoids weak sample passwords"
  fi
fi

# 4) Informational checks.
if check_file_exists "$chart_values" "proxy-image-tag"; then
  if contains "$chart_values" 'tag: "proxy-latest"'; then
    add_warn "proxy-image-tag: proxy image uses mutable tag proxy-latest; pin immutable version before production"
  else
    add_pass "proxy-image-tag: proxy image tag appears pinned"
  fi
fi

echo "# HydraStream Cybersecurity Gate"
echo
echo "Target: streaming_infra"
echo "Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo
echo "## Verdict"
if [[ "$fail_count" -eq 0 ]]; then
  echo "PASS - release readiness criteria satisfied (${pass_count} controls passed, ${warn_count} warnings)."
else
  echo "FAIL - release readiness blocked (${fail_count} failed, ${pass_count} passed, ${warn_count} warnings)."
fi

echo
echo "## Passed Controls"
if [[ "${#passes[@]}" -eq 0 ]]; then
  echo "- None"
else
  for item in "${passes[@]}"; do
    echo "- $item"
  done
fi

echo
echo "## Warnings"
if [[ "${#warnings[@]}" -eq 0 ]]; then
  echo "- None"
else
  for item in "${warnings[@]}"; do
    echo "- $item"
  done
fi

echo
echo "## Failed Controls"
if [[ "${#failures[@]}" -eq 0 ]]; then
  echo "- None"
else
  for item in "${failures[@]}"; do
    echo "- $item"
  done
fi

if [[ "$fail_count" -ne 0 ]]; then
  exit 1
fi
