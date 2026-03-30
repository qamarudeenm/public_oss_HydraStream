#!/bin/bash

# ==============================================================================
# Local Dependencies Startup Script
# ==============================================================================
# This script checks if required local services (ClickHouse and Flink)
# are running and starts them if they are not.
#
# Services managed:
#   1. ClickHouse (systemd)
#   2. Flink Cluster (JobManager + TaskManager)
#   3. Flink SQL Gateway
# ==============================================================================

FLINK_BIN="/home/blueberry/flink-2.1.0/bin"

echo "--- Checking Local Dependencies ---"

# 1. ClickHouse Check
echo "[1/3] Checking ClickHouse..."
if systemctl is-active clickhouse-server >/dev/null 2>&1; then
    echo "✔ ClickHouse is already running."
else
    echo "✘ ClickHouse is NOT running. Starting it..."
    sudo systemctl start clickhouse-server
    if [ $? -eq 0 ]; then
        echo "✔ ClickHouse started successfully."
    else
        echo "✖ Failed to start ClickHouse. Check 'systemctl status clickhouse-server'."
    fi
fi

# 2. Flink Cluster Check
echo "[2/3] Checking Flink Cluster (JobManager)..."
if ps aux | grep -v grep | grep "org.apache.flink.runtime.entrypoint.StandaloneSessionClusterEntrypoint" >/dev/null 2>&1; then
    echo "✔ Flink JobManager is already running."
else
    echo "✘ Flink JobManager is NOT running. Starting cluster..."
    ${FLINK_BIN}/start-cluster.sh
    if [ $? -eq 0 ]; then
        echo "✔ Flink Cluster started (JobManager & TaskManager)."
    else
        echo "✖ Failed to start Flink Cluster."
    fi
fi

# 3. Flink SQL Gateway Check
echo "[3/3] Checking Flink SQL Gateway..."
# Using ps to check for SqlGateway class
if ps aux | grep -v grep | grep "org.apache.flink.table.gateway.SqlGateway" >/dev/null 2>&1; then
    echo "✔ Flink SQL Gateway is already running."
else
    echo "✘ Flink SQL Gateway is NOT running. Starting..."
    # Starting standard gateway (defaults to port 8083)
    ${FLINK_BIN}/sql-gateway.sh start
    if [ $? -eq 0 ]; then
        echo "✔ Flink SQL Gateway started (Session management enabled)."
    else
        echo "✖ Failed to start Flink SQL Gateway."
    fi
fi

echo "-----------------------------------"
echo "All local dependencies verified."
echo "Access Flink Dashboard: http://localhost:8081"
echo "Access SQL Gateway:    http://localhost:8083"
echo "-----------------------------------"
