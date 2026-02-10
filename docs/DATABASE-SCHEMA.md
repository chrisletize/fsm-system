# FieldKit Database Schema

*Last Updated: 2026-02-10*

## Schema Overview

This document defines the complete database schema for FieldKit. Each of the four company databases (fieldkit_getagrip, fieldkit_kleanit_charlotte, fieldkit_cts, fieldkit_kleanit_sf) contains an identical schema structure.

---

## Global Conventions

### Audit Trail Columns (All Tables)

Every table includes comprehensive audit tracking:

```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
created_by VARCHAR(100),          -- Username who created
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_by VARCHAR(100),          -- Username who last modified
deleted_at TIMESTAMP NULL,        -- NULL = active, timestamp = soft deleted
deleted_by VARCHAR(100)           -- Who deleted the record
```

### Automatic Update Trigger

Applied to every table to auto-update `updated_at`:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Example application (repeat for each table)
CREATE TRIGGER update_customers_updated_at 
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### Naming Conventions

- **Tables**: snake_case, plural (customers, sales_visits)
- **Columns**: snake_case (property_name, customer_id)
- **Indexes**: idx_[table]_[column(s)] (idx_customers_name)
- **Foreign Keys**: fk_[table]_[referenced_table] (fk_invoices_customers)

---

## Core Customer Management

### `management_companies`

*Property management companies that own multiple properties*

```sql
CREATE TABLE management_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    website VARCHAR(255),
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_management_companies_name ON management_companies(name);
CREATE INDEX idx_management_companies_deleted ON management_companies(deleted_at);
```

**Purpose**: Ensures consistent naming, enables management-company-level reporting.

**Business Rules**:
- One management company can own many properties
- Used for tracking contact movements between properties
- Cross-database matching uses this for property identification

---

### `customers`

*Properties that are active or former customers*

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    property_name VARCHAR(255) NOT NULL,
    customer_type VARCHAR(50) NOT NULL, -- 'Multi Family', 'Contractors', 'Residential'
    
    -- Address
    address VARCHAR(500),
    address_2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(2),
    zip VARCHAR(10),
    
    -- Management
    management_company_id INTEGER REFERENCES management_companies(id),
    
    -- Customer status
    status VARCHAR(50) DEFAULT 'Active', -- 'Active', 'Inactive', 'On Hold'
    
    -- Billing preferences
    billing_email VARCHAR(255),
    payment_terms VARCHAR(50), -- 'Net 30', 'Due on Receipt', etc.
    
    -- Internal notes
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_customers_name ON customers(property_name);
CREATE INDEX idx_customers_type ON customers(customer_type);
CREATE INDEX idx_customers_management ON customers(management_company_id);
CREATE INDEX idx_customers_status ON customers(status);
CREATE INDEX idx_customers_deleted ON customers(deleted_at);

