"""
Smoke test: Increment 1.7 — email delivery (invoices & statements).

*** SAFETY ***
RESEND_API_KEY is a real, live key in this environment, and real customer
email addresses exist in this database. This test NEVER lets a real network
call happen:
  1. `_resend.Emails.send` (the one function that ever talks to Resend) is
     monkey-patched to a local fake for the entire run, restored in `finally`
     even on failure.
  2. As defense in depth on top of that, every recipient used here is a
     freshly-created throwaway customer/contact with an address on the
     `.invalid` TLD (RFC 2606 — reserved, guaranteed never to resolve or
     deliver), never a real customer's real contact.
If you are extending this file: keep both of those. Do not call
`_send_email_via_resend`, `_send_invoice_email`, `_send_statement_email`, or
any of the send routes without the monkey-patch active.

Run inside the app container:

    docker compose exec -T app python tests/smoke_email_delivery.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402
from app import (  # noqa: E402
    get_db_connection, app, _resolve_email_recipients, _render_email_template,
    _send_email_via_resend, _parse_extra_emails,
)


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


SENT_CALLS = []


def fake_resend_send(payload):
    SENT_CALLS.append(payload)
    return {'id': f'fake-message-{len(SENT_CALLS)}'}


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids, customer_ids, contact_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    original_send = app_module._resend.Emails.send
    app_module._resend.Emails.send = fake_resend_send
    original_api_key = app_module.RESEND_API_KEY

    try:
        print("smoke_email_delivery: unit helpers")
        check("template renders {customer}/{number}/{total}/{balance}",
              _render_email_template('Hi {customer}, {number} totals {total}, balance {balance}.',
                                      'Oakwood', 'GAG-2026-0001', 100.0, 25.0)
              == 'Hi Oakwood, GAG-2026-0001 totals $100.00, balance $25.00.')
        check("template falls back when unset",
              _render_email_template(None, 'X', 'Y', None, None) == 'Hi X, please find attached Y.')
        check("extra-email parsing: comma + newline separated, trimmed",
              _parse_extra_emails('a@x.invalid, b@x.invalid\nc@x.invalid ') == ['a@x.invalid', 'b@x.invalid', 'c@x.invalid'])
        check("extra-email parsing: empty -> []", _parse_extra_emails('') == [])

        print("smoke_email_delivery: RESEND_API_KEY missing is a clean error, not a crash, and NEVER calls Resend")
        app_module.RESEND_API_KEY = ''
        calls_before = len(SENT_CALLS)
        msg_id, err = _send_email_via_resend(['x@smoketest.invalid'], 'subj', '<p>body</p>')
        check("returns (None, error) when key is missing", msg_id is None and err is not None)
        check("Resend was NOT called while the key was missing", len(SENT_CALLS) == calls_before)
        app_module.RESEND_API_KEY = original_api_key

        print("smoke_email_delivery: _send_email_via_resend calls the (mocked) API correctly")
        calls_before = len(SENT_CALLS)
        msg_id, err = _send_email_via_resend(
            ['a@smoketest.invalid'], 'Test Subject', '<p>Test body</p>',
            attachment_bytes=b'%PDF-fake', attachment_filename='test.pdf',
            reply_to='office@smoketest.invalid', from_name='Smoke Co', bcc='office@smoketest.invalid')
        check("returns a message id, no error", msg_id is not None and err is None)
        check("Resend WAS called exactly once", len(SENT_CALLS) == calls_before + 1)
        payload = SENT_CALLS[-1]
        check("payload has the right recipient", payload['to'] == ['a@smoketest.invalid'])
        check("payload has an attachment with base64 content", 'attachments' in payload and len(payload['attachments']) == 1)
        check("payload has reply_to and bcc", payload.get('reply_to') == 'office@smoketest.invalid' and payload.get('bcc') == ['office@smoketest.invalid'])

        # --- Fixtures: a throwaway customer + contact, never real data ---
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Email Test Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        cur.execute("""
            INSERT INTO customer_contacts (customer_id, first_name, last_name, office_email,
                accepts_billing, accepts_statements, is_primary, created_by, updated_by)
            VALUES (%s, 'Smoke', 'Contact', 'billing@smoketest.invalid', TRUE, TRUE, TRUE, 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        contact_ids.append(cur.fetchone()['id'])
        conn.commit()

        print("smoke_email_delivery: recipient resolution respects accepts_billing/accepts_statements")
        check("invoice recipients resolve to the billing contact",
              _resolve_email_recipients(cur, customer_id, 'invoice') == ['billing@smoketest.invalid'])
        check("statement recipients resolve to the same contact (also accepts_statements)",
              _resolve_email_recipients(cur, customer_id, 'statement') == ['billing@smoketest.invalid'])

        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-EMAIL-0001', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Smoke line', 1, 60.00, 60.00, FALSE, 0, 'smoketest', 'smoketest')
        """, (wo_id, catalog_id))
        conn.commit()

        r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        invoice_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(invoice_id)
        client.post(f'/getagrip/invoices/{invoice_id}/harden')

        print("smoke_email_delivery: invoice detail shows the send dialog context")
        r = client.get(f'/getagrip/invoices/{invoice_id}')
        check(f"invoice detail renders ({r.status_code})", r.status_code == 200)
        check("shows the Send Email button", b'Send Email' in r.data)
        check("shows the resolved recipient", b'billing@smoketest.invalid' in r.data)

        print("smoke_email_delivery: sending the invoice email")
        calls_before = len(SENT_CALLS)
        r = client.post(f'/getagrip/invoices/{invoice_id}/send-email', data={
            'recipients': ['billing@smoketest.invalid'],
            'subject': 'Smoke test invoice',
            'body': 'Smoke test body',
        }, follow_redirects=False)
        check(f"send-email route redirects ({r.status_code})", r.status_code == 302)
        check("Resend WAS called exactly once for this send", len(SENT_CALLS) == calls_before + 1)
        check("sent to the right (fake) address", SENT_CALLS[-1]['to'] == ['billing@smoketest.invalid'])

        cur.execute("SELECT state FROM invoice_versions WHERE id = (SELECT current_version_id FROM invoices WHERE id=%s)", (invoice_id,))
        check("invoice transitioned to Sent after a successful send", cur.fetchone()['state'] == 'Sent')

        cur.execute("SELECT kind, related_id, to_emails, status, resend_message_id FROM email_log WHERE kind='invoice' AND related_id=%s", (invoice_id,))
        log_row = cur.fetchone()
        check(f"email_log row written correctly ({dict(log_row) if log_row else None})",
              log_row is not None and log_row['status'] == 'sent' and 'billing@smoketest.invalid' in log_row['to_emails'])

        print("smoke_email_delivery: no billing contact blocks the send (no Resend call, no state change)")
        cur.execute("UPDATE customer_contacts SET accepts_billing = FALSE WHERE id = %s", (contact_ids[0],))
        conn.commit()
        # Revise -> Live -> re-harden a fresh invoice to get back to Hardened for this test.
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-EMAIL-0002', %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo2_id = cur.fetchone()['id']
        wo_ids.append(wo2_id)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Smoke line 2', 1, 15.00, 15.00, FALSE, 0, 'smoketest', 'smoketest')
        """, (wo2_id, catalog_id))
        conn.commit()
        r = client.post(f'/getagrip/workorders/{wo2_id}/invoice/new', follow_redirects=False)
        invoice2_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(invoice2_id)
        client.post(f'/getagrip/invoices/{invoice2_id}/harden')

        calls_before = len(SENT_CALLS)
        r = client.post(f'/getagrip/invoices/{invoice2_id}/send-email', data={}, follow_redirects=False)
        check(f"send-email with no recipient redirects, not a 500 ({r.status_code})", r.status_code == 302)
        check("Resend was NOT called", len(SENT_CALLS) == calls_before)
        cur.execute("SELECT state FROM invoice_versions WHERE id = (SELECT current_version_id FROM invoices WHERE id=%s)", (invoice2_id,))
        check("invoice stayed Hardened (not Sent)", cur.fetchone()['state'] == 'Hardened')

        print("smoke_email_delivery: a failed send logs 'failed' and does NOT transition to Sent")
        cur.execute("UPDATE customer_contacts SET accepts_billing = TRUE WHERE id = %s", (contact_ids[0],))
        conn.commit()

        def failing_send(payload):
            raise RuntimeError('simulated Resend outage')
        app_module._resend.Emails.send = failing_send
        r = client.post(f'/getagrip/invoices/{invoice2_id}/send-email', data={
            'recipients': ['billing@smoketest.invalid'],
        }, follow_redirects=False)
        app_module._resend.Emails.send = fake_resend_send
        check(f"send-email with a failing API redirects, not a 500 ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT state FROM invoice_versions WHERE id = (SELECT current_version_id FROM invoices WHERE id=%s)", (invoice2_id,))
        check("invoice still Hardened after a failed send", cur.fetchone()['state'] == 'Hardened')
        cur.execute("SELECT status, error FROM email_log WHERE kind='invoice' AND related_id=%s ORDER BY id DESC LIMIT 1", (invoice2_id,))
        fail_log = cur.fetchone()
        check(f"email_log recorded the failure ({dict(fail_log) if fail_log else None})",
              fail_log is not None and fail_log['status'] == 'failed' and 'simulated Resend outage' in (fail_log['error'] or ''))

        print("smoke_email_delivery: statement send (single + batch)")
        calls_before = len(SENT_CALLS)
        r = client.post(f'/getagrip/customers/{customer_id}/send-statement', data={
            'recipients': ['billing@smoketest.invalid'],
        }, follow_redirects=False)
        check(f"send-statement redirects ({r.status_code})", r.status_code == 302)
        check("Resend was called once for the statement", len(SENT_CALLS) == calls_before + 1)
        cur.execute("SELECT last_statement_at FROM customers WHERE id = %s", (customer_id,))
        check("last_statement_at set after sending", cur.fetchone()['last_statement_at'] is not None)

        # Second customer with no statement contact, for the batch skip case.
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Email No-Contact Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer2_id = cur.fetchone()['id']
        customer_ids.append(customer2_id)
        conn.commit()

        calls_before = len(SENT_CALLS)
        r = client.post('/getagrip/billing/send-statements', data={
            'customer_ids': [str(customer_id), str(customer2_id)],
        }, follow_redirects=False)
        check(f"batch send-statements renders a summary page ({r.status_code})", r.status_code == 200)
        check("summary shows one sent", b'Sent (1)' in r.data or b'SMOKE Email Test Co' in r.data)
        check("summary shows one skipped (no contact)", b'SMOKE Email No-Contact Co' in r.data)
        check("Resend was called exactly once more (only the customer with a contact)", len(SENT_CALLS) == calls_before + 1)

        print("ALL CHECKS PASSED")

    finally:
        app_module._resend.Emails.send = original_send
        app_module.RESEND_API_KEY = original_api_key

        cur.execute("DELETE FROM email_log WHERE related_id = ANY(%s) AND kind IN ('invoice', 'statement')",
                    (invoice_ids + customer_ids,))
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
        if contact_ids:
            cur.execute("DELETE FROM customer_contacts WHERE id = ANY(%s)", (contact_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s), "
              f"{len(customer_ids)} throwaway customer(s) removed. "
              f"Total fake Resend calls made this run: {len(SENT_CALLS)} (0 real).")


if __name__ == '__main__':
    main()
