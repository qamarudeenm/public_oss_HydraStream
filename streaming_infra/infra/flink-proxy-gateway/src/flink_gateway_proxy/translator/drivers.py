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
}

def detect_required_drivers(sql: str) -> Set[str]:
    """Detect required JDBC drivers from a SQL statement.

    Args:
        sql: SQL statement text

    Returns:
        Set of driver URLs that need to be added
    """
    required_urls = set()
    
    # Look for 'driver' = '...' in WITH clause
    # This is a naive regex-based search; it might need to be more robust for production
    driver_matches = re.findall(r"['\"]driver['\"]\s*=\s*['\"]([^'\"]+)['\"]", sql, re.IGNORECASE)
    
    for driver_class in driver_matches:
        if driver_class in DRIVER_REGISTRY:
            required_urls.add(DRIVER_REGISTRY[driver_class])
            logger.info(f"Detected required driver {driver_class}, mapping to {DRIVER_REGISTRY[driver_class]}")
            
    return required_urls
