-- Migration 003: Service Locations
-- Moves address, tax, and custom fields from customer to location level
-- Apply to all four company databases

-- Core service locations table
CREATE TABLE IF NOT EXISTS service_locations (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    location_name VARCHAR(255),
    address VARCHAR(500),
    address_2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip VARCHAR(10),
    county VARCHAR(100),
    is_taxable BOOLEAN DEFAULT TRUE,
    is_primary BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_locations_customer
    ON service_locations(customer_id);
CREATE INDEX IF NOT EXISTS idx_locations_active
    ON service_locations(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_locations_primary
    ON service_locations(customer_id, is_primary) WHERE deleted_at IS NULL;

-- File attachments per location (site maps, photos, documents)
CREATE TABLE IF NOT EXISTS service_location_files (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES service_locations(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) DEFAULT 'document',
    storage_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    uploaded_by VARCHAR(100),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_location_files_location
    ON service_location_files(location_id);

-- Add location_id to custom field values
-- (field values can belong to a customer OR a location)
ALTER TABLE customer_field_values
    ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES service_locations(id) ON DELETE CASCADE;

-- Migrate existing customer address data into service_locations
-- Creates one primary location per customer that has address data
INSERT INTO service_locations (
    customer_id, location_name, address, address_2,
    city, state, zip, county, is_taxable, is_primary,
    created_by
)
SELECT
    id,
    property_name,
    address,
    address_2,
    city,
    state,
    zip,
    tax_county,
    COALESCE(is_taxable, TRUE),
    TRUE,
    'migration_003'
FROM customers
WHERE deleted_at IS NULL
  AND (address IS NOT NULL OR city IS NOT NULL);

-- Migrate existing custom field values to be location-scoped
-- Links them to the primary location for each customer
UPDATE customer_field_values cfv
SET location_id = sl.id
FROM service_locations sl
WHERE sl.customer_id = cfv.customer_id
  AND sl.is_primary = TRUE
  AND cfv.location_id IS NULL;

-- Update the updated_at trigger for service_locations
CREATE TRIGGER update_service_locations_updated_at
    BEFORE UPDATE ON service_locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

