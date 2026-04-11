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

create table `default_catalog`.`default_database`.`transformed_clickstream_metrics`
    
    
  
  
  
  
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
  
  (`user_id` STRING,
    `event_type` STRING,
    `session_id` STRING,
    `event_count` BIGINT,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3))

    
    WITH ('connector' = 'jdbc','url' = 'jdbc:mysql://host.docker.internal:9004/clickstream','table-name' = 'transformed_clickstream_metrics','driver' = 'com.mysql.jdbc.Driver','username' = 'flink_user','password' = '12345')
    