-- FieldKit Migration 006b (Kleanit South Florida only)
-- Creates the tax_rates table WITHOUT the NC county seed.
-- Run on: fieldkit_kleanit_sf ONLY.
--
-- Why this exists:
--   006_tax_rates.sql bundles the table creation with the 100-county NC seed,
--   so it was intentionally skipped on the Florida DB to avoid seeding NC
--   counties there. But that also skipped creating the (empty) table. Florida
--   still needs the table structure so FL rates can be entered later via the
--   /settings/tax page. This creates the empty table only.
--   IF NOT EXISTS makes it a safe no-op if it somehow already exists.

CREATE TABLE IF NOT EXISTS tax_rates (
    id SERIAL PRIMARY KEY,
    county VARCHAR(100) NOT NULL,
    state_pct NUMERIC(5,3) NOT NULL DEFAULT 0,
    county_pct NUMERIC(5,3) NOT NULL DEFAULT 0,
    transit_pct NUMERIC(5,3) NOT NULL DEFAULT 0,
    total_pct NUMERIC(5,3) GENERATED ALWAYS AS (state_pct + county_pct + transit_pct) STORED,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100),
    UNIQUE (county)
);

CREATE INDEX IF NOT EXISTS idx_tax_rates_active
    ON tax_rates(is_active) WHERE deleted_at IS NULL;
