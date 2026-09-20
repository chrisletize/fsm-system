"""
Smoke test: Increment 3.1 — estimates + public estimate request form.

*** SAFETY ***
Same discipline as smoke_email_delivery.py: `_resend.Emails.send` is
monkey-patched for the entire run so no real network call can ever happen,
restored in `finally` even on failure.

Drives the real Flask routes (test client, forged admin session) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_estimates.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402
from app import get_db_connection, app  # noqa: E402


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
    customer_ids, estimate_ids, wo_ids, request_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    sent_calls = []
    def fake_resend_send(payload):
        sent_calls.append(payload)
        return {'id': f'fake-msg-{len(sent_calls)}'}
    original_send = app_module._resend.Emails.send
    app_module._resend.Emails.send = fake_resend_send

    try:
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Estimates Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        cur.execute("""
            INSERT INTO customer_contacts (customer_id, first_name, last_name, office_email, is_primary, created_by, updated_by)
            VALUES (%s, 'Est', 'Contact', 'est-contact@smoketest.invalid', TRUE, 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        contact_id = cur.fetchone()['id']
        conn.commit()

        cur.execute("SELECT id, unit_price FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        cat = cur.fetchone()
        catalog_id, catalog_price = cat['id'], float(cat['unit_price'])

        print("smoke_estimates: create a Draft estimate through the real form")
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': 'Smoke line', 'quantity': '2', 'unit_price': str(catalog_price),
        }])
        r = client.post('/getagrip/estimates/new', data={
            'customer_id': str(customer_id), 'primary_contact_id': str(contact_id),
            'work_site_label': 'Smoke Site', 'line_items_json': line_items,
        }, follow_redirects=False)
        check(f"estimate created ({r.status_code})", r.status_code == 302)
        location = r.headers['Location']
        est_id = int(location.rstrip('/').rsplit('/', 1)[-1])
        estimate_ids.append(est_id)

        cur.execute("SELECT estimate_number, status, subtotal FROM estimates WHERE id = %s", (est_id,))
        est = cur.fetchone()
        check(f"estimate_number formatted PREFIX-EST-YYYY-#### ({est['estimate_number']})",
              '-EST-' in est['estimate_number'])
        check("status starts Draft", est['status'] == 'Draft')
        check(f"subtotal = 2 x catalog price ({est['subtotal']})", close(float(est['subtotal']), 2 * catalog_price))

        print("smoke_estimates: edit while Draft")
        line_items2 = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': 'Smoke line v2', 'quantity': '3', 'unit_price': str(catalog_price),
        }])
        r = client.post(f'/getagrip/estimates/{est_id}/edit', data={
            'customer_id': str(customer_id), 'primary_contact_id': str(contact_id),
            'work_site_label': 'Smoke Site', 'line_items_json': line_items2,
        }, follow_redirects=False)
        check(f"edit succeeded ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT subtotal FROM estimates WHERE id = %s", (est_id,))
        check("subtotal updated to 3x", close(float(cur.fetchone()['subtotal']), 3 * catalog_price))

        print("smoke_estimates: customer detail shows the Estimates section")
        r = client.get(f'/getagrip/customers/{customer_id}')
        check(f"customer detail renders ({r.status_code})", r.status_code == 200)
        check("shows the estimate number", est['estimate_number'].encode() in r.data)

        print("smoke_estimates: send — tax frozen, email sent (mocked), status -> Sent")
        calls_before = len(sent_calls)
        r = client.post(f'/getagrip/estimates/{est_id}/send', data={'subject': 'Your estimate'}, follow_redirects=False)
        check(f"send responds 302 ({r.status_code})", r.status_code == 302)
        check("Resend was called", len(sent_calls) > calls_before)
        check("email went to the primary contact", sent_calls[-1]['to'] == ['est-contact@smoketest.invalid'])

        cur.execute("SELECT status, tax_total, total, sent_at FROM estimates WHERE id = %s", (est_id,))
        est2 = cur.fetchone()
        check(f"status = Sent ({est2['status']})", est2['status'] == 'Sent')
        check("tax_total frozen (not null)", est2['tax_total'] is not None)
        check("total frozen (not null)", est2['total'] is not None)
        check("sent_at set", est2['sent_at'] is not None)

        print("smoke_estimates: editing a Sent estimate is rejected")
        r = client.post(f'/getagrip/estimates/{est_id}/edit', data={
            'customer_id': str(customer_id), 'line_items_json': line_items2,
        }, follow_redirects=True)
        check("edit of a Sent estimate is rejected", b'Only a Draft estimate can be edited' in r.data)

        print("smoke_estimates: approve -> Approved")
        r = client.post(f'/getagrip/estimates/{est_id}/approve', follow_redirects=False)
        check(f"approve responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status, approved_at FROM estimates WHERE id = %s", (est_id,))
        est3 = cur.fetchone()
        check("status = Approved", est3['status'] == 'Approved')
        check("approved_at set", est3['approved_at'] is not None)

        print("smoke_estimates: convert -> pre-filled new-WO form -> WO save marks estimate Converted")
        r = client.get(f'/getagrip/estimates/{est_id}/convert', follow_redirects=False)
        check(f"convert redirects ({r.status_code})", r.status_code == 302)
        convert_url = r.headers['Location']
        check(f"redirect carries estimate_id + customer_id ({convert_url})",
              f'estimate_id={est_id}' in convert_url and f'customer_id={customer_id}' in convert_url)

        r = client.get(convert_url)
        check(f"pre-filled WO form renders ({r.status_code})", r.status_code == 200)
        check("pre-filled WO form shows the estimate's line description", b'Smoke line v2' in r.data)
        check(f'hidden estimate_id carries {est_id}', f'name="estimate_id" value="{est_id}"'.encode() in r.data)

        r = client.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': '2026-09-25', 'line_items_json': line_items2,
            'duration_overridden': 'false', 'estimate_id': str(est_id),
        }, follow_redirects=False)
        check(f"WO created from the converted estimate ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE estimate_id = %s", (est_id,))
        wo_row = cur.fetchone()
        check("new WO carries estimate_id", wo_row is not None)
        wo_ids.append(wo_row['id'])

        cur.execute("SELECT status, converted_to_job_id FROM estimates WHERE id = %s", (est_id,))
        est4 = cur.fetchone()
        check("estimate status = Converted", est4['status'] == 'Converted')
        check("converted_to_job_id matches the new WO", est4['converted_to_job_id'] == wo_row['id'])

        print("smoke_estimates: decline path on a second estimate")
        r = client.post('/getagrip/estimates/new', data={
            'customer_id': str(customer_id), 'primary_contact_id': str(contact_id), 'line_items_json': line_items,
        }, follow_redirects=False)
        est_id2 = int(r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
        estimate_ids.append(est_id2)
        r = client.post(f'/getagrip/estimates/{est_id2}/send', data={})
        check(f"second estimate sent ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status FROM estimates WHERE id = %s", (est_id2,))
        check("second estimate actually reached Sent before declining", cur.fetchone()['status'] == 'Sent')
        r = client.post(f'/getagrip/estimates/{est_id2}/decline', data={'declined_reason': 'Too expensive'}, follow_redirects=False)
        check(f"decline responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status, declined_reason FROM estimates WHERE id = %s", (est_id2,))
        est5 = cur.fetchone()
        check("status = Declined", est5['status'] == 'Declined')
        check("declined_reason saved", est5['declined_reason'] == 'Too expensive')

        print("smoke_estimates: PDF export")
        r = client.get(f'/getagrip/estimates/{est_id}/pdf')
        check(f"PDF responds 200 ({r.status_code})", r.status_code == 200)
        check("PDF mimetype", r.mimetype == 'application/pdf')
        check("PDF contains the customer name (pageCompression=0)", b'SMOKE Estimates Co' in r.data)

        print("smoke_estimates: estimates list + filters")
        r = client.get('/getagrip/estimates')
        check(f"list renders ({r.status_code})", r.status_code == 200)
        check("list shows both estimates", r.data.count(b'SMOKE Estimates Co') >= 2)
        r = client.get('/getagrip/estimates?status=Declined')
        check("status filter narrows to the declined one", est5['status'].encode() in r.data)

        print("smoke_estimates: public request form — submit, honeypot, rate limit")
        r = client.get('/request/getagrip')
        check(f"public form renders (no login) ({r.status_code})", r.status_code == 200)
        check("form is a standalone page (no app nav)", b'subnav' not in r.data)

        r = client.post('/request/getagrip', data={
            'name': 'Smoke Public Requester', 'email': 'public-req@smoketest.invalid',
            'services': ['Resurfacing'],
        }, follow_redirects=False)
        check(f"submission succeeds ({r.status_code})", r.status_code == 200)
        check("shows the thank-you page", b'Thank you' in r.data)
        cur.execute("SELECT id, status FROM estimate_requests WHERE name = 'Smoke Public Requester'")
        req_row = cur.fetchone()
        check("estimate_requests row created", req_row is not None)
        request_ids.append(req_row['id'])
        check("status defaults to new", req_row['status'] == 'new')

        r = client.post('/request/getagrip', data={
            'name': 'Smoke Bot', 'website': 'http://spam.example',  # honeypot filled
        }, follow_redirects=False)
        check(f"honeypot submission still 200s (silently no-ops)", r.status_code == 200)
        cur.execute("SELECT count(*) AS n FROM estimate_requests WHERE name = 'Smoke Bot'")
        check("honeypot submission was NOT recorded", cur.fetchone()['n'] == 0)

        limited = False
        for i in range(6):
            r = client.post('/request/getagrip', data={'name': f'Smoke Rate {i}'}, follow_redirects=False)
            if b'Too many requests' in r.data:
                limited = True
        check("6th submission from the same IP within an hour is rate-limited", limited)
        cur.execute("SELECT id FROM estimate_requests WHERE name LIKE 'Smoke Rate%'")
        request_ids.extend(r['id'] for r in cur.fetchall())

        print("smoke_estimates: requests queue — mark contacted, create customer + estimate")
        r = client.get('/getagrip/estimates/requests')
        check(f"queue renders ({r.status_code})", r.status_code == 200)
        check("queue shows the real request", b'Smoke Public Requester' in r.data)

        r = client.post(f'/getagrip/estimates/requests/{req_row["id"]}/create-customer', follow_redirects=False)
        check(f"create-customer responds 302 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status, linked_customer_id FROM estimate_requests WHERE id = %s", (req_row['id'],))
        req_after = cur.fetchone()
        check("request marked converted", req_after['status'] == 'converted')
        check("linked to a new customer", req_after['linked_customer_id'] is not None)
        customer_ids.append(req_after['linked_customer_id'])
        check("redirected into a pre-filled new-estimate form",
              f'/estimates/new?customer_id={req_after["linked_customer_id"]}' in r.headers['Location'])

        print("ALL CHECKS PASSED")

    finally:
        app_module._resend.Emails.send = original_send
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("UPDATE estimates SET converted_to_job_id = NULL WHERE converted_to_job_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        for eid in estimate_ids:
            cur.execute("DELETE FROM estimate_status_history WHERE estimate_id = %s", (eid,))
            cur.execute("DELETE FROM estimate_line_items WHERE estimate_id = %s", (eid,))
        if estimate_ids:
            cur.execute("DELETE FROM email_log WHERE kind = 'estimate' AND related_id = ANY(%s)", (estimate_ids,))
            cur.execute("DELETE FROM estimates WHERE id = ANY(%s)", (estimate_ids,))
        if request_ids:
            cur.execute("DELETE FROM estimate_requests WHERE id = ANY(%s)", (request_ids,))
        cur.execute("DELETE FROM estimate_requests WHERE name IN ('Smoke Bot') OR name LIKE 'Smoke Rate%'")
        if customer_ids:
            cur.execute("DELETE FROM customer_contacts WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(estimate_ids)} estimate(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} customer(s), {len(request_ids)} request(s) removed. "
              f"{len(sent_calls)} fake Resend call(s) made this run (0 real).")


if __name__ == '__main__':
    main()
