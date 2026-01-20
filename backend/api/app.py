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
from datetime import date
from branding import get_branding

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
    return jsonify(branding)

@app.route('/api/generate-statement/<int:customer_id>')
def generate_statement(customer_id):
    """Generate PDF statement for a customer"""
    
    # Get customer name
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT customer_name FROM customers WHERE id = %s", (customer_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    if not result:
        return jsonify({'error': 'Customer not found'}), 404
    
    customer_name = result['customer_name']
    
    # Generate PDF
    output_dir = '/tmp/statements'
    os.makedirs(output_dir, exist_ok=True)
    
    safe_name = customer_name.replace(' ', '_').replace('/', '_')
    output_file = f"{output_dir}/statement_{safe_name}_{date.today().strftime('%Y%m%d')}.pdf"
    
    try:
        result = generate_pdf_statement(customer_name, output_file)
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

if __name__ == '__main__':
    print("\n" + "="*60)
    print("FSM STATEMENT GENERATOR - Starting...")
    print("="*60)
    print(f"Access at: http://localhost:5000")
    print("Press Ctrl+C to stop")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
