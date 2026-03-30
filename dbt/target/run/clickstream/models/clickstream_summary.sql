create table `default_catalog`.`default_database`.`clickstream_summary`
    
    
  
  
  
  
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
      
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
    
    
    
    
    
  
  
  (`event_type` STRING,
    `session_id` STRING,
    `product_id` STRING,
    `event_count` BIGINT,
    `window_start` TIMESTAMP(3),
    `window_end` TIMESTAMP(3))

    
    WITH ('password' = '12345pP','connector' = 'jdbc','table-name' = 'clickstream_analytics','url' = 'jdbc:postgresql://host.docker.internal:5414/postgres?currentSchema=clickstream','username' = 'data_eng','driver' = 'org.postgresql.Driver')
    