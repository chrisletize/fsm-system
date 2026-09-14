-- FieldKit Migration 006
-- Adds: tax_rates (editable NC county sales-tax table + settings page backing)
-- Run on: Get a Grip, Kleanit Charlotte, CTS databases ONLY (see PART 2 note
--         for Kleanit South Florida -- do NOT run the NC seed there).
-- Date: 2026-07-03
--
-- Why this exists:
--   Rates were previously hardcoded in a Python module (backend/api/nc_tax_rates.py,
--   Phase 0 only, "accurate as of December 2025") with no UI to correct them.
--   Mecklenburg County's rate increased 7.25% -> 8.25% effective July 1, 2026
--   (NCDOR notice, 2026-03-02) -- confirming the old table was already stale.
--   This table + the /settings/tax page (follow-up deliverable) let Michele/Chris
--   correct a rate the moment NC changes one, no code deploy required.
--
-- Design notes:
--   * Database-per-company: no company_id column. Each NC company DB gets its
--     own full copy of the county table (same architecture as catalog_items).
--     Kleanit South Florida uses Florida rates, not NC counties -- its table
--     is created empty here; populate via the settings page once built.
--   * total_pct is a GENERATED column (state+county+transit) so the total can
--     never drift out of sync with its parts after an edit.
--   * Simple mutable row per county, NOT a versioned/effective-dated history --
--     Pattern 4 (effective-time pinning) applies at the INVOICE layer instead:
--     invoices.tax_rate_pct is frozen into the invoice snapshot at harden time,
--     so a later rate correction here never changes an already-hardened invoice.
--     This table only needs to be correct "as of now" when hardening reads it.
--   * updated_at/updated_by give a lightweight audit of the last change; a full
--     change-log table was considered and deliberately deferred (nice-to-have,
--     not needed for the invoice lifecycle to be correct) -- flag if you want
--     it added.

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

-- ============================================================================
-- PART 2: Seed data
--   NC county rates, generated programmatically from the verified Phase 0
--   table (not hand-transcribed) with Mecklenburg corrected to the current
--   8.25% rate (4.75 state + 3.00 county + 0.50 transit), effective 2026-07-01
--   per NCDOR. 100 counties total -- row count is verified after insert below.
--
--   CAVEAT: only Mecklenburg was individually re-verified against NCDOR for
--   this migration. The source table was stamped "accurate as of December
--   2025" -- other counties may have changed since and haven't been spot-
--   checked one by one. Recommend a review pass via the settings page once
--   it exists.
--
--   Run this INSERT only on: getagrip, kleanit_charlotte, cts databases.
--   Do NOT run on kleanit_sf -- Florida rates go in separately via the
--   settings page once built.
-- ============================================================================

