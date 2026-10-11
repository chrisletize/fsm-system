-- FieldKit Migration 036
-- Rolls existing weekend follow-ups forward to the following Monday
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-11
--
-- Chris spotted follow-ups scheduled for Saturdays and Sundays. The cause was
-- that follow_up_date was pure arithmetic -- visit date plus the visit tag's
-- default_followup_days -- with nothing aware of the working week. Nobody
-- visits a leasing office on a Sunday, so those follow-ups were really Monday
-- follow-ups that read as overdue by the time anyone acted on them.
--
-- The code fix is _next_business_day() in app.py, applied in sales_visit_log
-- to both the tag arithmetic and a hand-typed date. This migration cleans up
-- the rows written before it existed.
--
-- Rolls FORWARD only. Moving a Saturday back to Friday would shorten the
-- interval the visit tag asked for, and for a follow-up due this weekend it
-- would land in the past.
--
-- Scoped to OPEN follow-ups: a completed one is history, and its date records
-- when the follow-up was actually due, not when someone should go now. Same
-- reasoning as the sales-hold suppression in 035 leaving Recent Visits alone.
--
-- ISODOW: 6=Saturday, 7=Sunday. Saturday +2 days, Sunday +1 day.

UPDATE sales_visits
SET follow_up_date = follow_up_date + (CASE EXTRACT(ISODOW FROM follow_up_date)
                                           WHEN 6 THEN 2
                                           WHEN 7 THEN 1
                                       END)::int,
    updated_at = CURRENT_TIMESTAMP,
    updated_by = 'migration_036'
WHERE deleted_at IS NULL
  AND follow_up_needed = TRUE
  AND follow_up_completed = FALSE
  AND follow_up_date IS NOT NULL
  AND EXTRACT(ISODOW FROM follow_up_date) > 5;
