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

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install dbt and confluent adapter
RUN pip install --no-cache-dir \
    dbt-core \
    dbt-confluent

# Patch the dbt-confluent adapter to accept our local proxy endpoint
# (By default it ignores custom hosts and hardcodes https://*.confluent.cloud)
RUN sed -i 's/cloud_provider=credentials.cloud_provider,//' /usr/local/lib/python3.11/site-packages/dbt/adapters/confluent/connections.py
RUN sed -i 's/cloud_region=credentials.cloud_region,/endpoint="http:\/\/flink-proxy-gateway:8080",/' /usr/local/lib/python3.11/site-packages/dbt/adapters/confluent/connections.py
RUN sed -i 's/httpx.Client(/httpx.Client(timeout=httpx.Timeout(300.0, connect=30.0), /g' /usr/local/lib/python3.11/site-packages/confluent_sql/connection.py

# Copy the dbt project and profiles
COPY . /app/

# Default command: keep container alive or run dbt
CMD ["tail", "-f", "/dev/null"]
