"""
Smoke test: Increment 5.1 — Dashboard (directive §5.1).

Drives the real Flask routes (test client, forged sessions per role) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_dashboard.py
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
    wo_ids, customer_ids = [], []
    TODAY = date.today().isoformat()

    admin = client_as('admin')

    try:
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Dashboard Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '100.00',
        }])

        print("smoke_dashboard: baseline read (admin) before fixtures")
        r = client_as('admin').get('/getagrip/dashboard')
        check(f"dashboard 200 ({r.status_code})", r.status_code == 200)
        import re
        def extract_dollar(label_snippet, html):
            # crude but adequate: find the stat tile whose label contains the snippet
            m = re.search(r'\$([\d,]+)</div>\s*<div class="label">' + re.escape(label_snippet), html)
            return float(m.group(1).replace(',', '')) if m else None
        def extract_90plus(html):
            # "Outstanding A/R ($X 90+)" -- pull the 90+ figure out of the label text.
            m = re.search(r'Outstanding A/R \(\$([\d,]+) 90\+\)', html)
            return float(m.group(1).replace(',', '')) if m else None

        html0 = r.data.decode()
        baseline_ar = extract_dollar('Outstanding A/R', html0)
        baseline_90plus = extract_90plus(html0)

        print("smoke_dashboard: WO scheduled TODAY shows up in today's-jobs count")
        r = admin.get('/getagrip/dashboard')
        m = re.search(r'<div class="n">(\d+)</div>\s*<div class="label">Today', r.data.decode())
        before_today = int(m.group(1))

        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"WO1 (today, Scheduled) created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo1 = cur.fetchone()['id']
        wo_ids.append(wo1)

        r = admin.get('/getagrip/dashboard')
        m = re.search(r'<div class="n">(\d+)</div>\s*<div class="label">Today', r.data.decode())
        after_today = int(m.group(1))
        check("today's-jobs count incremented by 1", after_today == before_today + 1,
              f"(before={before_today}, after={after_today})")

        print("smoke_dashboard: Completed WO with no invoice shows up as uninvoiced (loud)")
        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Completed', 'priority': 'Normal',
            'start_date': TODAY, 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [],
        }, follow_redirects=False)
        check(f"WO2 (Completed, uninvoiced) created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s AND id != %s ORDER BY id DESC LIMIT 1",
                    (customer_id, wo1))
        wo2 = cur.fetchone()['id']
        wo_ids.append(wo2)

        r = admin.get('/getagrip/dashboard')
        html = r.data.decode()
        check("SMOKE Dashboard Co appears under Uninvoiced Completed Work Orders", 'SMOKE Dashboard Co' in html)
        check("stat tile carries the loud class when uninvoiced > 0", 'stat-tile loud' in html)

        print("smoke_dashboard: recent activity shows the new WO's status-history events")
        r = admin.get('/getagrip/dashboard')
        html = r.data.decode()
        cur.execute("SELECT work_order_number FROM work_orders WHERE id = %s", (wo2,))
        wo2_number = cur.fetchone()['work_order_number']
        check("recent activity shows WO2's number", wo2_number in html)

        print("smoke_dashboard: outstanding A/R + 90+ + unapplied credits read from customer_flags cache")
        r = admin.get('/getagrip/dashboard')
        baseline_credit = extract_dollar('Unapplied Credits', r.data.decode())
        cur.execute("""
            INSERT INTO customer_flags (customer_id, is_delinquent, oldest_open_invoice_date,
                open_balance, unapplied_credit, computed_at)
            VALUES (%s, TRUE, %s, 543.21, 12.50, CURRENT_TIMESTAMP)
        """, (customer_id, date(2020, 1, 1)))
        conn.commit()

        r = admin.get('/getagrip/dashboard')
        html = r.data.decode()
        after_ar = extract_dollar('Outstanding A/R', html)
        check("outstanding A/R increased by the fixture's open_balance (543)",
              after_ar is not None and baseline_ar is not None and round(after_ar - baseline_ar) == 543,
              f"(baseline={baseline_ar}, after={after_ar})")
        after_90plus = extract_90plus(html)
        check("90+ figure increased by the fixture's open_balance (543, since is_delinquent=TRUE)",
              after_90plus is not None and baseline_90plus is not None and round(after_90plus - baseline_90plus) == 543,
              f"(baseline={baseline_90plus}, after={after_90plus})")
        after_credit = extract_dollar('Unapplied Credits', html)
        check("unapplied credits increased by the fixture's $12.50 (Python %.0f rounds .5 to even -> 12)",
              after_credit is not None and baseline_credit is not None and round(after_credit - baseline_credit) == 12,
              f"(baseline={baseline_credit}, after={after_credit})")

        print("smoke_dashboard: role-based visibility — technician sees no financial tiles")
        tech = client_as('technician')
        r = tech.get('/getagrip/dashboard')
        check(f"technician dashboard 200 ({r.status_code})", r.status_code == 200)
        html = r.data.decode()
        check("technician does NOT see Outstanding A/R", 'Outstanding A/R' not in html)
        check("technician does NOT see Uninvoiced Completed WOs", 'Uninvoiced Completed' not in html)
        check("technician still sees Today's Jobs", "Today's Jobs" in html)

        print("smoke_dashboard: salesperson sees follow-ups but not approvals; admin sees both")
        sales = client_as('salesperson')
        r = sales.get('/getagrip/dashboard')
        html = r.data.decode()
        check("salesperson sees Follow-Ups Due", 'Follow-Ups Due' in html)
        check("salesperson does NOT see Pending Approvals", 'Pending Approvals' not in html)

        r = admin.get('/getagrip/dashboard')
        html = r.data.decode()
        check("admin sees Follow-Ups Due", 'Follow-Ups Due' in html)
        check("admin sees Pending Approvals", 'Pending Approvals' in html)

        print("smoke_dashboard: quick actions respect role (estimate link only for estimate roles)")
        r = tech.get('/getagrip/dashboard')
        html = r.data.decode()
        check("technician has no + New Estimate quick action", '+ New Estimate' not in html)
        r = sales.get('/getagrip/dashboard')
        html = r.data.decode()
        check("salesperson has + New Estimate quick action", '+ New Estimate' in html)
        check("salesperson has no Record Payment quick action", 'Record Payment' not in html)

        print("ALL CHECKS PASSED")

    finally:
        cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
        for wid in wo_ids:
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
