-- FieldKit Migration 020
-- Adds: customer_flags, job_runs, work_orders.alert_sent_at, and a master
--       on/off switch for scheduled email alerts (build directive Stage 2,
--       Increment 2.5 — nightly + periodic jobs).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   §3.5's nightly job needs somewhere to write its computed delinquency flags
--   (customer_flags) and a record of each run (job_runs, so the settings page can
--   show "last run" per job -- "that panel is how Chris knows cron is wired," per the
--   directive). `uninvoiced` needs a dedupe column so the same Completed-but-
--   uninvoiced WO doesn't get a fresh alert email every 15 minutes forever.
--
-- Design notes:
--   * scheduled_alerts_enabled is the master on/off switch Chris asked for
--     (2026-09-19 conversation): jobs.py's computational work (customer_flags,
--     extraction_day_count, Missed Today logging, job_runs bookkeeping) always runs
--     regardless of this flag -- only the actual email-sending steps check it. It
--     defaults FALSE, so installing the cron schedule is safe before Chris has
--     reviewed and explicitly turned emailing on; see docs/DECISIONS-MADE-DURING-BUILD.md.
--   * customer_flags.customer_id is the primary key (one row per customer, replaced
--     wholesale each nightly run) rather than an append-only log -- callers always
--     want "the current answer," never history, and the directive's own column list
--     (is_delinquent, oldest_open_invoice_date, open_balance, unapplied_credit,
--     computed_at) is exactly a point-in-time snapshot.
--   * job_runs has no foreign key to anything -- company_key is a plain string (it
--     selects a whole DATABASE, not a row in this one), matching how company_key is
--     used as a routing key everywhere else in this codebase (never a real FK target).

CREATE TABLE IF NOT EXISTS customer_flags (
    customer_id               INTEGER PRIMARY KEY REFERENCES customers(id),
    is_delinquent              BOOLEAN NOT NULL DEFAULT FALSE,
    oldest_open_invoice_date   DATE,
    open_balance                NUMERIC(12,2) NOT NULL DEFAULT 0,
    unapplied_credit            NUMERIC(12,2) NOT NULL DEFAULT 0,
    computed_at                  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_runs (
    id           SERIAL PRIMARY KEY,
    job_name     VARCHAR(50) NOT NULL,
    company_key  VARCHAR(30) NOT NULL,
    started_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at  TIMESTAMP,
    status       VARCHAR(20) NOT NULL DEFAULT 'running'
                     CHECK (status IN ('running', 'success', 'partial', 'failed', 'skipped')),
    summary      TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_runs_lookup
    ON job_runs(job_name, company_key, started_at DESC);

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS alert_sent_at TIMESTAMP;

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS scheduled_alerts_enabled BOOLEAN NOT NULL DEFAULT FALSE;