-- Full-text search index for property names
CREATE INDEX idx_customers_name_search ON customers USING gin(to_tsvector('english', property_name));
```

**Business Rules**:
- `property_name` is primary identifier (apartment complex name, contractor company, etc.)
- `customer_type` determines workflow differences
- `management_company_id` can be NULL for independent properties
- Soft delete preserves historical data

---

### `customer_contacts`

*Multiple contacts per customer (Property Managers, Maintenance Supervisors, etc.)*

```sql
CREATE TABLE customer_contacts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Contact info
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    title VARCHAR(150), -- 'Property Manager', 'Maintenance Supervisor', 'Regional Manager'
    
    office_phone VARCHAR(20),
    office_email VARCHAR(255),
    mobile_phone VARCHAR(20),
    
    is_primary BOOLEAN DEFAULT FALSE,
    
    -- Notes about this contact
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_customer_contacts_customer ON customer_contacts(customer_id);
CREATE INDEX idx_customer_contacts_name ON customer_contacts(last_name, first_name);
CREATE INDEX idx_customer_contacts_primary ON customer_contacts(customer_id, is_primary);
CREATE INDEX idx_customer_contacts_deleted ON customer_contacts(deleted_at);
```

**Business Rules**:
- Each customer can have multiple contacts
- One contact marked as `is_primary` (receives invoices/statements)
- Contacts tied to customer, not global (same person at different properties = different records)
- Cascade delete: removing customer removes contacts

---

## Invoices & Payments

### `invoices`

*Individual invoices for completed work*

```sql
CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    due_date DATE,
    
    -- Amounts
    subtotal DECIMAL(10,2) NOT NULL,
    tax_total DECIMAL(10,2) DEFAULT 0.00,
    invoice_total DECIMAL(10,2) NOT NULL,
    amount_paid DECIMAL(10,2) DEFAULT 0.00,
    amount_due DECIMAL(10,2) NOT NULL,
    
    -- Tax details
    tax_rate_name VARCHAR(100), -- 'Mecklenburg County 7.25%'
    
    -- Service details
    service_location_address VARCHAR(500),
    service_location_address_2 VARCHAR(255),
    service_description TEXT,
    
    -- Status
    invoice_status VARCHAR(50) DEFAULT 'Unpaid', -- 'Unpaid', 'Partial', 'Paid', 'Void'
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_invoices_customer ON invoices(customer_id);
CREATE INDEX idx_invoices_number ON invoices(invoice_number);
CREATE INDEX idx_invoices_date ON invoices(invoice_date DESC);
CREATE INDEX idx_invoices_status ON invoices(invoice_status);
CREATE INDEX idx_invoices_amount_due ON invoices(amount_due) WHERE amount_due > 0;
CREATE INDEX idx_invoices_deleted ON invoices(deleted_at);
```

**Business Rules**:
- `invoice_number` must be unique per company
- `amount_due` = `invoice_total` - `amount_paid`
- Tax fields support both taxable and non-taxable invoices
- Service location may differ from customer billing address

---

### `payments`

*Payments applied to invoices*

```sql
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    
    payment_date DATE NOT NULL,
    payment_amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(50), -- 'Check', 'Credit Card', 'Cash', 'ACH'
    
    reference_number VARCHAR(100), -- Check number, transaction ID
    
    notes TEXT,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_payments_invoice ON payments(invoice_id);
