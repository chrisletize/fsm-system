#!/usr/bin/env python3
"""
Generate professional PDF statement
Usage: python3 scripts/generate_pdf_statement.py <customer_name> [output_file.pdf]
"""

import sys
import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'api'))
from branding import get_branding

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
    return (reference_date - invoice_date).days

def get_aging_bucket(days):
    """Determine which aging bucket an invoice falls into"""
    if days < 0:
        return "FUTURE"
    elif days <= 30:
        return "CURRENT"
    elif days <= 60:
        return "31-60 DAYS"
    elif days <= 90:
        return "61-90 DAYS"
    else:
        return "90+ DAYS"

def generate_pdf_statement(customer_name_search=None, output_file=None, company_id=None, customer_id=None):
    """Generate a professional PDF statement for a customer"""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find customer and company
    if customer_id:
        # Use customer_id for exact lookup (more reliable)
        cur.execute("""
            SELECT c.id, c.customer_name, c.account_number,
                   c.contact_email, c.contact_phone,
                   c.service_location_address_1, c.service_location_address_2,
                   c.service_location_city, c.service_location_state, c.service_location_zip,
                   co.name as company_name
            FROM customers c
            JOIN companies co ON c.company_id = co.id
            WHERE c.id = %s AND c.company_id = %s
            LIMIT 1
        """, (customer_id, company_id))
    else:
        # Fallback to name search for CLI usage
        cur.execute("""
            SELECT c.id, c.customer_name, c.account_number,
                   c.contact_email, c.contact_phone,
                   c.service_location_address_1, c.service_location_address_2,
                   c.service_location_city, c.service_location_state, c.service_location_zip,
                   co.name as company_name
            FROM customers c
            JOIN companies co ON c.company_id = co.id
            WHERE c.customer_name ILIKE %s
              AND c.company_id = %s
            LIMIT 1
        """, (customer_name_search, company_id))
    
    customer = cur.fetchone()
    if not customer:
        print(f"Customer matching '{customer_name_search}' not found")
        cur.close()
        conn.close()
        return None

    # Get company_id for branding
    cur.execute("SELECT company_id FROM customers WHERE id = %s", (customer[0],))
    company_id = cur.fetchone()[0]
    
    # Load company branding
    branding = get_branding(company_id)
    
    # Set colors and logo from branding
    PRIMARY_COLOR = colors.HexColor(branding['primary_color'])
    ACCENT_COLOR = colors.HexColor(branding['accent_color'])
    # Use cream color for Kleanit invoice backgrounds (better readability)
    if company_id in [1, 4]:  # Kleanit Charlotte and Kleanit South Florida
        SECONDARY_COLOR = colors.HexColor('#F5F5DC')  # Cream
    else:
        SECONDARY_COLOR = colors.HexColor(branding['secondary_color'])
    HEADER_TEXT_COLOR = colors.whitesmoke  # White text works on all primary colors
    HEADER_TEXT_COLOR = colors.whitesmoke  # White text works on all primary colors
    LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', branding['logo'])
    
    (customer_id, name, account_num, email, phone, 
     addr1, addr2, city, state, zip_code, company_name) = customer
    
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
    
    if not invoices:
        print(f"No unpaid invoices found for {name}")
        cur.close()
        conn.close()
        return None
    
    # Calculate aging
    aging_buckets = {
        "CURRENT": 0,
        "31-60 DAYS": 0,
        "61-90 DAYS": 0,
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
            'bucket': bucket
        })
    
    total_due = sum(aging_buckets.values())
    
    # Generate output filename if not provided
    if output_file is None:
        safe_name = name.replace(' ', '_').replace('/', '_')
        output_file = f"statement_{safe_name}_{today.strftime('%Y%m%d')}.pdf"
    
    # Create PDF
    doc = SimpleDocTemplate(output_file, pagesize=letter,
                           rightMargin=0.5*inch, leftMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=PRIMARY_COLOR,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=PRIMARY_COLOR,
        spaceAfter=12
    )
    
    # Add logo if available
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        logo = Image(LOGO_PATH, width=2.5*inch, height=1.25*inch, kind='proportional')
        elements.append(logo)
        elements.append(Spacer(1, 0.2*inch))
    
    # Title
    elements.append(Paragraph(f"<b>{company_name}</b>", title_style))
    elements.append(Paragraph("ACCOUNT STATEMENT", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Statement date
    date_style = ParagraphStyle('date', parent=styles['Normal'], alignment=TA_RIGHT)
    elements.append(Paragraph(f"Statement Date: {today.strftime('%B %d, %Y')}", date_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Customer information box
    customer_data = [
        ["Customer Information"],
        ["Account Name:", name],
    ]
    if addr1:
        customer_data.append(["Address:", addr1])
        if addr2:
            customer_data.append(["", addr2])
        customer_data.append(["", f"{city}, {state} {zip_code}"])
    
    if email:
        customer_data.append(["Email:", email])
    if phone:
        customer_data.append(["Phone:", phone])
    
    customer_table = Table(customer_data, colWidths=[1.5*inch, 4*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (1, 0), HEADER_TEXT_COLOR),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('SPAN', (0, 0), (1, 0)),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (1, 0), 12),
        ('BACKGROUND', (0, 1), (1, -1), SECONDARY_COLOR),
        ('GRID', (0, 0), (1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (1, -1), 10),
        ('TOPPADDING', (0, 1), (1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (1, -1), 6),
    ]))
    
    elements.append(customer_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Invoice details
    elements.append(Paragraph("<b>INVOICE DETAILS</b>", heading_style))
    
    invoice_data = [["Invoice #", "Date", "Original Amount", "Amount Due", "Days", "Age"]]
    
    for inv in invoice_details:
        invoice_data.append([
            str(inv['number']),
            inv['date'].strftime('%m/%d/%Y'),
            f"${inv['total']:,.2f}",
            f"${inv['due']:,.2f}",
            str(inv['days']),
            inv['bucket']
        ])
    
    # Add total row
    invoice_data.append([
        "TOTAL", "", "", f"${total_due:,.2f}", "", ""
    ])
    
    invoice_table = Table(invoice_data, colWidths=[1*inch, 1*inch, 1.3*inch, 1.3*inch, 0.6*inch, 1.3*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT_COLOR),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), SECONDARY_COLOR),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('TOPPADDING', (0, 1), (-1, -2), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 4),
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, -1), (-1, -1), HEADER_TEXT_COLOR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('SPAN', (0, -1), (2, -1)),
        ('ALIGN', (0, -1), (0, -1), 'CENTER'),
    ]))
    
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Payment notice
    if total_due > 0:
        notice_style = ParagraphStyle(
            'notice',
            parent=styles['Normal'],
            fontSize=11,
            textColor=PRIMARY_COLOR,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        elements.append(Paragraph("<b>⚠ PAYMENT REQUIRED ⚠</b>", notice_style))
        elements.append(Paragraph(f"Please remit payment of <b>${total_due:,.2f}</b> to the address on file.", styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    
    cur.close()
    conn.close()
    
    print(f"\n✅ PDF statement generated: {output_file}")
    print(f"   Customer: {name}")
    print(f"   Total Due: ${total_due:,.2f}")
    print(f"   Invoices: {len(invoice_details)}")
    
    return output_file

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/generate_pdf_statement.py <customer_name> [output_file.pdf]")
        print("\nExample: python3 scripts/generate_pdf_statement.py 'Bella Vista'")
        print("         python3 scripts/generate_pdf_statement.py 'Bella Vista' bella_statement.pdf")
        sys.exit(1)
    
    customer_search = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = generate_pdf_statement(customer_search, output_file)
    
    if result:
        print(f"\n📄 Open the PDF with: xdg-open {result}")
