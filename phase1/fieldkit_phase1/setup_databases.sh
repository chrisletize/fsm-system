#!/bin/bash
# FieldKit Phase 1: Database Setup Script
# Created: 2026-02-10
# Purpose: Initialize all four company databases with complete schema

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_USER="${DB_USER:-postgres}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATABASE_DIR="$SCRIPT_DIR/database"

# Company databases
DATABASES=("fieldkit_getagrip" "fieldkit_kleanit_charlotte" "fieldkit_cts" "fieldkit_kleanit_sf")

# Company names for display
declare -A COMPANY_NAMES
COMPANY_NAMES["fieldkit_getagrip"]="Get a Grip Charlotte"
COMPANY_NAMES["fieldkit_kleanit_charlotte"]="Kleanit Charlotte"
COMPANY_NAMES["fieldkit_cts"]="CTS of Raleigh"
COMPANY_NAMES["fieldkit_kleanit_sf"]="Kleanit South Florida"

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}     FieldKit Phase 1: Database Initialization${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Check if PostgreSQL is running
if ! pg_isready -U "$DB_USER" > /dev/null 2>&1; then
    echo -e "${RED}✗ Error: PostgreSQL is not running or not accessible${NC}"
    echo "  Please start PostgreSQL and try again"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is running${NC}"
echo ""

# Step 1: Create databases
echo -e "${YELLOW}Step 1: Creating four company databases...${NC}"
psql -U "$DB_USER" -f "$DATABASE_DIR/init_databases.sql"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Databases created successfully${NC}"
else
    echo -e "${RED}✗ Error creating databases${NC}"
    exit 1
fi
echo ""

# Step 2: Apply schema to each database
echo -e "${YELLOW}Step 2: Applying schema to each database...${NC}"

for db in "${DATABASES[@]}"; do
    echo ""
    echo -e "${BLUE}  Processing: ${COMPANY_NAMES[$db]} ($db)${NC}"
    
    # Core tables (users, management companies)
    echo "    → Creating core tables..."
    psql -U "$DB_USER" -d "$db" -f "$DATABASE_DIR/schema/01_core_tables.sql" -q
    
    # Customer tables
    echo "    → Creating customer tables..."
    psql -U "$DB_USER" -d "$db" -f "$DATABASE_DIR/schema/02_customers.sql" -q
    
    # Seed data
    echo "    → Inserting seed data..."
    psql -U "$DB_USER" -d "$db" -f "$DATABASE_DIR/seed/seed_data.sql" -q
    
    echo -e "    ${GREEN}✓ ${COMPANY_NAMES[$db]} complete${NC}"
done

echo ""
echo -e "${GREEN}✓ All databases configured successfully${NC}"
echo ""

# Step 3: Verify installation
echo -e "${YELLOW}Step 3: Verifying installation...${NC}"

for db in "${DATABASES[@]}"; do
    # Count tables
    TABLE_COUNT=$(psql -U "$DB_USER" -d "$db" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
    
    # Count users
    USER_COUNT=$(psql -U "$DB_USER" -d "$db" -t -c "SELECT COUNT(*) FROM users;" | tr -d ' ')
    
    # Count customers
    CUSTOMER_COUNT=$(psql -U "$DB_USER" -d "$db" -t -c "SELECT COUNT(*) FROM customers;" | tr -d ' ')
    
    echo "  $db:"
    echo "    Tables: $TABLE_COUNT"
    echo "    Users: $USER_COUNT"
    echo "    Customers: $CUSTOMER_COUNT"
done

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}     ✓ FieldKit Phase 1 Setup Complete!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  1. Update user passwords (default is 'fieldkit2026')"
echo "  2. Import real customer data from ServiceFusion"
echo "  3. Test authentication system"
echo "  4. Build Flask backend for Phase 1"
echo ""
echo "Database connection examples:"
echo "  psql -U $DB_USER -d fieldkit_getagrip"
echo "  psql -U $DB_USER -d fieldkit_kleanit_charlotte"
echo ""
echo -e "${YELLOW}IMPORTANT: Change default passwords immediately!${NC}"
echo ""
