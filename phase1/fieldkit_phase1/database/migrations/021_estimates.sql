-- FieldKit Migration 021
-- Adds: estimates, estimate_line_items, estimate_status_history, estimate_requests
--       (build directive Stage 3, Increment 3.1).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   Estimates are deliberately a SIMPLER model than the invoice engine's
--   receivable/version split (migration 010) -- an estimate has no cash-basis
--   compliance requirement and no need for a "what did the customer actually see"
--   frozen presentation history, so it doesn't need a two-table split. One row per
--   estimate, editable while Draft, frozen (tax_rate_pct/tax_total/total) the moment
--   it's sent -- the same freeze discipline as invoices (D-025 era), just without the
--   version table, since an estimate that needs a real revision after being sent is
--   rare enough that "decline it and create a new one" is an acceptable answer (unlike
--   an invoice, which has real payment history riding on it).
--
-- Design notes:
--   * estimate_number format PREFIX-EST-YYYY-#### per the directive, reusing the same
--     per-company prefix map (WO_NUMBER_PREFIXES) and the same LIKE/ORDER-BY-id
--     sequence pattern _next_wo_number/_next_invoice_number already use.
--   * work_orders.estimate_id already existed (anticipated in an earlier increment,
--     confirmed via \d work_orders before writing this migration) -- only the FK
--     itself was missing, added here now that estimates(id) exists to reference.
--   * estimate_requests has no FK requiring a logged-in user for created_by (the
--     public request form has no login) -- source_ip is the only accountability trail
--     for a submission until it's triaged into status='contacted'/'spam'/'converted'.
--   * status values intentionally match the directive's list exactly
--     (Draft/Sent/Approved/Declined/Converted for estimates;
--     new/contacted/converted/spam for requests) -- no extra states invented.

CREATE TABLE IF NOT EXISTS estimates (
    id                    SERIAL PRIMARY KEY,
    estimate_number       VARCHAR(30) NOT NULL UNIQUE,
    customer_id           INTEGER NOT NULL REFERENCES customers(id),
    service_location_id   INTEGER REFERENCES service_locations(id),
    primary_contact_id    INTEGER REFERENCES customer_contacts(id),
    work_site_label       VARCHAR(255),

    status                VARCHAR(20) NOT NULL DEFAULT 'Draft'
                              CHECK (status IN ('Draft', 'Sent', 'Approved', 'Declined', 'Converted')),

    tax_county            VARCHAR(100),
    tax_rate_pct          NUMERIC(5,3),                 -- NULL until sent (frozen then)
    subtotal              NUMERIC(12,2) NOT NULL DEFAULT 0,
    tax_total             NUMERIC(12,2),                 -- NULL until sent
    total                  NUMERIC(12,2),                 -- NULL until sent

    notes_to_customer     TEXT,
    internal_notes        TEXT,

    sent_at               TIMESTAMP,
    sent_by               VARCHAR(100),
    sent_to_emails        TEXT,
    approved_at           TIMESTAMP,
    declined_at           TIMESTAMP,
    declined_reason       TEXT,
    converted_to_job_id   INTEGER REFERENCES work_orders(id),
    pdf_filename          VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_estimates_customer ON estimates(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_estimates_status ON estimates(status) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS estimate_line_items (
    id               SERIAL PRIMARY KEY,
    estimate_id      INTEGER NOT NULL REFERENCES estimates(id),
    catalog_item_id  INTEGER REFERENCES catalog_items(id),
    description      TEXT,
    quantity         NUMERIC(10,2) NOT NULL DEFAULT 1,
    unit_price       NUMERIC(10,2) NOT NULL DEFAULT 0,
    total            NUMERIC(12,2) NOT NULL DEFAULT 0,
    is_taxable       BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order       INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_eli_estimate ON estimate_line_items(estimate_id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS estimate_status_history (
    id           SERIAL PRIMARY KEY,
    estimate_id  INTEGER NOT NULL REFERENCES estimates(id),
    status       VARCHAR(20) NOT NULL,
    changed_by   VARCHAR(100),
    changed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS idx_esh_estimate ON estimate_status_history(estimate_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'work_orders_estimate_id_fkey'
    ) THEN
        ALTER TABLE work_orders
            ADD CONSTRAINT work_orders_estimate_id_fkey FOREIGN KEY (estimate_id) REFERENCES estimates(id);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS estimate_requests (
    id                    SERIAL PRIMARY KEY,
    name                  VARCHAR(200) NOT NULL,
    email                 VARCHAR(255),
    phone                 VARCHAR(20),
    property_name         VARCHAR(255),
    address               VARCHAR(500),
    city                  VARCHAR(100),
    state                 VARCHAR(2),
    zip                   VARCHAR(10),
    customer_type         VARCHAR(50),
    services              TEXT,
    description           TEXT,
    preferred_dates       VARCHAR(255),
    source_ip             VARCHAR(45),

    status                VARCHAR(20) NOT NULL DEFAULT 'new'
                              CHECK (status IN ('new', 'contacted', 'converted', 'spam')),
    assigned_to_username  VARCHAR(100),
    linked_customer_id    INTEGER REFERENCES customers(id),
    linked_estimate_id    INTEGER REFERENCES estimates(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_er_status ON estimate_requests(status) WHERE deleted_at IS NULL;
