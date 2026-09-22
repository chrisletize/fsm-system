"""
Smoke test: Increment 2.4 — replacements for the retired tag concept
(Misc Task / is_internal_task, and the derived "New Customer" badge).

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_tag_replacements.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, customer_ids = [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    TEST_DATE_1 = '2026-08-10'
    TEST_DATE_2 = '2026-08-20'

    try:
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '75.00',
        }])

        print("smoke_tag_replacements: Misc Task — no customer required, but WITHOUT notes it's rejected")
        r = client.post('/getagrip/workorders/new', data={
            'status': 'Scheduled', 'priority': 'Normal', 'start_date': TEST_DATE_1,
            'arrival_window_start': '9:00 AM', 'line_items_json': '[]',
            'duration_overridden': 'false', 'is_internal_task': 'on',
        }, follow_redirects=False)
        check(f"internal task with no notes_for_techs is rejected (200, re-renders) ({r.status_code})", r.status_code == 200)
        check("rejection message explains why", b'Describe what needs to be done' in r.data)

        print("smoke_tag_replacements: Misc Task — create an internal task with no customer, notes instead of line items")
        r = client.post('/getagrip/workorders/new', data={
            'status': 'Scheduled', 'priority': 'Normal', 'start_date': TEST_DATE_1,
            'arrival_window_start': '9:00 AM', 'line_items_json': line_items,  # deliberately sent anyway -- must be ignored, not saved
            'notes_for_techs': 'Pick up supplies from the shop.',
            'duration_overridden': 'false', 'is_internal_task': 'on',
        }, follow_redirects=False)
        check(f"internal task WO created without a customer ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id FROM work_orders
            WHERE is_internal_task = TRUE AND start_date = %s AND deleted_at IS NULL
            ORDER BY id DESC LIMIT 1
        """, (TEST_DATE_1,))
        wo_internal = cur.fetchone()['id']
        wo_ids.append(wo_internal)

        cur.execute("SELECT COUNT(*) AS n FROM work_order_line_items WHERE work_order_id = %s AND deleted_at IS NULL", (wo_internal,))
        check("submitted line items were IGNORED, not saved (internal tasks are never billed)", cur.fetchone()['n'] == 0)
        cur.execute("SELECT notes_for_techs FROM work_orders WHERE id = %s", (wo_internal,))
        check("notes_for_techs saved instead", cur.fetchone()['notes_for_techs'] == 'Pick up supplies from the shop.')

        cur.execute("SELECT customer_id, is_internal_task FROM work_orders WHERE id = %s", (wo_internal,))
        row = cur.fetchone()
        check("customer_id is NULL", row['customer_id'] is None)
        check("is_internal_task saved true", row['is_internal_task'] is True)

        print("smoke_tag_replacements: internal task appears in lists with 'Internal Task' label")
        r = client.get('/getagrip/workorders')
        check(f"WO list renders ({r.status_code})", r.status_code == 200)
        check("WO list shows 'Internal Task' for it", b'Internal Task' in r.data)

        r = client.get(f'/getagrip/dispatch/data?date={TEST_DATE_1}')
        check(f"dispatch data responds 200 ({r.status_code})", r.status_code == 200)
        data = r.get_json()
        block = next((b for b in data['blocks'] if b['id'] == wo_internal), None)
        check("internal task appears as a dispatch block", block is not None)
        check(f"customer_name is null in the JSON ({block and block.get('customer_name')})",
              block and block['customer_name'] is None)

        print("smoke_tag_replacements: internal task WO detail shows the badge, no invoice banner")
        r = client.get(f'/getagrip/workorders/{wo_internal}')
        check(f"WO detail renders ({r.status_code})", r.status_code == 200)
        check("shows 'Internal Task' badge", b'Internal Task' in r.data)
        check("shows 'no customer' in the customer field", b'Internal Task \xe2\x80\x94 no customer' in r.data)

        print("smoke_tag_replacements: Completed internal task cannot be invoiced")
        r = client.post(f'/getagrip/workorders/{wo_internal}/edit', data={
            'status': 'Completed', 'priority': 'Normal', 'start_date': TEST_DATE_1,
            'arrival_window_start': '9:00 AM', 'line_items_json': line_items,
            'notes_for_techs': 'Pick up supplies from the shop.',
            'duration_overridden': 'false', 'is_internal_task': 'on',
        }, follow_redirects=False)
        check(f"internal task marked Completed ({r.status_code})", r.status_code == 302)
        r = client.get(f'/getagrip/workorders/{wo_internal}')
        check("no 'Generate invoice now?' banner for an internal task", b'Generate invoice now?' not in r.data)
        r = client.post(f'/getagrip/workorders/{wo_internal}/invoice/new', follow_redirects=True)
        check(f"invoice attempt redirects back with an error, no crash ({r.status_code})", r.status_code == 200)
        cur.execute("SELECT count(*) AS n FROM invoices WHERE work_order_id = %s", (wo_internal,))
        check("no invoice was created", cur.fetchone()['n'] == 0)

        print("smoke_tag_replacements: New Customer badge — derived from completed-job history")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Tag Replacements Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TEST_DATE_1, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"first WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_first = cur.fetchone()['id']
        wo_ids.append(wo_first)

        r = client.get(f'/getagrip/workorders/{wo_first}')
        check("first-ever job for this customer IS flagged New Customer", b'New Customer' in r.data)

        r = client.post(f'/getagrip/workorders/{wo_first}/edit', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': TEST_DATE_1, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"first WO marked Completed ({r.status_code})", r.status_code == 302)

        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TEST_DATE_2, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"second WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND id != %s ORDER BY id DESC LIMIT 1",
                    (customer_id, wo_first))
        wo_second = cur.fetchone()['id']
        wo_ids.append(wo_second)

        r = client.get(f'/getagrip/workorders/{wo_second}')
        check("second job (after a completed one) is NOT flagged New Customer", b'New Customer' not in r.data)

        r = client.get(f'/getagrip/dispatch/data?date={TEST_DATE_2}')
        data2 = r.get_json()
        block2 = next((b for b in data2['blocks'] if b['id'] == wo_second), None)
        check("dispatch board also shows is_new_customer=false for the second job",
              block2 is not None and block2['is_new_customer'] is False)

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
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
