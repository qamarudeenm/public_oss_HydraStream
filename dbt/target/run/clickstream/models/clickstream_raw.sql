CREATE TABLE `default_catalog`.`default_database`.`clickstream_raw`
    ( 

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
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND)
    WITH (
      'connector' = 'kafka', 'scan.startup.mode' = 'latest-offset', 'properties.bootstrap.servers' = 'kafka:29092', 'topic' = 'clickstream', 'format' = 'json', 'properties.group.id' = 'clickstream-consumer-group')