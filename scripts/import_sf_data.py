#!/usr/bin/env python3
"""
Import ServiceFusion invoice data into FSM database
Usage: python3 scripts/import_sf_data.py <excel_file> <company_name>
Example: python3 scripts/import_sf_data.py Report_Invoice.xlsx "Get a Grip Resurfacing of Charlotte"
"""

import sys
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create database connection from environment variables"""
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )

def parse_date(date_str):
    """Parse date from ServiceFusion format"""
    if pd.isna(date_str):
        return None
    try:
        return pd.to_datetime(date_str).date()
    except:
        return None

def parse_decimal(value):
    """Parse decimal values, handling NaN"""
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except:
        return 0.0

def import_invoices(excel_file, company_name):
    """Import invoices from ServiceFusion Excel export"""
    
    print(f"Reading Excel file: {excel_file}")
    
    # Read Excel file, skipping metadata rows (header is at row 5)
    df = pd.read_excel(excel_file, header=5)
    
    print(f"Found {len(df)} invoices")
    print(f"Columns: {list(df.columns)[:5]}...")  # Show first 5 columns
    
    # Connect to database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get company ID
    cur.execute("SELECT id FROM companies WHERE name = %s", (company_name,))
    company_result = cur.fetchone()
    if not company_result:
        print(f"Error: Company '{company_name}' not found in database")
        print("Available companies:")
        cur.execute("SELECT name FROM companies")
        for row in cur.fetchall():
            print(f"  - {row[0]}")
        conn.close()
        return
    
    company_id = company_result[0]
    print(f"Importing for company: {company_name} (ID: {company_id})")
    
    customers_added = 0
    invoices_added = 0
    errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Extract customer data
            account_number = str(row.get('Account Number', '')).strip()
            customer_name = str(row.get('Customer Name', '')).strip()
            
            if not customer_name or customer_name == 'nan':
                print(f"Skipping row {idx}: No customer name")
                continue
            
            # Insert or get customer
            cur.execute("""
                INSERT INTO customers (
                    company_id, account_number, customer_name,
                    contact_first_name, contact_last_name, contact_email, contact_phone,
                    parent_account_name,
                    bill_to_address_1, bill_to_address_2, bill_to_city, bill_to_state, bill_to_zip,
                    service_location_name, service_location_address_1, service_location_address_2,
                    service_location_city, service_location_state, service_location_zip
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (company_id, account_number) DO UPDATE 
                SET customer_name = EXCLUDED.customer_name
                RETURNING id
            """, (
                company_id,
                account_number if account_number != 'nan' else None,
                customer_name,
                str(row.get('Contact First Name', '')).strip() or None,
                str(row.get('Contact Last Name', '')).strip() or None,
                str(row.get('Contact Email 1', '')).strip() or None,
                str(row.get('Contact Phone 1', '')).strip() or None,
                str(row.get('Parent Account Name', '')).strip() or None,
                str(row.get('Bill To Location Address 1', '')).strip() or None,
                str(row.get('Bill To Location Address 2', '')).strip() or None,
                str(row.get('Bill To City', '')).strip() or None,
                str(row.get('Bill To State/Province', '')).strip() or None,
                str(row.get('Bill To Zip/Post Code', '')).strip() or None,
                str(row.get('Service Location Name', '')).strip() or None,
                str(row.get('Service Location Address 1', '')).strip() or None,
                str(row.get('Service Location Address 2', '')).strip() or None,
                str(row.get('Service Location City', '')).strip() or None,
                str(row.get('Service Location State/Province', '')).strip() or None,
                str(row.get('Service Location Zip/Post Code', '')).strip() or None
            ))
            
            customer_id = cur.fetchone()[0]
            if cur.rowcount == 1:
                customers_added += 1
            
            # Insert invoice
            invoice_number = str(row.get('Invoice#', '')).strip()
            if not invoice_number or invoice_number == 'nan':
                print(f"Skipping row {idx}: No invoice number")
                continue
            
            cur.execute("""
                INSERT INTO invoices (
                    company_id, customer_id, invoice_number, invoice_date, invoice_status,
                    invoice_total, invoice_total_due, service_total, product_total,
                    tax_total, tax_rate_name, discount_total, job_amount,
                    job_number, job_date, job_category, job_description,
                    assigned_tech, completion_notes, po_number, payment_terms,
                    payment_type, payment_date, mail_sent_by, mail_sent_date
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (company_id, invoice_number) DO UPDATE
                SET invoice_total_due = EXCLUDED.invoice_total_due,
                    invoice_status = EXCLUDED.invoice_status
            """, (
                company_id,
                customer_id,
                invoice_number,
                parse_date(row.get('Invoice Date')),
                str(row.get('Invoice Status', 'UNPAID')).strip(),
                parse_decimal(row.get('Invoice Total')),
                parse_decimal(row.get('Invoice Total Due')),
                parse_decimal(row.get('Service Total')),
                parse_decimal(row.get('Product Total')),
                parse_decimal(row.get('Tax Total')),
                str(row.get('Tax Rate Name', '')).strip() or None,
                parse_decimal(row.get('Discount Total')),
                parse_decimal(row.get('Job Amount')),
                str(row.get('Job#', '')).strip() or None,
                parse_date(row.get('Job Date')),
                str(row.get('Job Category', '')).strip() or None,
                str(row.get('Job Description', '')).strip() or None,
                str(row.get('Assigned Tech(s)', '')).strip() or None,
                str(row.get('Completion Notes', '')).strip() or None,
                str(row.get('PO#', '')).strip() or None,
                str(row.get('Payment Terms', '')).strip() or None,
                str(row.get('Payment Type', '')).strip() or None,
                parse_date(row.get('Payment Date')),
                str(row.get('Mail Sent By', '')).strip() or None,
                parse_date(row.get('Mail Sent Date'))
            ))
            
            if cur.rowcount == 1:
                invoices_added += 1
                
        except Exception as e:
            errors += 1
            print(f"Error on row {idx}: {e}")
            if errors > 10:
                print("Too many errors, stopping")
                break
    
    # Commit the transaction
    conn.commit()
    
    # Print summary
    print("\n" + "="*50)
    print("IMPORT SUMMARY")
    print("="*50)
    print(f"Customers added/updated: {customers_added}")
    print(f"Invoices added/updated: {invoices_added}")
    print(f"Errors: {errors}")
    
    # Show some stats
    cur.execute("""
        SELECT 
            invoice_status,
            COUNT(*) as count,
            SUM(invoice_total_due) as total_due
        FROM invoices
        WHERE company_id = %s
        GROUP BY invoice_status
    """, (company_id,))
    
    print(f"\nInvoice Status Breakdown for {company_name}:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} invoices, ${row[2]:,.2f} due")
    
    cur.close()
    conn.close()
    
    print("\n✅ Import complete!")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/import_sf_data.py <excel_file> <company_name>")
        print("\nAvailable companies:")
        print('  - "Kleanit Charlotte"')
        print('  - "Get a Grip Resurfacing of Charlotte"')
        print('  - "CTS of Raleigh"')
        print('  - "Kleanit South Florida"')
        sys.exit(1)
    
    excel_file = sys.argv[1]
    company_name = sys.argv[2]
    
    if not os.path.exists(excel_file):
        print(f"Error: File '{excel_file}' not found")
        sys.exit(1)
    
    import_invoices(excel_file, company_name)
