"""
Smoke test: Increment 1.10 — NC cash-basis tax report.

Drives the real Flask routes (test client, forged admin session) against live
getagrip, plus calls _tax_report_data() directly for precise numeric checks
(HTML-string-grepping dollar amounts is fragile; the underlying dict isn't).
Everything created is hard-deleted in a `finally` block. Run inside the app
container:

    docker compose exec -T app python tests/smoke_tax_report.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, _tax_report_data  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def close(a, b, tol=0.02):
    return abs(a - b) < tol


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids, payment_ids, customer_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    TEST_DATE = '2026-08-15'   # historical, unambiguous month
    TODAY = None                # filled in after we ask Postgres, for refund rows

    try:
        cur.execute("SELECT CURRENT_DATE AS d")
        TODAY = cur.fetchone()['d'].isoformat()

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Tax Report Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        def make_invoice(source='fieldkit'):
            cur.execute("""
                INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
                VALUES (%s, %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
            """, (f'ZZZ-TAX-{len(wo_ids)+1:04d}', customer_id))
            wo_id = cur.fetchone()['id']
            wo_ids.append(wo_id)
            cur.execute("""
                INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
                VALUES (%s, %s, 'Smoke taxable line', 1, 1000.00, 1000.00, TRUE, 0, 'smoketest', 'smoketest')
            """, (wo_id, catalog_id))
            conn.commit()
            r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
            inv_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
            invoice_ids.append(inv_id)

            cur.execute("SELECT current_version_id FROM invoices WHERE id = %s", (inv_id,))
            ver_id = cur.fetchone()['current_version_id']
            cur.execute("UPDATE invoice_versions SET tax_county = 'Mecklenburg' WHERE id = %s", (ver_id,))
            if source == 'sf_import':
                cur.execute("UPDATE invoices SET source = 'sf_import' WHERE id = %s", (inv_id,))
            conn.commit()

            client.post(f'/getagrip/invoices/{inv_id}/harden')
            client.post(f'/getagrip/invoices/{inv_id}/send')
            return inv_id, ver_id

        print("smoke_tax_report: harden freezes the new tax component columns")
        inv_main, ver_main = make_invoice('fieldkit')
        cur.execute("""
            SELECT tax_rate_pct, tax_total, total, state_pct, county_pct, transit_pct, taxable_subtotal
            FROM invoice_versions WHERE id = %s
        """, (ver_main,))
        v = cur.fetchone()
        check(f"tax_rate_pct = 8.25 ({v['tax_rate_pct']})", close(float(v['tax_rate_pct']), 8.25))
        check(f"tax_total = 82.50 ({v['tax_total']})", close(float(v['tax_total']), 82.50))
        check(f"total = 1082.50 ({v['total']})", close(float(v['total']), 1082.50))
        check(f"state_pct = 4.75 ({v['state_pct']})", close(float(v['state_pct']), 4.75))
        check(f"county_pct = 3.00 ({v['county_pct']})", close(float(v['county_pct']), 3.00))
        check(f"transit_pct = 0.50 ({v['transit_pct']})", close(float(v['transit_pct']), 0.50))
        check(f"taxable_subtotal = 1000.00 ({v['taxable_subtotal']})", close(float(v['taxable_subtotal']), 1000.00))

        print("smoke_tax_report: sf_import fixture (must be excluded from the report)")
        inv_sf, ver_sf = make_invoice('sf_import')

        print("smoke_tax_report: partial payment -> proportional allocation incl. Mecklenburg 1% additional-county split")
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'payment_date': TEST_DATE, 'amount': '541.25',
            'apply_to_invoice_id': inv_main,
        }, follow_redirects=False)
        check(f"payment 1 recorded ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id", (customer_id,))
        payment_ids.extend(row['id'] for row in cur.fetchall())

        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'payment_date': TEST_DATE, 'amount': '250.00',
            'apply_to_invoice_id': inv_sf,
        }, follow_redirects=False)
        check(f"sf_import payment recorded ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id", (customer_id,))
        new_ids = [row['id'] for row in cur.fetchall() if row['id'] not in payment_ids]
        payment_ids.extend(new_ids)

        data = _tax_report_data(cur, TEST_DATE, TEST_DATE)
        check(f"exactly one county in the report ({[c['county'] for c in data['counties']]})",
              len(data['counties']) == 1 and data['counties'][0]['county'] == 'Mecklenburg')
        meck = data['counties'][0]
        check(f"exactly one row (sf_import excluded) ({len(meck['rows'])})", len(meck['rows']) == 1)
        t = meck['totals']
        check(f"applied = 541.25 ({t['applied']})", close(t['applied'], 541.25))
        check(f"taxable = 500.00 ({t['taxable']})", close(t['taxable'], 500.00))
        check(f"tax = 41.25 ({t['tax']})", close(t['tax'], 41.25))
        check(f"state = 23.75 ({t['state']})", close(t['state'], 23.75))
        check(f"county (base, 2%) = 10.00 ({t['county']})", close(t['county'], 10.00))
        check(f"additional_county (Mecklenburg 1%) = 5.00 ({t['additional_county']})", close(t['additional_county'], 5.00))
        check(f"transit = 2.50 ({t['transit']})", close(t['transit'], 2.50))
        check("components sum back to tax collected",
              close(t['state'] + t['county'] + t['additional_county'] + t['transit'], t['tax']))

        print("smoke_tax_report: refund from never-applied credit -> unallocated bucket")
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'payment_date': TODAY, 'amount': '100.00',
        }, follow_redirects=False)
        check(f"unapplied payment recorded ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id FROM payments WHERE customer_id = %s AND id != ALL(%s)
            ORDER BY id DESC LIMIT 1
        """, (customer_id, payment_ids))
        pay_unapplied = cur.fetchone()['id']
        payment_ids.append(pay_unapplied)

        r = client.post(f'/getagrip/payments/{pay_unapplied}/refund', data={'amount': '100.00', 'reference': 'SMOKE-REFUND-1'})
        check(f"refund of never-applied credit recorded ({r.status_code})", r.status_code == 302)

        print("smoke_tax_report: refund of previously-applied-then-unapplied money -> negative row in its county")
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'payment_date': TODAY, 'amount': '200.00',
            'apply_to_invoice_id': inv_main,
        }, follow_redirects=False)
        check(f"third payment recorded ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id FROM payments WHERE customer_id = %s AND id != ALL(%s)
            ORDER BY id DESC LIMIT 1
        """, (customer_id, payment_ids))
        pay_reversed = cur.fetchone()['id']
        payment_ids.append(pay_reversed)

        cur.execute("""
            SELECT id FROM payment_applications
            WHERE payment_id = %s AND reverses_application_id IS NULL
        """, (pay_reversed,))
        app_id = cur.fetchone()['id']
        r = client.post(f'/getagrip/payments/{pay_reversed}/unapply/{app_id}', data={'reason': 'smoke test'})
        check(f"un-apply succeeded ({r.status_code})", r.status_code == 302)

        r = client.post(f'/getagrip/payments/{pay_reversed}/refund', data={'amount': '200.00', 'reference': 'SMOKE-REFUND-2'})
        check(f"refund of un-applied money recorded ({r.status_code})", r.status_code == 302)

        data_today = _tax_report_data(cur, TODAY, TODAY)
        check(f"one unallocated refund ({len(data_today['unallocated'])})", len(data_today['unallocated']) == 1)
        check(f"unallocated amount = 100.00 ({data_today['unallocated'][0]['refunded_amount']})",
              close(data_today['unallocated'][0]['refunded_amount'], 100.00))

        meck_today = next((c for c in data_today['counties'] if c['county'] == 'Mecklenburg'), None)
        check("Mecklenburg bucket present for today's refund", meck_today is not None)
        refund_rows = [r for r in meck_today['rows'] if r['is_refund']]
        check(f"exactly one refund row ({len(refund_rows)})", len(refund_rows) == 1)
        rr = refund_rows[0]
        check(f"refund row applied_amount = -200.00 ({rr['applied_amount']})", close(rr['applied_amount'], -200.00))
        expected_frac = -200.00 / 1082.50
        check("refund row taxable_alloc matches the proportional formula",
              close(rr['taxable_alloc'], expected_frac * 1000.00))
        check("refund row tax_alloc matches the proportional formula",
              close(rr['tax_alloc'], expected_frac * 82.50))

        print("smoke_tax_report: HTTP page + exports don't 500")
        r = client.get(f'/getagrip/reports/tax?date_from={TEST_DATE}&date_to={TEST_DATE}')
        check(f"report page renders ({r.status_code})", r.status_code == 200)
        check("page shows Mecklenburg", b'Mecklenburg' in r.data)
        check("page shows the 1% additional county column", b'Additional County' in r.data)

        r = client.get(f'/getagrip/reports/tax/export.xlsx?date_from={TEST_DATE}&date_to={TEST_DATE}')
        check(f"xlsx export responds 200 ({r.status_code})", r.status_code == 200)
        check("xlsx export is the right mimetype",
              r.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        check(f"xlsx export non-trivial size ({len(r.data)} bytes)", len(r.data) > 1000)

        r = client.get(f'/getagrip/reports/tax/export.pdf?date_from={TEST_DATE}&date_to={TEST_DATE}')
        check(f"pdf export responds 200 ({r.status_code})", r.status_code == 200)
        check("pdf export is the right mimetype", r.mimetype == 'application/pdf')
        check("pdf contains 'Mecklenburg' (pageCompression=0 keeps streams greppable)", b'Mecklenburg' in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for pid in payment_ids:
            cur.execute("DELETE FROM payment_status_history WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payment_applications WHERE payment_id = %s", (pid,))
        if payment_ids:
            cur.execute("DELETE FROM payments WHERE id = ANY(%s)", (payment_ids,))
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
        cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(payment_ids)} payment(s), {len(invoice_ids)} invoice(s), "
              f"{len(wo_ids)} WO(s), {len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