CREATE INDEX idx_payments_customer ON payments(customer_id);
CREATE INDEX idx_payments_date ON payments(payment_date DESC);
CREATE INDEX idx_payments_deleted ON payments(deleted_at);
```

**Business Rules**:
- Multiple payments can apply to one invoice (partial payments)
- Payment triggers invoice `amount_due` recalculation
- `customer_id` denormalized for faster customer payment history queries

---

## Sales System Tables

### `sales_prospects`

*Properties not yet customers (or dormant customers being re-prospected)*

```sql
CREATE TABLE sales_prospects (
    id SERIAL PRIMARY KEY,
    property_name VARCHAR(255) NOT NULL,
    
    -- Address
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(2),
    zip VARCHAR(10),
    
    management_company_id INTEGER REFERENCES management_companies(id),
    customer_type VARCHAR(50), -- 'Multi Family', 'Contractors', 'Residential'
    
    -- Contractor-specific
    contractor_company_name VARCHAR(255),
    active_projects INTEGER DEFAULT 0,
    
    -- Location tracking
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Former customer tracking
    is_former_customer BOOLEAN DEFAULT FALSE,
    customer_id INTEGER, -- Reference to customers table if was customer before
    former_customer_last_job DATE,
    
    -- Conversion tracking
    converted_to_customer BOOLEAN DEFAULT FALSE,
    converted_date DATE,
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_prospects_name ON sales_prospects(property_name);
CREATE INDEX idx_prospects_location ON sales_prospects(latitude, longitude);
CREATE INDEX idx_prospects_type ON sales_prospects(customer_type);
CREATE INDEX idx_prospects_converted ON sales_prospects(converted_to_customer);
CREATE INDEX idx_prospects_former ON sales_prospects(is_former_customer);
CREATE INDEX idx_prospects_deleted ON sales_prospects(deleted_at);
```

**Business Rules**:
- Separate from customers table to prevent accidental modification
- Can reference former customer via `customer_id`
- Location enables proximity-based queries
- Conversion tracking preserves sales history

---

### `sales_contacts`

*People salespeople meet (Property Managers, Maintenance Supervisors, etc.)*

```sql
CREATE TABLE sales_contacts (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    title VARCHAR(150),
    
    -- Contact information
    personal_phone VARCHAR(20),
    personal_email VARCHAR(255),
    office_phone VARCHAR(20),
    office_email VARCHAR(255),
    
    -- Current employment
    current_property_id INTEGER,
    current_property_type VARCHAR(20), -- 'prospect' or 'customer'
    
    notes TEXT,
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_sales_contacts_name ON sales_contacts(last_name, first_name);
CREATE INDEX idx_sales_contacts_property ON sales_contacts(current_property_id, current_property_type);
CREATE INDEX idx_sales_contacts_deleted ON sales_contacts(deleted_at);
```

**Business Rules**:
- Personal contact info = salesperson's relationship
- Office contact info = company property
- Can work at prospect or existing customer
- Notes field for relationship details

---

### `contact_property_history`

*Tracks contact movements between properties*

```sql
CREATE TABLE contact_property_history (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES sales_contacts(id) ON DELETE CASCADE,
    
    property_id INTEGER NOT NULL,
    property_type VARCHAR(20) NOT NULL, -- 'prospect' or 'customer'
    property_name VARCHAR(255), -- Denormalized for history
    
    started_date DATE,
    ended_date DATE,
    
    notes TEXT, -- Why they left, where they went
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_contact_history_contact ON contact_property_history(contact_id);
CREATE INDEX idx_contact_history_dates ON contact_property_history(contact_id, ended_date);
```

**Business Rules**:
- Tracks career movements (valuable for relationship building)
- Property name denormalized to preserve history if property renamed
- `ended_date` NULL = currently works there
- Cascade delete with contact (history tied to person)

---

### `sales_visits`

*Every interaction salesperson has with a property*

```sql
CREATE TABLE sales_visits (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    property_type VARCHAR(20) NOT NULL, -- 'prospect' or 'customer'
    
    visit_date DATE NOT NULL,
    visit_time TIME,
    
    -- Visit classification
    visit_tag VARCHAR(50), -- References visit_tags_config.tag_name
    contact_id INTEGER REFERENCES sales_contacts(id),
    
    notes TEXT,
    
    -- Follow-up tracking
    follow_up_needed BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    follow_up_completed BOOLEAN DEFAULT FALSE,
    
    -- Dormant customer investigation
    is_dormant_investigation BOOLEAN DEFAULT FALSE,
    dormancy_reason TEXT,
    dormancy_reported_to_management BOOLEAN DEFAULT FALSE,
    
    -- Location
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
);

CREATE INDEX idx_visits_property ON sales_visits(property_id, property_type);
CREATE INDEX idx_visits_date ON sales_visits(visit_date DESC);
CREATE INDEX idx_visits_contact ON sales_visits(contact_id);
CREATE INDEX idx_visits_followup ON sales_visits(follow_up_date) WHERE follow_up_needed = TRUE AND follow_up_completed = FALSE;
CREATE INDEX idx_visits_dormant ON sales_visits(is_dormant_investigation) WHERE is_dormant_investigation = TRUE;
CREATE INDEX idx_visits_tag ON sales_visits(visit_tag);
```

**Business Rules**:
- Every visit logged (builds activity history)
- `visit_tag` determines auto-calculated follow-up date
- Dormant investigations trigger management reports
- Location enables route optimization
- No delete (audit trail of all sales activity)

---

### `visit_tags_config`

*Customizable visit types with follow-up schedules*

```sql
CREATE TABLE visit_tags_config (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(50) NOT NULL UNIQUE,
    tag_description TEXT,
    default_followup_days INTEGER, -- NULL = no automatic follow-up
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default tags (insert during database initialization)
INSERT INTO visit_tags_config (tag_name, tag_description, default_followup_days, display_order) VALUES
('Leasing Agent Only', 'Could not reach decision-maker, left card', 14, 1),
('Brief chat', 'Short conversation under 5 minutes', 30, 2),
('Full meeting', 'Substantial discussion 15+ minutes', 21, 3),
('Hot lead', 'Expressed immediate interest', 5, 4),
('Warm lead', 'Interested but timing unclear', 21, 5),
('Cold/No interest', 'Not interested currently', 90, 6),
('Existing customer check-in', 'Relationship maintenance', 60, 7),
('Pricing requested', 'Needs quote or proposal', 3, 8),
('Follow-up scheduled', 'They asked for specific return date', NULL, 9);
```

**Business Rules**:
- Tag names must be unique
- `default_followup_days` auto-calculates next visit date
- `is_active = FALSE` retires old tags without deleting history
- `display_order` controls UI presentation order

---

### `approval_queue`

*Sales-to-customer update requests pending manager approval*

```sql
CREATE TABLE approval_queue (
    id SERIAL PRIMARY KEY,
    request_type VARCHAR(50) NOT NULL, -- 'add_contact', 'update_contact', 'convert_prospect'
    
    -- Target of change (direct columns for search)
    target_type VARCHAR(20), -- 'customer', 'prospect'
    target_id INTEGER,
    target_name VARCHAR(255),
    
    -- Contact info (for global search)
    contact_name VARCHAR(200),
    contact_phone VARCHAR(20),
    contact_email VARCHAR(255),
    
    -- Flexible additional details
    request_details JSONB,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'edited'
    submitted_by VARCHAR(100) NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    -- Cross-database sync (Phase 2)
    requires_cross_db_sync BOOLEAN DEFAULT FALSE,
    target_databases TEXT[],
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approval_status ON approval_queue(status, submitted_at DESC);
CREATE INDEX idx_approval_submitter ON approval_queue(submitted_by);
CREATE INDEX idx_approval_target ON approval_queue(target_type, target_id);
```

**Business Rules**:
- Hybrid approach: searchable fields as columns, extras in JSONB
- Daily digest reports pending approvals to managers
- Approved requests update customer database
- Audit trail preserved even after approval

**Example JSONB content**:
```json
{
  "action": "add_contact",
  "customer_id": 45,
  "contact": {
    "first_name": "Sarah",
    "last_name": "Johnson",
    "title": "Property Manager",
    "office_phone": "555-1234"
  }
}
```

---

### `dormancy_alerts_config`

*Per-company settings for customer dormancy detection*

```sql
CREATE TABLE dormancy_alerts_config (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    alert_after_weeks INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default settings (one row per database during setup)
-- fieldkit_getagrip:
INSERT INTO dormancy_alerts_config (company_name, alert_after_weeks) 
VALUES ('Get a Grip Charlotte', 8);

-- fieldkit_kleanit_charlotte:
INSERT INTO dormancy_alerts_config (company_name, alert_after_weeks) 
VALUES ('Kleanit Charlotte', 3);

-- fieldkit_cts:
INSERT INTO dormancy_alerts_config (company_name, alert_after_weeks) 
VALUES ('CTS Raleigh', 4);

-- fieldkit_kleanit_sf:
INSERT INTO dormancy_alerts_config (company_name, alert_after_weeks) 
VALUES ('Kleanit South Florida', 3);
```

**Business Rules**:
- Different thresholds per company (project vs high-volume services)
- Single row per database
- Updated via admin settings page

---

## User Management (Shared Schema)

*Note: User management may live in separate central database or duplicated per company*

### `users`

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, -- bcrypt hash
    full_name VARCHAR(200) NOT NULL,
    
    role VARCHAR(50) NOT NULL, -- 'admin', 'manager', 'salesperson', 'technician', 'office_staff'
    
    -- Company access as JSON array
    company_access JSONB NOT NULL,
    -- Examples:
    -- ['getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf'] - admin with all access
    -- ['kleanit_charlotte'] - manager of one company
    -- ['getagrip', 'kleanit_charlotte'] - access to multiple companies
    
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_active ON users(is_active);
```

**Business Rules**:
- Password stored as bcrypt hash (never plaintext)
- `company_access` controls which databases user can switch between
- `role` determines permissions within each company
- One user record shared across all companies

---

### `user_sessions`

*Active login sessions*

```sql
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    session_token VARCHAR(255) NOT NULL UNIQUE,
    
    current_company VARCHAR(50), -- Which database they're viewing
    
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    expires_at TIMESTAMP NOT NULL,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

**Business Rules**:
- Session expires after 24 hours or on logout
- `current_company` tracks which database user is viewing
- Cleanup job removes expired sessions nightly

---

## Reporting Tables

### `weekly_sales_reports`

*Generated reports cached for historical reference*

```sql
CREATE TABLE weekly_sales_reports (
    id SERIAL PRIMARY KEY,
    report_week_start DATE NOT NULL,
    report_week_end DATE NOT NULL,
    
    salesperson VARCHAR(100) NOT NULL,
    
    -- Summary metrics
    total_visits INTEGER,
    total_contacts_created INTEGER,
    total_contacts_updated INTEGER,
    prospects_added INTEGER,
    dormant_investigations INTEGER,
    hot_leads_count INTEGER,
    
    -- Full report data as JSON
    report_data JSONB,
    
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sales_reports_week ON weekly_sales_reports(report_week_start DESC);
CREATE INDEX idx_sales_reports_person ON weekly_sales_reports(salesperson);
```

**Business Rules**:
- Reports generated Monday morning
- Cached for fast access and historical comparison
- JSONB contains full breakdown by company, property details, etc.

---

## Indexes Summary

### Performance Optimization Strategy

**1. Foreign Key Indexes**
- Every foreign key column has index
- Enables fast JOIN operations
- Example: `idx_invoices_customer ON invoices(customer_id)`

**2. Search Indexes**
- Name columns: `idx_customers_name`, `idx_sales_contacts_name`
- Date columns: `idx_visits_date DESC` (newest first)
- Status/flag columns: `idx_customers_status`, `idx_invoices_status`

**3. Partial Indexes (Conditional)**
- Only index rows matching condition
- Saves space, improves performance
- Example: `WHERE amount_due > 0` (only unpaid invoices)
- Example: `WHERE deleted_at IS NULL` (only active records)

**4. Full-Text Search**
- GIN indexes for text search
- `idx_customers_name_search USING gin(to_tsvector('english', property_name))`
- Enables fast "contains" searches

**5. Composite Indexes**
- Multiple columns in one index
- Order matters (most selective first)
- Example: `idx_visits_property ON sales_visits(property_id, property_type)`

---

## Triggers & Functions

### Auto-Update Timestamp

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to every table (example)
CREATE TRIGGER update_customers_updated_at 
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Purpose**: Automatically tracks last modification time without manual code.

---

### Invoice Amount Due Recalculation

```sql
CREATE OR REPLACE FUNCTION recalculate_invoice_amount_due()
RETURNS TRIGGER AS $$
BEGIN
    -- Recalculate amount_due when payment inserted/updated/deleted
    UPDATE invoices
    SET amount_due = invoice_total - COALESCE((
        SELECT SUM(payment_amount)
        FROM payments
        WHERE invoice_id = NEW.invoice_id
        AND deleted_at IS NULL
    ), 0)
    WHERE id = NEW.invoice_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER recalc_amount_due_after_payment
    AFTER INSERT OR UPDATE OR DELETE ON payments
    FOR EACH ROW
    EXECUTE FUNCTION recalculate_invoice_amount_due();
```

**Purpose**: Keeps `amount_due` accurate when payments change.

---

## Migration Strategy

### Initial Setup Script

```bash
# Create all four databases
psql -U postgres -c "CREATE DATABASE fieldkit_getagrip;"
psql -U postgres -c "CREATE DATABASE fieldkit_kleanit_charlotte;"
psql -U postgres -c "CREATE DATABASE fieldkit_cts;"
psql -U postgres -c "CREATE DATABASE fieldkit_kleanit_sf;"

# Run schema on each database
for db in fieldkit_getagrip fieldkit_kleanit_charlotte fieldkit_cts fieldkit_kleanit_sf; do
    psql -U postgres -d $db -f database/migrations/001_initial_schema.sql
    psql -U postgres -d $db -f database/migrations/002_sales_system.sql
    psql -U postgres -d $db -f database/migrations/003_triggers.sql
    psql -U postgres -d $db -f database/seed/default_data.sql
done
```

### Future Schema Changes

**Process**:
1. Write migration script (e.g., `004_add_customer_portal.sql`)
2. Test on one database first (fieldkit_cts - smallest)
3. Verify no errors
4. Apply to remaining three databases
5. Update this schema document

**Rollback Plan**:
- Always include DOWN migration script
- Test rollback on dev database first
- Keep backups before major migrations

---

## Data Relationships Diagram

```
management_companies
    ↓ (owns)
customers ←→ customer_contacts (many)
    ↓
invoices ←→ payments (many)
    
sales_prospects
    ↓ (references via customer_id when former customer)
customers

sales_contacts ←→ contact_property_history (many)
    ↓
sales_visits

approval_queue
    ↓ (references)
customers OR sales_prospects

users
    ↓
user_sessions
```

---

## Query Patterns

### Common Queries for Optimization

**1. Customer Statement Query**
```sql
SELECT 
    c.property_name,
    c.address,
    i.invoice_number,
    i.invoice_date,
    i.invoice_total,
    i.amount_paid,
    i.amount_due,
    AGE(CURRENT_DATE, i.invoice_date) as age_days
FROM customers c
JOIN invoices i ON c.id = i.customer_id
WHERE c.id = :customer_id
    AND i.amount_due > 0
    AND i.deleted_at IS NULL
ORDER BY i.invoice_date DESC;
```

**2. Dormancy Detection Query**
```sql
SELECT 
    c.id,
    c.property_name,
    MAX(j.completed_date) as last_job_date,
    EXTRACT(WEEK FROM CURRENT_DATE - MAX(j.completed_date)) as weeks_since_last_job
FROM customers c
LEFT JOIN jobs j ON c.id = j.customer_id
WHERE c.deleted_at IS NULL
GROUP BY c.id
HAVING MAX(j.completed_date) < (CURRENT_DATE - INTERVAL '3 weeks')
    OR MAX(j.completed_date) IS NULL;
```

**3. Sales Visit Activity Report**
```sql
SELECT 
    DATE_TRUNC('week', visit_date) as week_start,
    COUNT(*) as total_visits,
    COUNT(DISTINCT property_id) as unique_properties,
    COUNT(*) FILTER (WHERE visit_tag = 'Hot lead') as hot_leads,
    COUNT(*) FILTER (WHERE is_dormant_investigation) as dormant_investigations
FROM sales_visits
WHERE created_by = :salesperson
    AND visit_date >= :start_date
    AND visit_date <= :end_date
GROUP BY week_start
ORDER BY week_start DESC;
```

**4. Proximity Search**
```sql
SELECT 
    id,
    property_name,
    address,
    (3959 * acos(
        cos(radians(:user_lat)) 
        * cos(radians(latitude)) 
        * cos(radians(longitude) - radians(:user_lng)) 
        + sin(radians(:user_lat)) 
        * sin(radians(latitude))
    )) AS distance_miles
FROM sales_prospects
WHERE deleted_at IS NULL
    AND latitude IS NOT NULL
    AND longitude IS NOT NULL
HAVING distance_miles < 5
ORDER BY distance_miles
LIMIT 20;
```

---

## Backup & Restore

### Daily Backup Script

```bash
#!/bin/bash
BACKUP_DIR="/backups/fieldkit"
DATE=$(date +%Y%m%d_%H%M%S)

for db in fieldkit_getagrip fieldkit_kleanit_charlotte fieldkit_cts fieldkit_kleanit_sf; do
    pg_dump -U postgres -d $db -F c -f "$BACKUP_DIR/${db}_${DATE}.dump"
done

# Keep last 30 days, delete older
find $BACKUP_DIR -name "*.dump" -mtime +30 -delete
```

### Restore Single Database

```bash
pg_restore -U postgres -d fieldkit_getagrip --clean --if-exists /backups/fieldkit/fieldkit_getagrip_20260210_020000.dump
```

---

## Performance Monitoring

### Slow Query Logging

```sql
-- Enable in postgresql.conf
log_min_duration_statement = 1000  -- Log queries > 1 second

-- View slow queries
SELECT 
    query,
    calls,
    total_time / calls as avg_time_ms,
    rows / calls as avg_rows
FROM pg_stat_statements
WHERE total_time / calls > 100
ORDER BY total_time DESC
LIMIT 20;
```

### Index Usage Analysis

```sql
-- Find unused indexes
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
    AND indexname NOT LIKE '%_pkey';
```

---

*This schema supports FieldKit's multi-company architecture with complete audit trails, flexible data structures, and performance-optimized queries.*
