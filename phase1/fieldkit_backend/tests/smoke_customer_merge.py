"""
Smoke test: Increment 5.2 — Duplicate detection + customer merge (directive §5.2).

Drives the real Flask routes (test client, forged sessions per role) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_customer_merge.py
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


def client_as(role):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = role
        sess['company_access'] = ['getagrip']
    return c


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, wo_ids, merge_log_ids = [], [], []
    admin = client_as('admin')

    try:
        print("smoke_customer_merge: duplicate detection at create — normalized name + address match")
        r = admin.post('/getagrip/customers/new', data={
            'property_name': 'SMOKE Merge Co', 'customer_type': 'Commercial', 'status': 'Active',
            'address': '100 Oak St.', 'payment_terms': 'Net 30',
        }, follow_redirects=False)
        check(f"customer A created ({r.status_code})", r.status_code == 302)
        source_id = int(r.headers['Location'].rstrip('/').split('/')[-1])
        customer_ids.append(source_id)

        r = admin.get(f'/getagrip/customers/dupe_check?name=SMOKE+Merge+Co&address=100+oak+st')
        data = r.get_json()
        check("dupe_check matches on normalized name+address (punctuation/case-insensitive)",
              any(m['id'] == source_id for m in data['matches']), data)

        r = admin.get(f'/getagrip/customers/dupe_check?name=SMOKE+Merge+Co&address=100+oak+st&exclude_id={source_id}')
        data = r.get_json()
        check("dupe_check exclude_id omits the customer itself", data['matches'] == [], data)

        print("smoke_customer_merge: fixtures — source customer with a contact/note/location/WO/field-value/job-date")
        r = admin.post('/getagrip/customers/new', data={
            'property_name': 'SMOKE Merge Target', 'customer_type': 'Commercial', 'status': 'Active',
            'payment_terms': 'Net 30',
        }, follow_redirects=False)
        check(f"target customer created ({r.status_code})", r.status_code == 302)
        target_id = int(r.headers['Location'].rstrip('/').split('/')[-1])
        customer_ids.append(target_id)

        cur.execute("""
            INSERT INTO customer_contacts (customer_id, first_name, last_name, is_primary, created_by, updated_by)
            VALUES (%s, 'Smoke', 'Contact', TRUE, 'smoketest', 'smoketest')
        """, (source_id,))
        cur.execute("""
            INSERT INTO customer_notes (customer_id, note_text, note_type, created_by)
            VALUES (%s, 'pre-merge note', 'General', 'smoketest')
        """, (source_id,))
        cur.execute("""
            INSERT INTO service_locations (customer_id, location_name, is_primary, created_by, updated_by)
            VALUES (%s, 'Main Site', TRUE, 'smoketest', 'smoketest')
        """, (source_id,))
        cur.execute("""
            INSERT INTO customer_field_values (customer_id, field_definition_id, value, updated_by)
            VALUES (%s, 1, 'blue/green', 'smoketest')
        """, (source_id,))
        # Collision case: both source and target already have a value for field_definition_id=2 --
        # the merge must NOT try to move the source's row on top of the target's (UNIQUE violation),
        # and must leave exactly one winner (the target's).
        cur.execute("""
            INSERT INTO customer_field_values (customer_id, field_definition_id, value, updated_by)
            VALUES (%s, 2, 'source-code-999', 'smoketest')
        """, (source_id,))
        cur.execute("""
            INSERT INTO customer_field_values (customer_id, field_definition_id, value, updated_by)
            VALUES (%s, 2, 'target-code-111', 'smoketest')
        """, (target_id,))
        # Collision case on customer_job_dates: same job_date on both sides.
        cur.execute("""
            INSERT INTO customer_job_dates (customer_id, job_date, source, created_by)
            VALUES (%s, '2026-05-01', 'manual', 'smoketest'), (%s, '2026-06-01', 'manual', 'smoketest')
        """, (source_id, source_id))
        cur.execute("""
            INSERT INTO customer_job_dates (customer_id, job_date, source, created_by)
            VALUES (%s, '2026-05-01', 'manual', 'smoketest')
        """, (target_id,))
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '50.00',
        }])
        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(source_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': date.today().isoformat(), 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"source WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (source_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        print("smoke_customer_merge: preview reflects the real fixture counts")
        r = admin.get(f'/getagrip/customers/merge_preview?source_id={source_id}&target_id={target_id}')
        preview = r.get_json()
        check(f"preview 200 ({r.status_code})", r.status_code == 200)
        check("preview source work_orders count == 1", preview['source']['counts']['work_orders'] == 1, preview)
        check("preview source customer_contacts count == 1", preview['source']['counts']['customer_contacts'] == 1)
        check("preview source customer_field_values count == 2", preview['source']['counts']['customer_field_values'] == 2)
        check("preview target customer_field_values count == 1", preview['target']['counts']['customer_field_values'] == 1)

        print("smoke_customer_merge: non-admin is blocked from merge routes")
        manager = client_as('manager')
        r = manager.get(f'/getagrip/customers/{source_id}/merge')
        check(f"manager GET /merge -> 403 ({r.status_code})", r.status_code == 403)
        r = manager.post(f'/getagrip/customers/{source_id}/merge', data={'target_customer_id': str(target_id)})
        check(f"manager POST /merge -> 403 ({r.status_code})", r.status_code == 403)

        print("smoke_customer_merge: confirm the merge")
        r = admin.post(f'/getagrip/customers/{source_id}/merge',
                        data={'target_customer_id': str(target_id)}, follow_redirects=False)
        check(f"merge POST redirects to target ({r.status_code})", r.status_code == 302)
        check("redirect target is the target customer", r.headers['Location'].endswith(f'/customers/{target_id}'))

        print("smoke_customer_merge: re-pointed records land on the target")
        cur.execute("SELECT customer_id FROM work_orders WHERE id = %s", (wo_id,))
        check("WO re-pointed to target", cur.fetchone()['customer_id'] == target_id)
        cur.execute("SELECT COUNT(*) AS n FROM customer_contacts WHERE customer_id = %s", (target_id,))
        check("contact re-pointed to target", cur.fetchone()['n'] == 1)
        cur.execute("SELECT COUNT(*) AS n FROM service_locations WHERE customer_id = %s", (target_id,))
        check("service location re-pointed to target", cur.fetchone()['n'] == 1)

        print("smoke_customer_merge: unique-constraint collisions handled without error")
        cur.execute("SELECT value FROM customer_field_values WHERE customer_id = %s AND field_definition_id = 2", (target_id,))
        check("target keeps its OWN field_definition_id=2 value (not overwritten by source's)",
              cur.fetchone()['value'] == 'target-code-111')
        cur.execute("SELECT COUNT(*) AS n FROM customer_field_values WHERE customer_id = %s AND field_definition_id = 1", (target_id,))
        check("non-colliding field value (id=1) moved to target", cur.fetchone()['n'] == 1)
        cur.execute("SELECT COUNT(*) AS n FROM customer_job_dates WHERE customer_id = %s", (target_id,))
        check("target has both job dates (5/1 pre-existing + 6/1 moved, not a duplicate 5/1)", cur.fetchone()['n'] == 2)

        print("smoke_customer_merge: source soft-deleted, merged_into_customer_id set, notes + log written")
        cur.execute("SELECT deleted_at, merged_into_customer_id FROM customers WHERE id = %s", (source_id,))
        src = cur.fetchone()
        check("source soft-deleted", src['deleted_at'] is not None)
        check("source merged_into_customer_id points at target", src['merged_into_customer_id'] == target_id)

        cur.execute("SELECT COUNT(*) AS n FROM customer_notes WHERE customer_id = %s AND note_type = 'Merge'", (target_id,))
        check("merge note added to target", cur.fetchone()['n'] == 1)
        cur.execute("SELECT COUNT(*) AS n FROM customer_notes WHERE customer_id = %s AND note_type = 'Merge'", (source_id,))
        check("merge note added to source", cur.fetchone()['n'] == 1)

        cur.execute("""
            SELECT id, details FROM customer_merge_log
            WHERE source_customer_id = %s AND target_customer_id = %s
        """, (source_id, target_id))
        log_row = cur.fetchone()
        check("customer_merge_log row written", log_row is not None)
        merge_log_ids.append(log_row['id'])
        details = log_row['details'] if isinstance(log_row['details'], dict) else json.loads(log_row['details'])
        check("merge log details recorded work_orders: 1", details.get('work_orders') == 1, details)

        print("smoke_customer_merge: visiting the merged (source) customer redirects to the target")
        r = admin.get(f'/getagrip/customers/{source_id}', follow_redirects=False)
        check(f"source detail redirects ({r.status_code})", r.status_code == 302)
        check("redirects to target", r.headers['Location'].endswith(f'/customers/{target_id}'))

        print("ALL CHECKS PASSED")

    finally:
        for mid in merge_log_ids:
            cur.execute("DELETE FROM customer_merge_log WHERE id = %s", (mid,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_notes WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_contacts WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM service_locations WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_field_values WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_job_dates WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close(); conn.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s), "
              f"{len(merge_log_ids)} merge log row(s) removed.")


if __name__ == '__main__':
    main()
