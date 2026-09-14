-- FieldKit Phase 1: Seed Data
-- Created: 2026-02-10
-- Purpose: Initial data for testing and production setup

-- ============================================================================
-- SEED USERS
-- ============================================================================

-- Note: These are example users. Passwords should be hashed with bcrypt before insertion.
-- The setup script will handle actual password hashing.

-- Admin users (full access to all companies)
INSERT INTO users (username, email, password_hash, full_name, role, company_access, is_active) VALUES
('chris', 'chris@getagrip.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Chris Letize', 'admin', 
 '["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]'::jsonb, TRUE),
('michele', 'michele@getagrip.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Michele', 'admin', 
 '["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]'::jsonb, TRUE),
('mike', 'mike@getagrip.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Mike', 'admin', 
 '["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]'::jsonb, TRUE);

-- Manager users (company-specific access)
INSERT INTO users (username, email, password_hash, full_name, role, company_access, is_active) VALUES
('patrick', 'patrick@ctsraleigh.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Patrick', 'manager', 
 '["cts"]'::jsonb, TRUE),
('walter', 'walter@kleanitcharlotte.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Walter', 'manager', 
 '["kleanit_charlotte"]'::jsonb, TRUE),
('mikeyc', 'mikey@kleanitsouthflorida.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Mikey C', 'manager', 
 '["kleanit_sf"]'::jsonb, TRUE);

-- Salesperson users (all companies for sales work)
INSERT INTO users (username, email, password_hash, full_name, role, company_access, is_active) VALUES
('chriso', 'chriso@getagrip.com', '$2b$12$zATZJitxE7rKtICSre7zne9jaM4UxRrilZvupoLDDF9ex8fgEYPoe', 'Chris O', 'salesperson', 
 '["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]'::jsonb, TRUE);

-- ============================================================================
-- SAMPLE MANAGEMENT COMPANIES
-- ============================================================================

INSERT INTO management_companies (name, phone, email, website, notes, created_by) VALUES
('Greystar', '704-555-0100', 'contact@greystar.com', 'https://www.greystar.com', 
 'Large property management company - multiple properties', 'system'),
('MAA (Mid-America Apartment Communities)', '704-555-0200', 'info@maac.com', 'https://www.maac.com',
 'Major apartment REIT in Charlotte area', 'system'),
('Lincoln Property Company', '704-555-0300', 'charlotte@lincolnapts.com', 'https://www.lincolnapts.com',
 'National property manager with Charlotte presence', 'system'),
('Cushman & Wakefield', '704-555-0400', 'charlotte@cushwake.com', 'https://www.cushmanwakefield.com',
 'Commercial property management', 'system'),
('Independent Owner', NULL, NULL, NULL,
 'Catch-all for properties not managed by a company', 'system');

-- ============================================================================
-- SAMPLE CUSTOMERS (for testing)
-- ============================================================================

-- Note: These are example customers. Real customer data will be imported from ServiceFusion.

DO $$
DECLARE
    greystar_id INTEGER;
    maa_id INTEGER;
    independent_id INTEGER;
BEGIN
    -- Get management company IDs
    SELECT id INTO greystar_id FROM management_companies WHERE name = 'Greystar';
    SELECT id INTO maa_id FROM management_companies WHERE name LIKE 'MAA%';
    SELECT id INTO independent_id FROM management_companies WHERE name = 'Independent Owner';
    
    -- Sample multi-family properties
    INSERT INTO customers (property_name, customer_type, address, city, state, zip, 
                          management_company_id, status, payment_terms, notes, created_by)
    VALUES
    ('Oakwood Apartments', 'Multi Family', '123 Main St', 'Charlotte', 'NC', '28202',
     greystar_id, 'Active', 'Net 30', 'Regular carpet cleaning customer', 'system'),
    ('Riverside Commons', 'Multi Family', '456 River Rd', 'Charlotte', 'NC', '28203',
     maa_id, 'Active', 'Net 30', 'Both Get a Grip and Kleanit customer', 'system'),
    ('Sunset Village', 'Multi Family', '789 Sunset Blvd', 'Charlotte', 'NC', '28204',
     independent_id, 'Active', 'Due on Receipt', 'Independent owner - direct contact', 'system');
    
    RAISE NOTICE '✓ Sample customers created';
