"""
Smoke test: Increment 5.3 — Audit trail (directive §5.3).

*** SAFETY ***
Estimate send fires a real email; `_resend.Emails.send` is monkey-patched
for this entire run (same discipline as smoke_estimates.py), restored in
`finally` even on failure.

Drives the real Flask routes (test client, forged sessions) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_audit_trail.py
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = role
        sess['company_access'] = ['getagrip']
    return c


def latest_audit(cur, table_name, record_id, action=None):
    q = "SELECT * FROM record_audit WHERE table_name = %s AND record_id = %s"
    params = [table_name, record_id]
    if action:
        q += " AND action = %s"
        params.append(action)
    q += " ORDER BY id DESC LIMIT 1"
    cur.execute(q, params)
    return cur.fetchone()


SENT_CALLS = []


def fake_resend_send(payload):
    SENT_CALLS.append(payload)
    return {'id': f'fake-message-{len(SENT_CALLS)}'}


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, catalog_ids, wo_ids, invoice_ids, payment_ids = [], [], [], [], []
    estimate_ids, tax_rate_ids, usernames = [], [], []
    audit_ids_to_clean = []

    admin = client_as('admin')
    original_send = app_module._resend.Emails.send
    app_module._resend.Emails.send = fake_resend_send

    try:
        # ---------------------------------------------------------------
        print("smoke_audit_trail: customers -- create + update write record_audit rows")
        r = admin.post('/getagrip/customers/new', data={
            'property_name': 'SMOKE Audit Co', 'customer_type': 'Commercial', 'status': 'Active',
            'payment_terms': 'Net 30',
        }, follow_redirects=False)
        check(f"customer created ({r.status_code})", r.status_code == 302)
        customer_id = int(r.headers['Location'].rstrip('/').split('/')[-1])
        customer_ids.append(customer_id)

        row = latest_audit(cur, 'customers', customer_id, 'create')
        check("customer create audit row exists", row is not None)
        check("create diff includes property_name", row['diff'].get('property_name') == 'SMOKE Audit Co', row['diff'] if row else None)
        check("create audit changed_by is smoketest", row['changed_by'] == 'smoketest')

        r = admin.post(f'/getagrip/customers/{customer_id}/edit', data={
            'property_name': 'SMOKE Audit Co Renamed', 'customer_type': 'Commercial', 'status': 'Active',
            'payment_terms': 'Net 30',
        }, follow_redirects=False)
        check(f"customer edited ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'customers', customer_id, 'update')
        check("update audit row exists", row is not None)
        check("update diff shows property_name old->new", row['diff'].get('property_name') ==
              {'old': 'SMOKE Audit Co', 'new': 'SMOKE Audit Co Renamed'}, row['diff'] if row else None)

        print("smoke_audit_trail: a no-op edit (nothing changed) writes NOTHING")
        cur.execute("SELECT COUNT(*) AS n FROM record_audit WHERE table_name='customers' AND record_id=%s", (customer_id,))
        count_before = cur.fetchone()['n']
        r = admin.post(f'/getagrip/customers/{customer_id}/edit', data={
            'property_name': 'SMOKE Audit Co Renamed', 'customer_type': 'Commercial', 'status': 'Active',
            'payment_terms': 'Net 30',
        }, follow_redirects=False)
        cur.execute("SELECT COUNT(*) AS n FROM record_audit WHERE table_name='customers' AND record_id=%s", (customer_id,))
        check("no-op update wrote no new row", cur.fetchone()['n'] == count_before)

        print("smoke_audit_trail: customer detail page renders the History panel with the rename")
        r = admin.get(f'/getagrip/customers/{customer_id}')
        check(f"customer detail 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("History panel present", 'audit-history' in html)
        check("panel shows the old name struck through", 'SMOKE Audit Co<' in html or 'SMOKE Audit Co ' in html)
        check("panel shows the new name", 'SMOKE Audit Co Renamed' in html)

        # ---------------------------------------------------------------
        print("smoke_audit_trail: catalog_items -- create/update/delete")
        r = admin.post('/getagrip/settings/catalog/new', data={
            'name': 'SMOKE Audit Catalog Item', 'billing_behavior': 'standard', 'unit_of_measure': 'each',
            'unit_price': '25.00',
        }, follow_redirects=False)
        check(f"catalog item created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM catalog_items WHERE name = 'SMOKE Audit Catalog Item' AND deleted_at IS NULL")
        cat_id = cur.fetchone()['id']
        catalog_ids.append(cat_id)
        check("catalog create audit row exists", latest_audit(cur, 'catalog_items', cat_id, 'create') is not None)

        r = admin.post(f'/getagrip/settings/catalog/{cat_id}/edit', data={
            'name': 'SMOKE Audit Catalog Item', 'billing_behavior': 'standard', 'unit_of_measure': 'each',
            'unit_price': '30.00',
        }, follow_redirects=False)
        row = latest_audit(cur, 'catalog_items', cat_id, 'update')
        check("catalog update audit row exists", row is not None)
        check("unit_price diff 25 -> 30", row['diff'].get('unit_price') == {'old': 25.0, 'new': 30.0}, row['diff'] if row else None)

        r = admin.post(f'/getagrip/settings/catalog/{cat_id}/delete', follow_redirects=False)
        row = latest_audit(cur, 'catalog_items', cat_id, 'delete')
        check("catalog delete audit row exists", row is not None)
        check("delete diff carries the pre-delete name", row['diff'].get('name') == 'SMOKE Audit Catalog Item')

        # ---------------------------------------------------------------
        print("smoke_audit_trail: work_orders -- create/update/delete")
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        std_catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': std_catalog_id, 'description': '', 'quantity': '1', 'unit_price': '75.00',
        }])
        TODAY = date.today().isoformat()
        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)
        row = latest_audit(cur, 'work_orders', wo_id, 'create')
        check("WO create audit row exists", row is not None)
        check("create diff has status Scheduled", row['diff'].get('status') == 'Scheduled')

        r = admin.post(f'/getagrip/workorders/{wo_id}/edit', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"WO status changed to Completed ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'work_orders', wo_id, 'update')
        check("WO update audit row exists", row is not None)
        check("status diff Scheduled -> Completed", row['diff'].get('status') == {'old': 'Scheduled', 'new': 'Completed'}, row['diff'])

        print("smoke_audit_trail: WO detail page renders the History panel")
        r = admin.get(f'/getagrip/workorders/{wo_id}')
        check(f"WO detail 200 ({r.status_code})", r.status_code == 200)
        check("WO History panel present", 'audit-history' in r.data.decode())

        # ---------------------------------------------------------------
        print("smoke_audit_trail: invoices -- create from WO, then harden")
        r = admin.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        check(f"invoice created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoices WHERE work_order_id = %s AND deleted_at IS NULL", (wo_id,))
        invoice_id = cur.fetchone()['id']
        invoice_ids.append(invoice_id)
        row = latest_audit(cur, 'invoices', invoice_id, 'create')
        check("invoice create audit row exists", row is not None)

        r = admin.post(f'/getagrip/invoices/{invoice_id}/harden', follow_redirects=False)
        check(f"invoice hardened ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'invoices', invoice_id, 'update')
        check("invoice hardened audit row exists", row is not None)
        check("version_state diff Live -> Hardened", row['diff'].get('version_state') ==
              {'old': 'Live', 'new': 'Hardened'}, row['diff'])

        print("smoke_audit_trail: invoice detail page renders the History panel")
        r = admin.get(f'/getagrip/invoices/{invoice_id}')
        check(f"invoice detail 200 ({r.status_code})", r.status_code == 200)
        check("invoice History panel present", 'audit-history' in r.data.decode())

        # ---------------------------------------------------------------
        print("smoke_audit_trail: payments -- record + void")
        r = admin.post('/getagrip/payments/new', data={
            'customer_id': str(customer_id), 'payment_date': TODAY, 'amount': '50.00', 'payment_method_id': '',
        }, follow_redirects=False)
        check(f"payment recorded ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        payment_id = cur.fetchone()['id']
        payment_ids.append(payment_id)
        row = latest_audit(cur, 'payments', payment_id, 'create')
        check("payment create audit row exists", row is not None)
        check("create diff has amount 50.0", row['diff'].get('amount') == 50.0, row['diff'])

        r = admin.post(f'/getagrip/payments/{payment_id}/void', data={'void_reason': 'smoke test void'}, follow_redirects=False)
        check(f"payment voided ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'payments', payment_id, 'update')
        check("payment void audit row exists", row is not None)
        check("status diff -> voided", row['diff'].get('status', {}).get('new') == 'voided', row['diff'])

        print("smoke_audit_trail: payment detail page renders the History panel")
        r = admin.get(f'/getagrip/payments/{payment_id}')
        check(f"payment detail 200 ({r.status_code})", r.status_code == 200)
        check("payment History panel present", 'audit-history' in r.data.decode())

        # ---------------------------------------------------------------
        print("smoke_audit_trail: estimates -- create, send (email mocked)")
        cur.execute("""
            INSERT INTO customer_contacts (customer_id, first_name, last_name, office_email, is_primary, created_by, updated_by)
            VALUES (%s, 'Audit', 'Contact', 'audit-contact@smoketest.invalid', TRUE, 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        est_contact_id = cur.fetchone()['id']
        conn.commit()
        est_lines = json.dumps([{
            'catalog_item_id': std_catalog_id, 'description': '', 'quantity': '1', 'unit_price': '75.00',
        }])
        r = admin.post('/getagrip/estimates/new', data={
            'customer_id': str(customer_id), 'primary_contact_id': str(est_contact_id),
            'work_site_label': 'Smoke Site', 'line_items_json': est_lines,
        }, follow_redirects=False)
        check(f"estimate created ({r.status_code})", r.status_code == 302)
        estimate_id = int(r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
        estimate_ids.append(estimate_id)
        check("estimate create audit row exists", latest_audit(cur, 'estimates', estimate_id, 'create') is not None)

        calls_before = len(SENT_CALLS)
        r = admin.post(f'/getagrip/estimates/{estimate_id}/send', data={'subject': 'Your estimate'}, follow_redirects=False)
        check(f"estimate sent ({r.status_code})", r.status_code == 302)
        check("Resend was called (mocked)", len(SENT_CALLS) > calls_before)
        row = latest_audit(cur, 'estimates', estimate_id, 'update')
        check("estimate sent audit row exists", row is not None)
        check("status diff Draft -> Sent", row['diff'].get('status') == {'old': 'Draft', 'new': 'Sent'}, row['diff'])

        # ---------------------------------------------------------------
        print("smoke_audit_trail: tax_rates -- create, then end")
        r = admin.post('/getagrip/settings/tax/new', data={
            'county': 'SmokeAuditCounty', 'state_pct': '4.75', 'county_pct': '2.0', 'transit_pct': '0',
            'effective_from': '2026-01-01', 'is_active': 'on',
        }, follow_redirects=False)
        check(f"tax rate created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM tax_rates WHERE county = 'SmokeAuditCounty' AND deleted_at IS NULL")
        tax_rate_id = cur.fetchone()['id']
        tax_rate_ids.append(tax_rate_id)
        check("tax rate create audit row exists", latest_audit(cur, 'tax_rates', tax_rate_id, 'create') is not None)

        r = admin.post(f'/getagrip/settings/tax/{tax_rate_id}/end', data={'effective_to': '2026-06-30'}, follow_redirects=False)
        check(f"tax rate ended ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'tax_rates', tax_rate_id, 'update')
        check("tax rate end audit row exists", row is not None)
        check("is_active diff True -> False", row['diff'].get('is_active') == {'old': True, 'new': False}, row['diff'])

        # ---------------------------------------------------------------
        print("smoke_audit_trail: users -- create/toggle-active/reset-password NEVER leak password_hash")
        r = admin.post('/getagrip/settings/users/new', data={
            'username': 'smokeaudituser', 'full_name': 'Smoke Audit User', 'email': 'smokeaudituser@smoketest.invalid',
            'role': 'technician', 'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['getagrip'],
        }, follow_redirects=False)
        check(f"user created ({r.status_code})", r.status_code == 302)
        usernames.append('smokeaudituser')
        cur.execute("SELECT id FROM users WHERE username = 'smokeaudituser'")
        new_user_id = cur.fetchone()['id']
        row = latest_audit(cur, 'users', new_user_id, 'create')
        check("user create audit row exists", row is not None)
        check("password_hash NEVER appears in the create diff", 'password_hash' not in row['diff'], row['diff'])

        r = admin.post(f'/getagrip/settings/users/{new_user_id}/toggle-active', follow_redirects=False)
        check(f"user toggled ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'users', new_user_id, 'update')
        check("user toggle audit row exists", row is not None)
        check("is_active diff True -> False", row['diff'].get('is_active') == {'old': True, 'new': False}, row['diff'])

        r = admin.post(f'/getagrip/settings/users/{new_user_id}/reset-password',
                        data={'new_password': 'newpass456', 'confirm_password': 'newpass456'}, follow_redirects=False)
        check(f"password reset ({r.status_code})", r.status_code == 302)
        row = latest_audit(cur, 'users', new_user_id, 'update')
        check("reset audit row exists and does not carry a hash", row is not None and 'password_hash' not in json.dumps(row['diff']))

        # ---------------------------------------------------------------
        print("smoke_audit_trail: global admin-only audit view -- filters + role gate")
        manager = client_as('manager')
        r = manager.get('/getagrip/settings/audit')
        check(f"manager blocked from global audit view (403) ({r.status_code})", r.status_code == 403)

        r = admin.get('/getagrip/settings/audit')
        check(f"admin sees global audit view ({r.status_code})", r.status_code == 200)

        r = admin.get(f'/getagrip/settings/audit?table=customers&id={customer_id}')
        check(f"filtered view 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("filtered view shows the customer's rename diff", 'SMOKE Audit Co Renamed' in html)
        check("filtered view does not show the unrelated catalog item change", 'SMOKE Audit Catalog Item' not in html)

        r = admin.get('/getagrip/settings/audit?table=users')
        check("global view never leaks a password_hash anywhere", 'password_hash' not in r.data.decode())

        print("ALL CHECKS PASSED")

    finally:
        app_module._resend.Emails.send = original_send

        for uname in usernames:
            for db in ('getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf'):
                c2 = get_db_connection(db)
                cu2 = c2.cursor()
                cu2.execute("SELECT id FROM users WHERE username = %s", (uname,))
                urow = cu2.fetchone()
                if urow:
                    cu2.execute("DELETE FROM record_audit WHERE table_name='users' AND record_id=%s", (urow['id'],))
                cu2.execute("DELETE FROM users WHERE username = %s", (uname,))
                c2.commit(); cu2.close(); c2.close()

        for tid in tax_rate_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='tax_rates' AND record_id=%s", (tid,))
            cur.execute("DELETE FROM tax_rates WHERE id = %s", (tid,))

        for eid in estimate_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='estimates' AND record_id=%s", (eid,))
            cur.execute("DELETE FROM estimate_status_history WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimate_line_items WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimates WHERE id = %s", (eid,))

        for pid in payment_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='payments' AND record_id=%s", (pid,))
            cur.execute("DELETE FROM payment_status_history WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payment_applications WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payments WHERE id = %s", (pid,))

        for iid in invoice_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='invoices' AND record_id=%s", (iid,))
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoices WHERE id = %s", (iid,))

        for wid in wo_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='work_orders' AND record_id=%s", (wid,))
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_orders WHERE id = %s", (wid,))

        for cid in catalog_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='catalog_items' AND record_id=%s", (cid,))
            cur.execute("DELETE FROM catalog_items WHERE id = %s", (cid,))

        if customer_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='customers' AND record_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_contacts WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))

        conn.commit()
        cur.close(); conn.close()
        print(f"cleanup done: {len(customer_ids)} customer(s), {len(catalog_ids)} catalog item(s), "
              f"{len(wo_ids)} WO(s), {len(invoice_ids)} invoice(s), {len(payment_ids)} payment(s), "
              f"{len(estimate_ids)} estimate(s), {len(tax_rate_ids)} tax rate(s), {len(usernames)} user(s) removed. "
              f"{len(SENT_CALLS)} fake Resend call(s) made this run (0 real).")


if __name__ == '__main__':
    main()
