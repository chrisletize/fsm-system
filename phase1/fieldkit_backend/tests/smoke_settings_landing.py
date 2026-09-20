"""
Smoke test: Increment 5.5 — Settings landing + in-app help (directive §5.5).

Drives the real Flask routes (test client, forged sessions per role) against
live getagrip. No fixtures needed beyond an existing invoice/estimate/WO to
view (creates one throwaway WO for the work-order-form help panel check).
Everything created is hard-deleted in a `finally` block. Run inside the app
container:

    docker compose exec -T app python tests/smoke_settings_landing.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, company_access=None):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = role
        sess['company_access'] = company_access or ['getagrip']
    return c


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, wo_ids, invoice_ids, estimate_ids = [], [], [], []

    admin = client_as('admin')

    try:
        print("smoke_settings_landing: admin sees every card + the scheduled jobs table")
        r = admin.get('/getagrip/settings')
        check(f"admin settings landing 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        for label in ('Custom Fields', 'Service Catalog', 'Equipment Registry', 'Tax Rates',
                      'Company Settings', 'User Management', 'Audit Log', 'Scheduled Jobs'):
            check(f"admin sees '{label}'", label in html)

        print("smoke_settings_landing: manager sees only catalog+equipment, no admin-only cards/table")
        manager = client_as('manager')
        r = manager.get('/getagrip/settings')
        check(f"manager settings landing 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("manager sees Service Catalog", 'Service Catalog' in html)
        check("manager sees Equipment Registry", 'Equipment Registry' in html)
        check("manager does NOT see Custom Fields", 'Custom Fields' not in html)
        check("manager does NOT see Tax Rates", 'Tax Rates' not in html)
        check("manager does NOT see User Management", 'User Management' not in html)
        check("manager does NOT see the Scheduled Jobs table", 'Scheduled Jobs' not in html)

        print("smoke_settings_landing: salesperson and technician blocked entirely")
        for role in ('salesperson', 'technician'):
            r = client_as(role).get('/getagrip/settings')
            check(f"{role} blocked from settings landing (403) ({r.status_code})", r.status_code == 403)

        print("smoke_settings_landing: nav shows 'All Settings' for admin/manager, not for salesperson/technician")
        r = admin.get('/getagrip/dashboard')
        check("admin nav has All Settings", 'All Settings' in r.data.decode())
        r = client_as('salesperson').get('/getagrip/dashboard')
        check("salesperson nav has no All Settings link", 'All Settings' not in r.data.decode())

        print("smoke_settings_landing: help panels render on each target page")
        r = admin.get('/getagrip/billing')
        check("billing page has a help panel", 'help-panel' in r.data.decode())
        check("billing help mentions the 90-day delinquent threshold", '90 days' in r.data.decode())

        r = admin.get('/getagrip/workorders/new')
        html = r.data.decode()
        check("WO form has a help panel", 'help-panel' in html)
        check("WO form help explains the callback prefill", 'callback' in html.lower())

        # getagrip has extraction gated off entirely (D-071, bathtub/surface
        # resurfacing never does this work) -- use a company that has it.
        r = client_as('admin', company_access=['kleanit_charlotte']).get('/kleanit_charlotte/extraction')
        check(f"extraction queue 200 on a company that has it ({r.status_code})", r.status_code == 200)
        check("extraction queue has a help panel", 'help-panel' in r.data.decode())

        print("smoke_settings_landing: help panels on invoice/estimate detail (real fixtures)")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Settings Landing Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        import json
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '40.00',
        }])
        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': '2026-01-15', 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"fixture WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        r = admin.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        check(f"fixture invoice created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoices WHERE work_order_id = %s AND deleted_at IS NULL", (wo_id,))
        invoice_id = cur.fetchone()['id']
        invoice_ids.append(invoice_id)

        r = admin.get(f'/getagrip/invoices/{invoice_id}')
        check("invoice detail has a help panel", 'help-panel' in r.data.decode())
        check("invoice help explains Revise vs Reissue", 'Revise vs' in r.data.decode())

        est_lines = json.dumps([{
            'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '40.00',
        }])
        r = admin.post('/getagrip/estimates/new', data={
            'customer_id': str(customer_id), 'work_site_label': 'Smoke Site', 'line_items_json': est_lines,
        }, follow_redirects=False)
        check(f"fixture estimate created ({r.status_code})", r.status_code == 302)
        estimate_id = int(r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
        estimate_ids.append(estimate_id)

        r = admin.get(f'/getagrip/estimates/{estimate_id}')
        check("estimate detail has a help panel", 'help-panel' in r.data.decode())
        check("estimate help explains the Draft->Sent lifecycle", 'Draft' in r.data.decode())

        print("ALL CHECKS PASSED")

    finally:
        for eid in estimate_ids:
            cur.execute("DELETE FROM estimate_status_history WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimate_line_items WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimates WHERE id = %s", (eid,))
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
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='customers' AND record_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close(); conn.close()
        print(f"cleanup done: {len(customer_ids)} customer(s), {len(wo_ids)} WO(s), "
              f"{len(invoice_ids)} invoice(s), {len(estimate_ids)} estimate(s) removed.")


if __name__ == '__main__':
    main()
