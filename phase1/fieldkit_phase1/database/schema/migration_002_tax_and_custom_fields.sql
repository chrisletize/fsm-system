-- Migration 002: Tax settings + Custom field system
-- Apply to all four company databases

-- Add tax columns to customers
ALTER TABLE customers 
    ADD COLUMN IF NOT EXISTS is_taxable BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS tax_county VARCHAR(100);

-- Custom field definitions (per company config)
CREATE TABLE IF NOT EXISTS customer_field_definitions (
    id SERIAL PRIMARY KEY,
    field_name VARCHAR(100) NOT NULL,
    field_type VARCHAR(20) NOT NULL DEFAULT 'text'
        CHECK (field_type IN ('text', 'textarea', 'toggle')),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- Customer field values (the actual data)
CREATE TABLE IF NOT EXISTS customer_field_values (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    field_definition_id INTEGER NOT NULL REFERENCES customer_field_definitions(id) ON DELETE CASCADE,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    UNIQUE(customer_id, field_definition_id)
);

CREATE INDEX IF NOT EXISTS idx_field_values_customer 
    ON customer_field_values(customer_id);
CREATE INDEX IF NOT EXISTS idx_field_definitions_order 
    ON customer_field_definitions(display_order) WHERE is_active = TRUE;

-- Seed default fields for Get a Grip
INSERT INTO customer_field_definitions (field_name, field_type, display_order, created_by)
VALUES 
    ('Colors', 'text', 1, 'system'),
    ('Access Codes', 'text', 2, 'system'),
    ('Special Instructions', 'textarea', 3, 'system')
ON CONFLICT DO NOTHING;
