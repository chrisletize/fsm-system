#!/usr/bin/env python3
"""
FSM Statement Generator - Web Interface
Simple Flask app for Michele to generate statements
"""

from flask import Flask, render_template, send_file, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import openpyxl
from werkzeug.utils import secure_filename
import os
import sys
from datetime import datetime, date
from nc_tax_rates import get_tax_breakdown, get_county_rate_display
from branding import get_branding
from io import BytesIO
import zipfile
from tax_processor import process_tax_report
import tempfile

# Add scripts directory to path so we can import our PDF generator
sys.path.append(os.path.join(os.path.dirname(__file__), '../../scripts'))
from generate_pdf_statement import generate_pdf_statement

load_dotenv()

app = Flask(__name__)
CORS(app)

# Upload configuration (ADD THIS HERE)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        cursor_factory=RealDictCursor
    )

@app.route('/')
def index():
    """Main page - show customers with outstanding balances"""
    return render_template('index.html')

@app.route('/api/customers')
def get_customers():
    """Get all customers with outstanding balances"""
    company_id = request.args.get('company_id', 2, type=int)  # Default to Get a Grip
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get customers with outstanding balances
    cur.execute("""
        SELECT 
            c.id,
            c.customer_name,
            c.account_number,
            c.contact_email,
            c.contact_phone,
            COUNT(i.id) as invoice_count,
            SUM(i.invoice_total_due) as total_due,
            MAX(i.invoice_date) as last_invoice_date,
            SUM(CASE WHEN (CURRENT_DATE - i.invoice_date) > 90 THEN i.invoice_total_due ELSE 0 END) as over_90_days,
            SUM(CASE WHEN (CURRENT_DATE - i.invoice_date) BETWEEN 61 AND 90 THEN i.invoice_total_due ELSE 0 END) as days_61_90,
            SUM(CASE WHEN (CURRENT_DATE - i.invoice_date) BETWEEN 31 AND 60 THEN i.invoice_total_due ELSE 0 END) as days_31_60,
            SUM(CASE WHEN (CURRENT_DATE - i.invoice_date) <= 30 THEN i.invoice_total_due ELSE 0 END) as current
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        WHERE c.company_id = %s
          AND i.invoice_total_due > 0
        GROUP BY c.id, c.customer_name, c.account_number, c.contact_email, c.contact_phone
        ORDER BY total_due DESC
    """, (company_id,))
    
    customers = cur.fetchall()
    
    cur.close()
    conn.close()
    
    # Convert Decimal to float for JSON serialization
    for customer in customers:
        customer['total_due'] = float(customer['total_due'])
        customer['over_90_days'] = float(customer['over_90_days'])
        customer['days_61_90'] = float(customer['days_61_90'])
        customer['days_31_60'] = float(customer['days_31_60'])
        customer['current'] = float(customer['current'])
    
    return jsonify(customers)

