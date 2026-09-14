-- FieldKit Migration 004
-- Adds: service catalog (catalog_items) + equipment registry (equipment_units)
-- Run on: ALL FOUR databases
-- Date: 2026-06-30
--
-- Notes:
--   * Database-per-company architecture: NO company_id column (the database IS the company),
--     consistent with customers / service_locations / etc.
--   * billing_behavior is the functional discriminator (replaces the old service/product axis):
--       'standard'          -> bills unit_price * quantity; carries estimated_minutes (feeds the
--                              dispatch-board block size)
--       'per_day_equipment' -> unit_price is a DAILY rate; quantity = days deployed; no
--                              estimated_minutes, no schedule-block impact
--   * estimated_minutes NULL contributes 0 to block math (per_day_equipment + Custom Service).
--   * Soft deletes only (deleted_at / deleted_by), consistent with the rest of the schema.

-- ============================================================================
-- PART 1: Service catalog
-- ============================================================================

CREATE TABLE IF NOT EXISTS catalog_items (
    id SERIAL PRIMARY KEY,
    billing_behavior VARCHAR(30) NOT NULL DEFAULT 'standard'
        CHECK (billing_behavior IN ('standard', 'per_day_equipment')),
    name VARCHAR(255) NOT NULL,
    default_description TEXT,
    category VARCHAR(100),
    unit_price NUMERIC(10,2) NOT NULL DEFAULT 0,
    unit_of_measure VARCHAR(20) NOT NULL DEFAULT 'each'
        CHECK (unit_of_measure IN ('each', 'sq ft', 'hour', 'flat rate', 'day')),
    estimated_minutes INTEGER,            -- NULL for per_day_equipment / Custom Service; NULL = 0 toward block math
    minimum_quantity NUMERIC(10,2),       -- billable-qty floor (water extraction = 1.0); NULL otherwise
    billing_increment NUMERIC(10,2),      -- billable-qty rounding step (water extraction = 0.25); NULL otherwise
    is_taxable BOOLEAN NOT NULL DEFAULT TRUE,
    cost NUMERIC(10,2),                   -- internal cost for margin calculation
    is_catch_all BOOLEAN NOT NULL DEFAULT FALSE,   -- 'Custom Service' catch-all: requires a description on use
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_catalog_active
    ON catalog_items(is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_catalog_category
    ON catalog_items(category) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_catalog_behavior
    ON catalog_items(billing_behavior) WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 2: Equipment registry
--   Physical units (e.g. "Ozone #2", "Dehumidifier #4") that each bill as a
--   per_day_equipment catalog item. Replaces the old one-catalog-item-per-machine hack.
--   No ON DELETE CASCADE: catalog deletes are soft, and a billing-type record should
--   never hard-delete the physical machine record that points at it.
-- ============================================================================

CREATE TABLE IF NOT EXISTS equipment_units (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,                                     -- physical unit label
    catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),  -- the per_day_equipment billing type
    is_active BOOLEAN NOT NULL DEFAULT TRUE,                        -- in service / retired
    notes TEXT,                                                     -- serial #, purchase date, condition
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_equipment_active
    ON equipment_units(is_active) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_equipment_catalog_item
    ON equipment_units(catalog_item_id) WHERE deleted_at IS NULL;
