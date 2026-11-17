-- 01_data_quality.sql
-- Diagnostics only: count every known data trap BEFORE deciding what to exclude.
-- Output: dq_checks (one row per check).
CREATE OR REPLACE TABLE dq_checks AS
WITH b AS (SELECT * FROM raw_bookings)
SELECT 'total_rows' AS check_name, count(*) AS n_rows FROM b
UNION ALL SELECT 'exact_duplicate_rows', count(*) - (SELECT count(*) FROM (SELECT DISTINCT * FROM b)) FROM b
UNION ALL SELECT 'zero_guests (adults+children+babies=0)', count(*) FROM b
  WHERE coalesce(adults,0) + coalesce(children,0) + coalesce(babies,0) = 0
UNION ALL SELECT 'zero_nights', count(*) FROM b
  WHERE stays_in_weekend_nights + stays_in_week_nights = 0
UNION ALL SELECT 'adr_negative', count(*) FROM b WHERE adr < 0
UNION ALL SELECT 'adr_zero', count(*) FROM b WHERE adr = 0
UNION ALL SELECT 'adr_gt_1000', count(*) FROM b WHERE adr > 1000
UNION ALL SELECT 'children_null', count(*) FROM b WHERE children IS NULL
UNION ALL SELECT 'country_null', count(*) FROM b WHERE country IS NULL
UNION ALL SELECT 'agent_null', count(*) FROM b WHERE agent IS NULL
UNION ALL SELECT 'company_null', count(*) FROM b WHERE company IS NULL
UNION ALL SELECT 'market_segment_undefined', count(*) FROM b WHERE market_segment = 'Undefined'
UNION ALL SELECT 'distribution_channel_undefined', count(*) FROM b WHERE distribution_channel = 'Undefined'
UNION ALL SELECT 'canceled', count(*) FROM b WHERE is_canceled = 1
-- Leakage check: reservation_status must agree perfectly with the target
UNION ALL SELECT 'leak_status_mismatch_target', count(*) FROM b
  WHERE (is_canceled = 1) <> (reservation_status IN ('Canceled', 'No-Show'));
