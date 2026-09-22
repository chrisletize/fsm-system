#!/usr/bin/env python3
"""
FieldKit: Open-invoice cutover import from a ServiceFusion invoice report.
Directive Stage 5 ("real run of import_open_invoices.py after dry-run
sign-off"). This is the script referenced there -- it didn't exist until now
because the data it needs was believed to already live in the sibling
statements database and turned out not to (D-038); Chris supplied a direct
ServiceFusion "Report_Invoice" export instead (2026-09-22).

Source format: header row 6 (5 metadata rows above it -- company name,
"Created At", "Created By", "Date Range"), columns: Bill To Location
Address 1, Customer Name, Invoice#, Invoice Date, Invoice Status, Invoice
Total, Invoice Total Due.

Scope decided with Chris (2026-09-22), reviewing this exact file for Get a
Grip (3,890 rows: 3,564 PAID IN FULL / 261 PAST DUE / 65 UNPAID):
  - Only PAST DUE and UNPAID rows are imported -- PAID IN FULL invoices
    aren't needed for an opening-balance cutover and importing 3,564 of them
    would be a much bigger, riskier operation for no billing-page benefit.
  - Customer matched by normalized property_name (same normalize_name() and
    exact-match-only discipline as import_job_dates.py -- no fuzzy matching,
    unmatched names logged to CSV, never auto-creates a customer).
  - invoice_number is prefixed 'SF-<original ServiceFusion number>' (e.g.
    SF-6047) -- FieldKit's own sequence is '<PREFIX>-<year>-####'
    (_next_invoice_number), a different shape that can never collide, but
    the SF- prefix also makes an imported receivable visually obvious
    everywhere it appears (billing page, invoice list, aging report).
  - source='sf_import' (invoices.source already has a CHECK constraint
    permitting this value -- it was reserved for exactly this import back
    when the schema was designed, never previously used).
  - One invoice_versions row per invoice, state='Hardened' (frozen -- this
    was already a real, finalized invoice in ServiceFusion, not something
    still editable) with NO line items: the source report is invoice-level
    only (no per-line detail), so subtotal=total, tax_total=0. This means
    these imported invoices won't itemize on their own PDF/detail page the
    way a FieldKit-native invoice does -- they carry the correct dollar
    total and balance, not a recreated line-item history. If per-invoice
    tax figures matter later, tax/TaxReport_*.xlsx has Invoice#-level
    Total Sales/Taxable Amount/Tax that could be joined in as a follow-up,
    deliberately not attempted here (separate file, separate date coverage,
    not part of this decision).
  - Two rows had Invoice Total Due < Invoice Total (a partial payment
    already made in ServiceFusion before cutover) -- for those, a real
    `payments` row (method='Other', dated the invoice date -- the actual
    payment date isn't in this report, flagged in the dry-run output) plus
    a `payment_applications` row for the paid amount is written alongside
    the invoice, so the balance and the payments ledger both come out
    correct rather than just quietly starting the balance lower with no
    paper trail.

Usage:
  Dry run (default):
    docker compose exec -T app python phase1/fieldkit_phase1/import_open_invoices.py \\
        /path/to/Report_Invoice-*.xlsx getagrip

  Real import:
    docker compose exec -T app python phase1/fieldkit_phase1/import_open_invoices.py \\
        /path/to/Report_Invoice-*.xlsx getagrip --commit
"""
import sys
import os
import re
import csv
import argparse
from datetime import datetime
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/app')
from app import get_db_connection  # noqa: E402

OPEN_STATUSES = {'PAST DUE', 'UNPAID'}
OTHER_PAYMENT_METHOD_ID = 6  # payment_methods.name = 'Other'


