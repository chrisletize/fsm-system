-- FieldKit Migration 025
-- Adds: sales_prospects, sales_contacts, contact_property_history, sales_visits,
--       visit_tags_config (+ seed), approval_queue, dormancy_alerts_config (+ seed,
--       company-aware via current_database())
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   Build directive Stage 3, Increment 3.5 (Sales CRM, §4.5), built against
--   docs/SALES-SYSTEM.md, trimmed to what the web app can do well (no offline
--   cache, no GPS-based proximity search, no cross-database contact sync -- all
--   explicitly Phase 2+/future in the spec). Chris O (all companies) and Mikey C
--   (Kleanit SF) log visits and manage prospects/contacts without ever writing
--   directly to `customers` -- every write that touches the real customer
--   database goes through `approval_queue` and a manager's explicit approval
--   (spec's "Zero accidental corruption of customer database" success criterion).
--
-- Design notes:
--   * This build follows the spec's schema (docs/SALES-SYSTEM.md) column-for-column,
--     with two deliberate additions beyond the spec: (1) every table gets the full
--     six-column audit+soft-delete set (created_at/by, updated_at/by, deleted_at/by)
--     per CLAUDE.md's blanket rule, even where the spec's own DDL omitted deleted_at
--     (sales_visits, approval_queue) or the full set (visit_tags_config,
--     dormancy_alerts_config) -- matching catalog_items' precedent of "is_active for
--     business-toggle + deleted_at for actual removal" coexisting on the same table.
--     contact_property_history is the one exception, deliberately: it's an
--     append-only log (created_at/created_by only), same convention as
--     estimate_status_history/work_order_status_history -- a log entry is never
--     edited or soft-deleted, only ever added to.
--   * property_id/property_type polymorphism (sales_contacts.current_property_id,
--     sales_visits.property_id, contact_property_history.property_id -- each paired
--     with a 'prospect'/'customer' property_type) stays exactly as the spec
--     specifies, no FK possible on either column since it can point into either
--     sales_prospects or the separate customers table. Same non-FK pattern as
--     work_order_techs.username / callback_responsible_username elsewhere in this
--     schema (CLAUDE.md: plain VARCHAR, not a foreign key, where a column can't
--     point at exactly one table).
--   * sales_prospects.customer_id is deliberately dual-purpose, matching the spec's
--     own narrative exactly: before conversion, if is_former_customer, it links the
--     prospect to the customer record they used to be; after conversion
--     (converted_to_customer = TRUE), the approval workflow populates this same
--     column with the newly created customer's id (spec's "Prospect-to-Customer
--     Conversion" section: "Prospect record gets customer_id field populated").
--     One column serves both cases because they're mutually exclusive in practice.
--   * sales_prospects.customer_type reuses the exact same CHECK list as
--     customers.customer_type ('Multi Family', 'Contractors', 'Residential',
--     'Commercial') so a converted prospect's type carries over verbatim with no
--     translation step at conversion time.
--   * visit_tags_config.tag_name has no FK from sales_visits.visit_tag -- a tag can
--     be retired (is_active = FALSE) without invalidating historical visits that
--     already used it, same reasoning as catalog_items / billing snapshot columns
--     elsewhere never re-deriving from a source row that might change later.
--   * dormancy_alerts_config is seeded company-aware via current_database(), same
--     technique as migration 009's company_settings seed -- one script, run
--     identically against all four DBs, produces the right alert_after_weeks per
--     company (GAG 8 weeks / KC 3 weeks / CTS 4 weeks / KSF 3 weeks, per directive
--     §4.5 and the spec's own "Get a Grip projects less frequent (resurfacing
--     multi-year cycle); Kleanit high-volume regular cleaning" rationale).
--   * approval_queue.requires_cross_db_sync / target_databases are kept from the
--     spec as unused Phase-2 columns (cross-database contact sync is explicitly
--     "not in MVP" per the spec) -- present so a future increment doesn't need a
--     schema change to light them up, but nothing in this increment writes them.

-- ============================================================================
-- PART 1: sales_prospects
-- ============================================================================

CREATE TABLE IF NOT EXISTS sales_prospects (
    id                       SERIAL PRIMARY KEY,
    property_name            VARCHAR(255) NOT NULL,
    address                  VARCHAR(500),
    city                     VARCHAR(100),
    state                    VARCHAR(2),
    zip                      VARCHAR(10),
    management_company_id    INTEGER REFERENCES management_companies(id),
    customer_type            VARCHAR(50)
                                 CHECK (customer_type IN ('Multi Family', 'Contractors', 'Residential', 'Commercial')),

    contractor_company_name  VARCHAR(255),
    active_projects          INTEGER DEFAULT 0,

    latitude                 DECIMAL(10, 8),
    longitude                DECIMAL(11, 8),

    is_former_customer       BOOLEAN DEFAULT FALSE,
    customer_id              INTEGER REFERENCES customers(id),  -- dual-purpose; see header
    former_customer_last_job DATE,

    converted_to_customer    BOOLEAN DEFAULT FALSE,
    converted_date           DATE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_prospects_type      ON sales_prospects(customer_type) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_prospects_converted ON sales_prospects(converted_to_customer) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_prospects_name      ON sales_prospects(property_name) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 2: sales_contacts
-- ============================================================================

CREATE TABLE IF NOT EXISTS sales_contacts (
    id                     SERIAL PRIMARY KEY,
    first_name             VARCHAR(100) NOT NULL,
    last_name              VARCHAR(100) NOT NULL,
    title                  VARCHAR(150),

    personal_phone         VARCHAR(20),
    personal_email         VARCHAR(255),
    office_phone           VARCHAR(20),
    office_email           VARCHAR(255),

    current_property_id    INTEGER,
    current_property_type  VARCHAR(20) CHECK (current_property_type IN ('prospect', 'customer')),

    notes                  TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_contacts_name     ON sales_contacts(last_name, first_name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_contacts_property ON sales_contacts(current_property_id, current_property_type) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 3: contact_property_history (append-only log — see header)
-- ============================================================================

CREATE TABLE IF NOT EXISTS contact_property_history (
    id             SERIAL PRIMARY KEY,
    contact_id     INTEGER REFERENCES sales_contacts(id) ON DELETE CASCADE,
    property_id    INTEGER NOT NULL,
    property_type  VARCHAR(20) NOT NULL CHECK (property_type IN ('prospect', 'customer')),
    property_name  VARCHAR(255),

    started_date   DATE,
    ended_date     DATE,

    notes          TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_contact_history ON contact_property_history(contact_id, ended_date);

-- ============================================================================
-- PART 4: sales_visits
-- ============================================================================

CREATE TABLE IF NOT EXISTS sales_visits (
    id             SERIAL PRIMARY KEY,
    property_id    INTEGER NOT NULL,
    property_type  VARCHAR(20) NOT NULL CHECK (property_type IN ('prospect', 'customer')),

    visit_date     DATE NOT NULL,
    visit_time     TIME,

    visit_tag      VARCHAR(50),
    contact_id     INTEGER REFERENCES sales_contacts(id),

    notes          TEXT,

    follow_up_needed     BOOLEAN DEFAULT FALSE,
    follow_up_date       DATE,
    follow_up_completed  BOOLEAN DEFAULT FALSE,

    is_dormant_investigation          BOOLEAN DEFAULT FALSE,
    dormancy_reason                   TEXT,
    dormancy_reported_to_management   BOOLEAN DEFAULT FALSE,

    latitude   DECIMAL(10, 8),
    longitude  DECIMAL(11, 8),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_visits_property ON sales_visits(property_id, property_type) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_visits_date     ON sales_visits(visit_date DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_visits_followup ON sales_visits(follow_up_date)
    WHERE follow_up_needed = TRUE AND follow_up_completed = FALSE AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_visits_dormant  ON sales_visits(is_dormant_investigation)
    WHERE is_dormant_investigation = TRUE AND deleted_at IS NULL;

-- ============================================================================
-- PART 5: visit_tags_config (+ seed)
-- ============================================================================

CREATE TABLE IF NOT EXISTS visit_tags_config (
    id                     SERIAL PRIMARY KEY,
    tag_name               VARCHAR(50) NOT NULL UNIQUE,
    tag_description        TEXT,
    default_followup_days  INTEGER,   -- NULL = no automatic follow-up
    is_active              BOOLEAN DEFAULT TRUE,
    display_order          INTEGER,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

INSERT INTO visit_tags_config (tag_name, tag_description, default_followup_days, display_order, created_by, updated_by)
VALUES
    ('Leasing Agent Only',          'Could not reach decision-maker, left card', 14, 1, 'migration_025', 'migration_025'),
    ('Brief chat',                  'Short conversation under 5 minutes',        30, 2, 'migration_025', 'migration_025'),
    ('Full meeting',                'Substantial discussion 15+ minutes',        21, 3, 'migration_025', 'migration_025'),
    ('Hot lead',                    'Expressed immediate interest',               5, 4, 'migration_025', 'migration_025'),
    ('Warm lead',                   'Interested but timing unclear',             21, 5, 'migration_025', 'migration_025'),
    ('Cold/No interest',            'Not interested currently',                  90, 6, 'migration_025', 'migration_025'),
    ('Existing customer check-in',  'Relationship maintenance',                  60, 7, 'migration_025', 'migration_025'),
    ('Pricing requested',           'Needs quote or proposal',                    3, 8, 'migration_025', 'migration_025'),
    ('Follow-up scheduled',         'They asked for specific return date',     NULL, 9, 'migration_025', 'migration_025')
ON CONFLICT (tag_name) DO NOTHING;

-- ============================================================================
-- PART 6: approval_queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS approval_queue (
    id             SERIAL PRIMARY KEY,
    request_type   VARCHAR(50) NOT NULL,   -- 'add_contact', 'update_contact', 'convert_prospect'

    target_type    VARCHAR(20),            -- 'customer', 'prospect'
    target_id      INTEGER,
    target_name    VARCHAR(255),           -- denormalized for display

    contact_name   VARCHAR(200),
    contact_phone  VARCHAR(20),
    contact_email  VARCHAR(255),

    request_details JSONB,

    status         VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'edited')),
    submitted_by   VARCHAR(100) NOT NULL,
    submitted_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    reviewed_by    VARCHAR(100),
    reviewed_at    TIMESTAMP,
    review_notes   TEXT,

    requires_cross_db_sync  BOOLEAN DEFAULT FALSE,   -- Phase 2, unused this increment (see header)
    target_databases        TEXT[],                  -- Phase 2, unused this increment (see header)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_approval_status    ON approval_queue(status, submitted_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_approval_submitter ON approval_queue(submitted_by) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 7: dormancy_alerts_config (+ company-aware seed)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dormancy_alerts_config (
    id                SERIAL PRIMARY KEY,
    company_name      VARCHAR(100) NOT NULL,
    alert_after_weeks INTEGER NOT NULL,
    is_active         BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

DO $$
DECLARE
    v_company_name VARCHAR(100);
    v_weeks        INTEGER;
BEGIN
    IF EXISTS (SELECT 1 FROM dormancy_alerts_config WHERE deleted_at IS NULL) THEN
        RETURN;  -- idempotent: already seeded
    END IF;

    v_company_name := CASE current_database()
        WHEN 'fieldkit_getagrip'          THEN 'Get a Grip Charlotte'
        WHEN 'fieldkit_kleanit_charlotte' THEN 'Kleanit Charlotte'
        WHEN 'fieldkit_cts'               THEN 'CTS of Raleigh'
        WHEN 'fieldkit_kleanit_sf'        THEN 'Kleanit South Florida'
        ELSE current_database()
    END;
    v_weeks := CASE current_database()
        WHEN 'fieldkit_getagrip'          THEN 8
        WHEN 'fieldkit_kleanit_charlotte' THEN 3
        WHEN 'fieldkit_cts'               THEN 4
        WHEN 'fieldkit_kleanit_sf'        THEN 3
        ELSE 4
    END;

    INSERT INTO dormancy_alerts_config (company_name, alert_after_weeks, created_by, updated_by)
    VALUES (v_company_name, v_weeks, 'migration_025', 'migration_025');
END $$;
