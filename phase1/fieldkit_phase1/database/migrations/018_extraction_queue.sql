-- FieldKit Migration 018
-- Adds: water extraction queue columns + daily log table
--       (build directive Stage 2, Increment 2.2).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   §3.2's model is "one work order per extraction job, from set-up through
--   retrieval" -- the WO stays one row for the whole lifecycle (no clone-forward).
--   A prior increment already anticipated most of this (work_orders.extraction_status,
--   extraction_day_count, parent_work_order_id, description_followup, and the
--   'Extraction Active' status value all already exist -- confirmed via \d
--   work_orders before writing this migration; nothing to re-add there). What's
--   actually missing is the flag that marks a WO as an extraction job at all
--   (is_extraction), the two lifecycle timestamps, the follow-up tech assignment,
--   the equipment-confirmation flag, and the daily status log the queue page reads.
--
-- Design notes:
--   * is_extraction is auto-set TRUE by the app the moment any per_day_equipment
--     line is added to a WO (app.py, _save_work_order) -- editable after, per the
--     directive, so the office can correct a false-positive.
--   * extraction_day_count already exists (INTEGER NOT NULL DEFAULT 0) from an
--     earlier increment's schema. The directive says it's "computed by the nightly
--     job (§3.5) and on read" -- §3.5 isn't built yet, so THIS increment computes it
--     live on every read (app.py's _extraction_day_count helper) rather than trusting
--     a column nothing is updating yet. The column stays for when §3.5 lands and
--     starts writing it (e.g. for a fast queue-page listing query without a
--     per-row date computation).
--   * extraction_daily_log is UNIQUE(work_order_id, log_date) -- one row per job per
--     day, upserted by the queue's row actions (Mark Ready / Needs More Time / Missed
--     Today) and by the "Log today's status for all" batch action. This is a log,
--     not a replacement for work_orders.extraction_status (the CURRENT status stays
--     on the WO row for fast queue rendering; the log is the day-by-day history).

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS is_extraction          BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS extraction_started_at    DATE,
    ADD COLUMN IF NOT EXISTS extraction_closed_at      DATE,
    ADD COLUMN IF NOT EXISTS followup_tech_username    VARCHAR(100),
    ADD COLUMN IF NOT EXISTS equipment_incomplete       BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_wo_extraction_active
    ON work_orders(is_extraction) WHERE deleted_at IS NULL AND status = 'Extraction Active';

CREATE TABLE IF NOT EXISTS extraction_daily_log (
    id                 SERIAL PRIMARY KEY,
    work_order_id      INTEGER NOT NULL REFERENCES work_orders(id),
    log_date           DATE NOT NULL,
    extraction_status  VARCHAR(30) CHECK (extraction_status IS NULL OR extraction_status IN
                          ('Drying', 'Ready for Pickup', 'Equipment Retrieved', 'Needs More Time', 'Missed Today')),
    tech_username      VARCHAR(100),
    notes              TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by         VARCHAR(100),
    UNIQUE (work_order_id, log_date)
);

CREATE INDEX IF NOT EXISTS idx_edl_wo ON extraction_daily_log(work_order_id);
CREATE INDEX IF NOT EXISTS idx_edl_date ON extraction_daily_log(log_date);
