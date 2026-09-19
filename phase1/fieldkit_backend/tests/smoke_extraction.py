"""
Smoke test: Increment 2.2 — water extraction queue + accrual engine.

Drives the real Flask routes (test client, forged admin session) against live
kleanit_charlotte — NOT getagrip: Get a Grip doesn't do water extraction work
(Chris, 2026-09-19) and /extraction 404s there by design (see
COMPANIES_WITHOUT_EXTRACTION in app.py and smoke_extraction_company_gate.py).
Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_extraction.py
"""
import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('kleanit_charlotte')
    cur = conn.cursor()
    wo_ids, customer_ids, equipment_unit_ids = [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['kleanit_charlotte']

    try:
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Extraction Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='per_day_equipment' AND deleted_at IS NULL LIMIT 1")
        eq_catalog_id = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO equipment_units (name, catalog_item_id, is_active, created_by, updated_by)
            VALUES ('SMOKE Unit 1', %s, TRUE, 'smoketest', 'smoketest') RETURNING id
        """, (eq_catalog_id,))
        equipment_unit_id = cur.fetchone()['id']
        equipment_unit_ids.append(equipment_unit_id)
        conn.commit()

        deployed_date = (date.today() - timedelta(days=3)).isoformat()

        print("smoke_extraction: create a WO with an equipment line -> is_extraction auto-set")
        line_items = json.dumps([{
            'kind': 'eq', 'equipment_unit_id': equipment_unit_id,
            'deployed_at': deployed_date, 'retrieved_at': '',
        }])
        r = client.post('/kleanit_charlotte/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': deployed_date, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'false',
        }, follow_redirects=False)
        check(f"WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        cur.execute("SELECT is_extraction FROM work_orders WHERE id = %s", (wo_id,))
        check("is_extraction auto-set true (equipment line present, no checkbox)", cur.fetchone()['is_extraction'] is True)

        print("smoke_extraction: complete + 'Yes - Start Extraction' -> Extraction Active, backdated start")
        r = client.post(f'/kleanit_charlotte/workorders/{wo_id}/edit', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': deployed_date, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items,
            'duration_overridden': 'false', 'is_extraction': 'on',
            'extraction_action': 'start',
        }, follow_redirects=False)
        check(f"WO edit (start extraction) responds 302 ({r.status_code})", r.status_code == 302)

        cur.execute("""
            SELECT status, extraction_status, extraction_started_at
            FROM work_orders WHERE id = %s
        """, (wo_id,))
        wo = cur.fetchone()
        check(f"status = Extraction Active ({wo['status']})", wo['status'] == 'Extraction Active')
        check(f"extraction_status = Drying ({wo['extraction_status']})", wo['extraction_status'] == 'Drying')
        check(f"extraction_started_at follows the backdated deployed_at ({wo['extraction_started_at']})",
              wo['extraction_started_at'].isoformat() == deployed_date)

        print("smoke_extraction: dispatch board shows the extraction droplet badge")
        r = client.get(f'/kleanit_charlotte/dispatch/data?date={deployed_date}')
        data = r.get_json()
        block = next((b for b in data['blocks'] if b['id'] == wo_id), None)
        check("WO appears on the dispatch board that date", block is not None)
        check("has_equipment (is_extraction) true on the block", block and block['has_equipment'] is True)

        print("smoke_extraction: extraction queue page + day count")
        r = client.get('/kleanit_charlotte/extraction')
        check(f"queue page renders ({r.status_code})", r.status_code == 200)
        check("queue shows the WO", b'SMOKE Extraction Co' in r.data)
        check("queue shows day 4 (started 3 days ago, +1)", b'>4<' in r.data or b'4' in r.data)

        print("smoke_extraction: row action -> Needs More Time, writes daily log")
        r = client.post(f'/kleanit_charlotte/extraction/{wo_id}/log', data={'extraction_status': 'Needs More Time'})
        check(f"log action responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT extraction_status FROM work_orders WHERE id = %s", (wo_id,))
        check("extraction_status updated", cur.fetchone()['extraction_status'] == 'Needs More Time')
        cur.execute("""
            SELECT extraction_status FROM extraction_daily_log
            WHERE work_order_id = %s AND log_date = CURRENT_DATE
        """, (wo_id,))
        check("daily log row written for today", cur.fetchone()['extraction_status'] == 'Needs More Time')

        print("smoke_extraction: batch 'Log today's status for all'")
        r = client.post('/kleanit_charlotte/extraction/log-all', data={'wo_ids': [str(wo_id)]}, follow_redirects=False)
        check(f"log-all responds 302 ({r.status_code})", r.status_code == 302)

        print("smoke_extraction: Mark Ready + pickup list PDF")
        r = client.post(f'/kleanit_charlotte/extraction/{wo_id}/log', data={'extraction_status': 'Ready for Pickup'})
        check(f"mark ready responds 302 ({r.status_code})", r.status_code == 302)
        r = client.get('/kleanit_charlotte/extraction/pickup-list.pdf')
        check(f"pickup list PDF responds 200 ({r.status_code})", r.status_code == 200)
        check("pickup list mimetype is pdf", r.mimetype == 'application/pdf')
        check("pickup list contains the customer name (pageCompression=0)", b'SMOKE Extraction Co' in r.data)

        print("smoke_extraction: Retrieved -> closes the job, Completed, invoice-prompt-ready")
        cur.execute("""
            SELECT id, description, deployed_at::text AS deployed_at FROM work_order_line_items
            WHERE work_order_id = %s AND deleted_at IS NULL
              AND equipment_unit_id IS NOT NULL AND retrieved_at IS NULL
        """, (wo_id,))
        open_line = cur.fetchone()
        retrieve_date = date.today().isoformat()
        r = client.post(f'/kleanit_charlotte/extraction/{wo_id}/retrieve', data={
            f'retrieved_{open_line["id"]}': retrieve_date,
        }, follow_redirects=False)
        check(f"retrieve responds 302 ({r.status_code})", r.status_code == 302)

        cur.execute("""
            SELECT status, extraction_status, extraction_closed_at FROM work_orders WHERE id = %s
        """, (wo_id,))
        wo2 = cur.fetchone()
        check(f"status = Completed ({wo2['status']})", wo2['status'] == 'Completed')
        check(f"extraction_status = Equipment Retrieved ({wo2['extraction_status']})", wo2['extraction_status'] == 'Equipment Retrieved')
        check(f"extraction_closed_at set ({wo2['extraction_closed_at']})", wo2['extraction_closed_at'] is not None)
        cur.execute("SELECT retrieved_at::text AS r, quantity FROM work_order_line_items WHERE id = %s", (open_line['id'],))
        li = cur.fetchone()
        check(f"line retrieved_at set ({li['r']})", li['r'] == retrieve_date)
        check(f"line quantity recomputed to 3 billable days (deployed_at -> retrieved_at delta) ({li['quantity']})",
              float(li['quantity']) == 3.0)
        cur.execute("""
            SELECT count(*) AS n FROM work_order_status_history
            WHERE work_order_id = %s AND status = 'Completed'
        """, (wo_id,))
        check("status history row written for the close", cur.fetchone()['n'] == 1)

        print("smoke_extraction: WO detail offers 'Create Follow-Up Cleaning Work Order'")
        r = client.get(f'/kleanit_charlotte/workorders/{wo_id}')
        check(f"WO detail renders ({r.status_code})", r.status_code == 200)
        check("follow-up offer button present", b'Create Follow-Up Cleaning Work Order' in r.data)

        print("smoke_extraction: follow-up WO prefill flow")
        r = client.get(f'/kleanit_charlotte/workorders/{wo_id}/followup-new', follow_redirects=False)
        check(f"followup-new redirects ({r.status_code})", r.status_code == 302)
        location = r.headers['Location']
        check(f"redirect carries parent_id + customer_id + followup=1 ({location})",
              f'parent_id={wo_id}' in location and f'customer_id={customer_id}' in location and 'followup=1' in location)
        r = client.get(location)
        check(f"prefilled new-WO form renders ({r.status_code})", r.status_code == 200)
        check("customer name pre-filled in the combo", b'SMOKE Extraction Co' in r.data)
        check("parent_work_order_id hidden field carries the parent",
              f'name="parent_work_order_id" value="{wo_id}"'.encode() in r.data)
        check("Follow-Up Visit checkbox pre-checked",
              b'id="chkFollowup"\n                       checked' in r.data or (b'chkFollowup' in r.data and b'checked' in r.data))

        print("smoke_extraction: equipment_incomplete auto-clears once an equipment line is saved")
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        std_catalog_id = cur.fetchone()['id']
        line_items_std_only = json.dumps([{
            'kind': 'std', 'catalog_item_id': std_catalog_id, 'description': '', 'quantity': '1', 'unit_price': '50.00',
        }])
        r = client.post('/kleanit_charlotte/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': date.today().isoformat(), 'line_items_json': line_items_std_only,
            'duration_overridden': 'false', 'equipment_incomplete': 'on',
        }, follow_redirects=False)
        check(f"second WO created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND id != %s ORDER BY id DESC LIMIT 1",
                    (customer_id, wo_id))
        wo_id2 = cur.fetchone()['id']
        wo_ids.append(wo_id2)
        cur.execute("SELECT equipment_incomplete FROM work_orders WHERE id = %s", (wo_id2,))
        check("equipment_incomplete=true saved (no equipment line yet)", cur.fetchone()['equipment_incomplete'] is True)

        line_items_with_eq = json.dumps([
            {'kind': 'std', 'catalog_item_id': std_catalog_id, 'description': '', 'quantity': '1', 'unit_price': '50.00'},
            {'kind': 'eq', 'equipment_unit_id': equipment_unit_id, 'deployed_at': date.today().isoformat(), 'retrieved_at': ''},
        ])
        r = client.post(f'/kleanit_charlotte/workorders/{wo_id2}/edit', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': date.today().isoformat(), 'line_items_json': line_items_with_eq,
            'duration_overridden': 'false', 'equipment_incomplete': 'on',  # still checked in the form...
        }, follow_redirects=False)
        check(f"WO2 edit adding equipment line responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT equipment_incomplete, is_extraction FROM work_orders WHERE id = %s", (wo_id2,))
        wo2b = cur.fetchone()
        check("equipment_incomplete auto-cleared despite checkbox staying checked", wo2b['equipment_incomplete'] is False)
        check("is_extraction auto-set true", wo2b['is_extraction'] is True)

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM extraction_daily_log WHERE work_order_id = %s", (wid,))
            cur.execute("UPDATE work_orders SET parent_work_order_id = NULL WHERE parent_work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if equipment_unit_ids:
            cur.execute("DELETE FROM equipment_units WHERE id = ANY(%s)", (equipment_unit_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(wo_ids)} WO(s), {len(equipment_unit_ids)} equipment unit(s), "
              f"{len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
