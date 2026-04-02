#!/bin/bash

# ==============================================================================
# Local Dependencies Startup Script (Flink 2.1.0 + PostgreSQL)
# ==============================================================================
# This script checks if required local services (PostgreSQL and Flink)
# are running and starts them if they are not.
#
# Services managed:
#   1. PostgreSQL (systemd)
#   2. Flink Cluster (JobManager + TaskManager)
#   3. Flink SQL Gateway
# ==============================================================================

# Configuration
FLINK_DIR="/home/blueberry/flink-2.1.0"
POSTGRES_JAR="postgresql-42.7.3.jar"
JDBC_CONNECTOR="flink-connector-jdbc-4.0.0-2.0.jar"
KAFKA_CONNECTOR="flink-sql-connector-kafka-3.3.0-2.0.jar"
MAVEN_REPO="https://repo1.maven.org/maven2"

echo "--- Initializing Flink 2.1.0 Connectors ---"

# 1. Purge legacy connectors
echo "Cleaning up legacy connectors..."
rm -vf "$FLINK_DIR/lib/flink-connector-jdbc-3.2.0-1.19.jar" 2>/dev/null
rm -vf "$FLINK_DIR/lib/flink-sql-connector-clickhouse"* 2>/dev/null

# Centralized JAR Management
# ==============================================================================
# Usage: manage_jar <filename> <maven_subpath>
manage_jar() {
    local jar=$1
    local maven_path=$2
    local target="$FLINK_DIR/lib/$jar"

    # Step A: Check if already in target lib
    if [ -f "$target" ]; then
        echo "[SKIP] $jar already exists in Flink lib."
        return 0
    fi

    # Step B: Check project-local locations
    # (Current dir and project-specific flink/lib)
    for loc in "." "./flink/lib"; do
        if [ -f "$loc/$jar" ]; then
            echo "[LOCAL] Found $jar in $loc. Copying to Flink lib..."
            cp -v "$loc/$jar" "$target"
            return 0
        fi
    done

    # Step C: Download if Maven path provided
    if [ -n "$maven_path" ]; then
        echo "[REMOTE] Downloading $jar from Maven..."
        wget -q "$MAVEN_REPO/$maven_path" -P "$FLINK_DIR/lib/"
        return 0
    fi

    echo "Warning: $jar not found locally and no download path provided."
    return 1
}

echo "--- Checking Dependencies ---"

# 2. Manage PostgreSQL JDBC Driver
manage_jar "$POSTGRES_JAR" "org/postgresql/postgresql/42.7.3/postgresql-42.7.3.jar"

# 3. Manage JDBC Connector (Flink 2.0 compatible)
manage_jar "$JDBC_CONNECTOR" "org/apache/flink/flink-connector-jdbc/4.0.0-2.0/$JDBC_CONNECTOR"

# 4. Manage Kafka Connector (Flink 2.0 compatible)
manage_jar "$KAFKA_CONNECTOR" "org/apache/flink/flink-sql-connector-kafka/3.3.0-2.0/$KAFKA_CONNECTOR"

echo "--- Flink Cluster Management ---"

# Restart Flink Cluster
echo "Restarting Flink Cluster..."
"$FLINK_DIR/bin/stop-cluster.sh"
sleep 2
"$FLINK_DIR/bin/start-cluster.sh"

# Restart Flink SQL Gateway
echo "Restarting Flink SQL Gateway on port 8083..."
# Kill existing gateway if running
pkill -f "SqlGateway" || true
nohup "$FLINK_DIR/bin/sql-gateway.sh" start -Dsql-gateway.endpoint.rest.address=localhost -Dsql-gateway.endpoint.rest.port=8083 > "$FLINK_DIR/log/sql_gateway.out" 2>&1 &

echo "Flink services are starting. Check logs in $FLINK_DIR/log/"

# Ensure Postgres is running (host-based)
echo "Ensuring PostgreSQL is active..."
sudo systemctl start postgresql 2>/dev/null || echo "PostgreSQL service management might require manual intervention."

echo "--- Startup Sequence Complete ---"
