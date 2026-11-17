-- 03_clean_bookings.sql
-- Room-level clean table. Grain: one row per raw record (= one room booking).
-- Duplicates are KEPT here: each copy is treated as a separate room in a group/agency block.
-- Exclusions (counts in dq_checks):
--   zero guests (180), zero nights (715, all ADR = 0: no stay to earn on),
--   ADR < 0 (1), ADR > 1000 (1), market segment / channel 'Undefined' (7)
CREATE OR REPLACE TABLE bookings_room AS
SELECT
      hash(b)                                                   AS block_key   -- identical rows share a key
    , hotel
    , is_canceled
    , reservation_status = 'No-Show'                            AS is_no_show
    , lead_time
    , make_date(arrival_date_year,
                month(strptime(arrival_date_month, '%B')),
                arrival_date_day_of_month)                      AS arrival_date
    , stays_in_weekend_nights + stays_in_week_nights            AS nights
    , adr
    , adr * (stays_in_weekend_nights + stays_in_week_nights)    AS booked_revenue
    , adr * (stays_in_weekend_nights + stays_in_week_nights)
          * (1 - is_canceled)                                   AS realized_revenue -- no-shows count as 0
    , market_segment
    , distribution_channel
    , deposit_type
    , customer_type
    , coalesce(country, 'Unknown')                              AS country
    , coalesce(children, 0)                                     AS children
    , adults
    , babies
    , is_repeated_guest
    , previous_cancellations
    , previous_bookings_not_canceled
    , total_of_special_requests
    , required_car_parking_spaces
    , agent IS NOT NULL                                         AS has_agent
    , company IS NOT NULL                                       AS has_company
    , CASE
        WHEN lead_time <= 7   THEN '1) 0-7d'
        WHEN lead_time <= 30  THEN '2) 8-30d'
        WHEN lead_time <= 90  THEN '3) 31-90d'
        WHEN lead_time <= 180 THEN '4) 91-180d'
        WHEN lead_time <= 365 THEN '5) 181-365d'
        ELSE                       '6) 365d+'
      END                                                       AS lead_bucket
FROM raw_bookings AS b
WHERE TRUE
  AND adults + coalesce(children, 0) + babies > 0
  AND stays_in_weekend_nights + stays_in_week_nights > 0
  AND adr BETWEEN 0 AND 1000
  AND market_segment <> 'Undefined'
  AND distribution_channel <> 'Undefined';
