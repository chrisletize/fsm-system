"""
Smoke test: Increment 2.1 — tech profiles + dispatch board.

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_dispatch.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, DISPATCH_COLOR_PALETTE, ALL_COMPANY_KEYS  # noqa: E402


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
    wo_ids, customer_ids, usernames = [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    TEST_DATE = '2026-08-20'

    try:
        print("smoke_dispatch: create a dispatchable tech via the real user form")
        tech_username = 'smoketech1'
        r = client.post('/getagrip/settings/users/new', data={
            'username': tech_username, 'full_name': 'Smoke Tech One',
            'email': 'smoketech1@smoketest.invalid', 'role': 'technician',
            'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['getagrip'],
            'is_field_tech': 'on', 'can_be_dispatched': 'on',
            'phone_mobile': '7045550100', 'default_start_time': '08:00',
            'dispatch_sort_order': '1',
        }, follow_redirects=False)
        check(f"tech created ({r.status_code})", r.status_code == 302)
        usernames.append(tech_username)

        cur.execute("SELECT id, color_hex, is_field_tech, can_be_dispatched, is_active_tech FROM users WHERE username = %s", (tech_username,))
        u = cur.fetchone()
        expected_color = DISPATCH_COLOR_PALETTE[u['id'] % len(DISPATCH_COLOR_PALETTE)]
        check(f"color assigned by id %% 12 ({u['color_hex']} == {expected_color})", u['color_hex'] == expected_color)
        check("is_field_tech saved", u['is_field_tech'] is True)
        check("can_be_dispatched saved", u['can_be_dispatched'] is True)
        check("is_active_tech defaults true", u['is_active_tech'] is True)

        print("smoke_dispatch: edit the tech, verify tech fields round-trip")
        cur.execute("SELECT id FROM users WHERE username = %s", (tech_username,))
        tech_id = cur.fetchone()['id']
        r = client.post(f'/getagrip/settings/users/{tech_id}/edit', data={
            'full_name': 'Smoke Tech One', 'email': 'smoketech1@smoketest.invalid',
            'role': 'technician', 'company_access': ['getagrip'],
            'is_field_tech': 'on', 'can_be_dispatched': 'on', 'is_active_tech': 'on',
            'phone_mobile': '7045550199', 'default_start_time': '07:30',
            'dispatch_sort_order': '1',
        }, follow_redirects=False)
        check(f"tech edited ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT phone_mobile FROM users WHERE username = %s", (tech_username,))
        check("edited phone saved", cur.fetchone()['phone_mobile'] == '7045550199')

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Dispatch Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        print("smoke_dispatch: create a WO through the real form -> live catalog duration total")
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': 1, 'description': '', 'quantity': '2', 'unit_price': '275.00',
        }])
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TEST_DATE, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'assigned_techs': [tech_username],
            'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"WO created ({r.status_code})", r.status_code == 302)
        # workorder_new redirects to the LIST page, not the detail page --
        # find the new WO by customer_id (freshest id).
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        cur.execute("""
            SELECT scheduled_start, catalog_estimated_duration_hours, estimated_duration_hours, duration_overridden
            FROM work_orders WHERE id = %s
        """, (wo_id,))
        wo = cur.fetchone()
        check(f"catalog_estimated_duration_hours = 4.0 (120min x 2 / 60) ({wo['catalog_estimated_duration_hours']})",
              close(float(wo['catalog_estimated_duration_hours']), 4.0))
        check(f"estimated_duration_hours auto-synced to 4.0 ({wo['estimated_duration_hours']})",
              close(float(wo['estimated_duration_hours']), 4.0))
        check("duration_overridden is false", wo['duration_overridden'] is False)
        check(f"scheduled_start = {TEST_DATE} 09:00 ({wo['scheduled_start']})",
              wo['scheduled_start'].strftime('%Y-%m-%d %H:%M') == f'{TEST_DATE} 09:00')

        cur.execute("SELECT estimated_minutes FROM work_order_line_items WHERE work_order_id = %s", (wo_id,))
        check("line item snapshotted estimated_minutes from catalog (120)", cur.fetchone()['estimated_minutes'] == 120)

        print("smoke_dispatch: a second overlapping WO on the same tech -> collision detection")
        line_items2 = json.dumps([{
            'kind': 'std', 'catalog_item_id': 1, 'description': '', 'quantity': '1', 'unit_price': '275.00',
        }])
        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'High',
            'start_date': TEST_DATE, 'arrival_window_start': '10:00 AM',
            'line_items_json': line_items2, 'assigned_techs': [tech_username],
            'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"second WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND id != %s ORDER BY id DESC LIMIT 1",
                    (customer_id, wo_id))
        wo_id2 = cur.fetchone()['id']
        wo_ids.append(wo_id2)

        print("smoke_dispatch: dispatch/data endpoint")
        r = client.get(f'/getagrip/dispatch/data?date={TEST_DATE}')
        check(f"dispatch data responds 200 ({r.status_code})", r.status_code == 200)
        data = r.get_json()
        check(f"tech appears in techs list ({[t['username'] for t in data['techs']]})",
              any(t['username'] == tech_username for t in data['techs']))
        blocks_by_wo = {b['id']: b for b in data['blocks']}
        check("both WOs appear as blocks", wo_id in blocks_by_wo and wo_id2 in blocks_by_wo)
        check(f"first block duration = 4.0h ({blocks_by_wo[wo_id]['duration_hours']})",
              close(blocks_by_wo[wo_id]['duration_hours'], 4.0))
        check("first block collides with second (9:00-13:00 overlaps 10:00-...)",
              blocks_by_wo[wo_id]['collides_with'] is not None)
        check("second block collides with first",
              blocks_by_wo[wo_id2]['collides_with'] is not None)

        print("smoke_dispatch: dispatch page renders")
        r = client.get(f'/getagrip/dispatch?date={TEST_DATE}')
        check(f"dispatch page renders ({r.status_code})", r.status_code == 200)
        r = client.get(f'/getagrip/dispatch?date={TEST_DATE}&view=week')
        check(f"dispatch week view renders ({r.status_code})", r.status_code == 200)

        print("smoke_dispatch: /dispatch/move re-homes tech + time")
        r = client.post('/getagrip/dispatch/move',
                         data=json.dumps({'wo_id': wo_id2, 'username': '', 'scheduled_start': f'{TEST_DATE}T14:00:00'}),
                         content_type='application/json')
        check(f"move responds ok ({r.get_json()})", r.get_json().get('ok') is True)
        cur.execute("SELECT scheduled_start FROM work_orders WHERE id = %s", (wo_id2,))
        check("moved WO's scheduled_start updated to 14:00",
              cur.fetchone()['scheduled_start'].strftime('%H:%M') == '14:00')
        cur.execute("SELECT count(*) AS n FROM work_order_techs WHERE work_order_id = %s", (wo_id2,))
        check("moving to Unassigned ('') cleared tech assignment", cur.fetchone()['n'] == 0)

        print("smoke_dispatch: /dispatch/resize sets duration_overridden + returns warning")
        r = client.post('/getagrip/dispatch/resize',
                         data=json.dumps({'wo_id': wo_id, 'estimated_duration_hours': 1.0}),
                         content_type='application/json')
        res = r.get_json()
        check(f"resize responds ok ({res})", res.get('ok') is True)
        check("resize warns (4.0h catalog vs 1.0h scheduled is > 15min gap)", res.get('warning') is not None)
        cur.execute("SELECT estimated_duration_hours, duration_overridden FROM work_orders WHERE id = %s", (wo_id,))
        wo2 = cur.fetchone()
        check(f"estimated_duration_hours updated to 1.0 ({wo2['estimated_duration_hours']})",
              close(float(wo2['estimated_duration_hours']), 1.0))
        check("duration_overridden flipped true", wo2['duration_overridden'] is True)

        print("smoke_dispatch: /workorders/<id>/quick-status")
        r = client.post(f'/getagrip/workorders/{wo_id}/quick-status', data={'status': 'Completed'})
        check(f"quick-status responds ok ({r.get_json()})", r.get_json().get('ok') is True)
        cur.execute("SELECT status FROM work_orders WHERE id = %s", (wo_id,))
        check("status updated to Completed", cur.fetchone()['status'] == 'Completed')
        cur.execute("SELECT count(*) AS n FROM work_order_status_history WHERE work_order_id = %s AND status = 'Completed'", (wo_id,))
        check("status history row written", cur.fetchone()['n'] == 1)

        print("smoke_dispatch: WO list tech + date filters")
        r = client.get(f'/getagrip/workorders?tech={tech_username}&date={TEST_DATE}')
        check(f"WO list with tech+date filter renders ({r.status_code})", r.status_code == 200)
        check("filtered list shows the first WO", str(wo_id).encode() in r.data or b'SMOKE Dispatch Co' in r.data)

        print("smoke_dispatch: /workorders/new prefill from dispatch board click")
        r = client.get(f'/getagrip/workorders/new?tech={tech_username}&date={TEST_DATE}&time=13:00')
        check(f"prefilled new-WO form renders ({r.status_code})", r.status_code == 200)
        check("tech checkbox pre-checked",
              f'id="tech_{tech_username}"'.encode() in r.data and b'checked>' in r.data)
        check(f"date prefilled ({TEST_DATE})", TEST_DATE.encode() in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        # user_new/user_edit write to ALL four DBs (write_to_all_dbs) -- clean up
        # everywhere, not just getagrip, or the other three DBs accumulate a
        # residual row each run.
        for key in ALL_COMPANY_KEYS:
            for uname in usernames:
                c2 = get_db_connection(key)
                cu2 = c2.cursor()
                cu2.execute("DELETE FROM users WHERE username = %s", (uname,))
                c2.commit()
                cu2.close(); c2.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s), {len(usernames)} tech(s) removed.")


if __name__ == '__main__':
    main()
