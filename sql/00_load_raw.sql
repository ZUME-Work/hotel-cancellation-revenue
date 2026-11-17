-- 00_load_raw.sql
-- Load the raw CSV as-is. Grain: one row per booking.
-- Missing values appear as both 'NULL' (agent, company, country) and 'NA' (children).
CREATE OR REPLACE TABLE raw_bookings AS
SELECT *
FROM read_csv('data/raw/hotels.csv', header = true, nullstr = ['NULL', 'NA'], auto_detect = true, sample_size = -1);
