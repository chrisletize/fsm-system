-- FieldKit Migration 009
-- Adds: effective-dated tax rates (tax_rates.effective_from/effective_to) +
--       company_settings (single row per DB)
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-18
--
-- Why this exists:
--   FIELDKIT_BUILD_DIRECTIVE_2026-09.md Stage 1, Increment 1.1. NC changes county and
--   transit tax components on different dates (e.g. Mecklenburg 7.25% -> 8.25%
--   effective 2026-07-01, added in migration 006); a single mutable row per county
--   can't answer "what rate applied on this invoice's date" once an invoice has
--   already been hardened against an old rate. Versioning the whole row by effective
--   date lets _compute_invoice_tax() anchor on invoice_date and always get the
--   historically-correct rate, while a future /settings/tax page lets Michele/Chris
--   correct a rate the moment NC changes one without touching already-hardened
--   invoices.
--
--   company_settings is created here (not its own migration) because the invoice tax
--   path needs company_key -> default_tax_county / tax-exempt flag (Kleanit South
--   Florida) before invoicing can be built. One-row-per-DB config table, not a
--   CRUD-of-many-rows table.
--
-- Design notes:
--   * effective_from/effective_to versions the WHOLE row (state+county+transit
--     together), not each component separately -- matches how NCDOR announces
--     changes (one notice per county) and how the source table (migration 006) was
--     already shaped.
--   * UNIQUE(county) is dropped in favor of UNIQUE(county, effective_from) so a
--     county can carry multiple historical rows.
--   * The historical Mecklenburg 7.25% row gets effective_to = the day before the
--     existing (now-current) 8.25% row's new effective_from, so the two ranges are
--     contiguous -- no gap, no overlap. The historical row is inserted inactive
--     (is_active = FALSE) since /settings/tax's "active as of today" filter should
--     never surface a closed-out historical rate as current.
--   * company_settings: only company_name is seeded (from the COMPANY_BRANDING dict
--     already in app.py -- the only per-company name data that exists in the
--     codebase). Every other field (legal_name, address, phone, remit-to text, etc.)
--     is left NULL for Chris/Michele to fill in via /settings/company once built --
--     see docs/DECISIONS-MADE-DURING-BUILD.md.
--   * kleanit_sf.tax_exempt_by_default = TRUE per Chris's 2026-09-18 answer (FL tax
--     table intentionally left empty for now). See
--     docs/DECISIONS-MADE-DURING-BUILD.md D-001.
--   * The seed block is company-aware via current_database() so this ONE script,
--     run identically against all four DBs, produces the right company_name/
--     tax_exempt_by_default per company -- no per-company file needed.

-- ============================================================================
-- PART 1: tax_rates -- effective-dating
-- ============================================================================

ALTER TABLE tax_rates
    ADD COLUMN IF NOT EXISTS effective_from DATE NOT NULL DEFAULT '2000-01-01',
    ADD COLUMN IF NOT EXISTS effective_to   DATE NULL;

ALTER TABLE tax_rates DROP CONSTRAINT IF EXISTS tax_rates_county_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'tax_rates_county_effective_from_key'
    ) THEN
        ALTER TABLE tax_rates
            ADD CONSTRAINT tax_rates_county_effective_from_key UNIQUE (county, effective_from);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_tax_rates_effective
    ON tax_rates(county, effective_from, effective_to) WHERE deleted_at IS NULL;

-- Mecklenburg: split the single current 8.25% row into two historical versions.
-- Idempotent: only fires once (guarded on the current row still being unmoved from
-- effective_from = 2000-01-01). The UPDATE must run BEFORE the INSERT: the unique
-- constraint is on (county, effective_from) only, so both rows can never hold
-- effective_from = '2000-01-01' at the same time even transiently.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM tax_rates
        WHERE county = 'Mecklenburg' AND effective_from = '2000-01-01' AND county_pct = 3.000
    ) THEN
        UPDATE tax_rates
        SET effective_from = '2026-07-01'
        WHERE county = 'Mecklenburg' AND effective_from = '2000-01-01' AND county_pct = 3.000;

        INSERT INTO tax_rates (county, state_pct, county_pct, transit_pct, effective_from, effective_to, is_active)
        VALUES ('Mecklenburg', 4.750, 2.000, 0.500, '2000-01-01', '2026-06-30', FALSE);
    END IF;
END $$;

-- ============================================================================
-- PART 2: company_settings -- one row per DB
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_settings (
    id                      SERIAL PRIMARY KEY,
    company_name            VARCHAR(200) NOT NULL,
    legal_name              VARCHAR(200),
    address                 VARCHAR(255),
    address_2               VARCHAR(255),
    city                    VARCHAR(100),
    state                   VARCHAR(2),
    zip                     VARCHAR(10),
    phone                   VARCHAR(20),
    email_from_name         VARCHAR(200),
    email_reply_to          VARCHAR(255),
    alert_email             VARCHAR(255),
    default_tax_county      VARCHAR(100),
    tax_exempt_by_default   BOOLEAN NOT NULL DEFAULT FALSE,
    state_base_rate         NUMERIC(5,3),
    business_hours_start    TIME NOT NULL DEFAULT '08:00',
    business_hours_end      TIME NOT NULL DEFAULT '17:00',
    remit_to_text           TEXT,
    invoice_footer_text     TEXT,
    logo_filename           VARCHAR(255),
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by              VARCHAR(100),
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by              VARCHAR(100),
    deleted_at              TIMESTAMP NULL,
    deleted_by              VARCHAR(100)
);

-- Enforce "single row per DB" at the schema level, not just by convention.
CREATE UNIQUE INDEX IF NOT EXISTS idx_company_settings_singleton
    ON company_settings ((TRUE)) WHERE deleted_at IS NULL;

DO $$
DECLARE
    v_company_name VARCHAR(200);
    v_tax_exempt   BOOLEAN;
BEGIN
    IF EXISTS (SELECT 1 FROM company_settings WHERE deleted_at IS NULL) THEN
        RETURN;
    END IF;

    v_company_name := CASE current_database()
        WHEN 'fieldkit_getagrip'          THEN 'Get a Grip Charlotte'
        WHEN 'fieldkit_kleanit_charlotte' THEN 'Kleanit Charlotte'
        WHEN 'fieldkit_cts'               THEN 'CTS of Raleigh'
        WHEN 'fieldkit_kleanit_sf'        THEN 'Kleanit South Florida'
        ELSE current_database()
    END;
    v_tax_exempt := (current_database() = 'fieldkit_kleanit_sf');

    INSERT INTO company_settings (company_name, tax_exempt_by_default, created_by, updated_by)
    VALUES (v_company_name, v_tax_exempt, 'migration_009', 'migration_009');
END $$;
