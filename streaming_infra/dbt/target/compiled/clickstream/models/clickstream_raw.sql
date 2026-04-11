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



event_type STRING,
page_url STRING,
user_id STRING,
session_id STRING,
element_id STRING,
element_text STRING,
product_id STRING,
`data` MAP<STRING, STRING>,
`timestamp` STRING,
event_time AS TO_TIMESTAMP(REPLACE(REPLACE(`timestamp`, 'T', ' '), 'Z', '')),
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND