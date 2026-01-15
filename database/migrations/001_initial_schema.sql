-- FSM System Database Schema - Initial Migration
-- Created: 2026-01-15
-- Purpose: Statement Generator (Phase 0)

-- Companies table (your 4 companies)
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    account_number VARCHAR(50),
    customer_name VARCHAR(255) NOT NULL,
    contact_first_name VARCHAR(100),
    contact_last_name VARCHAR(100),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(50),
    parent_account_name VARCHAR(255),
    bill_to_address_1 VARCHAR(255),
    bill_to_address_2 VARCHAR(255),
    bill_to_city VARCHAR(100),
    bill_to_state VARCHAR(50),
    bill_to_zip VARCHAR(20),
    service_location_name VARCHAR(255),
    service_location_address_1 VARCHAR(255),
    service_location_address_2 VARCHAR(255),
    service_location_city VARCHAR(100),
    service_location_state VARCHAR(50),
    service_location_zip VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, account_number)
);

-- Invoices table
CREATE TABLE IF NOT EXISTS invoices (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    invoice_number VARCHAR(50) NOT NULL,
    invoice_date DATE NOT NULL,
    invoice_status VARCHAR(50) NOT NULL,
    invoice_total DECIMAL(10, 2) NOT NULL,
    invoice_total_due DECIMAL(10, 2) NOT NULL,
    service_total DECIMAL(10, 2),
    product_total DECIMAL(10, 2),
    tax_total DECIMAL(10, 2),
    tax_rate_name VARCHAR(100),
    discount_total DECIMAL(10, 2),
    job_amount DECIMAL(10, 2),
    job_number VARCHAR(50),
    job_date DATE,
    job_category VARCHAR(100),
    job_description TEXT,
    assigned_tech VARCHAR(255),
    completion_notes TEXT,
    po_number VARCHAR(50),
    payment_terms VARCHAR(50),
    payment_type VARCHAR(50),
    payment_date DATE,
    mail_sent_by VARCHAR(100),
    mail_sent_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_id, invoice_number)
);

-- Create indexes for common queries
CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_invoices_company ON invoices(company_id);
CREATE INDEX idx_invoices_status ON invoices(invoice_status);
CREATE INDEX idx_invoices_date ON invoices(invoice_date);
CREATE INDEX idx_customers_company ON customers(company_id);
CREATE INDEX idx_customers_account ON customers(account_number);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables
CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_invoices_updated_at BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert the 4 companies
INSERT INTO companies (name) VALUES 
    ('Kleanit Charlotte'),
    ('Get a Grip Resurfacing of Charlotte'),
    ('CTS of Raleigh'),
    ('Kleanit South Florida')
ON CONFLICT (name) DO NOTHING;

-- Add comments for documentation
COMMENT ON TABLE companies IS 'The 4 service companies using the FSM system';
COMMENT ON TABLE customers IS 'Customer information across all companies';
COMMENT ON TABLE invoices IS 'Invoice records imported from ServiceFusion';
COMMENT ON COLUMN invoices.invoice_total_due IS 'Amount still owed (important for statements)';
COMMENT ON COLUMN invoices.invoice_status IS 'UNPAID, PAST DUE, PAID, etc';
