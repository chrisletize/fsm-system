-- FieldKit Migration 033
-- Adds: sales_prospects.rehab_planned / rehab_expected_date / rehab_notes,
--       dormancy_alerts_config.rehab_contact_days
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-06
--
-- Why this exists:
--   Chris, 2026-10-06: when a property plans a "rehab" -- a full renovation
--   rolling across every unit as it goes vacant -- it is among the most
--   valuable prospects these companies see, and the salesperson must not lose
--   contact with it.
--
--   The existing follow-up machinery can't carry that. A follow-up is created
--   BY a visit and dies when it's completed, so the prospect goes silent until
--   somebody remembers to log another visit. That's acceptable for an ordinary
--   prospect and exactly wrong for the one you can least afford to forget.
--
--   So this copies the shape of the dormancy alerts instead: a flag on the
--   prospect plus a COMPUTED resurfacing rule ("flagged, and not visited in N
--   days"). Nobody has to set a reminder and nothing can be completed away --
--   the prospect reappears on the sales dashboard every time it goes quiet,
--   until the flag is cleared.
--
-- Design notes:
--   * The flag lives on sales_prospects, not on a visit tag. "They are planning
--     a rehab" is a fact about the property that stays true across visits;
--     visit_tags_config describes what happened on ONE visit.
--   * rehab_expected_date is recorded for reference and reporting only --
--     Chris chose explicitly (2026-10-06) that the contact cadence stays fixed
--     rather than tightening as the date approaches, because early rehab plans
--     are usually vague and a date-driven cadence would churn on guesses.
--   * rehab_contact_days hangs off dormancy_alerts_config. The table name says
--     dormancy, but it is in practice the sales module's per-company cadence
--     config (one row per company DB, seeded by migration 025 via
--     current_database()), and this is the same KIND of setting: how long
--     silence is allowed before we resurface something. A second one-integer
--     table would have been worse. Changing it is the same one-line UPDATE the
--     dormancy threshold already takes.
--   * 21 days is a starting default, not a considered number -- expect to tune
--     it once there's real usage.
--   * No separate "rehab status" workflow (planned -> underway -> done). Chris
--     asked to keep these fresh for follow-up, not to track the renovation
--     itself; the flag gets cleared when it stops being useful.

ALTER TABLE sales_prospects
    ADD COLUMN IF NOT EXISTS rehab_planned       BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rehab_expected_date DATE NULL,
    ADD COLUMN IF NOT EXISTS rehab_notes         TEXT;

ALTER TABLE dormancy_alerts_config
    ADD COLUMN IF NOT EXISTS rehab_contact_days  INTEGER NOT NULL DEFAULT 21;

-- Drives the dashboard card, so it's indexed for exactly that question.
CREATE INDEX IF NOT EXISTS idx_prospects_rehab
    ON sales_prospects(rehab_planned)
    WHERE rehab_planned = TRUE AND deleted_at IS NULL AND converted_to_customer = FALSE;
