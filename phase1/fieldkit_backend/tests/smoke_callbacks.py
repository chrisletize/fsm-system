"""
Smoke test: Increment 3.4 — Callbacks (directive §4.4).

Drives the real Flask routes (test client, forged admin session) against
live getagrip, plus calls _job_recompute_customer_ratings() directly to
verify the callback penalty lands in the rating. Everything created is
hard-deleted in a `finally` block (customer_ratings deleted BEFORE customers,
per D-083's lesson about job_nightly-adjacent tests). Run inside the app
container:

    docker compose exec -T app python tests/smoke_callbacks.py
"""
import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, ALL_COMPANY_KEYS, _job_recompute_customer_ratings  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, customer_ids, usernames = [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    TODAY = date.today().isoformat()

    try:
        print("smoke_callbacks: two techs -- one goes back himself (unpaid), one sends someone else (paid)")
        for uname, full in (('smoketechcb1', 'Smoke Callback Tech One'), ('smoketechcb2', 'Smoke Callback Tech Two')):
            r = client.post('/getagrip/settings/users/new', data={
                'username': uname, 'full_name': full,
                'email': f'{uname}@smoketest.invalid', 'role': 'technician',
                'password': 'testpass123', 'confirm_password': 'testpass123',
                'company_access': ['getagrip'],
                'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on',
                'dispatch_sort_order': '1',
            }, follow_redirects=False)
            check(f"{uname} created ({r.status_code})", r.status_code == 302)
            usernames.append(uname)
        tech1, tech2 = usernames

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Callback Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Callback Other Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        other_customer_id = cur.fetchone()['id']
        customer_ids.append(other_customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': 'Original job',
            'quantity': '1', 'unit_price': '200.00',
        }])

        print("smoke_callbacks: original job, tech1 only (so callback_prefill's lead-tech pick is unambiguous)")
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': '2026-06-01', 'arrival_window_start': '9:00 AM',
            'work_site_label': 'Unit 100',
            'line_items_json': line_items, 'assigned_techs': [tech1],
            'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"original WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND work_site_label = 'Unit 100' ORDER BY id DESC LIMIT 1",
                    (customer_id,))
        wo1_id = cur.fetchone()['id']
        wo_ids.append(wo1_id)

        print("smoke_callbacks: workorder_customer_context lists it as a prior WO; excludes itself when editing")
        r = client.get(f'/getagrip/workorders/customer/{customer_id}/context')
        prior_ids = [w['id'] for w in r.get_json()['prior_workorders']]
        check("prior_workorders includes the original WO", wo1_id in prior_ids)
        r = client.get(f'/getagrip/workorders/customer/{customer_id}/context?exclude_wo_id={wo1_id}')
        prior_ids_excl = [w['id'] for w in r.get_json()['prior_workorders']]
        check("exclude_wo_id drops it from the list", wo1_id not in prior_ids_excl)

        print("smoke_callbacks: callback_prefill returns location/site/lead-tech/lines")
        r = client.get(f'/getagrip/workorders/{wo1_id}/callback_prefill')
        data = r.get_json()
        check("prefill site label matches", data['work_site_label'] == 'Unit 100')
        check("prefill lead tech is tech1", data['lead_tech_username'] == tech1)
        check("prefill has one catalog line item", len(data['line_items']) == 1
              and data['line_items'][0]['catalog_item_id'] == catalog_id)

        print("smoke_callbacks: a callback with no reason is rejected")
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'work_site_label': 'SMOKE Callback Invalid Attempt',
            'callback_of_work_order_id': str(wo1_id),
            'line_items_json': '[]', 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"rejected with a re-rendered form, not a redirect ({r.status_code})", r.status_code == 200)
        check("error message shown", b'A reason is required for a callback.' in r.data)
        cur.execute("SELECT id FROM work_orders WHERE work_site_label = 'SMOKE Callback Invalid Attempt'")
        check("no WO was actually created", cur.fetchone() is None)

        print("smoke_callbacks: a callback for a WO that isn't this customer's is rejected")
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(other_customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'work_site_label': 'SMOKE Callback CrossCustomer',
            'callback_of_work_order_id': str(wo1_id), 'callback_reason': 'test',
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"rejected ({r.status_code})", r.status_code == 200)
        check("error message shown", b'does not belong to this customer' in r.data)

        print("smoke_callbacks: WO2 -- unpaid (tech1 goes back himself)")
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '10:00 AM',
            'work_site_label': 'Unit 100 — Callback',
            'callback_of_work_order_id': str(wo1_id),
            'callback_reason': 'Tenant says tub still draining slow',
            'callback_responsible_username': tech1,
            'assigned_techs': [tech1],
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"WO2 created ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id, callback_of_work_order_id, callback_reason, callback_responsible_username
            FROM work_orders WHERE customer_id = %s AND work_site_label = 'Unit 100 — Callback' ORDER BY id DESC LIMIT 1
        """, (customer_id,))
        wo2 = cur.fetchone()
        wo2_id = wo2['id']
        wo_ids.append(wo2_id)
        check("WO2.callback_of_work_order_id points at WO1", wo2['callback_of_work_order_id'] == wo1_id)
        check("WO2.callback_reason saved", wo2['callback_reason'] == 'Tenant says tub still draining slow')
        check("WO2.callback_responsible_username saved", wo2['callback_responsible_username'] == tech1)

        print("smoke_callbacks: WO3 -- paid (tech1 responsible, tech2 actually goes)")
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'work_site_label': 'Unit 100 — Callback 2',
            'callback_of_work_order_id': str(wo1_id),
            'callback_reason': 'Still not draining, sending someone else this time',
            'callback_responsible_username': tech1,
            'assigned_techs': [tech2],
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"WO3 created ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id FROM work_orders WHERE customer_id = %s AND work_site_label = 'Unit 100 — Callback 2' ORDER BY id DESC LIMIT 1
        """, (customer_id,))
        wo3_id = cur.fetchone()['id']
        wo_ids.append(wo3_id)

        print("smoke_callbacks: WO list filter + badge")
        cur.execute("SELECT work_order_number FROM work_orders WHERE id = %s", (wo2_id,))
        wo2_number = cur.fetchone()['work_order_number']
        r = client.get('/getagrip/workorders?callback=1')
        check("callback filter includes WO2's number", wo2_number.encode() in r.data)
        r = client.get('/getagrip/workorders')
        check("unfiltered list shows a Callback badge", b'badge-callback' in r.data)

        print("smoke_callbacks: WO detail pages -- source banner + reverse list")
        cur.execute("SELECT work_order_number FROM work_orders WHERE id = %s", (wo1_id,))
        wo1_number = cur.fetchone()['work_order_number']
        r = client.get(f'/getagrip/workorders/{wo2_id}')
        check("WO2 detail shows it's a callback for WO1's number", wo1_number.encode() in r.data and b'Callback' in r.data)
        r = client.get(f'/getagrip/workorders/{wo1_id}')
        check("WO1 detail lists 2 callbacks against it", b'2 callback' in r.data)

        print("smoke_callbacks: customer detail Jobs list badges")
        r = client.get(f'/getagrip/customers/{customer_id}')
        check("customer detail shows a Callback badge", b'Callback</span>' in r.data)

        print("smoke_callbacks: dispatch board carries is_callback for a scheduled callback")
        r = client.get(f'/getagrip/dispatch/data?date={TODAY}')
        blocks = r.get_json()['blocks']
        wo2_block = next((b for b in blocks if b['id'] == wo2_id), None)
        check("WO2 is on today's board and flagged is_callback", wo2_block is not None and wo2_block['is_callback'] is True)

        print("smoke_callbacks: callbacks report -- grouped by tech, paid vs unpaid")
        r = client.get('/getagrip/reports/callbacks')
        check("report renders (200)", r.status_code == 200)
        body = r.data.decode()
        cur.execute("SELECT id, work_order_number FROM work_orders WHERE id = ANY(%s)", ([wo2_id, wo3_id],))
        numbers = {row['id']: row['work_order_number'] for row in cur.fetchall()}
        check("WO2's number is on the report", numbers[wo2_id] in body)
        check("WO3's number is on the report", numbers[wo3_id] in body)
        check("Unpaid badge present (WO2)", 'Unpaid' in body)
        check("Paid badge present (WO3)", '>Paid<' in body)

        print("smoke_callbacks: rating penalty -- 2 callbacks x -3 = -6")
        _job_recompute_customer_ratings('getagrip')
        cur.execute("SELECT callback_score, composite_score, payment_timeliness_score, cancellation_score, job_volume_score "
                    "FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        rating = cur.fetchone()
        check(f"callback_score == -6.0 ({rating['callback_score']})", float(rating['callback_score']) == -6.0)
        expected_composite = max(0.0, min(100.0, 100
            + float(rating['payment_timeliness_score']) + float(rating['cancellation_score'])
            + float(rating['callback_score']) + float(rating['job_volume_score'])))
        check(f"composite_score is the signed sum ({rating['composite_score']} == {expected_composite})",
              abs(float(rating['composite_score']) - expected_composite) < 0.01)

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            # NULL out callback_of_work_order_id first -- FK points wo2/wo3 -> wo1,
            # and wo1 would otherwise fail to delete while still referenced.
            cur.execute("UPDATE work_orders SET callback_of_work_order_id = NULL WHERE id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            # D-083 lesson: customer_ratings FKs to customers -- delete it first,
            # or one leftover row silently rolls back this whole finally block.
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_ratings WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        for key in ALL_COMPANY_KEYS:
            for uname in usernames:
                c2 = get_db_connection(key)
                cu2 = c2.cursor()
                cu2.execute("DELETE FROM user_company_dispatch WHERE user_id = (SELECT id FROM users WHERE username = %s)", (uname,))
                cu2.execute("DELETE FROM users WHERE username = %s", (uname,))
                c2.commit()
                cu2.close(); c2.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s), {len(usernames)} tech(s) removed.")


if __name__ == '__main__':
    main()
