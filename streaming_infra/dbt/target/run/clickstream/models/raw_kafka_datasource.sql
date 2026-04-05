CREATE TABLE `default_catalog`.`default_database`.`raw_kafka_datasource`
    ( -- example_source.sql


-- Define your source schema here according to what your Kafka topic produces.
-- This uses Flink SQL DDL syntax.
user_id STRING,
event_type STRING,
session_id STRING,
`timestamp` STRING,
-- Add a conceptual event_time field extracted from a timestamp to handle windowing
event_time AS TO_TIMESTAMP(REPLACE(REPLACE(`timestamp`, 'T', ' '), 'Z', '')),
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND)
    WITH (
      'connector' = 'kafka', 'topic' = 'clickstream', 'properties.bootstrap.servers' = 'kafka:29092', 'properties.group.id' = 'flink-consumer-group', 'scan.startup.mode' = 'earliest-offset', 'format' = 'json')