-- FieldKit Migration 029
-- Adds: work_order_visit_status_log
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-25 (applied); file reconstructed 2026-10-19
--
-- RECONSTRUCTED FILE. Migration 029 was applied to all four production
-- databases on 2026-09-25 alongside commit 32406aa ("Visit status tracking +
-- dispatch board status colors"), but the .sql file itself was never
-- committed. This file was rebuilt on 2026-10-19 from `pg_dump -s` of the live
-- table, which is identical in all four DBs. Every statement is IF NOT EXISTS,
-- so running it against a database that already has the table is a no-op.
--
-- Why this exists:
--   Per-tech, timestamped visit status (On The Way / Started / Completed /
--   Cancelled) that is independent of work_orders.status -- a tech completing
--   today's five-minute extraction moisture check must not close a multi-day
--   Extraction Active job. Full design:
--   docs/FIELDKIT_DESIGN_ADDENDUM_visit-status-tracking.md
--
-- Design notes:
--   * Append-only: one row per status change. "Current status" for a
--     (work_order, tech) pair is the latest changed_at row -- no separate
--     column to drift, same pattern as invoice_display_status.
--   * No updated_*/deleted_* columns, deliberately: rows are never edited or
--     removed, and history is also captured via _record_audit().
--   * username / changed_by are plain VARCHAR, not FKs to users -- matching
--     work_order_techs.username (only getagrip.users is canonical; CLAUDE.md).

CREATE TABLE IF NOT EXISTS work_order_visit_status_log (
    id             SERIAL PRIMARY KEY,
    work_order_id  INTEGER NOT NULL REFERENCES work_orders(id),
    username       VARCHAR(100) NOT NULL,
    status         VARCHAR(20) NOT NULL
                   CONSTRAINT work_order_visit_status_log_status_check
                   CHECK (status IN ('On The Way', 'Started', 'Completed', 'Cancelled')),
    changed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by     VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wvsl_wo_tech
    ON work_order_visit_status_log (work_order_id, username, changed_at DESC);
