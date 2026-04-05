-- example_sink.sql


-- Define your transformation query here.
-- This query will continuously consume the streaming source and emit results to the sink.
SELECT 
    user_id,
    event_type,
    session_id,
    COUNT(*) as event_count,
    window_start,
    window_end
FROM TABLE(
    -- Using the source model we defined in example_source.sql
    TUMBLE(TABLE `default_catalog`.`default_database`.`raw_kafka_datasource`, DESCRIPTOR(event_time), INTERVAL '1' MINUTE)
)
GROUP BY user_id, event_type, session_id, window_start, window_end