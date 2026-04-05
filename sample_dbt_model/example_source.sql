-- example_source.sql
{{ config(
    materialized='streaming_source',
    connector='kafka',
    with={
        'topic': env_var('KAFKA_TOPIC', 'your_topic_here'),
        'properties.bootstrap.servers': env_var('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092'),
        'properties.group.id': env_var('KAFKA_GROUP_ID', 'flink-consumer-group'),
        'scan.startup.mode': 'earliest-offset',
        'format': 'json'
    }
) }}

-- Define your source schema here according to what your Kafka topic produces.
-- This uses Flink SQL DDL syntax.
event_type STRING,
session_id STRING,
`timestamp` STRING,
-- Add a conceptual event_time field extracted from a timestamp to handle windowing
event_time AS TO_TIMESTAMP(REPLACE(REPLACE(`timestamp`, 'T', ' '), 'Z', '')),
WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
