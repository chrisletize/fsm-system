# FieldKit Phase 1: Quick Start Guide

## What You Have

Complete database initialization system for FieldKit with:

✅ Four separate PostgreSQL databases (one per company)  
✅ Full schema with audit trails on every table  
✅ User authentication with bcrypt password hashing  
✅ Multi-contact customer support  
✅ Seed data with 7 users and sample customers  
✅ Automated setup scripts  
✅ Testing utilities  

## File Structure

```
fieldkit_phase1/
├── README.md                      # Detailed documentation
├── QUICKSTART.md                  # This file
├── setup_databases.sh             # 🎯 RUN THIS FIRST
├── generate_password_hash.py      # Generate password hashes
├── test_databases.py              # Verify installation
└── database/
    ├── init_databases.sql         # Creates 4 databases
    ├── schema/
    │   ├── 01_core_tables.sql     # Users, sessions, management
    │   └── 02_customers.sql       # Customers, contacts, tags
    └── seed/
        └── seed_data.sql          # Initial data
```

## 3-Step Setup

### Step 1: Generate Password Hash

```bash
cd fieldkit_phase1
./generate_password_hash.py
```

Copy the hash output and update seed_data.sql:

```bash
# Use the hash from the script output
sed -i 's/\$2b\$12\$PLACEHOLDER/YOUR_HASH_HERE/g' database/seed/seed_data.sql
```

### Step 2: Run Setup

```bash
./setup_databases.sh
```

This creates:
- 4 databases (fieldkit_getagrip, fieldkit_kleanit_charlotte, fieldkit_cts, fieldkit_kleanit_sf)
- 8 tables per database
- 7 user accounts
- 5 management companies
- 3 sample customers with contacts

### Step 3: Test Installation

```bash
./test_databases.py
```

Should show "✓ PASS" for all four databases.

## What's Created

### Databases

1. **fieldkit_getagrip** - Get a Grip Charlotte (surface resurfacing)
2. **fieldkit_kleanit_charlotte** - Kleanit Charlotte (carpet cleaning, high volume)
3. **fieldkit_cts** - CTS of Raleigh (umbrella company)
4. **fieldkit_kleanit_sf** - Kleanit South Florida (carpet cleaning)

### Tables (per database)

1. **users** - Authentication (7 users with bcrypt passwords)
2. **user_sessions** - Active session tracking
3. **management_companies** - Property management firms (5 sample companies)
4. **customers** - Properties (3 sample customers)
5. **customer_contacts** - Multiple contacts per customer (4 sample contacts)
6. **customer_tags** - Flexible categorization
7. **customer_notes** - Activity history log

### User Accounts

**Default password: fieldkit2026** (CHANGE IMMEDIATELY!)

| Username | Name | Role | Access |
|----------|------|------|--------|
| chris | Chris Letize | Admin | All companies |
| michele | Michele | Admin | All companies |
| mike | Mike | Admin | All companies |
| patrick | Patrick | Manager | CTS only |
| walter | Walter | Manager | Kleanit Charlotte only |
| mikeyc | Mikey C | Manager | Kleanit SF only |
| chriso | Chris O | Salesperson | All companies |

## Test Database Access

```bash
# Connect to Get a Grip database
psql -U postgres -d fieldkit_getagrip

# List tables
\dt

# Check users
SELECT username, full_name, role FROM users;

# Check customers
SELECT property_name, customer_type, status FROM customers;

# Exit
\q
```

## Next Steps

After successful database setup:

### 1. Secure the System
```bash
# Change all user passwords
psql -U postgres -d fieldkit_getagrip
# Then use UPDATE statements with bcrypt hashes
```

### 2. Import Real Data
- Export customer data from ServiceFusion
- Import into appropriate databases
- Verify data integrity

### 3. Build Backend (Phase 1 continues)
- Flask authentication API
- Company switcher logic
- Customer CRUD endpoints
- Search functionality

### 4. Build Frontend
- Login page with bcrypt verification
- Company switcher UI (color-coded)
- Customer management interface

## Troubleshooting

### PostgreSQL Not Running
```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Permission Errors
```bash
# Check if postgres user exists
psql -U postgres -c "SELECT version();"

# If using different user, set environment variable
export DB_USER=yourusername
./setup_databases.sh
```

### Missing Python Modules
```bash
pip install bcrypt psycopg2-binary --break-system-packages
```

### Database Already Exists
```bash
# The setup script includes DROP commands
# If issues persist, manually drop:
psql -U postgres -c "DROP DATABASE fieldkit_getagrip;"
# ... repeat for other databases
./setup_databases.sh
```

## Key Architecture Decisions

✅ **Four Separate Databases** - Not multi-tenant  
   → Performance isolation, true data separation

✅ **Comprehensive Audit Trails** - Every table  
   → created_at, created_by, updated_at, updated_by, deleted_at, deleted_by

✅ **Soft Deletes** - No hard deletes  
   → deleted_at timestamp preserves history

✅ **Multi-Contact Support** - Separate table  
   → Multiple contacts per customer property

✅ **Bcrypt Password Hashing** - Cost factor 12  
   → Industry standard security

✅ **JSONB for Flexibility** - company_access field  
   → Easy permission management

## Important Security Notes

⚠️ **Change default passwords immediately!**  
⚠️ Default password is "fieldkit2026" for all users  
⚠️ Use strong, unique passwords in production  
⚠️ Enable HTTPS in production  
⚠️ Configure firewall to restrict database access  

## Documentation

- **Full README**: See README.md in this directory
- **Architecture**: /docs/ARCHITECTURE.md in main repo
- **Database Schema**: /docs/DATABASE-SCHEMA.md in main repo
- **Decisions Log**: /docs/PROJECT-KNOWLEDGE/DECISIONS.md

## Support

Questions or issues? Check:
1. README.md (this directory) - Detailed documentation
2. Test output from test_databases.py
3. PostgreSQL logs: `sudo journalctl -u postgresql`
4. Script output for specific error messages

---

**Ready to build Phase 1!** 🚀

Database foundation complete. Next: Flask backend with authentication.
