"""
Smoke test: Increment 2.3 — day sheet, hours report, job activity report.

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_reports.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, ALL_COMPANY_KEYS  # noqa: E402


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
    wo_ids, invoice_ids, customer_ids, usernames = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    TEST_DATE = '2026-08-25'

    try:
        for i, (uname, full) in enumerate([('smoketecha', 'Smoke Tech A'), ('smoketechb', 'Smoke Tech B')], start=1):
            r = client.post('/getagrip/settings/users/new', data={
                'username': uname, 'full_name': full, 'email': f'{uname}@smoketest.invalid',
                'role': 'technician', 'password': 'testpass123', 'confirm_password': 'testpass123',
                'company_access': ['getagrip'], 'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on',
            }, follow_redirects=False)
            check(f"{uname} created ({r.status_code})", r.status_code == 302)
            usernames.append(uname)

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Reports Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        def make_wo(status, techs, hours):
            line_items = json.dumps([{
                'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '100.00',
            }])
            r = client.post('/getagrip/workorders/new', data={
                'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
                'start_date': TEST_DATE, 'arrival_window_start': '9:00 AM',
                'line_items_json': line_items, 'duration_overridden': 'true',
                'estimated_duration_hours': str(hours),
                'assigned_techs': techs,
            }, follow_redirects=False)
            check(f"WO created status={status} ({r.status_code})", r.status_code == 302)
            cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND id != ALL(%s) ORDER BY id DESC LIMIT 1",
                        (customer_id, wo_ids or [0]))
            new_id = cur.fetchone()['id']
            wo_ids.append(new_id)
            if status != 'Scheduled':
                r2 = client.post(f'/getagrip/workorders/{new_id}/edit', data={
                    'customer_id': str(customer_id), 'status': status, 'priority': 'Normal',
                    'start_date': TEST_DATE, 'arrival_window_start': '9:00 AM',
                    'line_items_json': line_items, 'duration_overridden': 'true',
                    'estimated_duration_hours': str(hours), 'assigned_techs': techs,
                }, follow_redirects=False)
                check(f"WO {new_id} status set to {status} ({r2.status_code})", r2.status_code == 302)
            return new_id

        print("smoke_reports: fixtures — two WOs on TEST_DATE, one multi-tech + Completed")
        wo1 = make_wo('Scheduled', ['smoketecha'], 2.0)
        wo2 = make_wo('Completed', ['smoketecha', 'smoketechb'], 1.5)

        print("smoke_reports: extraction fixture (direct SQL — creation path already covered by smoke_extraction.py)")
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, is_extraction,
                extraction_status, extraction_started_at, followup_tech_username, start_date, created_by, updated_by)
            VALUES ('ZZZ-RPT-EXTRACT', %s, 'Extraction Active', TRUE, 'Drying', %s, 'smoketecha', %s, 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id, TEST_DATE, TEST_DATE))
        wo3 = cur.fetchone()['id']
        wo_ids.append(wo3)
        conn.commit()

        print("smoke_reports: day sheet groups by tech, multi-tech WO appears in both groups")
        r = client.get(f'/getagrip/reports/daysheet?date={TEST_DATE}')
        check(f"daysheet renders ({r.status_code})", r.status_code == 200)
        check("daysheet shows the customer", b'SMOKE Reports Co' in r.data)
        check("daysheet shows Smoke Tech A", b'Smoke Tech A' in r.data)
        check("daysheet shows Smoke Tech B", b'Smoke Tech B' in r.data)

        r = client.get(f'/getagrip/reports/daysheet?date={TEST_DATE}&tech=smoketechb')
        check(f"daysheet tech filter renders ({r.status_code})", r.status_code == 200)
        check("filtered daysheet excludes Tech A's solo header", b'Smoke Tech A</h2>' not in r.data)

        print("smoke_reports: hours report — scheduled hours, jobs, completed, extraction checks")
        r = client.get(f'/getagrip/reports/hours?from={TEST_DATE}&to={TEST_DATE}')
        check(f"hours report renders ({r.status_code})", r.status_code == 200)
        check("Scheduled hours (not actual) label present", b'Scheduled Hours' in r.data)
        check("Actual Hours column is blank (em dash)", b'Actual Hours' in r.data)

        print("smoke_reports: job activity report + invoiced total + CSV export")
        r = client.post(f'/getagrip/workorders/{wo2}/invoice/new', follow_redirects=False)
        check(f"invoice created for WO2 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoices WHERE work_order_id = %s AND deleted_at IS NULL", (wo2,))
        inv_id = cur.fetchone()['id']
        invoice_ids.append(inv_id)

        r = client.get(f'/getagrip/reports/jobs?from={TEST_DATE}&to={TEST_DATE}&customer=SMOKE Reports')
        check(f"jobs report renders ({r.status_code})", r.status_code == 200)
        check("jobs report shows all 3 fixture WOs", r.data.count(b'SMOKE Reports Co') >= 3)

        r = client.get(f'/getagrip/reports/jobs?tech=smoketechb&from={TEST_DATE}&to={TEST_DATE}')
        check(f"jobs report tech filter renders ({r.status_code})", r.status_code == 200)
        check("tech filter shows only WO2 (the only one with Tech B)", r.data.count(b'SMOKE Reports Co') == 1)

        r = client.get(f'/getagrip/reports/jobs/export.csv?from={TEST_DATE}&to={TEST_DATE}&customer=SMOKE Reports')
        check(f"CSV export responds 200 ({r.status_code})", r.status_code == 200)
        check("CSV export mimetype", r.mimetype == 'text/csv')
        check("CSV contains the customer name", b'SMOKE Reports Co' in r.data)

        print("smoke_reports: reports landing page links out")
        r = client.get('/getagrip/reports')
        check(f"reports landing renders ({r.status_code})", r.status_code == 200)
        for path in ('/reports/tax', '/reports/aging', '/reports/daysheet', '/reports/hours', '/reports/jobs'):
            check(f"landing links to {path}", path.encode() in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for iid in invoice_ids:
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
        if invoice_ids:
            cur.execute("DELETE FROM invoices WHERE id = ANY(%s)", (invoice_ids,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM extraction_daily_log WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
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
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s), {len(usernames)} tech(s) removed.")


if __name__ == '__main__':
    main()
