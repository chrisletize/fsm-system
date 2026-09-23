"""
Smoke test: sitewide "return to origin" navigation (Chris, 2026-09-23 --
"upon successful creation of a work order... it should go back to whatever
origin page you were on... this type of logic should be consistent
throughout the site").

Covers the shared safe_return_to()/return_to_from_request() helpers
(app.py) directly, plus the routes wired into them: workorder_new,
workorder_edit, estimate_new, payment_new, and (touched for the same
open-redirect fix) sales_contact_new. Existing smoke tests for these routes
only ever assert `status_code == 302` and look the created record up by id
via a direct DB query -- none of them assert WHERE the redirect actually
points, so this file is the only place that class of regression is caught.

Drives the real Flask routes (test client, forged admin session) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_return_to_navigation.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, safe_return_to  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role='admin'):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'chris'
        sess['user_role'] = role
        sess['company_access'] = ['getagrip']
    return c


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids = []
    est_ids = []
    customer_ids = []
    contact_ids = []
    payment_ids = []
    admin = client_as()

    try:
        print("smoke_return_to_navigation: safe_return_to() rejects anything not a same-site relative path")
        check("plain relative path accepted", safe_return_to('/getagrip/dispatch', '/fallback') == '/getagrip/dispatch')
        check("path with query string accepted",
              safe_return_to('/getagrip/workorders?status=Scheduled', '/fallback') == '/getagrip/workorders?status=Scheduled')
        check("absolute URL rejected (open redirect)", safe_return_to('https://evil.example.com/phish', '/fallback') == '/fallback')
        check("protocol-relative URL rejected", safe_return_to('//evil.example.com/phish', '/fallback') == '/fallback')
        check("scheme-embedded value rejected", safe_return_to('/ok://evil.example.com', '/fallback') == '/fallback')
        check("empty value falls back", safe_return_to('', '/fallback') == '/fallback')
        check("missing leading slash rejected", safe_return_to('getagrip/dispatch', '/fallback') == '/fallback')

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE ReturnTo Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        def new_wo(return_to=None, status='Scheduled'):
            data = {
                'customer_id': str(customer_id), 'status': status, 'priority': 'Normal',
                'start_date': '2026-09-23', 'arrival_window_start': '9:00 AM',
                'line_items_json': json.dumps([{'kind': 'std', 'catalog_item_id': 1, 'description': '',
                                                 'quantity': '1', 'unit_price': '275.00'}]),
                'assigned_techs': [], 'duration_overridden': 'false',
            }
            if return_to is not None:
                data['return_to'] = return_to
            r = admin.post('/getagrip/workorders/new', data=data, follow_redirects=False)
            cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
            wid = cur.fetchone()['id']
            wo_ids.append(wid)
            return r, wid

        print("smoke_return_to_navigation: workorder_new with no return_to lands on the new WO's own detail page (design v2 Part Four default)")
        r, wid = new_wo()
        check(f"created (302) ({r.status_code})", r.status_code == 302)
        check(f"redirects to its own detail page, not the list ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/workorders/{wid}')

        print("smoke_return_to_navigation: workorder_new with return_to honors it (dispatch board round-trip)")
        r, wid2 = new_wo(return_to='/getagrip/dispatch?date=2026-09-23')
        check(f"redirects to the dispatch board it was launched from ({r.headers.get('Location')})",
              r.headers.get('Location') == '/getagrip/dispatch?date=2026-09-23')

        print("smoke_return_to_navigation: workorder_new rejects a malicious return_to and falls back safely")
        r, wid3 = new_wo(return_to='https://evil.example.com/phish')
        check(f"does NOT redirect off-site ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/workorders/{wid3}')

        def edit_wo(wid, status, return_to=None):
            data = {
                'customer_id': str(customer_id), 'status': status, 'priority': 'Normal',
                'start_date': '2026-09-23', 'arrival_window_start': '9:00 AM',
                'line_items_json': json.dumps([{'kind': 'std', 'catalog_item_id': 1, 'description': '',
                                                 'quantity': '1', 'unit_price': '275.00'}]),
                'assigned_techs': [], 'duration_overridden': 'false',
            }
            if return_to is not None:
                data['return_to'] = return_to
            return admin.post(f'/getagrip/workorders/{wid}/edit', data=data, follow_redirects=False)

        print("smoke_return_to_navigation: workorder_edit with no return_to preserves both existing defaults")
        r = edit_wo(wid, 'Scheduled')
        check(f"non-Completed edit still defaults to the list ({r.headers.get('Location')})",
              r.headers.get('Location') == '/getagrip/workorders')
        r = edit_wo(wid, 'Completed')
        check(f"Completed edit still defaults to its own detail page (invoice banner) ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/workorders/{wid}')

        print("smoke_return_to_navigation: workorder_edit's explicit return_to overrides the Completed special case")
        r = edit_wo(wid, 'Completed', return_to='/getagrip/dispatch?date=2026-09-23')
        check(f"return_to wins even when marking Completed ({r.headers.get('Location')})",
              r.headers.get('Location') == '/getagrip/dispatch?date=2026-09-23')

        def new_estimate(return_to=None):
            data = {
                'customer_id': str(customer_id), 'status': 'Draft',
                'line_items_json': json.dumps([{'catalog_item_id': 1, 'description': '',
                                                 'quantity': '1', 'unit_price': '275.00'}]),
            }
            if return_to is not None:
                data['return_to'] = return_to
            r = admin.post('/getagrip/estimates/new', data=data, follow_redirects=False)
            cur.execute("SELECT id FROM estimates WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
            row = cur.fetchone()
            eid = row['id'] if row else None
            if eid:
                est_ids.append(eid)
            return r, eid

        print("smoke_return_to_navigation: estimate_new with no return_to lands on its own detail page")
        r, eid = new_estimate()
        check(f"estimate created (302) ({r.status_code})", r.status_code == 302)
        check(f"redirects to its own detail page ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/estimates/{eid}')

        print("smoke_return_to_navigation: estimate_new with return_to honors it (e.g. back to customer detail)")
        r, eid2 = new_estimate(return_to=f'/getagrip/customers/{customer_id}')
        check(f"redirects back to the customer it was launched from ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/customers/{customer_id}')

        print("smoke_return_to_navigation: payment_new folded the old unvalidated redirect_to into return_to")
        r = admin.post('/getagrip/payments/new', data={
            'customer_id': str(customer_id), 'amount': '10.00',
            'return_to': f'/getagrip/customers/{customer_id}',
        }, follow_redirects=False)
        check(f"payment recorded (302) ({r.status_code})", r.status_code == 302)
        check(f"redirects back to the customer page it was recorded from ({r.headers.get('Location')})",
              r.headers.get('Location') == f'/getagrip/customers/{customer_id}')
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        payment_ids.append(cur.fetchone()['id'])

        print("smoke_return_to_navigation: payment_new falls back to /payments when nothing is given")
        r = admin.post('/getagrip/payments/new', data={
            'customer_id': str(customer_id), 'amount': '5.00',
        }, follow_redirects=False)
        check(f"defaults to the payments list ({r.headers.get('Location')})",
              r.headers.get('Location') == '/getagrip/payments')
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        payment_ids.append(cur.fetchone()['id'])

        print("smoke_return_to_navigation: payment_new rejects a malicious return_to")
        r = admin.post('/getagrip/payments/new', data={
            'customer_id': str(customer_id), 'amount': '5.00', 'return_to': '//evil.example.com/steal',
        }, follow_redirects=False)
        check(f"falls back to /payments, not the attacker's host ({r.headers.get('Location')})",
              r.headers.get('Location') == '/getagrip/payments')
        cur.execute("SELECT id FROM payments WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        payment_ids.append(cur.fetchone()['id'])

        print("smoke_return_to_navigation: sales_contact_new (the original pattern) also rejects a malicious return_to now")
        r = admin.post('/getagrip/sales/contacts/new', data={
            'first_name': 'Smoke', 'last_name': 'ReturnTo',
            'return_to': 'https://evil.example.com/phish',
        }, follow_redirects=False)
        check(f"contact created (302) ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM sales_contacts WHERE first_name = 'Smoke' AND last_name = 'ReturnTo' ORDER BY id DESC LIMIT 1")
        contact_row = cur.fetchone()
        contact_ids.append(contact_row['id'])
        check(f"falls back to its own edit page, not the attacker's host ({r.headers.get('Location')})",
              r.headers.get('Location') == f"/getagrip/sales/contacts/{contact_row['id']}/edit")

        print("smoke_return_to_navigation: the hidden field actually renders on GET so a real form submit would carry it through")
        r = admin.get('/getagrip/workorders/new?return_to=/getagrip/dispatch?date=2026-09-23')
        check("workorder_new GET renders 200", r.status_code == 200)
        check("hidden return_to field present in the form", b'name="return_to"' in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM record_audit WHERE table_name = 'work_orders' AND record_id = %s", (wid,))
            cur.execute("DELETE FROM work_orders WHERE id = %s", (wid,))
        for eid in est_ids:
            cur.execute("DELETE FROM estimate_line_items WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimate_status_history WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimates WHERE id = %s", (eid,))
        for pid in payment_ids:
            cur.execute("DELETE FROM payment_applications WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payment_status_history WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payments WHERE id = %s", (pid,))
        for cid in contact_ids:
            cur.execute("DELETE FROM sales_contacts WHERE id = %s", (cid,))
        for cid in customer_ids:
            cur.execute("DELETE FROM customers WHERE id = %s", (cid,))
        conn.commit()
        cur.close(); conn.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(est_ids)} estimate(s), {len(payment_ids)} payment(s), "
              f"{len(contact_ids)} contact(s), {len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
