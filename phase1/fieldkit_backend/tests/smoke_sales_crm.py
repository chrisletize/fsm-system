"""
Smoke test: Increment 3.5 — Sales CRM (directive §4.5, docs/SALES-SYSTEM.md).

*** SAFETY ***
RESEND_API_KEY is a real, live key in this environment. Both the
prospect-conversion notification (emails real admin/manager users) and the
weekly sales report can fire real sends, so `_resend.Emails.send` is
monkey-patched to a local fake for this entire run, restored in `finally`
even on failure -- same pattern as smoke_email_delivery.py. company_settings'
scheduled_alerts_enabled/alert_email are flipped on briefly to exercise the
weekly report's email path, then restored to their real (false/NULL)
production values immediately after that check and again in `finally`.

Drives the real Flask routes (test client, forged admin session) against
live getagrip. Everything created is hard-deleted in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_sales_crm.py
"""
import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module  # noqa: E402
from app import (  # noqa: E402
    get_db_connection, app, job_weekly_sales_report, _sales_dormant_customers,
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
    prospect_ids, contact_ids, visit_ids, customer_ids, approval_ids = [], [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    original_send = app_module._resend.Emails.send
    app_module._resend.Emails.send = fake_resend_send

    TODAY = date.today()

    try:
        print("smoke_sales_crm: dashboard renders with no data yet")
        r = client.get('/getagrip/sales')
        check(f"dashboard 200 ({r.status_code})", r.status_code == 200)

        print("smoke_sales_crm: prospect create/list/search/edit/detail")
        r = client.post('/getagrip/sales/prospects/new', data={
            'property_name': 'SMOKE Riverside Apartments', 'customer_type': 'Multi Family',
            'address': '456 Oak Rd', 'city': 'Charlotte', 'state': 'NC', 'zip': '28202',
        }, follow_redirects=False)
        check(f"prospect created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM sales_prospects WHERE property_name = 'SMOKE Riverside Apartments'")
        prospect_id = cur.fetchone()['id']
        prospect_ids.append(prospect_id)

        r = client.get('/getagrip/sales/prospects?search=Riverside')
        check("prospect list search finds it", b'SMOKE Riverside Apartments' in r.data)

        r = client.get(f'/getagrip/sales/search?q=Riverside')
        results = r.get_json()['results']
        match = next((x for x in results if x['id'] == prospect_id and x['type'] == 'prospect'), None)
        check("unified search returns the prospect typed 'prospect'", match is not None)

        r = client.post(f'/getagrip/sales/prospects/{prospect_id}/edit', data={
            'property_name': 'SMOKE Riverside Apartments', 'customer_type': 'Multi Family',
            'address': '456 Oak Rd', 'city': 'Charlotte', 'state': 'NC', 'zip': '28202',
            'is_former_customer': 'on',
        }, follow_redirects=False)
        check(f"prospect edited ({r.status_code})", r.status_code == 302)
        r = client.get(f'/getagrip/sales/prospects/{prospect_id}')
        check("detail shows former-customer badge", b'Former customer' in r.data or b'Former Customer' in r.data)

        print("smoke_sales_crm: contact create links to prospect + property_history row")
        r = client.post('/getagrip/sales/contacts/new', data={
            'first_name': 'Sarah', 'last_name': 'SMOKEJohnson', 'title': 'Property Manager',
            'office_email': 'sjohnson@smoketest.invalid', 'office_phone': '555-1234',
            'current_property_id': str(prospect_id), 'current_property_type': 'prospect',
        }, follow_redirects=False)
        check(f"contact created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM sales_contacts WHERE last_name = 'SMOKEJohnson'")
        contact_id = cur.fetchone()['id']
        contact_ids.append(contact_id)
        cur.execute("""
            SELECT started_date, ended_date FROM contact_property_history
            WHERE contact_id = %s AND property_id = %s AND property_type = 'prospect'
        """, (contact_id, prospect_id))
        hist = cur.fetchone()
        check("property history row opened on create", hist is not None and hist['ended_date'] is None)

        print("smoke_sales_crm: re-pointing a contact's property closes the old history row and opens a new one")
        r = client.post('/getagrip/sales/prospects/new', data={
            'property_name': 'SMOKE Second Prospect', 'customer_type': 'Residential',
        }, follow_redirects=False)
        cur.execute("SELECT id FROM sales_prospects WHERE property_name = 'SMOKE Second Prospect'")
        prospect2_id = cur.fetchone()['id']
        prospect_ids.append(prospect2_id)
        r = client.post(f'/getagrip/sales/contacts/{contact_id}/edit', data={
            'first_name': 'Sarah', 'last_name': 'SMOKEJohnson', 'title': 'Property Manager',
            'current_property_id': str(prospect2_id), 'current_property_type': 'prospect',
        }, follow_redirects=False)
        check(f"contact re-pointed ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT ended_date FROM contact_property_history
            WHERE contact_id = %s AND property_id = %s AND property_type = 'prospect'
        """, (contact_id, prospect_id))
        check("old history row closed", cur.fetchone()['ended_date'] == TODAY)
        cur.execute("""
            SELECT ended_date FROM contact_property_history
            WHERE contact_id = %s AND property_id = %s AND property_type = 'prospect'
        """, (contact_id, prospect2_id))
        check("new history row opened", cur.fetchone()['ended_date'] is None)
        # move it back to prospect 1 for the rest of the test (convert flow needs it there)
        client.post(f'/getagrip/sales/contacts/{contact_id}/edit', data={
            'first_name': 'Sarah', 'last_name': 'SMOKEJohnson', 'title': 'Property Manager',
            'office_email': 'sjohnson@smoketest.invalid', 'office_phone': '555-1234',
            'current_property_id': str(prospect_id), 'current_property_type': 'prospect',
        }, follow_redirects=False)

        print("smoke_sales_crm: log visit -- tag auto-calculates follow_up_date")
        r = client.post('/getagrip/sales/visits/log', data={
            'property_type': 'prospect', 'property_id': str(prospect_id),
            'visit_tag': 'Hot lead', 'contact_id': str(contact_id),
            'notes': 'SMOKE: wants a quote by Friday', 'follow_up_needed': 'on',
        }, follow_redirects=False)
        check(f"visit logged ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id, follow_up_date FROM sales_visits
            WHERE property_id = %s AND property_type = 'prospect' ORDER BY id DESC LIMIT 1
        """, (prospect_id,))
        visit = cur.fetchone()
        visit_ids.append(visit['id'])
        expected_followup = TODAY + timedelta(days=5)  # 'Hot lead' default_followup_days = 5
        check(f"follow_up_date auto-set to +5 days ({visit['follow_up_date']} == {expected_followup})",
              visit['follow_up_date'] == expected_followup)

        print("smoke_sales_crm: follow-ups list shows it, mark-complete works")
        r = client.get('/getagrip/sales/followups')
        check("SMOKE Riverside appears in follow-ups list", b'SMOKE Riverside Apartments' in r.data)
        r = client.post(f"/getagrip/sales/followups/{visit['id']}/complete", follow_redirects=False)
        check(f"mark-complete redirects ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT follow_up_completed FROM sales_visits WHERE id = %s", (visit['id'],))
        check("follow_up_completed is now TRUE", cur.fetchone()['follow_up_completed'] is True)

        print("smoke_sales_crm: never-serviced customer shows up as dormant")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE Dormant Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        dormant_customer_id = cur.fetchone()['id']
        customer_ids.append(dormant_customer_id)
        conn.commit()
        dormant = _sales_dormant_customers('getagrip')
        check("never-serviced SMOKE customer is in the dormant list",
              any(d['id'] == dormant_customer_id and d['days'] is None for d in dormant))

        print("smoke_sales_crm: dormancy investigation visit requires a reason to send to management")
        r = client.post('/getagrip/sales/visits/log', data={
            'property_type': 'customer', 'property_id': str(dormant_customer_id),
            'visit_tag': 'Brief chat', 'is_dormant_investigation': 'on',
            'dormancy_reported_to_management': 'on', 'follow_up_needed': '',
        }, follow_redirects=False)
        check(f"rejected with no reason ({r.status_code})", r.status_code == 200)
        check("error shown", b'reason is required' in r.data)
        r = client.post('/getagrip/sales/visits/log', data={
            'property_type': 'customer', 'property_id': str(dormant_customer_id),
            'visit_tag': 'Brief chat', 'is_dormant_investigation': 'on',
            'dormancy_reason': 'SMOKE: switched to a competitor after two missed visits',
            'dormancy_reported_to_management': 'on', 'follow_up_needed': '',
        }, follow_redirects=False)
        check(f"dormancy visit logged ({r.status_code})", r.status_code == 302)
        cur.execute("""
            SELECT id, dormancy_reason, dormancy_reported_to_management FROM sales_visits
            WHERE property_id = %s AND property_type = 'customer' ORDER BY id DESC LIMIT 1
        """, (dormant_customer_id,))
        dv = cur.fetchone()
        visit_ids.append(dv['id'])
        check("dormancy_reported_to_management saved", dv['dormancy_reported_to_management'] is True)

        print("smoke_sales_crm: weekly report -- data always computed; email only when alerts are enabled")
        summary_disabled = job_weekly_sales_report('getagrip')
        check("summary computed with alerts off", 'no email sent' in summary_disabled or 'visit(s)' in summary_disabled)
        sent_before = len(SENT_CALLS)

        cur.execute("""
            UPDATE company_settings SET scheduled_alerts_enabled = TRUE, alert_email = 'smoketest@smoketest.invalid'
            WHERE deleted_at IS NULL
        """)
        conn.commit()
        summary_enabled = job_weekly_sales_report('getagrip')
        cur.execute("""
            UPDATE company_settings SET scheduled_alerts_enabled = FALSE, alert_email = NULL WHERE deleted_at IS NULL
        """)
        conn.commit()
        check("an email was sent this time (mocked)", len(SENT_CALLS) > sent_before)
        report_body = SENT_CALLS[-1]['html']
        check("report mentions the dormancy reason", 'switched to a competitor' in report_body)
        check("report was addressed to the throwaway alert address", 'smoketest@smoketest.invalid' in SENT_CALLS[-1]['to'])

        print("smoke_sales_crm: convert prospect -> approval_queue -> manager approves -> customer created")
        r = client.get(f'/getagrip/sales/prospects/{prospect_id}/convert')
        check(f"convert form renders ({r.status_code})", r.status_code == 200)
        calls_before_convert = len(SENT_CALLS)
        r = client.post(f'/getagrip/sales/prospects/{prospect_id}/convert', data={
            'primary_contact_id': str(contact_id), 'submitted_reason': 'SMOKE: hot lead, wants immediate service',
        }, follow_redirects=False)
        check(f"convert submitted ({r.status_code})", r.status_code == 302)
        check("manager notification email attempted (mocked)", len(SENT_CALLS) > calls_before_convert)
        cur.execute("""
            SELECT id, status, request_details FROM approval_queue
            WHERE target_type = 'prospect' AND target_id = %s ORDER BY id DESC LIMIT 1
        """, (prospect_id,))
        approval = cur.fetchone()
        approval_ids.append(approval['id'])
        check("approval is pending", approval['status'] == 'pending')
        check("request_details captured the contact", len(approval['request_details']['contacts']) == 1)

        r = client.post(f'/getagrip/sales/prospects/{prospect_id}/convert', data={}, follow_redirects=False)
        check(f"a second convert while one is pending is blocked ({r.status_code})", r.status_code == 302)
        r = client.get(f'/getagrip/sales/prospects/{prospect_id}/convert', follow_redirects=True)
        check("blocked-convert flash message shown", b'already pending approval' in r.data)

        r = client.post(f"/getagrip/sales/approvals/{approval['id']}/approve", data={
            'property_name': 'SMOKE Riverside Apartments (Approved)', 'customer_type': 'Multi Family',
            'address': '456 Oak Rd', 'city': 'Charlotte', 'state': 'NC', 'zip': '28202',
            'review_notes': 'SMOKE: looks good',
        }, follow_redirects=False)
        check(f"approve redirects to the new customer ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id, property_name FROM customers WHERE property_name = 'SMOKE Riverside Apartments (Approved)'")
        new_cust = cur.fetchone()
        check("customer was actually created", new_cust is not None)
        customer_ids.append(new_cust['id'])
        cur.execute("SELECT first_name, last_name, is_primary, accepts_billing FROM customer_contacts WHERE customer_id = %s", (new_cust['id'],))
        cc = cur.fetchone()
        check("contact copied onto the new customer as primary + billing", cc is not None and cc['is_primary'] and cc['accepts_billing'])
        cur.execute("SELECT converted_to_customer, customer_id FROM sales_prospects WHERE id = %s", (prospect_id,))
        p = cur.fetchone()
        check("prospect marked converted and linked", p['converted_to_customer'] is True and p['customer_id'] == new_cust['id'])
        cur.execute("SELECT status FROM approval_queue WHERE id = %s", (approval['id'],))
        check("approval marked approved", cur.fetchone()['status'] == 'approved')
        cur.execute("SELECT current_property_type, current_property_id FROM sales_contacts WHERE id = %s", (contact_id,))
        moved = cur.fetchone()
        check("sales_contacts re-pointed at the new customer", moved['current_property_type'] == 'customer'
              and moved['current_property_id'] == new_cust['id'])

        print("smoke_sales_crm: reject flow -- second prospect stays unconverted")
        r = client.post(f'/getagrip/sales/prospects/{prospect2_id}/convert', data={}, follow_redirects=False)
        cur.execute("""
            SELECT id FROM approval_queue WHERE target_type = 'prospect' AND target_id = %s ORDER BY id DESC LIMIT 1
        """, (prospect2_id,))
        approval2_id = cur.fetchone()['id']
        approval_ids.append(approval2_id)
        r = client.post(f'/getagrip/sales/approvals/{approval2_id}/reject', data={}, follow_redirects=False)
        check("reject with no note is rejected by the form", r.status_code == 302)
        r = client.post(f'/getagrip/sales/approvals/{approval2_id}/reject',
                         data={'review_notes': 'SMOKE: not a real lead'}, follow_redirects=False)
        check(f"reject with a note succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status FROM approval_queue WHERE id = %s", (approval2_id,))
        check("approval marked rejected", cur.fetchone()['status'] == 'rejected')
        cur.execute("SELECT converted_to_customer FROM sales_prospects WHERE id = %s", (prospect2_id,))
        check("prospect2 NOT converted", cur.fetchone()['converted_to_customer'] is False)

        print("smoke_sales_crm: approvals list page renders both entries")
        r = client.get('/getagrip/sales/approvals')
        check("approvals list 200", r.status_code == 200)
        check("shows approved entry", b'Approved' in r.data)
        check("shows rejected entry", b'Rejected' in r.data)

        print("ALL CHECKS PASSED")

    finally:
        app_module._resend.Emails.send = original_send
        cur.execute("UPDATE company_settings SET scheduled_alerts_enabled = FALSE, alert_email = NULL WHERE deleted_at IS NULL")
        if visit_ids:
            cur.execute("DELETE FROM sales_visits WHERE id = ANY(%s)", (visit_ids,))
        if contact_ids:
            cur.execute("DELETE FROM contact_property_history WHERE contact_id = ANY(%s)", (contact_ids,))
            cur.execute("DELETE FROM sales_contacts WHERE id = ANY(%s)", (contact_ids,))
        if approval_ids:
            cur.execute("DELETE FROM approval_queue WHERE id = ANY(%s)", (approval_ids,))
        if prospect_ids:
            cur.execute("DELETE FROM sales_prospects WHERE id = ANY(%s)", (prospect_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_contacts WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customer_ratings WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(prospect_ids)} prospect(s), {len(contact_ids)} contact(s), "
              f"{len(visit_ids)} visit(s), {len(customer_ids)} customer(s), {len(approval_ids)} approval(s) removed.")


if __name__ == '__main__':
    main()
