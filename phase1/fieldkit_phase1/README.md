# FieldKit Phase 1: Database Setup

## Overview

This directory contains the complete database initialization scripts for FieldKit Phase 1. It creates four separate PostgreSQL databases (one per company) with identical schemas.

## Directory Structure

```
fieldkit_phase1/
├── setup_databases.sh           # Master setup script (run this)
├── generate_password_hash.py    # Generate bcrypt password hashes
├── database/
│   ├── init_databases.sql       # Creates four databases
│   ├── schema/
│   │   ├── 01_core_tables.sql   # Users, sessions, management companies
│   │   └── 02_customers.sql     # Customers, contacts, tags, notes
│   └── seed/
│       └── seed_data.sql        # Initial users and sample data
└── README.md                    # This file
```

## Four Separate Databases

FieldKit uses **four independent databases** for data separation and performance isolation:

| Database | Company | Purpose |
|----------|---------|---------|
| `fieldkit_getagrip` | Get a Grip Charlotte | Surface resurfacing |
| `fieldkit_kleanit_charlotte` | Kleanit Charlotte | Carpet cleaning (high volume) |
| `fieldkit_cts` | CTS of Raleigh | Umbrella company |
| `fieldkit_kleanit_sf` | Kleanit South Florida | Carpet cleaning |

## Prerequisites

1. **PostgreSQL 16** installed and running
2. **Python 3.11+** with bcrypt module
3. **psql** command-line tool
4. **bash** shell

### Install bcrypt (if needed)

```bash
pip install bcrypt --break-system-packages
```

## Quick Start

### 1. Generate Password Hash

First, generate a bcrypt hash for the default password:

```bash
cd /home/chrisletize/fsm-system/database
python3 generate_password_hash.py
```

This will output a bcrypt hash. Copy it and update `seed/seed_data.sql`:

```bash
# Replace placeholder with actual hash (output from script above)
sed -i 's/\$2b\$12\$PLACEHOLDER/YOUR_HASH_HERE/g' database/seed/seed_data.sql
```

### 2. Run Setup Script

Execute the master setup script:

```bash
chmod +x setup_databases.sh
./setup_databases.sh
```

This script will:
1. ✓ Create four databases
2. ✓ Apply core schema (users, management companies)
3. ✓ Apply customer schema (customers, contacts, tags, notes)
4. ✓ Insert seed data (7 users, 5 management companies, 3 sample customers)
5. ✓ Verify installation

### 3. Verify Installation

Connect to a database and verify:

```bash
# Connect to Get a Grip database
psql -U postgres -d fieldkit_getagrip

# Check tables
\dt

# Check users
SELECT username, full_name, role, company_access FROM users;

# Check customers
SELECT property_name, customer_type, status FROM customers;

# Exit
\q
```

## Database Schema

### Core Tables

- **users**: Authentication and authorization (bcrypt passwords)
- **user_sessions**: Active session tracking
- **management_companies**: Property management firms
- **customers**: Properties (multi-family, commercial, residential)
- **customer_contacts**: Multiple contacts per customer
- **customer_tags**: Flexible categorization
- **customer_notes**: Activity history log

### Audit Trails

Every table includes:
- `created_at`, `created_by`
- `updated_at`, `updated_by` (auto-updated via trigger)
- `deleted_at`, `deleted_by` (soft deletes)

## Seed Users

Default password for all users: **fieldkit2026**

### Admins (Full access to all companies)
- `chris` - Chris Letize
- `michele` - Michele
- `mike` - Mike

### Managers (Company-specific access)
- `patrick` - CTS of Raleigh
- `walter` - Kleanit Charlotte
- `mikeyc` - Kleanit South Florida

### Salespeople (All companies)
- `chriso` - Chris O

**⚠️ IMPORTANT: Change default passwords immediately after setup!**

## Manual Database Operations

### Create Databases Only

```bash
psql -U postgres -f database/init_databases.sql
```

### Apply Schema to Single Database

```bash
# Core tables
psql -U postgres -d fieldkit_getagrip -f database/schema/01_core_tables.sql

# Customer tables
psql -U postgres -d fieldkit_getagrip -f database/schema/02_customers.sql

# Seed data
psql -U postgres -d fieldkit_getagrip -f database/seed/seed_data.sql
```

### Drop and Recreate

```bash
# Drop all databases (WARNING: Deletes all data!)
psql -U postgres -c "DROP DATABASE IF EXISTS fieldkit_getagrip;"
psql -U postgres -c "DROP DATABASE IF EXISTS fieldkit_kleanit_charlotte;"
psql -U postgres -c "DROP DATABASE IF EXISTS fieldkit_cts;"
psql -U postgres -c "DROP DATABASE IF EXISTS fieldkit_kleanit_sf;"

# Run setup again
./setup_databases.sh
```

