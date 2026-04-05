create table `default_catalog`.`default_database`.`clickstream_summary`
    
    
  
  
  
  
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
  
  (`event_type` STRING,
    `session_id` STRING,
    `product_id` STRING,
    `event_count` BIGINT,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3))

    
    WITH ('connector' = 'jdbc','url' = 'jdbc:mysql://host.docker.internal:9004/clickstream','table-name' = 'clickstream_summary','driver' = 'com.mysql.jdbc.Driver','username' = 'flink_user','password' = '12345')
    