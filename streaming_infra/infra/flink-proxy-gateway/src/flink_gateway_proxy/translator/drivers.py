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

"""On-demand JDBC driver management."""

import logging
import re
from typing import Set

logger = logging.getLogger(__name__)

# Registry of known drivers and their download URLs
DRIVER_REGISTRY = {
    "com.mysql.jdbc.Driver": "https://repo.maven.apache.org/maven2/mysql/mysql-connector-java/5.1.49/mysql-connector-java-5.1.49.jar",
    "com.mysql.cj.jdbc.Driver": "https://repo.maven.apache.org/maven2/mysql/mysql-connector-java/8.0.33/mysql-connector-java-8.0.33.jar",
    "org.postgresql.Driver": "https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.2/postgresql-42.7.2.jar",
    "com.clickhouse.jdbc.ClickHouseDriver": "https://repo1.maven.org/maven2/com/clickhouse/clickhouse-jdbc/0.6.3/clickhouse-jdbc-0.6.3-all.jar",
    "net.snowflake.client.jdbc.SnowflakeDriver": "https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/3.16.0/snowflake-jdbc-3.16.0.jar",
}

def detect_required_drivers(sql: str) -> Set[str]:
    """Detect required JDBC drivers from a SQL statement.

    Args:
        sql: SQL statement text

    Returns:
        Set of driver URLs that need to be added
    """
    required_urls = set()
    
    # 1. Look for 'driver' = '...' in WITH clause
    driver_matches = re.findall(r"['\"]driver['\"]\s*=\s*['\"]([^'\"]+)['\"]", sql, re.IGNORECASE)
    
    for driver_class in driver_matches:
        if driver_class in DRIVER_REGISTRY:
            required_urls.add(DRIVER_REGISTRY[driver_class])
            logger.info(f"Detected required driver {driver_class}, mapping to {DRIVER_REGISTRY[driver_class]}")

    # 2. Fallback: Look for 'url' = 'jdbc:...' to infer driver if not explicitly specified
    # Only do this if no driver was explicitly specified, or to be safe, always check
    url_matches = re.findall(r"['\"]url['\"]\s*=\s*['\"]jdbc:([^:']+):", sql, re.IGNORECASE)
    for protocol in url_matches:
        protocol = protocol.lower()
        if protocol == "mysql" and DRIVER_REGISTRY["com.mysql.jdbc.Driver"] not in required_urls:
            required_urls.add(DRIVER_REGISTRY["com.mysql.jdbc.Driver"])
            logger.info("Inferred MySQL driver from JDBC URL")
        elif protocol == "postgresql" and DRIVER_REGISTRY["org.postgresql.Driver"] not in required_urls:
            required_urls.add(DRIVER_REGISTRY["org.postgresql.Driver"])
            logger.info("Inferred PostgreSQL driver from JDBC URL")
        elif protocol == "clickhouse" and DRIVER_REGISTRY["com.clickhouse.jdbc.ClickHouseDriver"] not in required_urls:
            required_urls.add(DRIVER_REGISTRY["com.clickhouse.jdbc.ClickHouseDriver"])
            logger.info("Inferred ClickHouse driver from JDBC URL")
        elif protocol == "snowflake" and DRIVER_REGISTRY["net.snowflake.client.jdbc.SnowflakeDriver"] not in required_urls:
            required_urls.add(DRIVER_REGISTRY["net.snowflake.client.jdbc.SnowflakeDriver"])
            logger.info("Inferred Snowflake driver from JDBC URL")
            
    return required_urls
