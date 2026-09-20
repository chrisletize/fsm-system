-- FieldKit Migration 026
-- Adds: customers.merged_into_customer_id, customer_merge_log
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   Build directive Stage 4, Increment 5.2 (§5.2): duplicate detection at customer
--   create (no schema needed -- reuses the same normalized-match pattern as the
--   double-booking check, app.py only) and a customer merge tool. When an admin
--   merges customer B into customer A, every table that references B gets
--   re-pointed at A in one transaction, B is soft-deleted (never hard-deleted --
--   CLAUDE.md's blanket rule) with merged_into_customer_id set so any old link to
--   B can redirect to A instead of 404ing, and the merge itself is logged here.
--
-- Design notes:
--   * customer_merge_log is append-only (created_at/created_by-equivalent
--     merged_at/merged_by only, no update/delete columns) -- same convention as
--     contact_property_history/estimate_status_history: a merge, once done, is
--     history, not a record anyone edits. source_property_name/
--     target_property_name are denormalized onto the log row because the source
--     customer's own name is still readable (soft-deleted, not gone) but a log
--     should not depend on that staying true.
--   * merged_into_customer_id has no ON DELETE behavior specified (customers are
--     never hard-deleted, so the question never comes up) and is nullable --
--     NULL for every ordinary customer, set only on a merge's source row.
CREATE TABLE IF NOT EXISTS customer_merge_log (
    id SERIAL PRIMARY KEY,
    source_customer_id INTEGER NOT NULL,
    source_property_name VARCHAR(255),
    target_customer_id INTEGER NOT NULL REFERENCES customers(id),
    target_property_name VARCHAR(255),
    details JSONB,                        -- {"work_orders": 4, "invoices": 2, ...} row counts repointed, for audit

    merged_by VARCHAR(100),
    merged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_merge_log_source ON customer_merge_log(source_customer_id);
CREATE INDEX IF NOT EXISTS idx_merge_log_target ON customer_merge_log(target_customer_id);

ALTER TABLE customers ADD COLUMN IF NOT EXISTS merged_into_customer_id INTEGER REFERENCES customers(id);
CREATE INDEX IF NOT EXISTS idx_customers_merged_into ON customers(merged_into_customer_id) WHERE merged_into_customer_id IS NOT NULL;
