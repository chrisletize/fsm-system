#!/usr/bin/env python3
"""
Generate professional PDF tax report (cash basis)
Creates a formatted PDF from processed tax report data
B&W printing friendly while maintaining branded web design

Section order:
    1. Executive Summary        -- grand totals by component
    2. Unexpected Tax Rates     -- only when exceptions exist; placed high on
                                   purpose so it cannot be missed
    3. Totals by County         -- every county on one page, ties to section 4
    4. Tax Breakdown by County  -- invoice-level detail
    5. Customer Tax Totals

Columns for Transit, Additional County, and Unallocated appear only when the
period actually contains them, so a report with no Mecklenburg activity is not
padded with permanent $0.00 columns.
"""

import os
from datetime import datetime, date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT


def _money(value):
    """Format a number as $1,234.56."""
    return f"${(value or 0):,.2f}"


def _rate_label(county):
    """Rate text for a county header.

    Uses the processor's rate_label ('7.25% / 8.25%' when a county was billed at
    more than one rate during the period). Falls back to the older single
    tax_rate field so this still renders if handed an older report payload.
    """
    label = county.get('rate_label')
    if label:
        return label
    rate = county.get('tax_rate')
    if rate is None:
        return 'n/a'
    return f"{rate:.2f}%"


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

    notice_body_style = ParagraphStyle(
        'NoticeBody',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=6
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
    additional_county_tax = totals.get('additional_county_tax', 0)
    unallocated_tax = totals.get('unallocated_tax', 0)

    summary_data = [
        ["Tax Component", "Amount"],
        ["State Tax (4.75%)", _money(totals['state_tax'])],
        ["County Tax", _money(totals['county_tax'])],
    ]
    if transit_tax > 0:
        summary_data.append(["Transit Tax", _money(transit_tax)])
    if additional_county_tax > 0:
        summary_data.append(["Additional County Tax", _money(additional_county_tax)])
    if unallocated_tax > 0:
        summary_data.append(["Unallocated (see below)", _money(unallocated_tax)])

    # Row index of the last shaded component row, used by the table style below.
    # This used to be hardcoded to 3, which silently mis-styled the table as soon
    # as an optional component row appeared.
    last_component_row = len(summary_data) - 1

    summary_data += [
        ["Total Taxable Sales", _money(totals.get('taxable_amount', 0))],
        ["Total Tax Collected", _money(totals['total_tax'])],
        ["", ""],
        ["Paid Invoices Processed", str(totals['invoice_count'])],
    ]
    separator_row = len(summary_data) - 2
    invoice_row = len(summary_data) - 1
    
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
        ('BACKGROUND', (0, 1), (-1, last_component_row), SECONDARY_COLOR),
        ('GRID', (0, 0), (-1, separator_row - 1), 1, colors.black),
        ('ALIGN', (1, 1), (1, separator_row - 1), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, separator_row - 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, separator_row - 1), 11),
        ('TOPPADDING', (0, 1), (-1, separator_row - 1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, separator_row - 1), 8),
        # Separator row (invisible)
        ('LINEABOVE', (0, separator_row), (-1, separator_row), 0, colors.white),
        ('LINEBELOW', (0, separator_row), (-1, separator_row), 0, colors.white),
        # Invoice count
        ('BACKGROUND', (0, invoice_row), (-1, invoice_row), colors.lightgrey),
        ('FONTNAME', (0, invoice_row), (0, invoice_row), 'Helvetica-Bold'),
        ('ALIGN', (1, invoice_row), (1, invoice_row), 'RIGHT'),
        ('GRID', (0, invoice_row), (-1, invoice_row), 1, colors.black),
        ('FONTSIZE', (0, invoice_row), (-1, invoice_row), 10),
        ('TOPPADDING', (0, invoice_row), (-1, invoice_row), 6),
        ('BOTTOMPADDING', (0, invoice_row), (-1, invoice_row), 6),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.4*inch))
    
    counties = report_data['counties']

    # ====== UNEXPECTED TAX RATES ======
    # Invoices whose billed rate does not match a known rate for their county.
    # Their tax is in the totals but is NOT split into components, so this sits
    # ahead of everything else rather than tucked away at the end.
    exceptions = report_data.get('exceptions', [])
    if exceptions:
        elements.append(Paragraph("<b>UNEXPECTED TAX RATES</b>", heading_style))

        plural = "" if len(exceptions) == 1 else "s"
        elements.append(Paragraph(
            f"{len(exceptions)} invoice{plural} billed at a rate that does not match a known "
            f"rate for that county. The tax is included in the county and grand totals below, "
            f"but is not split into state / county / transit components. Each is either a "
            f"mis-billed invoice or a rate change the system has not been told about.",
            notice_body_style
        ))
        elements.append(Spacer(1, 0.1 * inch))

        exception_data = [["County", "Invoice #", "Customer", "Billed", "Expected", "Tax"]]
        for ex in exceptions:
            expected = " or ".join(f"{r:.2f}%" for r in ex.get('expected_rates', []))
            exception_data.append([
                ex.get('county', ''),
                str(ex.get('invoice_num', '') or ''),
                str(ex.get('customer_name', '') or '')[:30],
                f"{(ex.get('tax_rate') or 0):.2f}%",
                expected or "n/a",
                _money(ex.get('tax')),
            ])

        exception_table = Table(
            exception_data,
            colWidths=[1.0 * inch, 0.8 * inch, 2.2 * inch, 0.7 * inch, 0.9 * inch, 0.9 * inch]
        )
        exception_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.black),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            # Warm tint reads as a warning in colour and as a light fill in B&W.
            ('BACKGROUND', (0, 1), (-1, -1), colors.Color(1, 0.95, 0.8)),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 2, colors.black),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        elements.append(exception_table)
        elements.append(Spacer(1, 0.35 * inch))

    # ====== TOTALS BY COUNTY ======
    # One-page roll-up. Every figure ties exactly to the detail that follows.
    elements.append(Paragraph("<b>TOTALS BY COUNTY</b>", heading_style))

    show_transit = transit_tax > 0
    show_addl = additional_county_tax > 0
    show_unalloc = unallocated_tax > 0

    header_row = ["County", "Rate", "Taxable Sales", "State", "County"]
    if show_transit:
        header_row.append("Transit")
    if show_addl:
        header_row.append("Addl Cnty")
    if show_unalloc:
        header_row.append("Unalloc")
    header_row += ["Total Tax", "Inv"]

    totals_by_county_data = [header_row]

    for county in counties:
        row = [
            county['name'],
            _rate_label(county),
            _money(county.get('taxable_amount')),
            _money(county.get('state_tax')),
            _money(county.get('county_tax')),
        ]
        if show_transit:
            row.append(_money(county.get('transit_tax')))
        if show_addl:
            row.append(_money(county.get('additional_county_tax')))
        if show_unalloc:
            row.append(_money(county.get('unallocated_tax')))
        row += [_money(county.get('total_tax')), str(county.get('invoice_count', ''))]
        totals_by_county_data.append(row)

    total_row = [
        "TOTAL",
        f"{len(counties)} counties",
        _money(totals.get('taxable_amount', 0)),
        _money(totals['state_tax']),
        _money(totals['county_tax']),
    ]
    if show_transit:
        total_row.append(_money(transit_tax))
    if show_addl:
        total_row.append(_money(additional_county_tax))
    if show_unalloc:
        total_row.append(_money(unallocated_tax))
    total_row += [_money(totals['total_tax']), str(totals['invoice_count'])]
    totals_by_county_data.append(total_row)

    # Fit the 7.5" content width no matter how many optional columns are present,
    # rather than overflowing the page when Mecklenburg activity adds two.
    money_col_count = 4 + sum([show_transit, show_addl, show_unalloc])
    name_w, rate_w, inv_w = 1.05, 0.95, 0.40
    money_w = (7.5 - name_w - rate_w - inv_w) / money_col_count
    col_widths = ([name_w * inch, rate_w * inch]
                  + [money_w * inch] * money_col_count
                  + [inv_w * inch])

    totals_table = Table(totals_by_county_data, colWidths=col_widths, repeatRows=1)
    totals_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT_COLOR),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BOX', (0, 0), (-1, 0), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.Color(0.95, 0.95, 0.95)]),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('TOPPADDING', (0, 1), (-1, -2), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 5),
        ('BACKGROUND', (0, -1), (-1, -1), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, -1), (-1, -1), HEADER_TEXT_COLOR),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('BOX', (0, -1), (-1, -1), 2, colors.black),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.4 * inch))

    # ====== TAX BY COUNTY ======
    elements.append(Paragraph("<b>TAX BREAKDOWN BY COUNTY</b>", heading_style))
    
    for county in counties:
        # County header section
        # Components present for this county only. A county billed at more than
        # one rate during the period shows both, e.g. "7.25% / 8.25%".
        breakdown_parts = [
            f"State: {_money(county.get('state_tax'))}",
            f"County: {_money(county.get('county_tax'))}",
        ]
        if county.get('transit_tax', 0) > 0:
            breakdown_parts.append(f"Transit: {_money(county['transit_tax'])}")
        if county.get('additional_county_tax', 0) > 0:
            breakdown_parts.append(f"Addl County: {_money(county['additional_county_tax'])}")
        if county.get('unallocated_tax', 0) > 0:
            breakdown_parts.append(f"UNALLOCATED: {_money(county['unallocated_tax'])}")
        breakdown_parts.append(f"Taxable Sales: {_money(county.get('taxable_amount'))}")
        breakdown_parts.append(f"Total Tax: {_money(county.get('total_tax'))}")

        county_header_data = [
            [f"{county['name']} County - {_rate_label(county)} Tax Rate"],
            ["  |  ".join(breakdown_parts)]
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
        
        # Show a per-invoice Rate column when the county has more than one billed
        # rate, or when any invoice carries an unrecognized rate. Without it the
        # flagged row would be invisible in this table.
        has_unrecognized = any(not c.get('rate_recognized', True) for c in county['customers'])
        show_rate_col = len(county.get('rates', [])) > 1 or has_unrecognized

        if show_rate_col:
            customer_data = [["Customer", "Invoice #", "Payment Date", "Rate", "Taxable Sales", "Tax Collected"]]
            col_widths = [2.05*inch, 0.75*inch, 1.0*inch, 0.7*inch, 1.5*inch, 1.5*inch]
        else:
            customer_data = [["Customer", "Invoice #", "Payment Date", "Taxable Sales", "Tax Collected"]]
            col_widths = [2.45*inch, 0.85*inch, 1.1*inch, 1.55*inch, 1.55*inch]

        for customer in county['customers']:
            payment_date = datetime.fromisoformat(customer['payment_date']).strftime('%m/%d/%Y')
            row = [
                customer['customer_name'],
                str(customer.get('invoice_num', '') or ''),
                payment_date,
            ]
            if show_rate_col:
                marker = "" if customer.get('rate_recognized', True) else " *"
                row.append(f"{(customer.get('tax_rate') or 0):.2f}%{marker}")
            row += [
                _money(customer.get('taxable_amount')),
                _money(customer.get('tax')),
            ]
            customer_data.append(row)

        # County subtotal. Ties to the sum of the rows above it.
        subtotal_row = [f"SUBTOTAL - {county['name']} County", "", ""]
        if show_rate_col:
            subtotal_row.append("")
        subtotal_row += [
            _money(county.get('taxable_amount')),
            _money(county.get('total_tax')),
        ]
        customer_data.append(subtotal_row)

        customer_table = Table(customer_data, colWidths=col_widths, repeatRows=1)
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
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
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
            ('ALIGN', (0, -1), (0, -1), 'LEFT'),
            ('SPAN', (0, -1), (-3, -1)),
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
                    'taxable_amount': 0,
                    'tax': 0
                }
            customer_totals[name]['transactions'] += 1
            customer_totals[name]['taxable_amount'] += customer.get('taxable_amount', 0)
            customer_totals[name]['tax'] += customer['tax']
    
    # Sort by tax amount (highest first)
    sorted_customers = sorted(customer_totals.items(), 
                             key=lambda x: x[1]['tax'], 
                             reverse=True)
    
    customer_summary_data = [["Customer", "Transactions", "Taxable Sales", "Tax Collected"]]

    for customer_name, data in sorted_customers:
        customer_summary_data.append([
            customer_name,
            str(data['transactions']),
            _money(data['taxable_amount']),
            _money(data['tax'])
        ])

    # Grand total
    customer_summary_data.append([
        "GRAND TOTAL",
        str(totals['invoice_count']),
        _money(totals.get('taxable_amount', 0)),
        _money(totals['total_tax'])
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

    if exceptions:
        elements.append(Paragraph(
            "* Rate not recognized for that county. See UNEXPECTED TAX RATES above.",
            notice_style
        ))
    
    # Build PDF
    doc.build(elements)
    
    print(f"\n✅ PDF tax report generated: {output_file}")
    print(f"   Company: {company_branding['display_name']}")
    print(f"   Total Tax: ${totals['total_tax']:,.2f}")
    print(f"   Taxable Sales: {_money(totals.get('taxable_amount', 0))}")
    print(f"   Counties: {len(counties)}")
    print(f"   Invoices: {totals['invoice_count']}")
    if exceptions:
        print(f"   ⚠ Unexpected rates: {len(exceptions)} invoice(s), {_money(unallocated_tax)} unallocated")
    
    return output_file

if __name__ == "__main__":
    print("This script is designed to be imported and called from app.py")
    print("Use the /api/generate-tax-report-pdf endpoint to generate tax report PDFs")
