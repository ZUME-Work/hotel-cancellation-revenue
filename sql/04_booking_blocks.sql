-- 04_booking_blocks.sql
-- Block-level table. Grain: one row per distinct booking record; n_rooms = number of identical copies.
-- Use for cancellation BEHAVIOUR and modelling, so one 40-room group block counts as one decision,
-- not 40. Revenue questions use bookings_room instead.
CREATE OR REPLACE TABLE bookings_block AS
SELECT
      block_key
    , count(*)                    AS n_rooms
    , any_value(COLUMNS(* EXCLUDE (block_key)))
FROM bookings_room
GROUP BY block_key;
