CREATE DATABASE IF NOT EXISTS clickstream;

CREATE TABLE IF NOT EXISTS clickstream.clickstream_summary (
    event_type String,
    session_id String,
    product_id Nullable(String),
    event_count UInt64,
    window_start DateTime64(3),
    window_end DateTime64(3)
) ENGINE = MergeTree()
ORDER BY (window_end, event_type, session_id);
