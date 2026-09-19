-- FieldKit Migration 010
-- The receivable/version invoice refactor (build directive Stage 1, Increment 1.2).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Migration 007's single-table invoice ('Live'/'Hardened'/'Sent'/'Paid'/'Void'/
--   'Revision' all on one row) can't represent "this invoice was sent, got revised,
--   and the customer has a partial payment against the ORIGINAL sent version" — there
--   is only one row, so a revision had to mutate or replace it, losing the distinction
--   between the receivable (the thing that owes money, has one number, gets paid
--   against) and its presentations over time (the thing that gets printed/emailed/
--   superseded). This migration is the July 22 decision: `invoices` becomes the
--   RECEIVABLE (open/void, one row per invoice number, ever), `invoice_versions`
--   becomes the immutable PRESENTATION history (Live -> Hardened -> Sent ->
--   Superseded, one row per revision). `Paid` and `Revision` stop being stored states
--   entirely — paid-ness is derived from balance = 0 with a payment application
--   (built in Increment 1.4); a revision is just a new version row.
--
--   Zero invoice rows exist in production (confirmed before writing this migration),
--   so this is a schema rebuild, not a data migration — no backfill/conversion logic
--   is needed, only structure. Nothing in app.py calls the old invoice-engine
--   functions from any live route (confirmed via grep), so replacing them in the same
--   deploy as this migration is safe.
--
-- Design notes:
--   * reissue_of_invoice_id / reissued_as_invoice_id are the old
--     supersedes_invoice_id / superseded_by_invoice_id columns RENAMED, not new
--     columns. Under the old single-table model those two columns did double duty
--     (revision predecessor/successor OR reissue source/target); under this model
--     revision linkage moves down to invoice_versions.superseded_by_version_id, so
--     the receivable-level pointer only ever means "which invoice number this one
--     reissued from/into" -- hence the rename to reissue_of_/reissued_as_ for clarity.
--   * invoice_versions.subtotal is NOT NULL (computed live from lines even before
--     harden); tax_rate_pct/tax_total/total stay NULL until harden freezes them --
--     same "undetermined until frozen" discipline as the old invoices table had.
--   * invoice_status_history keeps its NOT NULL `state` column (the directive only
--     specifies adding columns here) -- new rows set it equal to `to_state` (or
--     'Void'/'Sent' for receivable-level events) so it stays populated and roughly
--     matches its old meaning; from_state/to_state/version_id are the columns actual
--     new code reads going forward. See docs/DECISIONS-MADE-DURING-BUILD.md.
--   * invoice_line_items is dropped (confirmed empty in production) in favor of
--     invoice_version_line_items, which hangs off a version instead of a receivable.

-- ============================================================================
-- PART 1: invoices -- becomes the RECEIVABLE
-- ============================================================================

-- Constraints/indexes tied to columns we're about to drop or repurpose.
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_state_check;
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_invoice_number_revision_number_key;
DROP INDEX IF EXISTS idx_inv_state;

-- Renames (see design notes above -- these are the old supersede-linkage columns).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'invoices' AND column_name = 'supersedes_invoice_id')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'invoices' AND column_name = 'reissue_of_invoice_id') THEN
        ALTER TABLE invoices RENAME COLUMN supersedes_invoice_id TO reissue_of_invoice_id;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'invoices' AND column_name = 'superseded_by_invoice_id')
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'invoices' AND column_name = 'reissued_as_invoice_id') THEN
        ALTER TABLE invoices RENAME COLUMN superseded_by_invoice_id TO reissued_as_invoice_id;
    END IF;
END $$;

-- New receivable-level columns.
ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS receivable_state VARCHAR(10) NOT NULL DEFAULT 'open'
        CHECK (receivable_state IN ('open', 'void')),
    ADD COLUMN IF NOT EXISTS current_version_id INTEGER,  -- FK added in PART 3, after invoice_versions exists
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'fieldkit'
        CHECK (source IN ('fieldkit', 'sf_import')),
    ADD COLUMN IF NOT EXISTS portal_id INTEGER,
    ADD COLUMN IF NOT EXISTS portal_status VARCHAR(20)
        CHECK (portal_status IN ('pending', 'submitted', 'accepted', 'rejected')),
    ADD COLUMN IF NOT EXISTS portal_submitted_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS portal_submission_notes TEXT,
    ADD COLUMN IF NOT EXISTS wtn_po_number VARCHAR(100);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'invoices_portal_id_fkey') THEN
        ALTER TABLE invoices ADD CONSTRAINT invoices_portal_id_fkey
            FOREIGN KEY (portal_id) REFERENCES customer_compliance_portals(id);
    END IF;
END $$;

