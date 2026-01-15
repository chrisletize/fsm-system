#!/usr/bin/env python3
"""
Generate a simple text-based statement for testing
Usage: python3 scripts/generate_test_statement.py <customer_name>
"""

import sys
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, date

load_dotenv()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )

def calculate_aging_days(invoice_date, reference_date=None):
    """Calculate how many days past due an invoice is"""
    if reference_date is None:
        reference_date = date.today()
    
    days = (reference_date - invoice_date).days
    return days

def get_aging_bucket(days):
    """Determine which aging bucket an invoice falls into"""
    if days < 0:
        return "FUTURE"
    elif days <= 30:
        return "CURRENT"
    elif days <= 60:
        return "30 DAYS"
    elif days <= 90:
        return "60 DAYS"
    else:
        return "90+ DAYS"

def generate_statement(customer_name_search):
    """Generate a statement for a customer"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find customer
    cur.execute("""
        SELECT id, customer_name, account_number,
               contact_email, contact_phone,
               service_location_address_1, service_location_city,
               service_location_state, service_location_zip
        FROM customers
        WHERE customer_name ILIKE %s
        LIMIT 1
    """, (f'%{customer_name_search}%',))
    
    customer = cur.fetchone()
    if not customer:
        print(f"Customer matching '{customer_name_search}' not found")
        cur.close()
        conn.close()
        return
    
    customer_id, name, account_num, email, phone, addr, city, state, zip_code = customer
    
    # Get unpaid invoices
    cur.execute("""
        SELECT invoice_number, invoice_date, invoice_total, invoice_total_due,
               job_description, invoice_status
        FROM invoices
        WHERE customer_id = %s
          AND invoice_total_due > 0
        ORDER BY invoice_date
    """, (customer_id,))
    
    invoices = cur.fetchall()
    
    # Calculate aging
    aging_buckets = {
        "CURRENT": 0,
        "30 DAYS": 0,
        "60 DAYS": 0,
        "90+ DAYS": 0
    }
    
    today = date.today()
    invoice_details = []
    
    for inv in invoices:
        inv_num, inv_date, inv_total, inv_due, description, status = inv
        days = calculate_aging_days(inv_date, today)
        bucket = get_aging_bucket(days)
        
        if bucket in aging_buckets:
            aging_buckets[bucket] += float(inv_due)
        
        invoice_details.append({
            'number': inv_num,
            'date': inv_date,
            'total': float(inv_total),
            'due': float(inv_due),
            'days': days,
            'bucket': bucket,
            'description': description[:50] if description else "N/A"
        })
    
    total_due = sum(aging_buckets.values())
    
    # Print statement
    print("\n" + "="*80)
    print("ACCOUNT STATEMENT")
    print("="*80)
    print(f"Statement Date: {today.strftime('%B %d, %Y')}")
    print(f"\nCustomer: {name}")
    print(f"Account #: {account_num or 'N/A'}")
    if addr:
        print(f"Address: {addr}")
        print(f"         {city}, {state} {zip_code}")
    if email:
        print(f"Email: {email}")
    if phone:
        print(f"Phone: {phone}")
    
    print("\n" + "-"*80)
    print("AGING SUMMARY")
    print("-"*80)
    print(f"{'Bucket':<15} {'Amount':>15}")
    print("-"*80)
    for bucket in ["CURRENT", "30 DAYS", "60 DAYS", "90+ DAYS"]:
        amount = aging_buckets[bucket]
        if amount > 0:
            print(f"{bucket:<15} ${amount:>14,.2f}")
    print("-"*80)
    print(f"{'TOTAL DUE':<15} ${total_due:>14,.2f}")
    print("="*80)
    
    print("\nINVOICE DETAILS")
    print("-"*80)
    print(f"{'Invoice #':<12} {'Date':<12} {'Total':>12} {'Due':>12} {'Days':>6}  {'Age':<10}  {'Description':<30}")
    print("-"*80)
    
    for inv in invoice_details:
        print(f"{inv['number']:<12} {inv['date'].strftime('%m/%d/%Y'):<12} "
              f"${inv['total']:>11,.2f} ${inv['due']:>11,.2f} {inv['days']:>6}  "
              f"{inv['bucket']:<10}  {inv['description']:<30}")
    
    print("-"*80)
    print(f"{'TOTAL':<12} {'':<12} {'':<12} ${total_due:>11,.2f}")
    print("="*80)
    
    print(f"\nTotal Invoices: {len(invoices)}")
    print(f"Amount Due: ${total_due:,.2f}")
    
    if total_due > 0:
        print("\n⚠️  PAYMENT REQUIRED")
        print("Please remit payment to the address on file.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 scripts/generate_test_statement.py <customer_name>")
        print("\nExample: python3 scripts/generate_test_statement.py 'Bella Vista'")
        sys.exit(1)
    
    customer_search = sys.argv[1]
    generate_statement(customer_search)
