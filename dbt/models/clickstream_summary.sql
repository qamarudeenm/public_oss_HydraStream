{{ config(
    materialized='streaming_table',
    with={
        'connector': 'jdbc',
        'url': 'jdbc:postgresql://localhost:5414/postgres?currentSchema=clickstream',
        'table-name': 'clickstream_analytics',
        'driver': 'org.postgresql.Driver',
        'username': 'data_eng',
        'password': '12345pP'
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