-- Drop everything that moved down to invoice_versions (or, for amount_paid/credit_*,
-- is superseded entirely by payment_applications in Increment 1.4).
ALTER TABLE invoices
    DROP COLUMN IF EXISTS revision_number,
    DROP COLUMN IF EXISTS state,
    DROP COLUMN IF EXISTS subtotal,
    DROP COLUMN IF EXISTS tax_county,
    DROP COLUMN IF EXISTS tax_rate_pct,
    DROP COLUMN IF EXISTS tax_total,
    DROP COLUMN IF EXISTS total,
    DROP COLUMN IF EXISTS amount_paid,
    DROP COLUMN IF EXISTS hardened_at,
    DROP COLUMN IF EXISTS hardened_by,
    DROP COLUMN IF EXISTS sent_at,
    DROP COLUMN IF EXISTS sent_by,
    DROP COLUMN IF EXISTS credit_amount,
    DROP COLUMN IF EXISTS credit_status,
    DROP COLUMN IF EXISTS credit_opened_at;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'invoices_invoice_number_key') THEN
        ALTER TABLE invoices ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inv_receivable_state
    ON invoices(receivable_state) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_inv_portal
    ON invoices(portal_id) WHERE deleted_at IS NULL AND portal_id IS NOT NULL;

-- ============================================================================
-- PART 2: invoice_versions -- the immutable PRESENTATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoice_versions (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    revision_number INTEGER NOT NULL DEFAULT 0,

    state VARCHAR(12) NOT NULL DEFAULT 'Live'
        CHECK (state IN ('Live', 'Hardened', 'Sent', 'Superseded')),

    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,   -- live-computed from lines even before harden
    tax_county VARCHAR(100),
    tax_rate_pct NUMERIC(5,3),                    -- NULL until harden
    tax_total NUMERIC(12,2),                      -- NULL until harden
    total NUMERIC(12,2),                          -- NULL until harden

    hardened_at TIMESTAMP,
    hardened_by VARCHAR(100),
    sent_at TIMESTAMP,
    sent_by VARCHAR(100),
    sent_to_emails TEXT,

    superseded_at TIMESTAMP,
    superseded_by_version_id INTEGER REFERENCES invoice_versions(id),

    revision_reason TEXT,
    notes_to_customer TEXT,
    internal_notes TEXT,
    pdf_filename VARCHAR(255),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100),

    UNIQUE (invoice_id, revision_number)
);

CREATE INDEX IF NOT EXISTS idx_iv_invoice
    ON invoice_versions(invoice_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_iv_state
    ON invoice_versions(state) WHERE deleted_at IS NULL;

-- Now that invoice_versions exists, wire the FK back from invoices.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'invoices_current_version_id_fkey') THEN
        ALTER TABLE invoices ADD CONSTRAINT invoices_current_version_id_fkey
            FOREIGN KEY (current_version_id) REFERENCES invoice_versions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inv_current_version
    ON invoices(current_version_id) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 3: invoice_version_line_items -- replaces invoice_line_items
-- ============================================================================

CREATE TABLE IF NOT EXISTS invoice_version_line_items (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES invoice_versions(id),
    catalog_item_id INTEGER REFERENCES catalog_items(id),
    equipment_unit_id INTEGER REFERENCES equipment_units(id),  -- per_day_equipment only; internal, never rendered

    description TEXT,
    resolved_label VARCHAR(255),          -- baked customer-facing label w/ ordinal; NULL while Live

    quantity NUMERIC(10,2),
    unit_price NUMERIC(10,2) NOT NULL DEFAULT 0,
    total NUMERIC(12,2),

    is_taxable BOOLEAN NOT NULL DEFAULT TRUE,

    deployed_at DATE,
    retrieved_at DATE,

    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_ivli_version
    ON invoice_version_line_items(version_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ivli_catalog_item
    ON invoice_version_line_items(catalog_item_id) WHERE deleted_at IS NULL;

-- invoice_line_items is confirmed empty in production; dropping it in favor of
-- the version-scoped table above.
DROP TABLE IF EXISTS invoice_line_items;

-- ============================================================================
-- PART 4: invoice_status_history -- carries version-level + dated-delta events
-- ============================================================================

ALTER TABLE invoice_status_history
    ADD COLUMN IF NOT EXISTS version_id INTEGER,
    ADD COLUMN IF NOT EXISTS from_state VARCHAR(12),
    ADD COLUMN IF NOT EXISTS to_state VARCHAR(12),
    ADD COLUMN IF NOT EXISTS subtotal_delta NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS tax_delta NUMERIC(12,2),
    ADD COLUMN IF NOT EXISTS effective_date DATE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'invoice_status_history_version_id_fkey') THEN
        ALTER TABLE invoice_status_history ADD CONSTRAINT invoice_status_history_version_id_fkey
            FOREIGN KEY (version_id) REFERENCES invoice_versions(id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ish_version
    ON invoice_status_history(version_id) WHERE version_id IS NOT NULL;
