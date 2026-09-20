"""
Smoke test: Increment 3.3 — recency report on live data (import_job_dates.py
itself is a one-time historical import, exercised by hand via its own
--dry-run, not by this smoke test — see docs/BUILD-LOG-2026-09.md).

Drives the real Flask routes (test client, forged admin session) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_recency.py
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, _recency_bucket  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, wo_ids, mc_ids, job_date_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        check("bucket boundaries: 29->None, 30->1-2, 59->1-2, 60->3-6, 182->3-6, 183->6-12, 364->6-12, 365->12+",
              _recency_bucket(29) is None and _recency_bucket(30) == '1-2 Months' and _recency_bucket(59) == '1-2 Months'
              and _recency_bucket(60) == '3-6 Months' and _recency_bucket(182) == '3-6 Months'
              and _recency_bucket(183) == '6-12 Months' and _recency_bucket(364) == '6-12 Months'
              and _recency_bucket(365) == '12+ Months')

        cur.execute("""
            INSERT INTO management_companies (name, created_by, updated_by)
            VALUES ('SMOKE Property Group', 'smoketest', 'smoketest') RETURNING id
        """)
        mc_id = cur.fetchone()['id']
        mc_ids.append(mc_id)
        conn.commit()

        print("smoke_recency: fixtures — one customer with a real WO 70 days ago (bucket 3-6), one with only imported job_dates 400 days ago (12+), one recent (excluded)")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, management_company_id, created_by, updated_by)
            VALUES ('SMOKE Recency WO Co', 'Commercial', 'Active', 'Net 30', %s, 'smoketest', 'smoketest')
            RETURNING id
        """, (mc_id,))
        cust_wo = cur.fetchone()['id']
        customer_ids.append(cust_wo)

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, management_company_id, created_by, updated_by)
            VALUES ('SMOKE Recency Import Co', 'Commercial', 'Active', 'Net 30', %s, 'smoketest', 'smoketest')
            RETURNING id
        """, (mc_id,))
        cust_import = cur.fetchone()['id']
        customer_ids.append(cust_import)

        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Recency Recent Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        cust_recent = cur.fetchone()['id']
        customer_ids.append(cust_recent)
        conn.commit()

        d_70 = (date.today() - timedelta(days=70)).isoformat()
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
            VALUES ('ZZZ-RECENCY-1', %s, 'Completed', %s, 'smoketest', 'smoketest') RETURNING id
        """, (cust_wo, d_70))
        wo_ids.append(cur.fetchone()['id'])

        d_400 = (date.today() - timedelta(days=400)).isoformat()
        cur.execute("""
            INSERT INTO customer_job_dates (customer_id, job_date, source, created_by)
            VALUES (%s, %s, 'servicefusion_import', 'smoketest') RETURNING id
        """, (cust_import, d_400))
        job_date_ids.append(cur.fetchone()['id'])

        d_5 = (date.today() - timedelta(days=5)).isoformat()
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
            VALUES ('ZZZ-RECENCY-2', %s, 'Completed', %s, 'smoketest', 'smoketest') RETURNING id
        """, (cust_recent, d_5))
        wo_ids.append(cur.fetchone()['id'])
        conn.commit()

        print("smoke_recency: report renders, correct bucketing, management-company grouping, recent customer excluded")
        r = client.get('/getagrip/reports/recency')
        check(f"report renders ({r.status_code})", r.status_code == 200)
        body = r.data.decode()
        check("SMOKE Property Group section present", 'SMOKE Property Group' in body)
        check("WO-derived customer appears under 3-6 Months", 'SMOKE Recency WO Co' in body)
        check("import-derived customer appears under 12+ Months", 'SMOKE Recency Import Co' in body)
        check("recent customer (5 days) is excluded entirely", 'SMOKE Recency Recent Co' not in body)

        # Confirm the WO-derived customer lands specifically inside the 3-6 bucket
        # section (not just present anywhere in the page). The 6-12 bucket is empty
        # for this fixture set and the template skips empty buckets entirely, so the
        # next marker after "3-6 Months" is whichever of "6-12 Months"/"12+ Months"
        # actually appears first.
        idx_36 = body.find('3-6 Months')
        candidates = [i for i in (body.find('6-12 Months', idx_36), body.find('12+ Months', idx_36)) if i != -1]
        idx_next = min(candidates) if candidates else -1
        section_36 = body[idx_36:idx_next] if idx_36 != -1 and idx_next != -1 else ''
        check("WO-derived customer is specifically inside the 3-6 Months section",
              'SMOKE Recency WO Co' in section_36)

        idx_12plus = body.find('12+ Months')
        section_12plus = body[idx_12plus:] if idx_12plus != -1 else ''
        check("import-derived customer is specifically inside the 12+ Months section",
              'SMOKE Recency Import Co' in section_12plus)

        print("smoke_recency: PDF export")
        r = client.get('/getagrip/reports/recency/pdf')
        check(f"PDF responds 200 ({r.status_code})", r.status_code == 200)
        check("PDF mimetype", r.mimetype == 'application/pdf')
        check("PDF contains the management company name (pageCompression=0)", b'SMOKE Property Group' in r.data)

        print("smoke_recency: reports landing links to it")
        r = client.get('/getagrip/reports')
        check("landing page links to /reports/recency", b'/reports/recency' in r.data)

        print("ALL CHECKS PASSED")

    finally:
        for jid in job_date_ids:
            cur.execute("DELETE FROM customer_job_dates WHERE id = %s", (jid,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_ratings WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        if mc_ids:
            cur.execute("DELETE FROM management_companies WHERE id = ANY(%s)", (mc_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(job_date_ids)} job date row(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s), {len(mc_ids)} management compan(y/ies) removed.")


if __name__ == '__main__':
    main()
