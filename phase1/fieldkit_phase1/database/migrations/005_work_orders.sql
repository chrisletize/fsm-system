-- FieldKit Migration 005
-- Adds: work orders core (work_orders, work_order_line_items,
--        work_order_status_history, work_order_techs)
-- Run on: ALL FOUR databases
-- Date: 2026-07-01
--
-- Notes:
--   * Database-per-company architecture: NO company_id column (the database IS
--     the company). work_order_number uniqueness is per-database = per-company.
--   * work_site_label per FIELDKIT_DESIGN_ADDENDUM_worksite-and-doublebooking.md:
--     freeform, never a line item; label/prefill driven by customer_type in the UI.
--     The expression index below backs the double-booking check (normalized:
--     lowercased, non-alphanumerics stripped).
--   * Line items carry the per-day equipment columns per
--     FIELDKIT_DESIGN_ADDENDUM_catalog-and-equipment.md: equipment_unit_id,
--     deployed_at, retrieved_at. quantity/total are NULLABLE — an equipment line
--     still deployed (retrieved_at IS NULL) is accruing and has no final quantity.
--   * work_order_techs keys on username (not user_id): users are replicated
--     across DBs via write_to_all_dbs with SERIAL ids, which can drift; every
--     other user reference in the codebase (created_by etc.) is by username.
--   * Extraction/dispatch columns (extraction_status, extraction_day_count,
--     parent_work_order_id, arrival windows) are included now to avoid migration
--     churn; this session's UI does not touch them.
--   * Soft deletes only (deleted_at / deleted_by), consistent with the rest of
--     the schema. Status history and tech assignments are append/replace rows,
--     not soft-deleted documents.

-- ============================================================================
-- PART 1: Work orders
-- ============================================================================

