"""
Smoke test: Increment 3.2 — customer rating system.

Drives the real Flask routes (test client, forged admin session) against
live getagrip, plus calls _job_recompute_customer_ratings() directly for
precise numeric checks. Everything created is hard-deleted in a `finally`
block. Run inside the app container:

    docker compose exec -T app python tests/smoke_customer_ratings.py
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, _job_recompute_customer_ratings, _rating_letter  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def close(a, b, tol=0.05):
    return abs(a - b) < tol


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    customer_ids, wo_ids, invoice_ids = [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        check("_rating_letter bands: 90->A, 89.99->B, 75->B, 60->C, 40->D, 39.99->F",
              _rating_letter(90) == 'A' and _rating_letter(89.99) == 'B' and _rating_letter(75) == 'B'
              and _rating_letter(60) == 'C' and _rating_letter(40) == 'D' and _rating_letter(39.99) == 'F')

        print("smoke_customer_ratings: kitchen-sink customer — payment + cancellation + volume all together")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Rating Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        conn.commit()

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        # One open invoice, 120 days old: days_past_30=90, factor=min(90/30,4)=3,
        # penalty=3*5=15, plus 10 (90+ bucket) = 25 total -> payment_timeliness_score = -25.0
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-RATE-INV', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_inv = cur.fetchone()['id']
        wo_ids.append(wo_inv)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Smoke line', 1, 500.00, 500.00, FALSE, 0, 'smoketest', 'smoketest')
        """, (wo_inv, catalog_id))
        conn.commit()
        r = client.post(f'/getagrip/workorders/{wo_inv}/invoice/new', follow_redirects=False)
        check(f"invoice created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoices WHERE work_order_id = %s", (wo_inv,))
        inv_id = cur.fetchone()['id']
        invoice_ids.append(inv_id)
        old_date = (date.today() - timedelta(days=120)).isoformat()
        cur.execute("UPDATE invoices SET invoice_date = %s WHERE id = %s", (old_date, inv_id))
        conn.commit()
        client.post(f'/getagrip/invoices/{inv_id}/harden')
        client.post(f'/getagrip/invoices/{inv_id}/send')

        # 4 trailing-12mo WOs: 1 Cancelled, 2 Completed, 1 Scheduled.
        # cancellation: 1/4 = 0.25 x 40 = 10 -> cancellation_score = -10.0
        # volume: 2 completed x 0.5 = 1.0 -> job_volume_score = +1.0
        recent = (date.today() - timedelta(days=10)).isoformat()
        for i, status in enumerate(['Cancelled', 'Completed', 'Completed', 'Scheduled']):
            cur.execute("""
                INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
                VALUES (%s, %s, %s, %s, 'smoketest', 'smoketest') RETURNING id
            """, (f'ZZZ-RATE-{i}', customer_id, status, recent))
            wo_ids.append(cur.fetchone()['id'])
        conn.commit()

        n = _job_recompute_customer_ratings('getagrip')
        check(f"ratings recomputed for all customers ({n})", n > 0)

        cur.execute("SELECT * FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        rating = cur.fetchone()
        check(f"payment_timeliness_score = -25.0 ({rating['payment_timeliness_score']})",
              close(float(rating['payment_timeliness_score']), -25.0))
        check(f"cancellation_score = -10.0 ({rating['cancellation_score']})",
              close(float(rating['cancellation_score']), -10.0))
        check(f"job_volume_score = +1.0 ({rating['job_volume_score']})",
              close(float(rating['job_volume_score']), 1.0))
        # composite = 100 - 25 - 10 + 1.0 = 66.0 -> band C (60-74)
        check(f"composite_score = 66.0 ({rating['composite_score']})", close(float(rating['composite_score']), 66.0))
        check(f"letter_grade = C ({rating['letter_grade']})", rating['letter_grade'] == 'C')
        check("adjusted_letter_grade defaults to the algorithmic grade (no override yet)",
              rating['adjusted_letter_grade'] == 'C')

        print("smoke_customer_ratings: customer detail shows the breakdown + badge")
        r = client.get(f'/getagrip/customers/{customer_id}')
        check(f"customer detail renders ({r.status_code})", r.status_code == 200)
        check("shows Customer Rating section", b'Customer Rating' in r.data)
        check("shows the composite score", b'66.0' in r.data or b'66.00' in r.data)

        print("smoke_customer_ratings: WO form embeds adjusted_letter_grade for this customer")
        r = client.get('/getagrip/workorders/new')
        body = r.data.decode()
        check("customer options JSON carries the grade",
              '"adjusted_letter_grade": "C"' in body or '"adjusted_letter_grade":"C"' in body)

        print("smoke_customer_ratings: manager override — set, verify, clear")
        r = client.post(f'/getagrip/customers/{customer_id}/rating-override', data={
            'manager_adjustment': '20', 'manager_adjustment_note': 'Longtime client, bumping up.',
        }, follow_redirects=False)
        check(f"override save responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT manager_adjustment, adjusted_letter_grade, manager_adjustment_note FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        rating2 = cur.fetchone()
        check(f"manager_adjustment saved as 20.0 ({rating2['manager_adjustment']})", close(float(rating2['manager_adjustment']), 20.0))
        # 66 + 20 = 86 -> band B (75-89)
        check(f"adjusted_letter_grade = B (66+20=86) ({rating2['adjusted_letter_grade']})", rating2['adjusted_letter_grade'] == 'B')
        check("note saved", rating2['manager_adjustment_note'] == 'Longtime client, bumping up.')

        r = client.post(f'/getagrip/customers/{customer_id}/rating-override', data={
            'manager_adjustment': '', 'manager_adjustment_note': '',
        }, follow_redirects=False)
        check(f"clearing the override responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT manager_adjustment, adjusted_letter_grade FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        rating3 = cur.fetchone()
        check("manager_adjustment cleared to NULL", rating3['manager_adjustment'] is None)
        check(f"adjusted_letter_grade reverted to algorithmic C ({rating3['adjusted_letter_grade']})",
              rating3['adjusted_letter_grade'] == 'C')

        print("smoke_customer_ratings: override with no note is rejected")
        r = client.post(f'/getagrip/customers/{customer_id}/rating-override', data={
            'manager_adjustment': '10',
        }, follow_redirects=True)
        check("rejected: note is required", b'A note is required' in r.data)
        cur.execute("SELECT manager_adjustment FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        check("no override was actually saved", cur.fetchone()['manager_adjustment'] is None)

        print("smoke_customer_ratings: recompute preserves an existing manager_adjustment")
        cur.execute("""
            UPDATE customer_ratings SET manager_adjustment = 5, manager_adjustment_note = 'kept across recompute',
                adjusted_letter_grade = 'C' WHERE customer_id = %s
        """, (customer_id,))
        conn.commit()
        _job_recompute_customer_ratings('getagrip')
        cur.execute("SELECT manager_adjustment, manager_adjustment_note FROM customer_ratings WHERE customer_id = %s", (customer_id,))
        rating4 = cur.fetchone()
        check("manager_adjustment survived a nightly recompute", close(float(rating4['manager_adjustment']), 5.0))
        check("note survived too", rating4['manager_adjustment_note'] == 'kept across recompute')

        print("smoke_customer_ratings: dispatch board carries adjusted_letter_grade")
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, start_date, scheduled_start, created_by, updated_by)
            VALUES ('ZZZ-RATE-DISPATCH', %s, 'Scheduled', %s, %s, 'smoketest', 'smoketest') RETURNING id
        """, (customer_id, date.today().isoformat(), f'{date.today().isoformat()} 09:00:00'))
        wo_dispatch = cur.fetchone()['id']
        wo_ids.append(wo_dispatch)
        conn.commit()
        r = client.get(f'/getagrip/dispatch/data?date={date.today().isoformat()}')
        data = r.get_json()
        block = next((b for b in data['blocks'] if b['id'] == wo_dispatch), None)
        check("WO appears on today's dispatch board", block is not None)
        check(f"block carries adjusted_letter_grade C ({block and block.get('adjusted_letter_grade')})",
              block is not None and block['adjusted_letter_grade'] == 'C')

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
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_ratings WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
