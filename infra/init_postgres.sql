-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS clickstream;

-- Create target table for Flink JDBC sink
CREATE TABLE IF NOT EXISTS clickstream.clickstream_analytics (
    event_type TEXT,
    session_id TEXT,
    product_id TEXT,
    event_count BIGINT,
    window_start TIMESTAMP(3),
    window_end TIMESTAMP(3)
);

-- Grant privileges (assuming data_eng exists)
-- This might fail if the user doesn't exist but we can try
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA clickstream TO data_eng;
