-- FieldKit Migration 024
-- Adds: work_orders.callback_of_work_order_id/callback_reason/callback_responsible_username,
--       customer_ratings.callback_score
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   Build directive Stage 3, Increment 3.4 (Callbacks, §4.4). A callback is a
--   corrective work order against a prior job -- the office links it from the
--   WO form's "This is a callback for…" combo, which pre-fills location/site
--   label/lines and defaults responsible = the original job's lead tech
--   (editable). callback_reason is required the moment a source WO is linked
--   (enforced in application code, not a CHECK, so a future NULL-cleanup or
--   partial-import doesn't need special-casing).
--
-- Design notes:
--   * callback_of_work_order_id is a self-referencing FK on work_orders, not a
--     new join table -- a callback is a work order like any other (it can be
--     dispatched, invoiced, etc.), just one that happens to point back at what
--     it corrects. No CASCADE: a deleted source WO leaves the callback's link
--     dangling to a soft-deleted row, which is fine (soft delete never hard-
--     removes rows -- see CLAUDE.md).
--   * callback_responsible_username is a plain VARCHAR, not a FK into a
--     per-company users table -- same pattern as every other tech-assignment
--     column in this schema (work_order_techs.username, followup_tech_username),
--     since only getagrip.users is ever populated (D-003).
--   * customer_ratings.callback_score is a SIGNED contribution (a penalty is
--     negative), same convention as the other three *_score columns from
--     migration 022 -- composite_score stays a direct auditable sum.

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS callback_of_work_order_id INTEGER REFERENCES work_orders(id);
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS callback_reason TEXT;
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS callback_responsible_username VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_work_orders_callback_of
    ON work_orders(callback_of_work_order_id) WHERE callback_of_work_order_id IS NOT NULL;

ALTER TABLE customer_ratings ADD COLUMN IF NOT EXISTS callback_score NUMERIC(6,2) NOT NULL DEFAULT 0;
