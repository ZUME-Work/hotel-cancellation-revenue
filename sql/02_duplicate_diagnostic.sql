-- 02_duplicate_diagnostic.sql
-- The dataset has no booking ID. Identical rows are probably separate rooms of one
-- group/agency block, not ingestion errors. Measure how much they distort cancel rates
-- before deciding the analysis grain.
CREATE OR REPLACE TABLE dq_duplicates AS
WITH h AS (
    SELECT b.*, count(*) OVER (PARTITION BY hash(b)) AS copies
    FROM raw_bookings AS b
)
SELECT
      deposit_type
    , market_segment
    , count(*)                                                  AS n_rows
    , round(avg((copies > 1)::int) * 100, 1)                    AS pct_rows_in_duplicate_groups
    , round(avg(is_canceled) * 100, 1)                          AS cancel_pct_row_level
    , round(avg(is_canceled) FILTER (WHERE copies = 1) * 100, 1) AS cancel_pct_unique_rows_only
FROM h
GROUP BY ALL
ORDER BY n_rows DESC;