## Testing Database Setup

### Test User Authentication Schema

```sql
-- Connect to any database
psql -U postgres -d fieldkit_getagrip

-- Check user with JSON company access
SELECT 
    username, 
    full_name, 
    role, 
    company_access::text,
    is_active
FROM users 
WHERE username = 'chris';

-- Should show: ["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]
```

### Test Customer Multi-Contact Support

```sql
-- Get customer with all contacts
SELECT 
    c.property_name,
    cc.first_name || ' ' || cc.last_name as contact_name,
    cc.title,
    cc.office_phone,
    cc.office_email,
    cc.is_primary
FROM customers c
LEFT JOIN customer_contacts cc ON c.id = cc.customer_id
WHERE c.property_name = 'Oakwood Apartments'
ORDER BY cc.is_primary DESC, cc.last_name;
```

### Test Soft Deletes

```sql
-- Soft delete a customer
UPDATE customers 
SET deleted_at = CURRENT_TIMESTAMP, 
    deleted_by = 'chris'
WHERE property_name = 'Sunset Village';

-- Verify it's hidden from normal queries
SELECT property_name, status, deleted_at 
FROM customers 
WHERE deleted_at IS NULL;

-- Restore the customer
UPDATE customers 
SET deleted_at = NULL, 
    deleted_by = NULL
WHERE property_name = 'Sunset Village';
```

## Next Steps

After successful database setup:

1. **Change Passwords**: Update default passwords for all users
2. **Import Real Data**: Import customer data from ServiceFusion
3. **Build Backend**: Create Flask API for Phase 1
4. **Test Authentication**: Implement login system with bcrypt
5. **Build Company Switcher**: Create UI for switching between databases

## Troubleshooting

### PostgreSQL Not Running

```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# Enable on boot
sudo systemctl enable postgresql
```

### Permission Denied

```bash
# Grant privileges to your user
psql -U postgres -c "CREATE USER yourusername WITH SUPERUSER PASSWORD 'yourpassword';"

# Or update DB_USER in setup script
export DB_USER=yourusername
./setup_databases.sh
```

### bcrypt Module Missing

```bash
pip install bcrypt --break-system-packages

# Or using apt
sudo apt install python3-bcrypt
```

### Database Already Exists

The `init_databases.sql` script includes `DROP DATABASE IF EXISTS` commands. If you get errors, manually drop databases:

```bash
psql -U postgres -c "DROP DATABASE fieldkit_getagrip;"
# ... repeat for other databases
```

## Architecture Notes

### Why Four Separate Databases?

1. **Performance Isolation**: Kleanit Charlotte's 250 jobs/day won't impact other companies
2. **True Data Separation**: Zero risk of cross-company contamination
3. **Operational Independence**: Backup/migrate companies separately
4. **Future Scalability**: Can move companies to different servers

### Schema Consistency

All four databases have **identical schemas**. Schema changes must be applied to all four databases.

### Cross-Database Queries

Cross-database operations require multiple connections. This is by design for data separation. Phase 2 will add a coordination layer for contact sync between companies.

## Security Notes

- Passwords hashed with bcrypt (cost factor 12)
- No plain text passwords ever stored
- Session tokens for authentication
- HTTPS enforced in production
- Rate limiting on login attempts (5/minute)
- Session expiration after 24 hours

## Backup & Restore

### Backup All Databases

```bash
# Create backup directory
mkdir -p /backups/fieldkit

# Backup each database
pg_dump -U postgres -d fieldkit_getagrip -F c -f /backups/fieldkit/getagrip_$(date +%Y%m%d).dump
pg_dump -U postgres -d fieldkit_kleanit_charlotte -F c -f /backups/fieldkit/kleanit_charlotte_$(date +%Y%m%d).dump
pg_dump -U postgres -d fieldkit_cts -F c -f /backups/fieldkit/cts_$(date +%Y%m%d).dump
pg_dump -U postgres -d fieldkit_kleanit_sf -F c -f /backups/fieldkit/kleanit_sf_$(date +%Y%m%d).dump
```

### Restore Single Database

```bash
pg_restore -U postgres -d fieldkit_getagrip --clean --if-exists /backups/fieldkit/getagrip_20260210.dump
```

## Documentation

- Full architecture: `/docs/ARCHITECTURE.md`
- Complete schema reference: `/docs/DATABASE-SCHEMA.md`
- Development decisions: `/docs/PROJECT-KNOWLEDGE/DECISIONS.md`
- Current status: `/docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md`

---

**FieldKit Phase 1** - Built by Chris Letize with Claude  
Database setup complete. Ready for backend development!
