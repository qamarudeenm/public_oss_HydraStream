{{ config(
    materialized='streaming_source',
    connector='kafka',
    with={
        'topic': 'clickstream',
        'properties.bootstrap.servers': 'kafka:29092',
        'properties.group.id': 'clickstream-consumer-group',
        'scan.startup.mode': 'earliest-offset',
        'format': 'json'
    }
) }}

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
