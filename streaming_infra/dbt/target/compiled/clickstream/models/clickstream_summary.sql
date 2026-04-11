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



SELECT 
    event_type,
    session_id,
    COALESCE(product_id, `data`['product_id']) as product_id,
    COUNT(*) as event_count,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE `default_catalog`.`default_database`.`clickstream_raw`, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
GROUP BY event_type, session_id, COALESCE(product_id, `data`['product_id']), window_start, window_end