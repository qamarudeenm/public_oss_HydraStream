

CREATE TABLE IF NOT EXISTS clickstream_sink (
    event_type STRING,
    session_id STRING,
    product_id STRING,
    event_count BIGINT,
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3)
) WITH (
    'connector' = 'clickhouse',
    'url' = 'clickhouse://host.docker.internal:8123',
    'database-name' = 'clickstream',
    'table-name' = 'clickstream_analytics',
    'username' = 'default',
    'password' = 'clickhouse'
);