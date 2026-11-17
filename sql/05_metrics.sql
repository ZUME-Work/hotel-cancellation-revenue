-- 05_metrics.sql
-- Two-level metrics:
--   cancel_pct_room  = share of ROOMS cancelled (what hits inventory and revenue)
--   cancel_pct_block = share of booking DECISIONS cancelled (behaviour; blocks counted once)
--   realized_rev_per_room = mean ADR x nights over rooms that were not cancelled, spread over all rooms booked

-- Baseline by hotel
CREATE OR REPLACE TABLE m_baseline AS
SELECT
      r.hotel
    , count(*)                                          AS rooms
    , (SELECT count(*) FROM bookings_block k WHERE k.hotel = r.hotel) AS blocks
    , round(avg(r.is_canceled) * 100, 1)                AS cancel_pct_room
    , (SELECT round(avg(k.is_canceled) * 100, 1) FROM bookings_block k WHERE k.hotel = r.hotel) AS cancel_pct_block
    , round(avg(r.adr), 1)                              AS avg_adr
    , round(avg(r.booked_revenue), 1)                   AS booked_rev_per_room
    , round(avg(r.realized_revenue), 1)                 AS realized_rev_per_room
    , round(sum(r.realized_revenue) / sum(r.booked_revenue) * 100, 1) AS revenue_kept_pct
FROM bookings_room r
GROUP BY r.hotel
ORDER BY r.hotel;

-- Lead-time trade-off: ADR rises or falls, cancellation rises, what is left?
CREATE OR REPLACE TABLE m_lead_time AS
WITH room AS (
    SELECT hotel, lead_bucket
         , count(*)                                     AS rooms
         , avg(adr)                                     AS avg_adr
         , avg(nights)                                  AS avg_nights
         , avg(is_canceled)                             AS cancel_room
         , avg(booked_revenue)                          AS booked_rev
         , avg(realized_revenue)                        AS realized_rev
    FROM bookings_room GROUP BY ALL
), blk AS (
    SELECT hotel, lead_bucket, avg(is_canceled) AS cancel_block
    FROM bookings_block GROUP BY ALL
)
SELECT
      room.hotel, room.lead_bucket, rooms
    , round(avg_adr, 1)              AS avg_adr
    , round(avg_nights, 2)           AS avg_nights
    , round(cancel_room * 100, 1)    AS cancel_pct_room
    , round(cancel_block * 100, 1)   AS cancel_pct_block
    , round(booked_rev, 1)           AS booked_rev_per_room
    , round(realized_rev, 1)         AS realized_rev_per_room
FROM room JOIN blk USING (hotel, lead_bucket)
ORDER BY 1, 2;

-- Segment view: which channels look good on ADR but lose the most to cancellation?
CREATE OR REPLACE TABLE m_segment AS
WITH room AS (
    SELECT market_segment
         , count(*)                  AS rooms
         , avg(adr)                  AS avg_adr
         , avg(is_canceled)          AS cancel_room
         , avg(booked_revenue)       AS booked_rev
         , avg(realized_revenue)     AS realized_rev
         , sum(realized_revenue)     AS total_realized
         , sum(booked_revenue - realized_revenue) AS revenue_lost
    FROM bookings_room GROUP BY ALL
), blk AS (
    SELECT market_segment, count(*) AS blocks, avg(is_canceled) AS cancel_block
    FROM bookings_block GROUP BY ALL
)
SELECT
      market_segment, rooms, blocks
    , round(avg_adr, 1)                                           AS avg_adr
    , round(cancel_room * 100, 1)                                 AS cancel_pct_room
    , round(cancel_block * 100, 1)                                AS cancel_pct_block
    , round(booked_rev, 1)                                        AS booked_rev_per_room
    , round(realized_rev, 1)                                      AS realized_rev_per_room
    , round(total_realized / sum(total_realized) OVER () * 100, 1) AS share_of_realized_rev_pct
    , round(revenue_lost / sum(revenue_lost) OVER () * 100, 1)     AS share_of_lost_rev_pct
FROM room JOIN blk USING (market_segment)
ORDER BY rooms DESC;
