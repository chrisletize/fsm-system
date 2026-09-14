-- FieldKit Phase 1: Customer Management Schema
-- Created: 2026-02-10
-- Purpose: Customer and contact tables with full audit trails

-- ============================================================================
-- CUSTOMERS TABLE (Properties that are active or former customers)
-- ============================================================================

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    property_name VARCHAR(255) NOT NULL,
    customer_type VARCHAR(50) NOT NULL CHECK (customer_type IN ('Multi Family', 'Contractors', 'Residential', 'Commercial')),
    
    -- Address
    address VARCHAR(500),
    address_2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip VARCHAR(10),
    
    -- Management relationship
    management_company_id INTEGER REFERENCES management_companies(id),
    
    -- Customer status
    status VARCHAR(50) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive', 'On Hold', 'Lead')),
    
    -- Billing preferences
    billing_email VARCHAR(255),
    payment_terms VARCHAR(50) DEFAULT 'Net 30', -- 'Net 30', 'Due on Receipt', 'Net 15', etc.
    
    -- Internal notes
    notes TEXT,
    
    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

-- Indexes for customers
CREATE INDEX idx_customers_name ON customers(property_name);
CREATE INDEX idx_customers_type ON customers(customer_type);
CREATE INDEX idx_customers_management ON customers(management_company_id);
CREATE INDEX idx_customers_status ON customers(status);
CREATE INDEX idx_customers_deleted ON customers(deleted_at);
CREATE INDEX idx_customers_active ON customers(deleted_at) WHERE deleted_at IS NULL;

-- Full-text search index for property names
CREATE INDEX idx_customers_name_search ON customers USING gin(to_tsvector('english', property_name));

-- Composite index for common queries
CREATE INDEX idx_customers_status_type ON customers(status, customer_type) WHERE deleted_at IS NULL;

-- Trigger for customers
CREATE TRIGGER update_customers_updated_at 
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CUSTOMER CONTACTS (Multiple contacts per customer)
-- ============================================================================

CREATE TABLE customer_contacts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Contact information
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    title VARCHAR(150), -- 'Property Manager', 'Maintenance Supervisor', 'Regional Manager', etc.
    
    -- Phone numbers
    office_phone VARCHAR(20),
    mobile_phone VARCHAR(20),
    
    -- Email
    office_email VARCHAR(255),
    
    -- Primary contact flag (one per customer should be primary)
    is_primary BOOLEAN DEFAULT FALSE,
    
    -- Notes about this specific contact
    notes TEXT,
    
    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

-- Indexes for customer contacts
CREATE INDEX idx_customer_contacts_customer ON customer_contacts(customer_id);
CREATE INDEX idx_customer_contacts_name ON customer_contacts(last_name, first_name);
CREATE INDEX idx_customer_contacts_primary ON customer_contacts(customer_id, is_primary);
CREATE INDEX idx_customer_contacts_deleted ON customer_contacts(deleted_at);
CREATE INDEX idx_customer_contacts_active ON customer_contacts(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_customer_contacts_email ON customer_contacts(office_email);

-- Trigger for customer contacts
CREATE TRIGGER update_customer_contacts_updated_at 
    BEFORE UPDATE ON customer_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- CUSTOMER TAGS (Flexible categorization)
-- ============================================================================

CREATE TABLE customer_tags (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    tag_name VARCHAR(100) NOT NULL,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- Indexes for customer tags
CREATE INDEX idx_customer_tags_customer ON customer_tags(customer_id);
CREATE INDEX idx_customer_tags_name ON customer_tags(tag_name);
CREATE INDEX idx_customer_tags_composite ON customer_tags(customer_id, tag_name);

-- Prevent duplicate tags per customer
CREATE UNIQUE INDEX idx_customer_tags_unique ON customer_tags(customer_id, tag_name);

-- ============================================================================
-- CUSTOMER NOTES (Timestamped history log)
-- ============================================================================

CREATE TABLE customer_notes (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    note_type VARCHAR(50) DEFAULT 'General', -- 'General', 'Service', 'Billing', 'Sales'
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

-- Indexes for customer notes
CREATE INDEX idx_customer_notes_customer ON customer_notes(customer_id);
CREATE INDEX idx_customer_notes_date ON customer_notes(created_at DESC);
CREATE INDEX idx_customer_notes_type ON customer_notes(note_type);
CREATE INDEX idx_customer_notes_composite ON customer_notes(customer_id, created_at DESC);

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✓ Customer schema created successfully';
    RAISE NOTICE '  - customers table (properties)';
    RAISE NOTICE '  - customer_contacts table (multi-contact support)';
    RAISE NOTICE '  - customer_tags table (flexible categorization)';
    RAISE NOTICE '  - customer_notes table (activity log)';
END $$;