@app.route('/api/companies')
def get_companies():
    """Get list of companies"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id, name FROM companies ORDER BY name")
    companies = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify(companies)

@app.route('/api/branding/<int:company_id>')
def get_company_branding(company_id):
    """Get branding configuration for a company"""
    branding = get_branding(company_id)
    # Add /static/ prefix to logo path
    branding_with_url = branding.copy()
    branding_with_url['logo_url'] = f"/static/{branding['logo']}"
    return jsonify(branding_with_url)

@app.route('/api/generate-statement/<int:customer_id>')
def generate_statement(customer_id):
    """Generate PDF statement for a customer"""
    
    # Get customer name
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT customer_name, company_id FROM customers WHERE id = %s", (customer_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if not result:
        return jsonify({'error': 'Customer not found'}), 404
    
    customer_name = result['customer_name']
    customer_company_id = result['company_id']
    
    # Generate PDF
    output_dir = '/tmp/statements'
    os.makedirs(output_dir, exist_ok=True)
    
    safe_name = customer_name.replace(' ', '_').replace('/', '_')
    output_file = f"{output_dir}/statement_{safe_name}_{date.today().strftime('%Y%m%d')}.pdf"
    
    try:
        result = generate_pdf_statement(customer_name, output_file, customer_company_id)
        if result:
            return send_file(result, 
                           mimetype='application/pdf',
                           as_attachment=True,
                           download_name=f"statement_{safe_name}.pdf")
        else:
            return jsonify({'error': 'Failed to generate statement'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary')
def get_summary():
    """Get overall summary stats with aging buckets"""
    company_id = request.args.get('company_id', 2, type=int)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get basic summary stats
    cur.execute("""
        SELECT
            COUNT(DISTINCT c.id) as customer_count,
            COUNT(i.id) as invoice_count,
            SUM(i.invoice_total_due) as total_due
        FROM customers c
        JOIN invoices i ON c.id = i.customer_id
        WHERE c.company_id = %s
          AND i.invoice_total_due > 0
    """, (company_id,))
    summary = cur.fetchone()
    
    # Calculate aging buckets
    cur.execute("""
        SELECT
            SUM(CASE 
                WHEN CURRENT_DATE - i.invoice_date <= 30 THEN i.invoice_total_due 
                ELSE 0 
            END) as current,
            SUM(CASE 
                WHEN CURRENT_DATE - i.invoice_date > 30 AND CURRENT_DATE - i.invoice_date <= 60 THEN i.invoice_total_due 
                ELSE 0 
            END) as days_30,
            SUM(CASE 
                WHEN CURRENT_DATE - i.invoice_date > 60 AND CURRENT_DATE - i.invoice_date <= 90 THEN i.invoice_total_due 
                ELSE 0 
            END) as days_60,
            SUM(CASE 
                WHEN CURRENT_DATE - i.invoice_date > 90 THEN i.invoice_total_due 
                ELSE 0 
            END) as days_90
        FROM invoices i
        WHERE i.company_id = %s
          AND i.invoice_total_due > 0
    """, (company_id,))
    aging = cur.fetchone()
    
    cur.close()
    conn.close()
    
    # Format response
    return jsonify({
        'customer_count': summary['customer_count'],
        'invoice_count': summary['invoice_count'],
        'total_due': float(summary['total_due']) if summary['total_due'] is not None else 0.0,
        'current': float(aging['current']) if aging['current'] is not None else 0.0,
        'days_30': float(aging['days_30']) if aging['days_30'] is not None else 0.0,
        'days_60': float(aging['days_60']) if aging['days_60'] is not None else 0.0,
        'days_90': float(aging['days_90']) if aging['days_90'] is not None else 0.0
    })
    
    cur.close()
    conn.close()
    
    summary['total_due'] = float(summary['total_due']) if summary['total_due'] is not None else 0.0
    
    return jsonify(summary)

@app.route('/upload', methods=['GET'])
def upload_page():
    """Show the upload interface"""
    return render_template('upload.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle Excel file upload and import"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only .xlsx and .xls files allowed'}), 400
    
    # Get selected company
    company_id = request.form.get('company_id')
    if not company_id:
        return jsonify({'error': 'No company selected'}), 400
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Parse and import
        result = import_servicefusion_excel(filepath, int(company_id))
        
        # Clean up
        os.remove(filepath)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-company-data/<int:company_id>', methods=['DELETE'])
def clear_company_data(company_id):
    """Delete all invoices and customers for a company"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Delete invoices first (due to foreign key constraint)
        cur.execute("DELETE FROM invoices WHERE company_id = %s", (company_id,))
        invoices_deleted = cur.rowcount
        
        # Delete customers
        cur.execute("DELETE FROM customers WHERE company_id = %s", (company_id,))
        customers_deleted = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'invoices_deleted': invoices_deleted,
            'customers_deleted': customers_deleted
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def import_servicefusion_excel(filepath, company_id):
    """Parse ServiceFusion Excel export and import to database"""
    
    # Load workbook
    wb = openpyxl.load_workbook(filepath)
    sheet = wb.active
    
    # Row 6 is headers, data starts at row 7
    header_row = list(sheet.iter_rows(min_row=6, max_row=6, values_only=True))[0]
    
    # Create column index mapping
    col_map = {header: idx for idx, header in enumerate(header_row)}
    
    stats = {
        'inserted': 0,
        'updated': 0,
        'skipped': 0,
        'errors': []
    }
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Process each invoice row
    for row_num, row in enumerate(sheet.iter_rows(min_row=7, values_only=True), start=7):
        try:
            # Extract data
            invoice_number = str(row[col_map['Invoice#']])
            customer_name = row[col_map['Customer Name']]
            invoice_date = row[col_map['Invoice Date']]
            invoice_total = float(row[col_map['Invoice Total']] or 0)
            
            # AUTO-SPLIT: If uploading to Kleanit Charlotte (2) and customer has *FL*, route to Kleanit FL (4)
            target_company_id = company_id
            print(f"DEBUG: Processing '{customer_name}' - company_id={company_id}, has FL={'*FL*' in str(customer_name)}")
            if company_id == 1 and customer_name and '*FL*' in str(customer_name):
                target_company_id = 4  # Kleanit South Florida
                print(f"DEBUG: ✓ Routing '{customer_name}' to Kleanit FL")

            # Extract tax data
            tax_total = float(row[col_map.get('Tax Total')] or 0)
            tax_rate_name = row[col_map.get('Tax Rate Name')]
            
            invoice_total = float(row[col_map['Invoice Total']] or 0)
            amount_due = float(row[col_map['Invoice Total Due']] or 0)
            
            # Skip if no invoice number or already paid
            if not invoice_number:
                stats['skipped'] += 1
                continue
            
            # Check if customer exists
            cur.execute("""
                SELECT id FROM customers 
                WHERE company_id = %s AND customer_name = %s
            """, (target_company_id, customer_name))
            
            customer = cur.fetchone()
            
            if not customer:
                # Create customer
                cur.execute("""
                    INSERT INTO customers (company_id, customer_name, contact_email, contact_phone, 
                                         service_location_address_1, service_location_city, 
                                         service_location_state, service_location_zip)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    target_company_id,
                    customer_name,
                    row[col_map.get('Contact Email 1')],
                    row[col_map.get('Contact Phone 1')],
                    row[col_map.get('Service Location Address 1')],
                    row[col_map.get('Service Location City')],
                    row[col_map.get('Service Location State/Province')],
                    row[col_map.get('Service Location Zip/Post Code')]
                ))
                customer_id_val = cur.fetchone()['id']
            else:
                customer_id_val = customer['id']
            
            # Check if invoice exists
            cur.execute("""
                SELECT id FROM invoices 
                WHERE company_id = %s AND invoice_number = %s
            """, (target_company_id, invoice_number))
            
            existing = cur.fetchone()
            
            if existing:
                # Update existing invoice
                cur.execute("""
                    UPDATE invoices SET
                        customer_id = %s,
                        invoice_date = %s,
                        invoice_total = %s,
                        tax_total = %s,
                        tax_rate_name = %s,
                        invoice_total_due = %s,
                        invoice_status = %s
                    WHERE id = %s
                """, (customer_id_val, invoice_date, invoice_total, amount_due, 'Unpaid', existing['id']))
                stats['updated'] += 1
            else:
                # Insert new invoice
                cur.execute("""
                    INSERT INTO invoices (
                        company_id, customer_id, invoice_number,
                        invoice_date, invoice_status, invoice_total, invoice_total_due
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (target_company_id, customer_id_val, invoice_number,
                      invoice_date, 'Unpaid', invoice_total, amount_due))
                stats['inserted'] += 1
        
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            stats['errors'].append(f"Row {row_num}: {str(e)}")
            print(f"ERROR on row {row_num}: {error_msg}")  # This will show in Flask console
            continue
    
    conn.commit()
    cur.close()
    conn.close()
    
    return stats
# ========================================
# TAX REPORT API ENDPOINTS
# Add these to your existing app.py file
# ========================================

from datetime import datetime
import openpyxl
from io import BytesIO
from flask import send_file

# Route for tax report page
@app.route('/tax-report')
def tax_report():
    """Tax report page"""
    return render_template('tax-report.html')

# API: Get tax data for a company
@app.route('/api/tax-data/<int:company_id>')
def get_tax_data(company_id):
    """Get all tax transactions for a company with state/county/transit breakdown"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            id,
            county,
            invoice_date,
            invoice_number,
            customer_name,
            job_number,
            total_sales,
            taxable_amount,
            tax_rate,
            tax_collected
        FROM tax_transactions
        WHERE company_id = %s
        ORDER BY county, invoice_date
    """, (company_id,))
    
    transactions = cur.fetchall()
    cur.close()
    conn.close()
    
    # Convert to list of dicts with Decimal to float AND add tax breakdown
    result = []
    for t in transactions:
        tax_collected = float(t['tax_collected'])
        breakdown = get_tax_breakdown(t['county'], tax_collected)
        
        result.append({
            'id': t['id'],
            'county': t['county'],
            'invoice_date': t['invoice_date'].isoformat() if t['invoice_date'] else None,
            'invoice_number': t['invoice_number'],
            'customer_name': t['customer_name'],
            'job_number': t['job_number'],
            'total_sales': float(t['total_sales']),
            'taxable_amount': float(t['taxable_amount']),
            'tax_rate': t['tax_rate'],
            'tax_collected': tax_collected,
            'state_tax': breakdown['state'],
            'county_tax': breakdown['county'],
            'transit_tax': breakdown['transit']
        })
    
    return jsonify(result)

