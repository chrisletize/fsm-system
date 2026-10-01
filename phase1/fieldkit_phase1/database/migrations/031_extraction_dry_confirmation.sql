-- FieldKit Migration 031
-- Adds: work_orders.dry_confirmed_at / dry_confirmed_by / dry_confirmation_notes
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-01
--
-- Why this exists:
--   Chris, 2026-10-01: equipment is often retrieved a piece at a time (areas
--   that are still wet keep their fans/dehus), and a job should only be
--   Completed once everything is back AND the area has been validated dry.
--   Per-piece retrieval already worked -- every equipment line has carried its
--   own deployed_at/retrieved_at since migration 012, and extraction_retrieve
--   has always kept the WO active while any line is still open. What was
--   missing was the dry validation: retrieval alone closed the job, with
--   nothing recording that anyone had actually checked.
--
-- Design notes:
--   * A plain confirmation, not moisture readings. Chris chose this on
--     2026-10-01: the tech ticks "confirmed dry" with an optional note, no
--     numbers to key in on a phone. If defensible per-area readings are ever
--     needed, that's a child table (extraction_dry_readings) rather than a
--     reshape of these columns.
--   * Three columns on work_orders rather than a new table: there is exactly
--     one dry confirmation per extraction job (it's the gate on closing that
--     one job), so this is a 1:1 fact about the WO, same shape as
--     extraction_started_at / extraction_closed_at already on this table. A
--     log table would imply a history that doesn't exist.
--   * dry_confirmed_by is a plain VARCHAR username, not an FK -- matching
--     work_orders.followup_tech_username and work_order_techs.username
--     (CLAUDE.md: the per-company DBs have no usable FK target for users,
--     since only getagrip.users is canonical).
--   * No soft-delete columns here: these are attributes OF a work order, not
--     rows of their own, and the WO's own deleted_at already covers them.
--     Clearing a mistaken confirmation sets all three back to NULL, which the
--     record_audit trail (migration 027) captures as an ordinary WO update.
--   * Deliberately added to all four DBs including getagrip, which does no
--     extraction work at all (COMPANIES_WITHOUT_EXTRACTION) -- this build's
--     blanket rule is that the schema stays identical across companies, and
--     the app gates the feature, not the schema.

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS dry_confirmed_at        TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS dry_confirmed_by        VARCHAR(100),
    ADD COLUMN IF NOT EXISTS dry_confirmation_notes  TEXT;
