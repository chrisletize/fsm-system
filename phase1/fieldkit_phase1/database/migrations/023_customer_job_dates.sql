-- FieldKit Migration 023
-- Adds: customer_job_dates (build directive Stage 3, Increment 3.3 — recency
--       report + history import).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   The recency report's "last service date" is MAX(work_orders.start_date) for
--   native FieldKit jobs, UNIONED with this table for pre-cutover ServiceFusion
--   history that has no corresponding FieldKit work order (import_job_dates.py,
--   this same increment) -- otherwise every customer's recency would silently look
--   worse than reality on day one, before any real WOs exist.
--
-- Design notes:
--   * UNIQUE(customer_id, job_date) -- a source system can (and does) have multiple
--     jobs on the same day for the same customer; this table only needs to answer
--     "was there a job on this date," not how many, so the natural key collapses
--     duplicates rather than erroring on them (import_job_dates.py inserts with
--     ON CONFLICT DO NOTHING).
--   * source defaults 'fieldkit' for parity with invoices.source (migration 010) --
--     nothing writes 'fieldkit' rows into this table yet (native jobs are read
--     directly from work_orders, never duplicated in here), but the column exists
--     now so a future direct-entry UI ("log a pre-FieldKit job we forgot") has
--     somewhere to write without another migration.

CREATE TABLE IF NOT EXISTS customer_job_dates (
    id           SERIAL PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id),
    job_date     DATE NOT NULL,
    source       VARCHAR(30) NOT NULL DEFAULT 'fieldkit',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100),

    UNIQUE (customer_id, job_date)
);

CREATE INDEX IF NOT EXISTS idx_cjd_customer ON customer_job_dates(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_cjd_date ON customer_job_dates(job_date);
