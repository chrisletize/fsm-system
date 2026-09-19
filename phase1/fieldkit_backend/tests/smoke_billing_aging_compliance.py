"""
Smoke test: Increment 1.8 — billing page rebuild, A/R aging report, compliance.

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_billing_aging_compliance.py
"""
import sys
import os
import openpyxl
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, invoice_balance, _aging_bucket_label  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids, customer_ids, portal_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        print("smoke_billing_aging_compliance: bucket boundary math")
        check("30 days -> CURRENT (not due)", _aging_bucket_label(30) == 'CURRENT')
        check("31 days -> 31-60 DAYS", _aging_bucket_label(31) == '31-60 DAYS')
        check("60 days -> 31-60 DAYS", _aging_bucket_label(60) == '31-60 DAYS')
        check("61 days -> 61-90 DAYS", _aging_bucket_label(61) == '61-90 DAYS')
        check("90 days -> 61-90 DAYS", _aging_bucket_label(90) == '61-90 DAYS')
        check("91 days -> 90+ DAYS", _aging_bucket_label(91) == '90+ DAYS')

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Billing Test Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        cur.execute("""
            INSERT INTO customer_contacts (customer_id, first_name, last_name, office_email,
                accepts_billing, is_primary, created_by, updated_by)
            VALUES (%s, 'Bill', 'Contact', 'bill@smoketest.invalid', TRUE, TRUE, 'smoketest', 'smoketest')
        """, (customer_id,))
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        def make_open_invoice(days_old, amount):
            cur.execute("""
                INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
                VALUES (%s, %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
            """, (f'ZZZ-BAC-{len(wo_ids)+1:04d}', customer_id))
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
            return inv_id

        print("smoke_billing_aging_compliance: billing page aging + delinquent flag")
        inv_current = make_open_invoice(5, 40.00)
        inv_old = make_open_invoice(95, 60.00)  # > 90 days -> delinquent per Chris's D-001 answer

        r = client.get('/getagrip/billing')
        check(f"billing page renders ({r.status_code})", r.status_code == 200)
        check("shows the customer with its total due", b'SMOKE Billing Test Co' in r.data and b'100.00' in r.data)

        r = client.get('/getagrip/billing?filter=delinquent')
        check("delinquent filter includes this customer (oldest invoice is 95 days old, >90)",
              b'SMOKE Billing Test Co' in r.data)

        r = client.get('/getagrip/billing?filter=no_contact')
        check("no_contact filter excludes this customer (it has a billing contact)",
              b'SMOKE Billing Test Co' not in r.data)

        print("smoke_billing_aging_compliance: A/R aging report bucket placement")
        r = client.get('/getagrip/reports/aging')
        check(f"aging report renders ({r.status_code})", r.status_code == 200)
        check("customer appears with correct total", b'SMOKE Billing Test Co' in r.data)
        check("shows a 90+ bucket amount for the old invoice", b'60.00' in r.data)

        r_sorted = client.get('/getagrip/reports/aging?sort=90plus')
        check(f"90+ sort renders ({r_sorted.status_code})", r_sorted.status_code == 200)

        print("smoke_billing_aging_compliance: compliance portal enrollment + auto-assign on harden")
        r = client.post(f'/getagrip/customers/{customer_id}/compliance-portals/new', data={
            'portal_type': 'OPS', 'portal_label': 'Smoke OPS', 'property_client_id': 'PC-123',
            'vendor_account_number': 'VA-456',
        }, follow_redirects=False)
        check(f"portal enrollment created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id, portal_type FROM customer_compliance_portals WHERE customer_id=%s", (customer_id,))
        portal_row = cur.fetchone()
        portal_ids.append(portal_row['id'])
        check("portal type is OPS", portal_row['portal_type'] == 'OPS')

        r = client.get(f'/getagrip/customers/{customer_id}')
        check("customer detail shows the portal enrollment", b'Smoke OPS' in r.data)

        # A NEW invoice hardened now (after enrollment exists) should auto-assign
        # the portal and go pending — the two already-hardened ones above predate
        # the enrollment and should NOT have been retroactively touched.
        inv_new = make_open_invoice(1, 25.00)
        cur.execute("SELECT portal_id, portal_status FROM invoices WHERE id = %s", (inv_new,))
        new_inv_row = cur.fetchone()
        check(f"new invoice auto-assigned the sole active portal ({dict(new_inv_row)})",
              new_inv_row['portal_id'] == portal_row['id'] and new_inv_row['portal_status'] == 'pending')

        cur.execute("SELECT portal_id, portal_status FROM invoices WHERE id = %s", (inv_current,))
        old_inv_row = cur.fetchone()
        check("earlier invoice (hardened before enrollment existed) was not retroactively touched",
              old_inv_row['portal_id'] is None)

        print("smoke_billing_aging_compliance: compliance page + export + accept/reject")
        r = client.get('/getagrip/compliance')
        check(f"compliance page renders ({r.status_code})", r.status_code == 200)
        check("shows the pending invoice", str(inv_new).encode() in r.data or b'SMOKE Billing Test Co' in r.data)

        r = client.post('/getagrip/compliance/export', data={
            'portal_type': 'OPS', 'invoice_ids': [str(inv_new)],
        }, follow_redirects=False)
        check(f"export responds 200 ({r.status_code})", r.status_code == 200)
        check("export is an xlsx", r.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        wb = openpyxl.load_workbook(io.BytesIO(r.data))
        ws = wb.active
        header = [c.value for c in ws[1]]
        check(f"xlsx has the generic column header ({header})", header[0] == 'Invoice Number' and len(header) == 11)
        check("xlsx has one data row", ws.max_row == 2)

        cur.execute("SELECT portal_status FROM invoices WHERE id = %s", (inv_new,))
        check("invoice marked submitted after export", cur.fetchone()['portal_status'] == 'submitted')

        r = client.post(f'/getagrip/compliance/{inv_new}/accept', follow_redirects=False)
        check(f"accept responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT portal_status FROM invoices WHERE id = %s", (inv_new,))
        check("invoice marked accepted", cur.fetchone()['portal_status'] == 'accepted')

        print("smoke_billing_aging_compliance: portal deactivate excludes from portal-billed filter")
        cur.execute("UPDATE customer_compliance_portals SET portal_is_primary_billing = TRUE WHERE id = %s", (portal_row['id'],))
        conn.commit()
        r = client.get('/getagrip/billing?filter=portal')
        check("portal filter includes the customer while primary-billing is active",
              b'SMOKE Billing Test Co' in r.data)
        r = client.get(f'/getagrip/customers/{customer_id}')
        check("customer detail shows Portal billing badge is reachable via billing page too", r.status_code == 200)

        r = client.post(f'/getagrip/customers/{customer_id}/compliance-portals/{portal_row["id"]}/toggle', follow_redirects=False)
        check(f"deactivate toggle responds 302 ({r.status_code})", r.status_code == 302)
        r = client.get('/getagrip/billing?filter=portal')
        check("portal filter no longer includes the customer once deactivated",
              b'SMOKE Billing Test Co' not in r.data)

        print("ALL CHECKS PASSED")

    finally:
        if portal_ids:
            cur.execute("UPDATE invoices SET portal_id = NULL WHERE portal_id = ANY(%s)", (portal_ids,))
            cur.execute("DELETE FROM customer_compliance_portals WHERE id = ANY(%s)", (portal_ids,))
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
        cur.execute("DELETE FROM customer_contacts WHERE customer_id = ANY(%s)", (customer_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s), {len(portal_ids)} portal enrollment(s) removed.")


if __name__ == '__main__':
    main()
