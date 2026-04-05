-- example_sink.sql
{{ config(
    materialized='streaming_table',
    with={
        'connector': 'jdbc',
        'url': env_var("CLICKHOUSE_JDBC_URL", "jdbc:mysql://host.docker.internal:9004/default"),
        'table-name': env_var("CLICKHOUSE_TARGET_TABLE", "your_target_table"),
        'driver': 'com.mysql.jdbc.Driver',
        'username': env_var("CLICKHOUSE_USER", "default"),
        'password': env_var("CLICKHOUSE_PASSWORD", ""),
    }
) }}

-- Define your transformation query here.
-- This query will continuously consume the streaming source and emit results to the sink.
SELECT 
    event_type,
    session_id,
    COUNT(*) as event_count,
    window_start,
    window_end
FROM TABLE(
    -- Using the source model we defined in example_source.sql
    TUMBLE(TABLE {{ ref('example_source') }}, DESCRIPTOR(event_time), INTERVAL '1' MINUTE)
)
GROUP BY event_type, session_id, window_start, window_end