END $$;

-- ============================================================================
-- SAMPLE CUSTOMER CONTACTS (for testing)
-- ============================================================================

DO $$
DECLARE
    oakwood_id INTEGER;
    riverside_id INTEGER;
    sunset_id INTEGER;
BEGIN
    -- Get customer IDs
    SELECT id INTO oakwood_id FROM customers WHERE property_name = 'Oakwood Apartments';
    SELECT id INTO riverside_id FROM customers WHERE property_name = 'Riverside Commons';
    SELECT id INTO sunset_id FROM customers WHERE property_name = 'Sunset Village';
    
    -- Contacts for Oakwood Apartments
    INSERT INTO customer_contacts (customer_id, first_name, last_name, title, 
                                   office_phone, office_email, is_primary, created_by)
    VALUES
    (oakwood_id, 'Sarah', 'Johnson', 'Property Manager', '704-555-1001', 
     'sjohnson@oakwood.com', TRUE, 'system'),
    (oakwood_id, 'Mike', 'Davis', 'Maintenance Supervisor', '704-555-1002', 
     'mdavis@oakwood.com', FALSE, 'system');
    
    -- Contacts for Riverside Commons
    INSERT INTO customer_contacts (customer_id, first_name, last_name, title, 
                                   office_phone, office_email, is_primary, created_by)
    VALUES
    (riverside_id, 'Jennifer', 'Smith', 'Regional Manager', '704-555-2001', 
     'jsmith@riverside.com', TRUE, 'system');
    
    -- Contacts for Sunset Village
    INSERT INTO customer_contacts (customer_id, first_name, last_name, title, 
                                   office_phone, mobile_phone, office_email, is_primary, created_by)
    VALUES
    (sunset_id, 'Tom', 'Anderson', 'Owner', '704-555-3001', '704-555-3099',
     'tanderson@gmail.com', TRUE, 'system');
    
    RAISE NOTICE '✓ Sample contacts created';
END $$;

-- ============================================================================
-- SAMPLE CUSTOMER TAGS (for testing)
-- ============================================================================

DO $$
DECLARE
    oakwood_id INTEGER;
    riverside_id INTEGER;
BEGIN
    SELECT id INTO oakwood_id FROM customers WHERE property_name = 'Oakwood Apartments';
    SELECT id INTO riverside_id FROM customers WHERE property_name = 'Riverside Commons';
    
    INSERT INTO customer_tags (customer_id, tag_name, created_by) VALUES
    (oakwood_id, 'High Volume', 'system'),
    (oakwood_id, 'Preferred Customer', 'system'),
    (riverside_id, 'Multi-Service', 'system'),
    (riverside_id, 'VIP', 'system');
    
    RAISE NOTICE '✓ Sample tags created';
END $$;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '════════════════════════════════════════════════════════';
    RAISE NOTICE '✓ Seed data inserted successfully';
    RAISE NOTICE '════════════════════════════════════════════════════════';
    RAISE NOTICE 'Users created:';
    RAISE NOTICE '  - 3 Admins (chris, michele, mike)';
    RAISE NOTICE '  - 3 Managers (patrick, walter, mikeyc)';
    RAISE NOTICE '  - 1 Salesperson (chriso)';
    RAISE NOTICE '';
    RAISE NOTICE 'Sample data created:';
    RAISE NOTICE '  - 5 Management companies';
    RAISE NOTICE '  - 3 Customers';
    RAISE NOTICE '  - 4 Customer contacts';
    RAISE NOTICE '  - 4 Customer tags';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: Default password is "fieldkit2026"';
    RAISE NOTICE 'Change passwords immediately after first login!';
    RAISE NOTICE '════════════════════════════════════════════════════════';
END $$;
