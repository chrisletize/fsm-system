-- FieldKit Migration 007
-- Adds: invoice lifecycle spine (invoices, invoice_line_items,
--        invoice_status_history) + catalog_items.invoice_label
-- Run on: ALL FOUR databases
-- Date: 2026-07-03
--
-- Notes:
--   * Database-per-company architecture: NO company_id column (the database IS
--     the company). invoice_number uniqueness is per-(number, revision_number),
--     scoped per-database = per-company, mirroring work_order_number.
--   * Reconciliation framework Pattern 2 (supersede, never mutate) + Pattern 4
--     (effective-time pinning: tax rate + equipment ordinals frozen at harden).
--     See FIELDKIT_DESIGN_ADDENDUM_reconciliation-framework.md, "Worked example:
--     the invoice lifecycle."
--   * State machine: Live -> Hardened -> Sent -> Paid, with Void and Revision
--     as terminal states for a given row. Revision and Void+reissue both create
--     a NEW row (linked via supersedes_invoice_id / superseded_by_invoice_id)
--     rather than mutating the frozen one.
--   * tax_rate_pct / tax_total are NULL while Live (undetermined until harden
--     resolves tax_county against the new tax_rates table, migration 006),
--     frozen at harden. tax_rates is now a real editable table (not the old
--     hardcoded nc_tax_rates.py module) -- see 006_tax_rates.sql.
--   * resolved_label on invoice_line_items is the baked equipment-ordinal
--     customer-facing text ("Set Dehu 1"); NULL while Live (derived fresh at
--     render from deployed_at order + line id tie-break), written at harden.
--   * Soft deletes only (deleted_at / deleted_by) for genuine accidental-row
--     cleanup, consistent with the rest of the schema. This is separate from
--     Void, which is a real lifecycle state, not a delete.
--   * Scope note: this migration supports single-work-order invoice creation
--     (one work_order_id per invoice) sufficient to exercise the state machine.
--     Multi-work-order batch invoicing (/invoices/create) is a later increment
--     and will need its own join table if/when it's built — not added here to
--     avoid guessing at an unbuilt UI's shape.

-- ============================================================================
-- PART 1: Invoices
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(20) NOT NULL,        -- e.g. KSF-2026-0142 (shared across revisions)
    revision_number INTEGER NOT NULL DEFAULT 1, -- Rev 1, Rev 2, ... same invoice_number

    state VARCHAR(20) NOT NULL DEFAULT 'Live'
        CHECK (state IN ('Live', 'Hardened', 'Sent', 'Paid', 'Void', 'Revision')),

    work_order_id INTEGER REFERENCES work_orders(id),   -- single-WO scope, see header note
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    service_location_id INTEGER REFERENCES service_locations(id),

    invoice_date DATE NOT NULL DEFAULT CURRENT_DATE,    -- effective date, pinned at creation

    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,          -- sum of taxable + non-taxable lines, pre-tax
    tax_county VARCHAR(100),                            -- copied from source at creation; re-confirmable while Live
    tax_rate_pct NUMERIC(5,3),                           -- NULL until harden resolves + freezes it
    tax_total NUMERIC(12,2),                             -- NULL until harden
    total NUMERIC(12,2),                                 -- NULL until harden (subtotal + tax_total)

    amount_paid NUMERIC(12,2) NOT NULL DEFAULT 0,

    hardened_at TIMESTAMP,
    hardened_by VARCHAR(100),
    sent_at TIMESTAMP,
    sent_by VARCHAR(100),
    voided_at TIMESTAMP,
    voided_by VARCHAR(100),
    void_reason TEXT,

    supersedes_invoice_id INTEGER REFERENCES invoices(id),     -- points at the prior version (Revision) or original (reissue)
    superseded_by_invoice_id INTEGER REFERENCES invoices(id),  -- points forward once superseded

    notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100),

    UNIQUE (invoice_number, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_inv_customer
    ON invoices(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_inv_work_order
    ON invoices(work_order_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_inv_state
    ON invoices(state) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_inv_number
    ON invoices(invoice_number) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 2: Line items
--   Snapshotted from work_order_line_items at invoice creation. Same two
--   shapes as work orders (standard / per_day_equipment), but frozen once the
--   parent invoice hardens.
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    catalog_item_id INTEGER REFERENCES catalog_items(id),
    equipment_unit_id INTEGER REFERENCES equipment_units(id),  -- per_day_equipment only; internal, never rendered

    description TEXT,                     -- snapshot of the WO line description
    resolved_label VARCHAR(255),          -- baked customer-facing label w/ ordinal; NULL while Live (derived at render)

    quantity NUMERIC(10,2),
    unit_price NUMERIC(10,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2),

    is_taxable BOOLEAN NOT NULL DEFAULT TRUE,

    deployed_at DATE,                     -- per_day_equipment only; drives ordinal ordering
    retrieved_at DATE,

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ili_invoice
    ON invoice_line_items(invoice_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ili_catalog_item
    ON invoice_line_items(catalog_item_id) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 3: Status history
--   Append-only audit trail. Mirrors work_order_status_history exactly.
--   The transition function writes one row per actual state change.
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoice_status_history (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    state VARCHAR(20) NOT NULL,
    changed_by VARCHAR(100),              -- username or 'system'
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ish_invoice
    ON invoice_status_history(invoice_id);

-- ============================================================================
-- PART 4: catalog_items.invoice_label
--   Customer-facing label distinct from the internal name. Render invoice_label
--   if set, else fall back to name. Prerequisite for correct ordinal labels
--   ("Set Dehu" vs. whatever internal name the catalog item has).
-- ============================================================================

ALTER TABLE catalog_items ADD COLUMN IF NOT EXISTS invoice_label VARCHAR(255);
