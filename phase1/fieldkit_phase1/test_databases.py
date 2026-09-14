#!/usr/bin/env python3
"""
FieldKit Phase 1: Database Connection Test
Created: 2026-02-10
Purpose: Verify all four databases are accessible with correct schema
"""

import sys
try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("Error: psycopg2 module not found")
    print("Install it with: pip install psycopg2-binary --break-system-packages")
    sys.exit(1)

# Database configuration
DATABASES = {
    'Get a Grip Charlotte': 'fieldkit_getagrip',
    'Kleanit Charlotte': 'fieldkit_kleanit_charlotte',
    'CTS of Raleigh': 'fieldkit_cts',
    'Kleanit South Florida': 'fieldkit_kleanit_sf'
}

DB_USER = 'postgres'
DB_PASSWORD = 'nygiants1'
DB_HOST = 'localhost'
DB_PORT = 5432

# Expected tables
EXPECTED_TABLES = [
    'users',
    'user_sessions',
    'management_companies',
    'customers',
    'customer_contacts',
    'customer_tags',
    'customer_notes'
]

def connect_db(db_name):
    """Connect to a database."""
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except psycopg2.Error as e:
        return None

def get_table_count(conn):
    """Get count of tables in database."""
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    count = cur.fetchone()[0]
    cur.close()
    return count

def get_missing_tables(conn):
    """Check which expected tables are missing."""
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    existing_tables = [row[0] for row in cur.fetchall()]
    cur.close()
    
    missing = [table for table in EXPECTED_TABLES if table not in existing_tables]
    return missing

def get_user_count(conn):
    """Get count of users."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
    except psycopg2.Error:
        count = 0
    cur.close()
    return count

def get_customer_count(conn):
    """Get count of customers."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM customers WHERE deleted_at IS NULL")
        count = cur.fetchone()[0]
    except psycopg2.Error:
        count = 0
    cur.close()
    return count

def test_trigger(conn):
    """Test that update trigger is working."""
    cur = conn.cursor()
    try:
        # Insert test management company
        cur.execute("""
            INSERT INTO management_companies (name, created_by)
            VALUES ('__TEST_COMPANY__', 'test_script')
            RETURNING id
        """)
        test_id = cur.fetchone()[0]
        
        # Get initial updated_at
        cur.execute("SELECT updated_at FROM management_companies WHERE id = %s", (test_id,))
        initial_time = cur.fetchone()[0]
        
        # Wait a moment and update
        import time
        time.sleep(1)
        
        cur.execute("""
            UPDATE management_companies 
            SET notes = 'Updated by test' 
            WHERE id = %s
        """, (test_id,))
        
        # Get new updated_at
        cur.execute("SELECT updated_at FROM management_companies WHERE id = %s", (test_id,))
        new_time = cur.fetchone()[0]
        
        # Clean up
        cur.execute("DELETE FROM management_companies WHERE id = %s", (test_id,))
        conn.commit()
        
        # Check if trigger worked
        return new_time > initial_time
        
    except psycopg2.Error as e:
        conn.rollback()
        return False
    finally:
        cur.close()

def main():
    """Run all database tests."""
    print("=" * 70)
    print("FieldKit Phase 1: Database Connection Test")
    print("=" * 70)
    print()
    
    all_good = True
    results = {}
    
    for company_name, db_name in DATABASES.items():
        print(f"Testing: {company_name} ({db_name})")
        print("-" * 70)
        
        # Test connection
        conn = connect_db(db_name)
        if conn is None:
            print(f"  ✗ Cannot connect to database")
            results[db_name] = False
            all_good = False
            print()
            continue
        
        print(f"  ✓ Connection successful")
        
        # Test table count
        table_count = get_table_count(conn)
        print(f"  ✓ Tables found: {table_count}")
        
        # Check for missing tables
        missing_tables = get_missing_tables(conn)
        if missing_tables:
            print(f"  ✗ Missing tables: {', '.join(missing_tables)}")
            results[db_name] = False
            all_good = False
        else:
            print(f"  ✓ All expected tables present")
        
        # Test user count
        user_count = get_user_count(conn)
        print(f"  ✓ Users: {user_count}")
        
        # Test customer count
        customer_count = get_customer_count(conn)
        print(f"  ✓ Customers: {customer_count}")
        
        # Test trigger
        if test_trigger(conn):
            print(f"  ✓ Update trigger working")
        else:
            print(f"  ✗ Update trigger failed")
            results[db_name] = False
            all_good = False
        
        conn.close()
        results[db_name] = True if db_name not in results else results[db_name]
        print()
    
    # Summary
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for company_name, db_name in DATABASES.items():
        status = "✓ PASS" if results.get(db_name, False) else "✗ FAIL"
        print(f"{company_name:30} {status}")
    
    print()
    
    if all_good:
        print("✓ All databases configured correctly!")
        print()
        print("Next steps:")
        print("  1. Change default user passwords")
        print("  2. Import real customer data")
        print("  3. Build Flask authentication backend")
        return 0
    else:
        print("✗ Some databases have issues - review errors above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
