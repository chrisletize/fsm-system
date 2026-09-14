-- FieldKit Migration 003
-- Adds: contact billing flags, contact_type, compliance portals table
-- Run on: ALL FOUR databases
-- Date: 2026-05-27

-- ============================================================================
-- PART 1: Add billing/communication flags to customer_contacts
-- ============================================================================

ALTER TABLE customer_contacts
    ADD COLUMN IF NOT EXISTS contact_type VARCHAR(50) DEFAULT 'general',
    ADD COLUMN IF NOT EXISTS accepts_billing BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS accepts_statements BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS accepts_general BOOLEAN NOT NULL DEFAULT TRUE;

-- Add index for billing lookups (Michele's batch billing page will query this constantly)
CREATE INDEX IF NOT EXISTS idx_customer_contacts_billing
    ON customer_contacts(customer_id, accepts_billing)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_customer_contacts_type
    ON customer_contacts(contact_type)
    WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 2: Seed billing flag for existing contacts
--
-- Logic: Any contact currently marked is_primary = TRUE gets accepts_billing = TRUE.
-- This is the best approximation we have for existing data — the primary contact
-- was the one receiving invoices before this flag existed.
-- After migration, Michele can adjust flags per customer as needed.
-- ============================================================================

UPDATE customer_contacts
    SET accepts_billing = TRUE,
        accepts_statements = TRUE,
        contact_type = 'general'
    WHERE is_primary = TRUE
      AND deleted_at IS NULL;

-- ============================================================================
-- PART 3: customer_compliance_portals table
--
-- One customer can be enrolled in multiple portals.
-- portal_type: 'ops', 'vendorcafe', 'paymode', 'other'
-- ============================================================================

CREATE TABLE IF NOT EXISTS customer_compliance_portals (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Portal identity
    portal_type VARCHAR(50) NOT NULL,   -- 'ops', 'vendorcafe', 'paymode', 'other'
    portal_label VARCHAR(100),          -- human label when portal_type = 'other'

    -- Account identifiers
    vendor_account_number VARCHAR(100), -- YOUR account number in their system
    property_client_id VARCHAR(100),    -- the property's ID in their system

    -- Submission requirements
    wtn_required BOOLEAN NOT NULL DEFAULT FALSE,  -- does this property require a WTN/PO?

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,

    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),

    -- Tracking
    last_submitted_at TIMESTAMP,        -- when we last submitted invoices for this portal

    -- Prevent duplicate enrollments for same customer+portal+property combo
    UNIQUE(customer_id, portal_type, property_client_id)
);

CREATE INDEX IF NOT EXISTS idx_compliance_portals_customer
    ON customer_compliance_portals(customer_id);

CREATE INDEX IF NOT EXISTS idx_compliance_portals_type
    ON customer_compliance_portals(portal_type)
    WHERE is_active = TRUE;

CREATE TRIGGER update_compliance_portals_updated_at
    BEFORE UPDATE ON customer_compliance_portals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- PART 4: Verify
-- ============================================================================

DO $$
DECLARE
    contact_count INTEGER;
    billing_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO contact_count
        FROM customer_contacts WHERE deleted_at IS NULL;

    SELECT COUNT(*) INTO billing_count
        FROM customer_contacts WHERE accepts_billing = TRUE AND deleted_at IS NULL;

    RAISE NOTICE '✓ Migration 003 complete';
    RAISE NOTICE '  customer_contacts: added contact_type, accepts_billing, accepts_statements, accepts_general';
    RAISE NOTICE '  customer_compliance_portals: table created';
    RAISE NOTICE '  Seeded % of % active contacts as billing contacts (was is_primary)', billing_count, contact_count;
END $$;
