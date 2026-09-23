"""
Smoke test: Increment 1.6 — statements (replaces the Phase 0 generator).

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_statements.py
"""
import sys
import os
import zipfile
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, generate_statement_pdf, _aging_bucket_label, _sanitize_filename  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids = [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        print("smoke_statements: helpers")
        check("0 days -> CURRENT", _aging_bucket_label(0) == 'CURRENT')
        check("30 days -> CURRENT", _aging_bucket_label(30) == 'CURRENT')
        check("31 days -> 31-60 DAYS", _aging_bucket_label(31) == '31-60 DAYS')
        check("61 days -> 61-90 DAYS", _aging_bucket_label(61) == '61-90 DAYS')
        check("91 days -> 90+ DAYS", _aging_bucket_label(91) == '90+ DAYS')
        check("sanitize strips '*' (Kleanit FL marker)", _sanitize_filename('Bella Vista *FL*') == 'Bella_Vista_FL')
        check("sanitize handles empty", _sanitize_filename('') == 'customer')

        cur.execute("SELECT id FROM customers WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        customer_id = cur.fetchone()['id']
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        def make_open_invoice(wo_number, amount, days_old):
            """Returns (invoice_id, invoice_number) — the invoice number is
            auto-generated (GAG-2026-NNNN) independently of wo_number, which
            only names the work order."""
            cur.execute("""
                INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
                VALUES (%s, %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
            """, (wo_number, customer_id))
            wo_id = cur.fetchone()['id']
            wo_ids.append(wo_id)
            cur.execute("""
                INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
                VALUES (%s, %s, 'Smoke line', 1, %s, %s, FALSE, 0, 'smoketest', 'smoketest')
            """, (wo_id, catalog_id, amount, amount))
            conn.commit()
            r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
            inv_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
            invoice_ids.append(inv_id)
            cur.execute("UPDATE invoices SET invoice_date = CURRENT_DATE - %s WHERE id = %s", (days_old, inv_id))
            conn.commit()
            client.post(f'/getagrip/invoices/{inv_id}/harden')
            client.post(f'/getagrip/invoices/{inv_id}/send')
            cur.execute("SELECT invoice_number FROM invoices WHERE id = %s", (inv_id,))
            return inv_id, cur.fetchone()['invoice_number']

        print("smoke_statements: single-customer statement with mixed aging")
        inv_current, num_current = make_open_invoice('ZZZ-STMT-0001', 50.00, 5)
        inv_old, num_old = make_open_invoice('ZZZ-STMT-0002', 75.00, 95)

        pdf_bytes, cust_name = generate_statement_pdf('getagrip', customer_id)
        check("statement PDF generated", pdf_bytes is not None and pdf_bytes[:4] == b'%PDF')
        check(f"mentions the current invoice number ({num_current})", num_current.encode() in pdf_bytes)
        check(f"mentions the 90+ invoice number ({num_old})", num_old.encode() in pdf_bytes)
        check("shows the 90+ DAYS bucket", b'90+ DAYS' in pdf_bytes)
        check("shows PAYMENT REQUIRED notice", b'PAYMENT REQUIRED' in pdf_bytes)

        cur.execute("SELECT last_statement_at FROM customers WHERE id = %s", (customer_id,))
        before = cur.fetchone()['last_statement_at']
        check("last_statement_at not yet set by direct generate call", before is None)

        r = client.get(f'/getagrip/customers/{customer_id}/statement')
        check(f"statement route responds 200 ({r.status_code})", r.status_code == 200)
        check("statement route returns application/pdf", r.mimetype == 'application/pdf')
        cur.execute("SELECT last_statement_at FROM customers WHERE id = %s", (customer_id,))
        check("last_statement_at set after the route serves a statement", cur.fetchone()['last_statement_at'] is not None)

        print("smoke_statements: an invoice with zero balance is excluded")
        inv_paid, num_paid = make_open_invoice('ZZZ-STMT-0003', 20.00, 2)
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'amount': '20.00', 'payment_date': '2026-09-19',
            'apply_to_invoice_id': str(inv_paid), 'return_to': f'/getagrip/invoices/{inv_paid}',
        }, follow_redirects=False)
        cur.execute("SELECT id FROM payments WHERE customer_id=%s AND amount=20.00 ORDER BY id DESC LIMIT 1", (customer_id,))
        pay_row = cur.fetchone()
        pdf_bytes2, _ = generate_statement_pdf('getagrip', customer_id)
        check(f"paid-in-full invoice ({num_paid}) does not appear on the statement", num_paid.encode() not in pdf_bytes2)

        print("smoke_statements: unapplied credit shown as a negative line")
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'amount': '30.00', 'payment_date': '2026-09-19',
        }, follow_redirects=False)
        cur.execute("SELECT id FROM payments WHERE customer_id=%s AND amount=30.00 ORDER BY id DESC LIMIT 1", (customer_id,))
        credit_pay_row = cur.fetchone()
        pdf_bytes3, _ = generate_statement_pdf('getagrip', customer_id)
        check("statement mentions the unapplied credit", b'Unapplied credit' in pdf_bytes3)

        print("smoke_statements: batch ZIP route")
        r = client.post('/getagrip/billing/statements', data={'customer_ids': [str(customer_id)]}, follow_redirects=False)
        check(f"batch route responds 200 ({r.status_code})", r.status_code == 200)
        check("batch route returns a zip", r.mimetype == 'application/zip')
        zf = zipfile.ZipFile(io.BytesIO(r.data))
        names = zf.namelist()
        check(f"zip contains exactly one PDF ({names})", len(names) == 1 and names[0].endswith('.pdf'))
        check("zip filename has no '*'", '*' not in names[0])

        r = client.post('/getagrip/billing/statements', data={}, follow_redirects=False)
        check("batch route with no customers redirects with an error, not a 500", r.status_code == 302)

        print("smoke_statements: billing page renders with the new button")
        r = client.get('/getagrip/billing')
        check(f"billing page renders ({r.status_code})", r.status_code == 200)
        check("billing page has the Generate Statements button", b'Generate Statements' in r.data)

        print("ALL CHECKS PASSED")

    finally:
        cur.execute("SELECT id FROM payments WHERE customer_id=%s AND payment_date='2026-09-19' AND amount IN (20.00, 30.00)", (customer_id,))
        cleanup_pay_ids = [r['id'] for r in cur.fetchall()]
        for pid in cleanup_pay_ids:
            cur.execute("DELETE FROM payment_status_history WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payment_applications WHERE payment_id = %s", (pid,))
        if cleanup_pay_ids:
            cur.execute("DELETE FROM payments WHERE id = ANY(%s)", (cleanup_pay_ids,))
        for iid in invoice_ids:
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
        if invoice_ids:
            cur.execute("DELETE FROM invoices WHERE id = ANY(%s)", (invoice_ids,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        cur.execute("UPDATE customers SET last_statement_at = NULL WHERE id = %s", (customer_id,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s) removed.")


if __name__ == '__main__':
    main()
