"""
Cash-Basis Tax Report Processing

Matches the ServiceFusion Tax Report against the Transaction Report by Job# so
that tax liability lands in the period the payment was COLLECTED, per NC cash-basis
reporting requirements.

-------------------------------------------------------------------------------
THREE CORRECTIONS OVER THE PRIOR VERSION
-------------------------------------------------------------------------------
1. TAXABLE BASE. The prior version reported ServiceFusion's "Total Sales" column
   (row[5]) under the name taxable_amount. That column is GROSS: it includes the
   tax itself AND any non-taxable line items. SF publishes the real taxable base
   in its own column (row[6]), which is what we now read.

   Subtraction would NOT have worked. Two rows from a real export:
       Caldwell inv 3672   Total Sales 780.00  Taxable 0.00     Tax 0.00
       Cabarrus inv 3469   Total Sales 444.25  Taxable 275.00   Tax 19.25
   The first is entirely non-taxable; the second carries $150 of non-taxable
   line items alongside $275 of taxable work.

2. PER-RECORD RATE SPLIT. The prior version pooled each county's tax and split
   the pool by a single county rate taken from whichever record happened to be
   read first. That is only valid when every row in a county shares one rate.
   Mecklenburg broke that on 07/01/2026 when it went 7.25% -> 8.25%; a report
   spanning the change contains both. We now split each invoice by the rate that
   invoice was actually billed, then sum the components.

3. AUTH_CAPTURE. Credit card captures appear in the Transaction Report with
   transaction type AUTH_CAPTURE rather than Payment. They are real collected
   payments and were being dropped from every report.

Rounding is done ONCE, at the county level, with the residual absorbed by the
largest component. Rounding each invoice and then summing accumulates drift.
"""

import openpyxl
from datetime import datetime
from collections import defaultdict
from nc_tax_rates import get_tax_breakdown, COMPONENTS

# Transaction Report rows that represent money actually collected.
PAYMENT_TRANSACTION_TYPES = ('Payment', 'AUTH_CAPTURE')


def parse_date(date_value):
    """Parse the date formats ServiceFusion exports emit."""
    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value.split()[0], '%m/%d/%Y')
        except (ValueError, IndexError):
            pass

        try:
            return datetime.strptime(date_value, '%m/%d/%Y %I:%M %p')
        except ValueError:
            pass

    return None


def parse_percentage(rate_str):
    """Convert '7.0000%' to 7.0. Returns None when unreadable."""
    if rate_str is None:
        return None
    if isinstance(rate_str, str):
        rate_str = rate_str.replace('%', '').strip()
        if not rate_str:
            return None
    try:
        return float(rate_str)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    """Coerce a spreadsheet cell to float, treating blanks as zero."""
    if value is None or value == '':
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _reconcile(components, target_total):
    """Round components to cents so they sum EXACTLY to target_total.

    Rounds each component, then pushes the leftover cent or two onto the largest
    component. Without this the four components can miss their own total by a
    cent or so, which is exactly the kind of thing that makes a tax report look
    untrustworthy even when the underlying math is right.
    """
    rounded = {c: round(components.get(c, 0.0), 2) for c in COMPONENTS}
    target = round(target_total, 2)
    residual = round(target - sum(rounded.values()), 2)

    if residual and any(rounded.values()):
        largest = max(COMPONENTS, key=lambda c: abs(rounded[c]))
        rounded[largest] = round(rounded[largest] + residual, 2)

    return rounded


