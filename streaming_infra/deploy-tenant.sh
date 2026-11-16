#!/bin/bash

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

# Script to deploy a HydraStream tenant using Helm

TENANT_ID=${1:-tenant-1}
NAMESPACE=${2:-$TENANT_ID}
# Proxy image tag must be a git-SHA-based tag, e.g. proxy-abc1234 (see docs/image-tagging.md).
PROXY_IMAGE_TAG=${3:-""}

if [[ -z "$PROXY_IMAGE_TAG" ]]; then
  echo "ERROR: PROXY_IMAGE_TAG is required. Pass the git-SHA tag as the third argument."
  echo "Usage: $0 <tenant-id> <namespace> <proxy-image-tag>"
  echo "Example: $0 tenant-1 tenant-1 proxy-abc1234"
  exit 1
fi

echo "Deploying tenant $TENANT_ID to namespace $NAMESPACE (proxy tag: $PROXY_IMAGE_TAG)..."

# Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Install the tenant chart
helm install $TENANT_ID ./charts/hydrastream-tenant \
    --namespace $NAMESPACE \
    --set flink.jobManager.replicaCount=1 \
    --set flink.taskManager.replicaCount=2 \
    --set kafka.bootstrapServers="hydrastream-infra-kafka.default:9092" \
    --set proxy.image.tag="$PROXY_IMAGE_TAG"

echo "Tenant $TENANT_ID deployed successfully!"