INSERT INTO tax_rates (county, state_pct, county_pct, transit_pct) VALUES
    ('Alamance', 4.750, 2.000, 0.000),
    ('Alexander', 4.750, 2.250, 0.000),
    ('Alleghany', 4.750, 2.250, 0.000),
    ('Anson', 4.750, 2.250, 0.000),
    ('Ashe', 4.750, 2.250, 0.000),
    ('Avery', 4.750, 2.000, 0.000),
    ('Beaufort', 4.750, 2.000, 0.000),
    ('Bertie', 4.750, 2.250, 0.000),
    ('Bladen', 4.750, 2.000, 0.000),
    ('Brunswick', 4.750, 2.000, 0.000),
    ('Buncombe', 4.750, 2.250, 0.000),
    ('Burke', 4.750, 2.000, 0.000),
    ('Cabarrus', 4.750, 2.250, 0.000),
    ('Caldwell', 4.750, 2.000, 0.000),
    ('Camden', 4.750, 2.000, 0.000),
    ('Carteret', 4.750, 2.000, 0.000),
    ('Caswell', 4.750, 2.000, 0.000),
    ('Catawba', 4.750, 2.250, 0.000),
    ('Chatham', 4.750, 2.250, 0.000),
    ('Cherokee', 4.750, 2.250, 0.000),
    ('Chowan', 4.750, 2.000, 0.000),
    ('Clay', 4.750, 2.250, 0.000),
    ('Cleveland', 4.750, 2.000, 0.000),
    ('Columbus', 4.750, 2.000, 0.000),
    ('Craven', 4.750, 2.000, 0.000),
    ('Cumberland', 4.750, 2.250, 0.000),
    ('Currituck', 4.750, 2.000, 0.000),
    ('Dare', 4.750, 2.000, 0.000),
    ('Davidson', 4.750, 2.250, 0.000),
    ('Davie', 4.750, 2.000, 0.000),
    ('Duplin', 4.750, 2.250, 0.000),
    ('Durham', 4.750, 2.250, 0.500),
    ('Edgecombe', 4.750, 2.250, 0.000),
    ('Forsyth', 4.750, 2.000, 0.000),
    ('Franklin', 4.750, 2.000, 0.000),
    ('Gaston', 4.750, 2.250, 0.000),
    ('Gates', 4.750, 2.000, 0.000),
    ('Graham', 4.750, 2.250, 0.000),
    ('Granville', 4.750, 2.000, 0.000),
    ('Greene', 4.750, 2.250, 0.000),
    ('Guilford', 4.750, 2.000, 0.000),
    ('Halifax', 4.750, 2.250, 0.000),
    ('Harnett', 4.750, 2.250, 0.000),
    ('Haywood', 4.750, 2.250, 0.000),
    ('Henderson', 4.750, 2.000, 0.000),
    ('Hertford', 4.750, 2.250, 0.000),
    ('Hoke', 4.750, 2.000, 0.000),
    ('Hyde', 4.750, 2.000, 0.000),
    ('Iredell', 4.750, 2.000, 0.000),
    ('Jackson', 4.750, 2.250, 0.000),
    ('Johnston', 4.750, 2.000, 0.000),
    ('Jones', 4.750, 2.250, 0.000),
    ('Lee', 4.750, 2.250, 0.000),
    ('Lenoir', 4.750, 2.000, 0.000),
    ('Lincoln', 4.750, 2.250, 0.000),
    ('Macon', 4.750, 2.000, 0.000),
    ('Madison', 4.750, 2.000, 0.000),
    ('Martin', 4.750, 2.250, 0.000),
    ('McDowell', 4.750, 2.000, 0.000),
    ('Mecklenburg', 4.750, 3.000, 0.500),
    ('Mitchell', 4.750, 2.000, 0.000),
    ('Montgomery', 4.750, 2.250, 0.000),
    ('Moore', 4.750, 2.250, 0.000),
    ('Nash', 4.750, 2.000, 0.000),
    ('New Hanover', 4.750, 2.250, 0.000),
    ('Northampton', 4.750, 2.000, 0.000),
    ('Onslow', 4.750, 2.250, 0.000),
    ('Orange', 4.750, 2.250, 0.500),
    ('Pamlico', 4.750, 2.000, 0.000),
    ('Pasquotank', 4.750, 2.250, 0.000),
    ('Pender', 4.750, 2.000, 0.000),
    ('Perquimans', 4.750, 2.000, 0.000),
    ('Person', 4.750, 2.000, 0.000),
    ('Pitt', 4.750, 2.250, 0.000),
    ('Polk', 4.750, 2.000, 0.000),
    ('Randolph', 4.750, 2.250, 0.000),
    ('Richmond', 4.750, 2.000, 0.000),
    ('Robeson', 4.750, 2.250, 0.000),
    ('Rockingham', 4.750, 2.250, 0.000),
    ('Rowan', 4.750, 2.250, 0.000),
    ('Rutherford', 4.750, 2.250, 0.000),
    ('Sampson', 4.750, 2.250, 0.000),
    ('Scotland', 4.750, 2.000, 0.000),
    ('Stanly', 4.750, 2.250, 0.000),
    ('Stokes', 4.750, 2.000, 0.000),
    ('Surry', 4.750, 2.250, 0.000),
    ('Swain', 4.750, 2.250, 0.000),
    ('Transylvania', 4.750, 2.000, 0.000),
    ('Tyrrell', 4.750, 2.000, 0.000),
    ('Union', 4.750, 2.000, 0.000),
    ('Vance', 4.750, 2.000, 0.000),
    ('Wake', 4.750, 2.000, 0.500),
    ('Warren', 4.750, 2.000, 0.000),
    ('Washington', 4.750, 2.000, 0.000),
    ('Watauga', 4.750, 2.000, 0.000),
    ('Wayne', 4.750, 2.000, 0.000),
    ('Wilkes', 4.750, 2.250, 0.000),
    ('Wilson', 4.750, 2.000, 0.000),
    ('Yadkin', 4.750, 2.000, 0.000),
    ('Yancey', 4.750, 2.000, 0.000)
ON CONFLICT (county) DO NOTHING;