def process_tax_report(tax_file_path, transaction_file_path, company_id):
    """Build a cash-basis tax report from the two ServiceFusion exports.

    Returns:
    {
        'success': True,
        'report': {
            'totals':     {...},   # grand totals, tie exactly to the county rows
            'counties':   [...],   # per-county detail, sorted by name
            'exceptions': [...],   # rows whose billed rate is not recognized
            'meta':       {...}    # match counts, for transparency
        }
    }
    """

    try:
        # ------------------------------------------------------------------
        # Step 1: Tax Report -> tax detail indexed by Job#
        #
        # Column layout (0-indexed), confirmed against a live export header:
        #   0 County   1 Invoice Date   2 Invoice#   3 Customer#   4 Job#
        #   5 Total Sales   6 Taxable Amount   7 Tax Rate   8 Tax
        # ------------------------------------------------------------------
        tax_data = {}

        wb_tax = openpyxl.load_workbook(tax_file_path)
        ws_tax = wb_tax.active

        print(f"Loading tax report: {ws_tax.max_row} rows")

        # SF groups rows by county; the county name appears only on the first
        # row of each group and is blank on every row beneath it.
        current_county = 'Unknown'

        for row in ws_tax.iter_rows(min_row=2, values_only=True):
            county = row[0]
            invoice_date = row[1]
            invoice_num = row[2]
            customer = row[3]
            job_num = row[4]
            total_sales = row[5]
            taxable_amount = row[6]
            tax_rate = row[7]
            tax = row[8]

            if county and str(county).strip():
                current_county = str(county).strip()

            # No job number means no way to match a payment; zero tax means
            # nothing to report on the E-500.
            if not job_num or not tax or tax == 0:
                continue

            # Kleanit Charlotte (company_id 1) and Kleanit South Florida share a
            # ServiceFusion tenant; FL customers are tagged and excluded here.
            if company_id == '1' and customer and '*FL*' in str(customer).upper():
                continue

            tax_data[str(job_num)] = {
                'invoice_num': invoice_num,
                'invoice_date': invoice_date,
                'customer_name': customer,
                'county': current_county,
                'tax_rate': parse_percentage(tax_rate),
                'tax_rate_raw': tax_rate,
                'tax_amount': _to_float(tax),
                'taxable_amount': _to_float(taxable_amount),
                'total_sales': _to_float(total_sales),
            }

        print(f"Loaded {len(tax_data)} tax records from tax report")

        # ------------------------------------------------------------------
        # Step 2: Transaction Report -> collection date indexed by Job#
        #
        # Column layout (0-indexed):
        #   1 Date & Time   2 For Job#   3 Customer Name   4 Transaction Type
        # ------------------------------------------------------------------
        payment_data = {}

        wb_trans = openpyxl.load_workbook(transaction_file_path)
        ws_trans = wb_trans.active

        print(f"Loading transaction report: {ws_trans.max_row} rows")

        for row in ws_trans.iter_rows(min_row=2, values_only=True):
            date_time = row[1]
            job_num = row[2]
            customer_name = row[3]
            trans_type = row[4]

            if trans_type not in PAYMENT_TRANSACTION_TYPES or not job_num:
                continue

            if company_id == '1' and customer_name and '*FL*' in str(customer_name).upper():
                continue

            payment_date = parse_date(date_time)
            if not payment_date:
                continue

            # A job can carry several payments. The first collection date is what
            # pulls the invoice into this period, so first one wins.
            if str(job_num) not in payment_data:
                payment_data[str(job_num)] = payment_date

        print(f"Loaded {len(payment_data)} payment records from transaction report")

        # ------------------------------------------------------------------
        # Step 3: Match tax detail to collection dates
        # ------------------------------------------------------------------
        matched_records = []
        unmatched_job_count = 0

        for job_num, tax_info in tax_data.items():
            if job_num not in payment_data:
                unmatched_job_count += 1
                continue

            record = dict(tax_info)
            record['job_num'] = job_num
            record['payment_date'] = payment_data[job_num].isoformat()
            matched_records.append(record)

        print(f"Matched {len(matched_records)} records")
        print(f"Unmatched jobs: {unmatched_job_count}")

        # ------------------------------------------------------------------
        # Step 4: Split each invoice by ITS OWN billed rate, accumulate by county
        # ------------------------------------------------------------------
        counties_data = defaultdict(lambda: {
            'name': '',
            'rates': set(),
            'taxable_amount': 0.0,
            'total_sales': 0.0,
            'total_tax': 0.0,
            'unallocated_tax': 0.0,
            'components': {c: 0.0 for c in COMPONENTS},
            'customers': [],
        })

        exceptions = []

        for record in matched_records:
            county = record['county']
            data = counties_data[county]

            breakdown = get_tax_breakdown(
                county,
                record['tax_amount'],
                record['tax_rate'],
            )

            if not data['name']:
                data['name'] = county

            data['taxable_amount'] += record['taxable_amount']
            data['total_sales'] += record['total_sales']
            data['total_tax'] += record['tax_amount']

            if breakdown['matched']:
                data['rates'].add(breakdown['rate'])
                for component in COMPONENTS:
                    data['components'][component] += breakdown[component]
            else:
                # Rate we do not recognize. Keep the dollars in the county total
                # so the report still ties to ServiceFusion, but allocate nothing
                # to the components and raise it where a human will see it.
                data['unallocated_tax'] += breakdown['unallocated']
                exceptions.append({
                    'county': county,
                    'invoice_num': record['invoice_num'],
                    'customer_name': record['customer_name'],
                    'payment_date': record['payment_date'],
                    'tax_rate': record['tax_rate'],
                    'taxable_amount': round(record['taxable_amount'], 2),
                    'tax': round(record['tax_amount'], 2),
                    'expected_rates': breakdown['expected_rates'],
                    'reason': breakdown['reason'],
                })

            data['customers'].append({
                'customer_name': record['customer_name'],
                'invoice_num': record['invoice_num'],
                'payment_date': record['payment_date'],
                'tax_rate': record['tax_rate'],
                'taxable_amount': round(record['taxable_amount'], 2),
                'total_sales': round(record['total_sales'], 2),
                'tax': round(record['tax_amount'], 2),
                'rate_recognized': breakdown['matched'],
            })

        # ------------------------------------------------------------------
        # Step 5: Round once per county, then build grand totals by summing the
        # ROUNDED county figures so the summary box ties to the detail below it.
        # ------------------------------------------------------------------
        counties_list = []
        totals = {c: 0.0 for c in COMPONENTS}
        total_tax = 0.0
        total_taxable = 0.0
        total_sales = 0.0
        total_unallocated = 0.0

        for county_name, data in sorted(counties_data.items()):
            allocatable = data['total_tax'] - data['unallocated_tax']
            rounded = _reconcile(data['components'], allocatable)

            rates = sorted(data['rates'])
            county_tax = round(data['total_tax'], 2)
            county_taxable = round(data['taxable_amount'], 2)
            county_gross = round(data['total_sales'], 2)
            county_unallocated = round(data['unallocated_tax'], 2)

            counties_list.append({
                'name': data['name'],
                'rates': rates,
                # 'X.XX%' for a single rate, 'X.XX% / Y.YY%' when a rate changed
                # mid-period and both still appear on cash-basis rows.
                'rate_label': ' / '.join(f'{r:.2f}%' for r in rates) if rates else 'n/a',
                # Backward-compatible key, now holding the TRUE taxable base.
                'tax_rate': rates[0] if len(rates) == 1 else None,
                'taxable_amount': county_taxable,
                'total_sales': county_gross,
                'total_tax': county_tax,
                'state_tax': rounded['state'],
                'county_tax': rounded['county'],
                'transit_tax': rounded['transit'],
                'additional_county_tax': rounded['additional_county'],
                'unallocated_tax': county_unallocated,
                'invoice_count': len(data['customers']),
                'customers': sorted(data['customers'], key=lambda x: (x['customer_name'] or '')),
            })

            for component in COMPONENTS:
                totals[component] += rounded[component]
            total_tax += county_tax
            total_taxable += county_taxable
            total_sales += county_gross
            total_unallocated += county_unallocated

        return {
            'success': True,
            'report': {
                'totals': {
                    'taxable_amount': round(total_taxable, 2),
                    'total_sales': round(total_sales, 2),
                    'total_tax': round(total_tax, 2),
                    'state_tax': round(totals['state'], 2),
                    'county_tax': round(totals['county'], 2),
                    'transit_tax': round(totals['transit'], 2),
                    'additional_county_tax': round(totals['additional_county'], 2),
                    'unallocated_tax': round(total_unallocated, 2),
                    'invoice_count': len(matched_records),
                    'county_count': len(counties_list),
                },
                'counties': counties_list,
                'exceptions': exceptions,
                'meta': {
                    'tax_records_loaded': len(tax_data),
                    'payments_loaded': len(payment_data),
                    'matched': len(matched_records),
                    'unmatched_jobs': unmatched_job_count,
                    'exception_count': len(exceptions),
                },
            }
        }

    except Exception as e:
        import traceback
        print(f"Error processing tax report: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }
