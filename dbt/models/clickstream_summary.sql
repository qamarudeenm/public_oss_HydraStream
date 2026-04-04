{{ config(
    materialized='streaming_table',
    with={
        'connector': 'jdbc',
        'url': 'jdbc:mysql://host.docker.internal:9004/clickstream',
        'table-name': 'clickstream_summary',
        'driver': 'com.mysql.jdbc.Driver',
        'username': env_var("CLICKHOUSE_USER"),
        'password': env_var("CLICKHOUSE_PASSWORD"),
    }
) }}

SELECT 
    event_type,
    session_id,
    COALESCE(product_id, `data`['product_id']) as product_id,
    COUNT(*) as event_count,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE {{ ref('clickstream_raw') }}, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
GROUP BY event_type, session_id, COALESCE(product_id, `data`['product_id']), window_start, window_end
