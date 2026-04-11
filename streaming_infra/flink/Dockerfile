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

FROM flink:1.19.1-scala_2.12-java11


# Flink now recommends installing Python into the base image yourself for PyFlink
# Switch to root user to install packages
USER root

RUN apt-get update -y && \
    apt-get install -y python3 python3-pip && \
    apt-get clean

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install the necessary python libraries
RUN pip3 install requests

# Fix permissions for Flink directories
RUN chown -R flink:flink /opt/flink && \
    chmod -R 755 /opt/flink

# Switch back to the non-privileged flink user
USER flink

# The connectors are large, so we download them during the build.
ARG FLINK_KAFKA_CONNECTOR_URL=https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.18/flink-sql-connector-kafka-3.1.0-1.18.jar
ARG FLINK_JDBC_CONNECTOR_URL=https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/3.2.0-1.19/flink-connector-jdbc-3.2.0-1.19.jar
# Download connectors into the Flink opt directory
RUN wget --no-check-certificate -P /opt/flink/lib/ ${FLINK_KAFKA_CONNECTOR_URL}
RUN wget --no-check-certificate -P /opt/flink/lib/ ${FLINK_JDBC_CONNECTOR_URL}

# Copy your Python job script into the container
COPY ./job /opt/flink/job

# Copy Flink configuration
COPY ./job/flink-conf.yaml /opt/flink/conf/flink-conf.yaml

# Copy the custom entrypoint script
COPY ./entrypoint.sh /entrypoint.sh
USER root
RUN chmod +x /entrypoint.sh
USER flink

# Fix permissions for the job directory
USER root
RUN chown -R flink:flink /opt/flink && \
    chmod -R 755 /opt/flink
USER flink

# Set the custom entrypoint
ENTRYPOINT ["/entrypoint.sh"]