def normalize_name(name):
    """Same discipline as import_job_dates.py -- exact match only, no fuzzy."""
    if not name:
        return ''
    s = name.strip().lower()
    s = re.sub(r"[.,'\"]", '', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def read_export(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(min_row=7, values_only=True))
    out = []
    for r in rows:
        addr, name, invnum, invdate, status, total, due = r[:7]
        if status not in OPEN_STATUSES:
            continue
        out.append({
            'customer_name': name,
            'sf_invoice_number': str(invnum),
            'invoice_date': datetime.strptime(invdate, '%m/%d/%Y').date(),
            'status': status,
            'total': float(total) if total is not None else 0.0,
            'due': float(due) if due is not None else 0.0,
        })
    return out


def run(xlsx_path, company_key, dry_run, username, out_dir):
    rows = read_export(xlsx_path)
    print(f"Source file: {len(rows)} open (PAST DUE/UNPAID) invoice row(s).\n")

    conn = get_db_connection(company_key)
    cur = conn.cursor()
    cur.execute("SELECT id, property_name FROM customers WHERE deleted_at IS NULL")
    by_name = {}
    for r in cur.fetchall():
        by_name.setdefault(normalize_name(r['property_name']), []).append(r['id'])

    cur.execute("SELECT invoice_number FROM invoices WHERE invoice_number LIKE 'SF-%'")
    already_imported = {r['invoice_number'] for r in cur.fetchall()}

    matched = skipped_existing = partial_payments = 0
    unmatched = {}
    total_balance = 0.0

    for row in rows:
        inv_num = f"SF-{row['sf_invoice_number']}"
        if inv_num in already_imported:
            skipped_existing += 1
            continue

        key = normalize_name(row['customer_name'])
        ids = by_name.get(key)
        if not ids:
            unmatched.setdefault(row['customer_name'], []).append(inv_num)
            continue
        if len(ids) > 1:
            print(f"  [SKIP] {inv_num}: '{row['customer_name']}' matches {len(ids)} customers -- ambiguous, needs a human.")
            continue
        customer_id = ids[0]

        is_partial = row['due'] < row['total'] - 0.005
        note = ''
        if is_partial:
            partial_payments += 1
            note = f"  (PARTIAL: ${row['total']-row['due']:.2f} already paid, recording a matching payment)"
        print(f"  {'[DRY RUN] would insert' if dry_run else '[INSERT]'} {inv_num} | {row['invoice_date']} | "
              f"{row['customer_name']:40} | total ${row['total']:.2f} | due ${row['due']:.2f}{note}")
        matched += 1
        total_balance += row['due']

        if dry_run:
            continue

        cur.execute("""
            INSERT INTO invoices (invoice_number, customer_id, invoice_date, source,
                receivable_state, notes, created_by, updated_by)
            VALUES (%s, %s, %s, 'sf_import', 'open', %s, %s, %s)
            RETURNING id
        """, (inv_num, customer_id, row['invoice_date'],
              f"Imported from ServiceFusion (original status: {row['status']}).",
              username, username))
        invoice_id = cur.fetchone()['id']

        cur.execute("""
            INSERT INTO invoice_versions (invoice_id, revision_number, state, subtotal, tax_total, total,
                hardened_at, hardened_by, internal_notes, created_by, updated_by)
            VALUES (%s, 0, 'Hardened', %s, 0, %s, CURRENT_TIMESTAMP, %s,
                'Cutover import from ServiceFusion -- no per-line detail available in the source report.', %s, %s)
            RETURNING id
        """, (invoice_id, row['total'], row['total'], username, username, username))
        version_id = cur.fetchone()['id']

        cur.execute("UPDATE invoices SET current_version_id = %s WHERE id = %s", (version_id, invoice_id))
        cur.execute("""
            INSERT INTO invoice_status_history (invoice_id, state, version_id, to_state, changed_by, notes)
            VALUES (%s, 'Hardened', %s, 'Hardened', %s, 'Cutover import from ServiceFusion.')
        """, (invoice_id, version_id, username))

        if is_partial:
            paid_amount = round(row['total'] - row['due'], 2)
            cur.execute("""
                INSERT INTO payments (customer_id, payment_date, amount, payment_method_id, notes, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (customer_id, row['invoice_date'], paid_amount, OTHER_PAYMENT_METHOD_ID,
                  f"Migrated partial payment on {inv_num} from ServiceFusion cutover import "
                  f"(exact payment date not available in the source report -- invoice date used).",
                  username, username))
            payment_id = cur.fetchone()['id']
            cur.execute("""
                INSERT INTO payment_status_history (payment_id, event, changed_by, notes)
                VALUES (%s, 'received', %s, 'Cutover import from ServiceFusion.')
            """, (payment_id, username))
            cur.execute("""
                INSERT INTO payment_applications (payment_id, invoice_id, amount, applied_date, reason, created_by)
                VALUES (%s, %s, %s, %s, 'Cutover import -- pre-existing partial payment from ServiceFusion.', %s)
            """, (payment_id, invoice_id, paid_amount, row['invoice_date'], username))

    if not dry_run:
        conn.commit()
    cur.close(); conn.close()

    print(f"\n{company_key}: {matched} invoice(s) {'would be' if dry_run else ''} imported "
          f"({partial_payments} with a matched partial payment), "
          f"{skipped_existing} already imported (skipped, SF- number match), "
          f"{len(unmatched)} unmatched customer name(s) "
          f"({sum(len(v) for v in unmatched.values())} invoice(s)), "
          f"${total_balance:,.2f} total open balance.")

    if unmatched:
        path = os.path.join(out_dir, f'unmatched_open_invoices_{company_key}.csv')
        with open(path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['servicefusion_customer_name', 'invoice_numbers'])
            for name, invnums in sorted(unmatched.items(), key=lambda x: -len(x[1])):
                w.writerow([name, '; '.join(invnums)])
        print(f"Unmatched names logged to {path}")

    if dry_run:
        print("\nDRY RUN -- nothing was written. Re-run with --commit to apply.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('xlsx_path', help='Path to the Report_Invoice-*.xlsx export')
    parser.add_argument('company_key', choices=['getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf'])
    parser.add_argument('--commit', action='store_true', help='Actually write. Default is a dry run.')
    parser.add_argument('--username', default='import_open_invoices.py')
    parser.add_argument('--out-dir', default='/tmp')
    args = parser.parse_args()
    run(args.xlsx_path, args.company_key, dry_run=not args.commit, username=args.username, out_dir=args.out_dir)
