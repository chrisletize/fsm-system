#!/usr/bin/env python3
"""
FieldKit: ServiceFusion Customer Import
Created: 2026-02-10
Purpose: Import customers from ServiceFusion Excel export to FieldKit databases
"""

import sys
import openpyxl
import psycopg2
from psycopg2 import sql
from datetime import datetime

# Database configuration
DB_CONFIG = {
    'getagrip': 'fieldkit_getagrip',
    'kleanit_charlotte': 'fieldkit_kleanit_charlotte',
    'cts': 'fieldkit_cts',
    'kleanit_sf': 'fieldkit_kleanit_sf'
}

DB_USER = 'postgres'
DB_HOST = 'localhost'
DB_PORT = 5432

def connect_db(db_name, password):
    """Connect to a FieldKit database."""
    return psycopg2.connect(
        dbname=db_name,
        user=DB_USER,
        password=password,
        host=DB_HOST,
        port=DB_PORT
    )

def parse_sf_customer_list(filepath):
    """
    Parse ServiceFusion customer list Excel file.
    Returns list of customer dictionaries.
    """
    print(f"Reading {filepath}...")
    wb = openpyxl.load_workbook(filepath)
    sheet = wb.active
    
    # Find header row (contains "Customer Name")
    header_row = None
    for row_idx in range(1, 15):
        row_values = [cell.value for cell in sheet[row_idx]]
        if any(val and 'Customer Name' in str(val) for val in row_values):
            header_row = row_idx
            break
    
    if header_row is None:
        raise ValueError("Could not find header row with 'Customer Name'")
    
    # Extract headers
    headers = [cell.value for cell in sheet[header_row]]
    print(f"Found {len(headers)} columns, starting at row {header_row}")
    
    # Parse data rows
    customers = []
    for row_idx in range(header_row + 1, sheet.max_row + 1):
        row_data = {}
        for col_idx, header in enumerate(headers, 1):
            cell_value = sheet.cell(row_idx, col_idx).value
            if header:
                row_data[header] = cell_value
        
        # Skip empty rows
        if row_data.get('Customer Name'):
            customers.append(row_data)
    
    print(f"Parsed {len(customers)} customers")
    return customers

def determine_customer_type(customer_name, parent_account):
    """
    Determine customer type based on name and parent account.
    """
    name_lower = customer_name.lower() if customer_name else ''
    
    # Residential patterns
    if any(word in name_lower for word in ['residential', 'homeowner', 'personal']):
        return 'Residential'
    
    # Contractor patterns
    if any(word in name_lower for word in ['contractor', 'construction', 'builder']):
        return 'Contractors'
    
    # Multi-family patterns (most common for Get a Grip)
    if any(word in name_lower for word in ['apartment', 'complex', 'village', 'commons', 
                                             'place', 'pointe', 'landing', 'park', 'manor',
                                             'towers', 'ridge', 'crest', 'hills', 'estates']):
        return 'Multi Family'
    
    # Default to Commercial if has parent account, otherwise Multi Family
    if parent_account and parent_account.strip():
        return 'Commercial'
    
    return 'Multi Family'  # Default for Get a Grip

def find_or_create_management_company(cursor, parent_account, created_by='sf_import'):
    """
    Find existing management company or create new one.
    Returns management_company_id or None.
    """
    if not parent_account or not parent_account.strip():
        return None
    
    # Check if exists
    cursor.execute("""
        SELECT id FROM management_companies 
        WHERE name = %s AND deleted_at IS NULL
    """, (parent_account.strip(),))
    
    result = cursor.fetchone()
    if result:
        return result[0]
    
    # Create new management company
    cursor.execute("""
        INSERT INTO management_companies (name, created_by)
        VALUES (%s, %s)
        RETURNING id
    """, (parent_account.strip(), created_by))
    
    return cursor.fetchone()[0]

def import_customer(cursor, customer_data, created_by='sf_import'):
    """
    Import a single customer with contacts into database.
    Returns (customer_id, contacts_created_count).
    """
    # Extract customer data
    customer_name = customer_data.get('Customer Name', '').strip()
    if not customer_name:
        return None, 0
    
    parent_account = customer_data.get('Parent Account Name')
    account_number = customer_data.get('Account Number')
    is_active = customer_data.get('Is Active', 'Yes') == 'Yes'
    
    # Determine customer type
    customer_type = determine_customer_type(customer_name, parent_account)
    
    # Find or create management company
    management_company_id = find_or_create_management_company(cursor, parent_account, created_by)
    
    # Service location address
    address_1 = customer_data.get('Primary Service Location Address 1')
    address_2 = customer_data.get('Primary Service Location Address 2')
    city = customer_data.get('Primary Service Location City')
    
    # Fix state - convert full names to abbreviations and limit to 2 chars
    state_raw = customer_data.get('Primary Service Location State/Province', '')
    if state_raw:
        state_map = {
            'North Carolina': 'NC', 'South Carolina': 'SC', 'Georgia': 'GA',
            'Virginia': 'VA', 'Tennessee': 'TN', 'Florida': 'FL'
        }
        state = state_map.get(state_raw, state_raw[:2] if state_raw else None)
    else:
        state = None
    
    # Fix zip - limit to 10 characters (truncate extended zip+4)
    zip_raw = customer_data.get('Primary Service Location Zip/Postal Code', '')
    zip_code = str(zip_raw)[:10] if zip_raw else None
    
    # Tax settings
    is_taxable = customer_data.get('Is Taxable', 'Yes') == 'Yes'
    tax_item = customer_data.get('Tax Item Name')
    
    # Customer status
    status = 'Active' if is_active else 'Inactive'
    
    # Insert customer
    cursor.execute("""
        INSERT INTO customers (
            property_name, customer_type, address, address_2, city, state, zip,
            management_company_id, status, notes, created_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        customer_name, customer_type, address_1, address_2, city, state, zip_code,
        management_company_id, status,
        f"SF Account: {account_number}, Tax: {tax_item if is_taxable else 'Non-taxable'}",
        created_by
    ))
    
    customer_id = cursor.fetchone()[0]
    
    # Insert primary contact
    contacts_created = 0
    primary_first = customer_data.get('Primary Contact First Name')
    primary_last = customer_data.get('Primary Contact Last Name')
    
    if primary_first or primary_last:
        cursor.execute("""
            INSERT INTO customer_contacts (
                customer_id, first_name, last_name, title,
                office_phone, office_email, is_primary, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_id,
            primary_first or '',
            primary_last or customer_name,  # Use customer name if no last name
            customer_data.get('Primary Contact Job Title'),
            customer_data.get('Primary Contact Phone 1'),
            customer_data.get('Primary Contact Email 1'),
            True,
            created_by
        ))
        contacts_created += 1
    
    # Insert secondary contact if exists
    secondary_first = customer_data.get('Secondary Contact First Name')
    secondary_last = customer_data.get('Secondary Contact Last Name')
    
    if secondary_first or secondary_last:
        cursor.execute("""
            INSERT INTO customer_contacts (
                customer_id, first_name, last_name, title,
                office_phone, office_email, is_primary, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            customer_id,
            secondary_first or '',
            secondary_last or '',
            customer_data.get('Secondary Contact Job Title'),
            customer_data.get('Secondary Contact Phone 1'),
            customer_data.get('Secondary Contact Email 1'),
            False,
            created_by
        ))
        contacts_created += 1
    
    return customer_id, contacts_created

def main():
    """Main import process."""
    print("=" * 70)
    print("FieldKit: ServiceFusion Customer Import")
    print("=" * 70)
    print()
    
    # Get arguments
    if len(sys.argv) < 3:
        print("Usage: ./import_sf_customers.py <excel_file> <target_database>")
        print()
        print("Target database options:")
        print("  - getagrip")
        print("  - kleanit_charlotte")
        print("  - cts")
        print("  - kleanit_sf")
        print()
        print("Example:")
        print("  ./import_sf_customers.py Report_CustomerList.xlsx getagrip")
        return 1
    
    excel_file = sys.argv[1]
    target_db_key = sys.argv[2]
    
    if target_db_key not in DB_CONFIG:
        print(f"Error: Invalid database '{target_db_key}'")
        print(f"Valid options: {', '.join(DB_CONFIG.keys())}")
        return 1
    
    target_db = DB_CONFIG[target_db_key]
    
    # Get password
    import getpass
    db_password = getpass.getpass(f"PostgreSQL password for {DB_USER}: ")
    
    try:
        # Parse Excel file
        customers = parse_sf_customer_list(excel_file)
        
        # Connect to database
        print(f"\nConnecting to {target_db}...")
        conn = connect_db(target_db, db_password)
        cursor = conn.cursor()
        
        # Import customers
        print(f"\nImporting {len(customers)} customers...")
        imported = 0
        total_contacts = 0
        skipped = 0
        
        for idx, customer_data in enumerate(customers, 1):
            try:
                customer_id, contacts_count = import_customer(cursor, customer_data)
                if customer_id:
                    conn.commit()
                    imported += 1
                    total_contacts += contacts_count
                    if idx % 100 == 0:
                        print(f"  Processed {idx}/{len(customers)} customers...")
                else:
                    skipped += 1
            except Exception as e:
                conn.rollback()
                print(f"  Warning: Failed to import customer {idx}")
                print(f"    Error: {e}")
                print(f"    Customer: {customer_data.get('Customer Name', 'N/A')}")
                skipped += 1
                continue
        
        # Commit transaction
        conn.commit()
        cursor.close()
        conn.close()
        
        # Summary
        print()
        print("=" * 70)
        print("Import Summary")
        print("=" * 70)
        print(f"Total customers processed: {len(customers)}")
        print(f"Successfully imported:     {imported}")
        print(f"Contacts created:          {total_contacts}")
        print(f"Skipped:                   {skipped}")
        print()
        print(f"✓ Import to {target_db} complete!")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
