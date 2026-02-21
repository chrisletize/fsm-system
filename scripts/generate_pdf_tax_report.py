#!/usr/bin/env python3
"""
Generate professional PDF tax report (cash basis)
Creates a formatted PDF from processed tax report data
B&W printing friendly while maintaining branded web design
"""

import os
from datetime import datetime, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

def generate_pdf_tax_report(report_data, company_branding, output_file):
    """
    Generate professional PDF tax report
    
    Args:
        report_data: Dict with structure from tax_processor.process_tax_report()
        company_branding: Dict from branding.get_branding()
        output_file: Path to save PDF
    
    Returns:
        Path to generated PDF file
    """
    
    # Extract branding colors
    PRIMARY_COLOR = colors.HexColor(company_branding['primary_color'])
    ACCENT_COLOR = colors.HexColor(company_branding['accent_color'])
    SECONDARY_COLOR = colors.HexColor(company_branding['secondary_color'])
    HEADER_TEXT_COLOR = colors.whitesmoke
    
    # Get logo path
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                             'assets', company_branding['logo'])
    
    # Create PDF
    doc = SimpleDocTemplate(output_file, pagesize=letter,
                           rightMargin=0.5*inch, leftMargin=0.5*inch,
                           topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=ACCENT_COLOR,
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=PRIMARY_COLOR,
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Add logo if available
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.5*inch, height=1.25*inch, kind='proportional')
        elements.append(logo)
        elements.append(Spacer(1, 0.2*inch))
    
    # Title
    elements.append(Paragraph(f"<b>{company_branding['display_name']}</b>", title_style))
    elements.append(Paragraph("Sales Tax Report (Cash Basis)", title_style))
    elements.append(Paragraph("North Carolina Department of Revenue", subtitle_style))
    
    # Report date
    today = date.today()
    date_style = ParagraphStyle('date', parent=styles['Normal'], 
                                alignment=TA_RIGHT, fontSize=10, textColor=ACCENT_COLOR)
    elements.append(Paragraph(f"Report Generated: {today.strftime('%B %d, %Y')}", date_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # ====== EXECUTIVE SUMMARY ======
    elements.append(Paragraph("<b>EXECUTIVE SUMMARY</b>", heading_style))
    
    totals = report_data['totals']
    
    transit_tax = totals.get('transit_tax', 0)
    summary_data = [
        ["Tax Component", "Amount"],
        ["State Tax (4.75%)", f"${totals['state_tax']:,.2f}"],
        ["County Tax", f"${totals['county_tax']:,.2f}"],
    ]
    if transit_tax > 0:
        summary_data.append(["Transit Tax", f"${transit_tax:,.2f}"])
    summary_data += [
        ["Total Tax Collected", f"${totals['total_tax']:,.2f}"],
        ["", ""],
        ["Paid Invoices Processed", str(totals['invoice_count'])],
    ]
    
    summary_table = Table(summary_data, colWidths=[4*inch, 2.5*inch])
    summary_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT_COLOR),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BOX', (0, 0), (-1, 0), 2, colors.black),  # Strong border for B&W
        # Data rows
        ('BACKGROUND', (0, 1), (-1, 3), SECONDARY_COLOR),
        ('GRID', (0, 0), (-1, 3), 1, colors.black),  # Grid lines visible in B&W
        ('ALIGN', (1, 1), (1, 3), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 3), 11),
        ('TOPPADDING', (0, 1), (-1, 3), 8),
        ('BOTTOMPADDING', (0, 1), (-1, 3), 8),
        # Separator row (invisible)
        ('LINEABOVE', (0, 4), (-1, 4), 0, colors.white),
        ('LINEBELOW', (0, 4), (-1, 4), 0, colors.white),
        # Invoice count
        ('BACKGROUND', (0, 5), (-1, 5), colors.lightgrey),
        ('FONTNAME', (0, 5), (0, 5), 'Helvetica-Bold'),
        ('ALIGN', (1, 5), (1, 5), 'RIGHT'),
        ('GRID', (0, 5), (-1, 5), 1, colors.black),
        ('FONTSIZE', (0, 5), (-1, 5), 10),
        ('TOPPADDING', (0, 5), (-1, 5), 6),
        ('BOTTOMPADDING', (0, 5), (-1, 5), 6),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # ====== TAX BY COUNTY ======
    elements.append(Paragraph("<b>TAX BREAKDOWN BY COUNTY</b>", heading_style))
    
    counties = report_data['counties']
    
    for county in counties:
        # County header section
        transit_line = f"  |  Transit: ${county['transit_tax']:,.2f}" if county.get('transit_tax', 0) > 0 else ""
        county_header_data = [
            [f"{county['name']} County - {county['tax_rate']}% Tax Rate"],
            [f"State: ${county['state_tax']:,.2f}  |  County: ${county['county_tax']:,.2f}{transit_line}  |  Taxable Sales: ${county['taxable_amount']:,.2f}  |  Total Tax: ${county['total_tax']:,.2f}"]
        ]
        
        county_header_table = Table(county_header_data, colWidths=[6.5*inch])
        county_header_table.setStyle(TableStyle([
            # Main header
            ('BACKGROUND', (0, 0), (0, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (0, 0), HEADER_TEXT_COLOR),
            ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, 0), 14),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('TOPPADDING', (0, 0), (0, 0), 10),
            ('BOTTOMPADDING', (0, 0), (0, 0), 10),
            ('LEFTPADDING', (0, 0), (0, 0), 15),
            # Breakdown row
            ('BACKGROUND', (0, 1), (0, 1), SECONDARY_COLOR),
            ('FONTNAME', (0, 1), (0, 1), 'Helvetica-Bold'),  # Bold for B&W clarity
            ('FONTSIZE', (0, 1), (0, 1), 10),
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),
            ('TOPPADDING', (0, 1), (0, 1), 8),
            ('BOTTOMPADDING', (0, 1), (0, 1), 8),
            ('LEFTPADDING', (0, 1), (0, 1), 15),
            ('BOX', (0, 0), (0, 1), 2, colors.black),  # Strong outer border
            ('LINEABOVE', (0, 1), (0, 1), 1, colors.black),  # Separator line
        ]))
        
        elements.append(Spacer(1, 0.15*inch))
        elements.append(county_header_table)
        elements.append(Spacer(1, 0.1*inch))
        
        # Customer transactions for this county
        customer_data = [["Customer", "Payment Date", "Invoice Amount", "Tax Collected"]]
        
        for customer in county['customers']:
            payment_date = datetime.fromisoformat(customer['payment_date']).strftime('%m/%d/%Y')
            customer_data.append([
                customer['customer_name'],
                payment_date,
                f"${customer['total_sales']:,.2f}",
                f"${customer['tax']:,.2f}"
            ])
        
        # Add county subtotal row
        customer_data.append([
            f"SUBTOTAL - {county['name']} County",
            "",
            f"${county['taxable_amount']:,.2f}",
            f"${county['total_tax']:,.2f}"
        ])
        
        customer_table = Table(customer_data, colWidths=[2.5*inch, 1.2*inch, 1.5*inch, 1.3*inch])
        customer_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), ACCENT_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BOX', (0, 0), (-1, 0), 1, colors.black),
            # Data rows - alternating shading for B&W readability
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
            ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -2), 9),
            ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
            ('TOPPADDING', (0, 1), (-1, -2), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -2), 5),
            # Subtotal row - strong visual weight
            ('BACKGROUND', (0, -1), (-1, -1), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, -1), (-1, -1), HEADER_TEXT_COLOR),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 11),
            ('TOPPADDING', (0, -1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
            ('SPAN', (0, -1), (1, -1)),
            ('BOX', (0, -1), (-1, -1), 2, colors.black),  # Extra bold border
        ]))
        
        elements.append(customer_table)
        elements.append(Spacer(1, 0.2*inch))
    
    # ====== PAGE BREAK BEFORE CUSTOMER SUMMARY ======
    elements.append(PageBreak())
    
    # ====== CUSTOMER TAX TOTALS ======
    elements.append(Paragraph("<b>CUSTOMER TAX TOTALS</b>", heading_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Aggregate customers across all counties
    customer_totals = {}
    
    for county in counties:
        for customer in county['customers']:
            name = customer['customer_name']
            if name not in customer_totals:
                customer_totals[name] = {
                    'transactions': 0,
                    'total_sales': 0,
                    'tax': 0
                }
            customer_totals[name]['transactions'] += 1
            customer_totals[name]['total_sales'] += customer['total_sales']
            customer_totals[name]['tax'] += customer['tax']
    
    # Sort by tax amount (highest first)
    sorted_customers = sorted(customer_totals.items(), 
                             key=lambda x: x[1]['tax'], 
                             reverse=True)
    
    customer_summary_data = [["Customer", "Transactions", "Total Sales", "Tax Collected"]]
    
    for customer_name, data in sorted_customers:
        customer_summary_data.append([
            customer_name,
            str(data['transactions']),
            f"${data['total_sales']:,.2f}",
            f"${data['tax']:,.2f}"
        ])
    
    # Grand total
    customer_summary_data.append([
        "GRAND TOTAL",
        str(totals['invoice_count']),
        "",
        f"${totals['total_tax']:,.2f}"
    ])
    
    customer_summary_table = Table(customer_summary_data, 
                                   colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    customer_summary_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT_COLOR),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BOX', (0, 0), (-1, 0), 1, colors.black),
        # Data rows - alternating for B&W clarity
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 9),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('TOPPADDING', (0, 1), (-1, -2), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 5),
        # Grand total row
        ('BACKGROUND', (0, -1), (-1, -1), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, -1), (-1, -1), HEADER_TEXT_COLOR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TOPPADDING', (0, -1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10),
        ('BOX', (0, -1), (-1, -1), 2, colors.black),
    ]))
    
    elements.append(customer_summary_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Footer notice
    notice_style = ParagraphStyle(
        'notice',
        parent=styles['Normal'],
        fontSize=10,
        textColor=ACCENT_COLOR,
        alignment=TA_CENTER,
        spaceAfter=10
    )
    elements.append(Paragraph(
        "<b>This report shows tax collected on a cash basis (by payment date) for NC filing requirements.</b>", 
        notice_style
    ))
    
    # Build PDF
    doc.build(elements)
    
    print(f"\n✅ PDF tax report generated: {output_file}")
    print(f"   Company: {company_branding['display_name']}")
    print(f"   Total Tax: ${totals['total_tax']:,.2f}")
    print(f"   Counties: {len(counties)}")
    print(f"   Invoices: {totals['invoice_count']}")
    
    return output_file

if __name__ == "__main__":
    print("This script is designed to be imported and called from app.py")
    print("Use the /api/generate-tax-report-pdf endpoint to generate tax report PDFs")
