#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

REPO="blue2berry/hydrastream"
FLINK_VERSION="flink1.19.1"
VERSION="latest"

PUSH=false
SCAN=false

for arg in "$@"; do
  case $arg in
    --push)
      PUSH=true
      shift
      ;;
    --scan)
      SCAN=true
      shift
      ;;
    *)
      ;;
  esac
done

echo "🌊 HydraStream - Local Build Script"
echo "-----------------------------------------"
echo "Repository : $REPO"
echo "Version Tag: $VERSION"
echo "Push       : $PUSH"
echo "Scan       : $SCAN"
echo "-----------------------------------------"

# 1. Build: Flink Engine
echo "🚀 Building Engine Image..."
docker build -t "$REPO:engine-$FLINK_VERSION" -t "$REPO:engine-$VERSION" -f streaming_infra/flink/Dockerfile streaming_infra/flink

if [ "$SCAN" = true ]; then
  echo "🔍 Scanning Engine Image..."
  docker scout quickview "$REPO:engine-$VERSION"
fi

if [ "$PUSH" = true ]; then
  echo "📤 Pushing Engine Image..."
  docker push "$REPO:engine-$FLINK_VERSION"
  docker push "$REPO:engine-$VERSION"
fi

# 2. Build: Flink Proxy Gateway
echo "🚀 Building Proxy Gateway Image..."
docker build -t "$REPO:proxy-$VERSION" -f streaming_infra/infra/flink-proxy-gateway/Dockerfile streaming_infra/infra/flink-proxy-gateway

if [ "$SCAN" = true ]; then
  echo "🔍 Scanning Proxy Gateway Image..."
  docker scout quickview "$REPO:proxy-$VERSION"
fi

if [ "$PUSH" = true ]; then
  echo "📤 Pushing Proxy Gateway Image..."
  docker push "$REPO:proxy-$VERSION"
fi

# 3. Build: dbt Worker
echo "🚀 Building dbt Worker Image..."
docker build -t "$REPO:dbt-$VERSION" -f streaming_infra/dbt/Dockerfile streaming_infra/dbt

if [ "$SCAN" = true ]; then
  echo "🔍 Scanning dbt Worker Image..."
  docker scout quickview "$REPO:dbt-$VERSION"
fi

if [ "$PUSH" = true ]; then
  echo "📤 Pushing dbt Worker Image..."
  docker push "$REPO:dbt-$VERSION"
fi

echo "✅ All requested operations completed successfully for $REPO!"