CREATE TABLE IF NOT EXISTS work_orders (
    id SERIAL PRIMARY KEY,
    work_order_number VARCHAR(20) NOT NULL UNIQUE,      -- e.g. GAG-2026-0001
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    service_location_id INTEGER REFERENCES service_locations(id),
    primary_contact_id INTEGER REFERENCES customer_contacts(id),
    estimate_id INTEGER,                                -- no estimates table yet (Phase 3); plain column, FK added later

    status VARCHAR(30) NOT NULL DEFAULT 'Scheduled'
        CHECK (status IN ('Scheduled', 'On The Way', 'In Progress', 'Completed',
                          'Invoiced', 'No Charge', 'Cancelled', 'Extraction Active')),
    extraction_status VARCHAR(30)
        CHECK (extraction_status IS NULL OR extraction_status IN
               ('Drying', 'Ready for Pickup', 'Equipment Retrieved',
                'Needs More Time', 'Missed Today')),

    work_site_label VARCHAR(255),                       -- freeform: "Unit #3430-308", "412 Oak St"; UI label varies by customer_type

    auto_description TEXT,                              -- generated job description (editable textarea, pre-filled)
    description_occ_vac VARCHAR(3)
        CHECK (description_occ_vac IS NULL OR description_occ_vac IN ('OCC', 'VAC')),
    description_am_pm VARCHAR(2)
        CHECK (description_am_pm IS NULL OR description_am_pm IN ('AM', 'PM')),
    description_gated BOOLEAN NOT NULL DEFAULT FALSE,
    description_followup BOOLEAN NOT NULL DEFAULT FALSE,
    description_special_notes TEXT,

    internal_notes TEXT,                                -- office only; never shown to tech or on invoice
    notes_for_techs TEXT,                               -- shown to tech, not on invoice
    completion_notes TEXT,                              -- filled by tech at completion (Phase 6 mobile)

    po_number VARCHAR(100),
    job_source VARCHAR(30)
        CHECK (job_source IS NULL OR job_source IN
               ('Phone', 'Email', 'Website', 'Referral', 'Salesperson')),
    priority VARCHAR(10) NOT NULL DEFAULT 'Normal'
        CHECK (priority IN ('Normal', 'High', 'Urgent')),

    start_date DATE,
    end_date DATE,
    arrival_window_start TIME,
    arrival_window_end TIME,
    estimated_duration_hours NUMERIC(5,2),
    actual_duration_hours NUMERIC(5,2),
    is_multi_day BOOLEAN NOT NULL DEFAULT FALSE,

    extraction_day_count INTEGER NOT NULL DEFAULT 0,    -- incremented by the Phase 4 rollover engine
    parent_work_order_id INTEGER REFERENCES work_orders(id),  -- extraction roll-forward link to original

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_wo_customer
    ON work_orders(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_wo_location
    ON work_orders(service_location_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_wo_status
    ON work_orders(status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_wo_start_date
    ON work_orders(start_date) WHERE deleted_at IS NULL;

-- Double-booking lookup: same customer + same service location + normalized
-- work_site_label ("Unit 308" / "#308" / "unit-308" all normalize identically).
CREATE INDEX IF NOT EXISTS idx_wo_site_dupe
    ON work_orders (customer_id, service_location_id,
                    lower(regexp_replace(work_site_label, '[^a-zA-Z0-9]', '', 'g')))
    WHERE deleted_at IS NULL;

-- ============================================================================
-- PART 2: Line items
--   Every line comes from the catalog (no freeform). Two shapes, one table:
--     standard          -> quantity entered, total = unit_price * quantity
--     per_day_equipment -> equipment_unit_id set, deployed_at set; quantity/total
--                          NULL while accruing; on retrieval, retrieved_at is set
--                          and quantity finalizes to billable days (floor of 1).
-- ============================================================================

CREATE TABLE IF NOT EXISTS work_order_line_items (
    id SERIAL PRIMARY KEY,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    catalog_item_id INTEGER NOT NULL REFERENCES catalog_items(id),
    equipment_unit_id INTEGER REFERENCES equipment_units(id),   -- set only for per_day_equipment deployments
    description TEXT,                                   -- editable per line; pre-filled from catalog default
    quantity NUMERIC(10,2),                             -- NULL while equipment line is accruing
    unit_price NUMERIC(10,2) NOT NULL DEFAULT 0,        -- snapshot; overridable for standard lines
    total NUMERIC(12,2),                                -- NULL while accruing
    cost NUMERIC(10,2),                                 -- snapshot of catalog cost for historical margin
    is_taxable BOOLEAN NOT NULL DEFAULT TRUE,           -- inherited from catalog item, overridable
    tax_county VARCHAR(100),                            -- inherited from service location
    deployed_at DATE,                                   -- per-day equipment only
    retrieved_at DATE,                                  -- per-day equipment only; set closes accrual
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_woli_wo
    ON work_order_line_items(work_order_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_woli_equipment
    ON work_order_line_items(equipment_unit_id)
    WHERE equipment_unit_id IS NOT NULL AND deleted_at IS NULL;
-- "Where is unit #4" / never-retrieved safeguard: open deployments only.
CREATE INDEX IF NOT EXISTS idx_woli_open_deployments
    ON work_order_line_items(equipment_unit_id)
    WHERE equipment_unit_id IS NOT NULL AND retrieved_at IS NULL AND deleted_at IS NULL;

-- ============================================================================
-- PART 3: Status history
--   Append-only audit trail. Create/edit routes write rows from day one.
-- ============================================================================

CREATE TABLE IF NOT EXISTS work_order_status_history (
    id SERIAL PRIMARY KEY,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    status VARCHAR(30) NOT NULL,
    extraction_status VARCHAR(30),
    changed_by VARCHAR(100),                            -- username or 'system' or 'mobile_app'
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_wosh_wo
    ON work_order_status_history(work_order_id);

-- ============================================================================
-- PART 4: Tech assignments
--   Keyed on username (see header note). Dispatch board later becomes a view
--   over this same table — nothing here is throwaway.
-- ============================================================================

CREATE TABLE IF NOT EXISTS work_order_techs (
    id SERIAL PRIMARY KEY,
    work_order_id INTEGER NOT NULL REFERENCES work_orders(id),
    username VARCHAR(100) NOT NULL,
    is_lead_tech BOOLEAN NOT NULL DEFAULT FALSE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (work_order_id, username)
);

CREATE INDEX IF NOT EXISTS idx_wot_wo
    ON work_order_techs(work_order_id);
