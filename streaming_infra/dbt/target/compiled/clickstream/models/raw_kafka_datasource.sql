-- Licensed under the Apache License, Version 2.0 (the "License");
-- you may not use this file except in compliance with the License.
-- You may obtain a copy of the License at
--
--     http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS,
-- WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
-- See the License for the specific language governing permissions and
-- limitations under the License.

-- example_source.sql


-- Define your source schema here according to what your Kafka topic produces.
-- This uses Flink SQL DDL syntax.
user_id STRING,
event_type STRING,
session_id STRING,
`timestamp` STRING,
-- Add a conceptual event_time field extracted from a timestamp to handle windowing
event_time AS TO_TIMESTAMP(REPLACE(REPLACE(`timestamp`, 'T', ' '), 'Z', '')),
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND