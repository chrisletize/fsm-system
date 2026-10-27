"""
Smoke test: Increment 5.4 — Permissions sweep (directive §5.4).

Drives the real Flask routes (test client, forged sessions per role) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_permissions.py
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, username='smoketest'):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = username
        sess['user_role'] = role
        sess['company_access'] = ['getagrip']
    return c


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, wo_ids = [], []
    TODAY = date.today().isoformat()
    TECH_USER = 'smoketechnician'
    OTHER_TECH = 'smoketechnician2'

    admin = client_as('admin')

    try:
        print("smoke_permissions: fixtures -- two customers, two WOs, one assigned to TECH_USER")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Perm Own', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        own_customer_id = cur.fetchone()['id']
        customer_ids.append(own_customer_id)
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Perm NotMine', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        other_customer_id = cur.fetchone()['id']
        customer_ids.append(other_customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '50.00',
        }])

        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(own_customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [TECH_USER],
        }, follow_redirects=False)
        check(f"WO for tech's own customer created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (own_customer_id,))
        own_wo_id = cur.fetchone()['id']
        wo_ids.append(own_wo_id)

        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(other_customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '10:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [OTHER_TECH],
        }, follow_redirects=False)
        check(f"WO for a DIFFERENT tech's customer created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (other_customer_id,))
        other_wo_id = cur.fetchone()['id']
        wo_ids.append(other_wo_id)

        tech = client_as('technician', username=TECH_USER)

        print("smoke_permissions: My Day shows only the tech's own assignment for the date")
        r = tech.get(f'/getagrip/myday?date={TODAY}')
        check(f"myday 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("myday shows the tech's own customer", 'SMOKE Perm Own' in html)
        check("myday does NOT show the other tech's customer", 'SMOKE Perm NotMine' not in html)
        check("myday shows the three status buttons", 'On The Way' in html and 'Start' in html and 'Complete' in html)

        print("smoke_permissions: admin/manager/salesperson blocked from My Day (it's technician-only)")
        for role in ('admin', 'manager', 'salesperson'):
            r = client_as(role).get('/getagrip/myday')
            check(f"{role} blocked from myday (403) ({r.status_code})", r.status_code == 403)

        # D-100: My Day's buttons log the tech's VISIT status (one row per tap in
        # work_order_visit_status_log) and never change the work order's own
        # status. The old /myday/<id>/status route that wrote work_orders.status
        # was retired.
        print("smoke_permissions: My Day visit status -- own job allowed, other tech's job rejected")
        rt = f'/getagrip/myday?date={TODAY}'

        def visit_rows(wid, user):
            cur.execute("""SELECT status FROM work_order_visit_status_log
                           WHERE work_order_id = %s AND username = %s ORDER BY id""", (wid, user))
            return [r['status'] for r in cur.fetchall()]

        r = tech.post(f'/getagrip/workorders/{own_wo_id}/visit-status',
                      data={'status': 'On The Way', 'return_to': rt}, follow_redirects=False)
        check(f"tech marks own visit On The Way ({r.status_code})", r.status_code == 302)
        check("visit status logged", visit_rows(own_wo_id, TECH_USER) == ['On The Way'])
        cur.execute("SELECT status FROM work_orders WHERE id = %s", (own_wo_id,))
        check("the work order's own status is untouched", cur.fetchone()['status'] == 'Scheduled')

        r = tech.post(f'/getagrip/workorders/{other_wo_id}/visit-status',
                      data={'status': 'Completed', 'return_to': rt}, follow_redirects=False)
        check(f"tech CANNOT log a visit on a job they're not assigned to ({r.status_code})",
              r.status_code == 302 and visit_rows(other_wo_id, TECH_USER) == [])
        cur.execute("SELECT status FROM work_orders WHERE id = %s", (other_wo_id,))
        check("other tech's job status untouched", cur.fetchone()['status'] == 'Scheduled')

        r = tech.post(f'/getagrip/workorders/{other_wo_id}/visit-status',
                      data={'status': 'Started', 'username': OTHER_TECH, 'return_to': rt}, follow_redirects=False)
        check(f"tech CANNOT set another tech's visit status (403) ({r.status_code})", r.status_code == 403)

        r = tech.post(f'/getagrip/workorders/{own_wo_id}/visit-status',
                      data={'status': 'Completed', 'return_to': rt}, follow_redirects=False)
        check(f"tech marks own visit Completed ({r.status_code})", r.status_code == 302)
        check("both taps logged in order", visit_rows(own_wo_id, TECH_USER) == ['On The Way', 'Completed'])
        cur.execute("SELECT status FROM work_orders WHERE id = %s", (own_wo_id,))
        check("completing the visit does NOT complete the job (office closes it out)",
              cur.fetchone()['status'] == 'Scheduled')

        print("smoke_permissions: office WO form still rejects the mobile-reserved statuses")
        r = admin.post(f'/getagrip/workorders/{other_wo_id}/edit', data={
            'customer_id': str(other_customer_id), 'status': 'On The Way', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '10:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [OTHER_TECH],
        }, follow_redirects=True)
        check("office form rejects 'On The Way' as an office-settable status", b'Invalid status' in r.data)

        print("smoke_permissions: technician customer access is read-only and scoped to own jobs")
        r = tech.get('/getagrip/customers')
        check(f"tech customer list 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("list shows the tech's own-job customer", 'SMOKE Perm Own' in html)
        check("list does NOT show the unrelated customer", 'SMOKE Perm NotMine' not in html)
        check("no Add Customer button for a read-only technician", '+ Add Customer' not in html)

        r = tech.get(f'/getagrip/customers/{own_customer_id}')
        check(f"tech CAN view their own-job customer's detail ({r.status_code})", r.status_code == 200)
        check("no Edit button on a read-only detail page", 'class="btn btn-outline">Edit</a>' not in r.data.decode())

        r = tech.get(f'/getagrip/customers/{other_customer_id}')
        check(f"tech is BLOCKED from a customer with no own-job relationship (403) ({r.status_code})", r.status_code == 403)

        print("smoke_permissions: every customer write path 403s for technician")
        write_checks = [
            ('POST', f'/getagrip/customers/{own_customer_id}/edit', {'property_name': 'x'}),
            ('GET', '/getagrip/customers/new', None),
            ('POST', f'/getagrip/customers/{own_customer_id}/notes', {'note_text': 'x'}),
            ('GET', f'/getagrip/customers/{own_customer_id}/locations/new', None),
            ('GET', f'/getagrip/customers/{own_customer_id}/contacts/new', None),
            ('GET', '/getagrip/customers/search?search=x', None),
        ]
        for method, url, data in write_checks:
            r = tech.post(url, data=data) if method == 'POST' else tech.get(url)
            check(f"{method} {url} -> 403 for technician ({r.status_code})", r.status_code == 403)

        # Since D-101 (2026-09-30) the salesperson is locked to /sales/* site-wide;
        # he reaches customers only through the sales customer page (D-116).
        print("smoke_permissions: salesperson is locked out of office customer pages (D-101)")
        sales = client_as('salesperson')
        r = sales.get('/getagrip/customers/search?search=SMOKE')
        check(f"salesperson customer search -> 403 ({r.status_code})", r.status_code == 403)
        r = sales.get(f'/getagrip/customers/{own_customer_id}')
        check(f"salesperson customer detail -> 403 ({r.status_code})", r.status_code == 403)
        r = sales.get(f'/getagrip/sales/customers/{own_customer_id}')
        check(f"...but the sales customer page is open to him ({r.status_code})", r.status_code == 200)

        print("smoke_permissions: field_settings is now admin-only (was admin+manager)")
        manager = client_as('manager')
        r = manager.get('/getagrip/settings/fields')
        check(f"manager blocked from field settings (403) ({r.status_code})", r.status_code == 403)
        r = admin.get('/getagrip/settings/fields')
        check(f"admin still allowed ({r.status_code})", r.status_code == 200)

        # The 5.4 sweep gave the salesperson recency/jobs/reports access; D-101's
        # sales-only lockdown later superseded that. Reports and estimates are
        # outside /sales, so they 403 for him regardless of the route's own roles.
        print("smoke_permissions: salesperson's sales-only lockdown covers reports and estimates (D-101)")
        for path in ('/getagrip/reports', '/getagrip/reports/jobs', '/getagrip/reports/recency',
                     '/getagrip/reports/tax', '/getagrip/estimates'):
            r = sales.get(path)
            check(f"salesperson GET {path} -> 403 ({r.status_code})", r.status_code == 403)
        r = client_as('manager').get('/getagrip/reports/recency')
        check(f"manager still reaches the recency report ({r.status_code})", r.status_code == 200)

        # The landing page's role-gated cards used to be checked as the
        # salesperson; he can't reach /reports any more (D-101), so check what a
        # manager, who can, is shown.
        print("smoke_permissions: reports landing shows a manager the job and tax cards")
        r = client_as('manager').get('/getagrip/reports')
        html = r.data.decode()
        check("manager reports landing shows Job Activity", 'Job Activity' in html)
        check("manager reports landing shows Tax Report", 'NC Cash-Basis Tax Report' in html)

        print("smoke_permissions: billing_export now gated (was wide open)")
        r = sales.post('/getagrip/billing/export', data={'customer_ids': [str(own_customer_id)]})
        check(f"salesperson blocked from billing export (403) ({r.status_code})", r.status_code == 403)
        r = admin.post('/getagrip/billing/export', data={'customer_ids': [str(own_customer_id)]})
        check(f"admin still allowed ({r.status_code})", r.status_code == 200)

        print("smoke_permissions: technician still 403 everywhere else in the app (dispatch/invoices/billing/sales/estimates)")
        for path in ('/getagrip/dispatch', '/getagrip/invoices', '/getagrip/billing',
                     '/getagrip/sales', '/getagrip/estimates', '/getagrip/settings/users'):
            r = tech.get(path)
            check(f"technician GET {path} -> 403 ({r.status_code})", r.status_code == 403)

        print("smoke_permissions: 'office' is no longer offered as a role on the New User form")
        r = admin.get('/getagrip/settings/users/new')
        check("New User form does not offer 'office' as a role option", b'value="office"' not in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("""DELETE FROM record_audit WHERE table_name = 'work_order_visit_status_log'
                           AND record_id IN (SELECT id FROM work_order_visit_status_log WHERE work_order_id = %s)""", (wid,))
            cur.execute("DELETE FROM work_order_visit_status_log WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM record_audit WHERE table_name='work_orders' AND record_id=%s", (wid,))
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close(); conn.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
