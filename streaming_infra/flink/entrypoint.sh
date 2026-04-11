#!/bin/bash
set -e

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

# On-demand JDBC driver download at container startup
if [ -n "$MYSQL_JDBC_DRIVER_URL" ]; then
    # Only download if it doesn't already exist to avoid redundant downloads on restart
    DRIVER_FILENAME=$(basename "$MYSQL_JDBC_DRIVER_URL")
    if [ ! -f "/opt/flink/lib/$DRIVER_FILENAME" ]; then
        echo "Downloading MySQL JDBC driver from $MYSQL_JDBC_DRIVER_URL..."
        wget --no-check-certificate -P /opt/flink/lib/ "$MYSQL_JDBC_DRIVER_URL"
    else
        echo "MySQL JDBC driver already exists in /opt/flink/lib/, skipping download."
    fi
fi

# Execute the standard Flink entrypoint
exec /docker-entrypoint.sh "$@"
