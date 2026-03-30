

SELECT 
    event_type,
    session_id,
    product_id,
    COUNT(*) as event_count,
    window_start,
    window_end
FROM TABLE(
    TUMBLE(TABLE `default_catalog`.`default_database`.`clickstream_raw`, DESCRIPTOR(event_time), INTERVAL '1' MINUTE))
GROUP BY event_type, session_id, product_id, window_start, window_end