# API: Upload tax report Excel file
@app.route('/api/upload-tax', methods=['POST'])
def upload_tax_report():
    """Upload and import ServiceFusion Tax Report"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    company_id = request.form.get('company_id')
    
    if not company_id:
        return jsonify({'error': 'No company selected'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join('/tmp', filename)
        file.save(filepath)
        
        # Parse Excel file
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        inserted = 0
        updated = 0
        skipped = 0
        errors = []
        
        current_county = None
        
        # Start from row 2 (after headers)
        for row_num in range(2, ws.max_row + 1):
            try:
                # Get cell values
                col_a = ws.cell(row=row_num, column=1).value  # County name
                invoice_date = ws.cell(row=row_num, column=2).value
                invoice_number = ws.cell(row=row_num, column=3).value
                customer_name = ws.cell(row=row_num, column=4).value
                job_number = ws.cell(row=row_num, column=5).value
                total_sales = ws.cell(row=row_num, column=6).value
                taxable_amount = ws.cell(row=row_num, column=7).value
                tax_rate = ws.cell(row=row_num, column=8).value
                tax_collected = ws.cell(row=row_num, column=9).value
                
                # County name in column A
                if col_a and isinstance(col_a, str) and col_a.strip():
                    current_county = col_a.strip()
                
                # Skip empty rows
                if not invoice_number:
                    skipped += 1
                    continue
                
                # Parse invoice date
                if isinstance(invoice_date, datetime):
                    invoice_date_str = invoice_date.strftime('%Y-%m-%d')
                elif isinstance(invoice_date, str):
                    try:
                        parsed_date = datetime.strptime(invoice_date, '%m/%d/%Y')
                        invoice_date_str = parsed_date.strftime('%Y-%m-%d')
                    except:
                        invoice_date_str = invoice_date
                else:
                    skipped += 1
                    continue
                
                # Convert values
                total_sales_val = float(total_sales) if total_sales else 0
                taxable_amount_val = float(taxable_amount) if taxable_amount else 0
                tax_collected_val = float(tax_collected) if tax_collected else 0
                tax_rate_str = str(tax_rate) if tax_rate else '0%'
                
                # Check if transaction already exists
                cur.execute("""
                    SELECT id FROM tax_transactions 
                    WHERE company_id = %s AND invoice_number = %s
                """, (company_id, str(invoice_number)))
                
                existing = cur.fetchone()
                
                # Skip FL customers for Kleanit Charlotte
                if company_id == '1' and customer_name and '*FL*' in customer_name.upper():
                    skipped += 1
                    continue

                if existing:
                    # Update existing
                    cur.execute("""
                        UPDATE tax_transactions SET
                            county = %s,
                            invoice_date = %s,
                            customer_name = %s,
                            job_number = %s,
                            total_sales = %s,
                            taxable_amount = %s,
                            tax_rate = %s,
                            tax_collected = %s
                        WHERE id = %s
                    """, (current_county, invoice_date_str, customer_name or '',
                         job_number or '', total_sales_val, taxable_amount_val,
                         tax_rate_str, tax_collected_val, existing['id']))
                    updated += 1
                else:
                    # Insert new
                    cur.execute("""
                        INSERT INTO tax_transactions (
                            company_id, county, invoice_date, invoice_number,
                            customer_name, job_number, total_sales, taxable_amount,
                            tax_rate, tax_collected
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (company_id, current_county, invoice_date_str, str(invoice_number),
                         customer_name or '', job_number or '', total_sales_val,
                         taxable_amount_val, tax_rate_str, tax_collected_val))
                    inserted += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Clean up temp file
        os.remove(filepath)
        
        return jsonify({
            'inserted': inserted,
            'updated': updated,
            'skipped': skipped,
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API: Export tax data to Excel
@app.route('/api/export-tax/<int:company_id>')
def export_tax_data(company_id):
    """Export tax data to Excel"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get company name
    cur.execute("SELECT name FROM companies WHERE id = %s", (company_id,))
    company = cur.fetchone()
    company_name = company['name'] if company else 'Unknown'
    
    # Get all tax transactions
    cur.execute("""
        SELECT 
            county,
            invoice_date,
            invoice_number,
            customer_name,
            job_number,
            total_sales,
            taxable_amount,
            tax_rate,
            tax_collected
        FROM tax_transactions
        WHERE company_id = %s
        ORDER BY county, invoice_date
    """, (company_id,))
    
    transactions = cur.fetchall()
    cur.close()
    conn.close()
    
    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Tax Report'
    
    # Headers
    headers = ['County', 'Invoice Date', 'Invoice #', 'Customer', 'Job #', 
               'Total Sales', 'Taxable Amount', 'Tax Rate', 'Tax Collected']
    ws.append(headers)
    
    # Data rows
    current_county = None
    county_totals = {}
    
    for t in transactions:
        county = t['county']
        
        # Track county totals
        if county not in county_totals:
            county_totals[county] = {
                'sales': 0,
                'taxable': 0,
                'tax': 0
            }
        
        county_totals[county]['sales'] += float(t['total_sales'])
        county_totals[county]['taxable'] += float(t['taxable_amount'])
        county_totals[county]['tax'] += float(t['tax_collected'])
        
        ws.append([
            county,
            t['invoice_date'].strftime('%m/%d/%Y') if t['invoice_date'] else '',
            t['invoice_number'],
            t['customer_name'],
            t['job_number'] or '',
            float(t['total_sales']),
            float(t['taxable_amount']),
            t['tax_rate'],
            float(t['tax_collected'])
        ])
    
    # Add summary sheet
    summary_ws = wb.create_sheet('Summary')
    summary_ws.append(['County', 'Total Sales', 'Taxable Amount', 'Tax Collected'])
    
    for county, totals in sorted(county_totals.items()):
        summary_ws.append([
            county,
            totals['sales'],
            totals['taxable'],
            totals['tax']
        ])
    
    # Grand total
    summary_ws.append([])
    summary_ws.append([
        'GRAND TOTAL',
        sum(t['sales'] for t in county_totals.values()),
        sum(t['taxable'] for t in county_totals.values()),
        sum(t['tax'] for t in county_totals.values())
    ])
    
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    # Generate filename
    today = datetime.now().strftime('%Y-%m-%d')
    filename = f'TaxReport_{company_name.replace(" ", "_")}_{today}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# API: Clear tax data for a company
@app.route('/api/clear-tax-data/<int:company_id>', methods=['DELETE'])
def clear_tax_data(company_id):
    """Clear all tax transactions for a company"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("DELETE FROM tax_transactions WHERE company_id = %s", (company_id,))
        deleted_count = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'deleted': deleted_count,
            'message': f'Deleted {deleted_count} tax transactions'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========================================
# BATCH STATEMENT GENERATION ENDPOINT
# Add this to your app.py file
# ========================================

import zipfile
from io import BytesIO
from datetime import datetime

# Add this import at the top if not already there:
# from flask import send_file

def clean_customer_name(name):
    """Convert customer name to proper Title Case with spaces"""
    # Replace underscores with spaces
    clean = name.replace('_', ' ')
    # Title case (capitalizes first letter of each word)
    clean = clean.title()
    return clean

@app.route('/api/generate-batch-statements', methods=['POST'])
def generate_batch_statements():
    """Generate PDF statements for multiple customers and return as ZIP file"""
    try:
        data = request.get_json()
        customer_ids = data.get('customer_ids', [])
        company_id = data.get('company_id')
        
        if not customer_ids:
            return jsonify({'error': 'No customers selected'}), 400
        
        if not company_id:
            return jsonify({'error': 'No company selected'}), 400
        
        # Import the PDF generation function
        sys.path.insert(0, '/home/chrisletize/fsm-system/scripts')
        from generate_pdf_statement import generate_pdf_statement
        
        # Create temp directory for PDFs
        temp_dir = '/tmp/batch_statements'
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        
        # Get company name for filename
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name FROM companies WHERE id = %s", (company_id,))
        company = cur.fetchone()
        company_name = company['name'] if company else 'Company'
        cur.close()
        conn.close()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Generate PDF for each customer
            for customer_id in customer_ids:
                try:
                    # Get customer name
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT customer_name, company_id FROM customers WHERE id = %s AND company_id = %s",
                               (customer_id, company_id))
                    customer = cur.fetchone()
                    cur.close()
                    conn.close()
                    
                    if not customer:
                        continue
                    
                    customer_name = customer['customer_name']
                    customer_company_id = customer['company_id']
                    
                    # Generate PDF to temp file
                    safe_name = customer_name.replace(' ', '_').replace('/', '_')
                    temp_pdf = f"{temp_dir}/statement_{safe_name}.pdf"
                    
                    # Generate the PDF using customer_id (more reliable than name matching)
                    result = generate_pdf_statement(
                        customer_name_search=None,
                        output_file=temp_pdf,
                        company_id=customer_company_id,
                        customer_id=customer_id
                    )
                    
                    if result and os.path.exists(result):
                        # Add PDF to ZIP
                        with open(result, 'rb') as pdf_file:
                            # Remove asterisks and extra spaces to avoid Windows ZIP preview issues
                            clean_name = clean_customer_name(customer_name).replace('*', '').replace('  ', ' ').strip()
                            zip_file.writestr(f'Statement - {clean_name}.pdf', pdf_file.read())
                        
                        # Clean up temp file
                        os.remove(result)
                    
                except Exception as e:
                    print(f"Error generating statement for customer {customer_id}: {e}")
                    continue
        
        # Clean up temp directory
        try:
            os.rmdir(temp_dir)
        except:
            pass
        
        # Prepare ZIP for download
        zip_buffer.seek(0)
        
        # Generate filename
        today = datetime.now().strftime('%Y-%m-%d')
        filename = f'Statements_{company_name.replace(" ", "_")}_{today}.zip'
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error in batch generation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tax-report')
def tax_report_page():
    """Display the cash-basis tax report page"""
    return render_template('tax-report.html')

@app.route('/api/process-tax-report', methods=['POST'])
def api_process_tax_report():
    """Process tax report and transaction report to create cash-basis tax breakdown"""
    try:
        tax_file = request.files.get('tax_report')
        transaction_file = request.files.get('transaction_report')
        company_id = request.form.get('company_id')
        
        if not all([tax_file, transaction_file, company_id]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Save uploaded files temporarily
        tax_path = os.path.join(tempfile.gettempdir(), f'tax_report_{company_id}.xlsx')
        transaction_path = os.path.join(tempfile.gettempdir(), f'transaction_report_{company_id}.xlsx')
        
        tax_file.save(tax_path)
        transaction_file.save(transaction_path)
        
        # Process the reports (no date filtering)
        result = process_tax_report(tax_path, transaction_path, company_id)
        
        # Clean up temp files
        os.remove(tax_path)
        os.remove(transaction_path)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print("\n" + "="*60)
    print("FSM STATEMENT GENERATOR - Starting...")
    print("="*60)
    print(f"Access at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
