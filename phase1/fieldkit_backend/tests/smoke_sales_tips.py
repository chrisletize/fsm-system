"""
Smoke test: sales tips (migration 039, D-115, Chris 2026-10-20). A tech on a
job spots something (e.g. a rehab with cabinet work), sends a tip, and it shows
up on the salesman's follow-up lists until a visit closes it.

Covers: tech sends a tip from a job (property pre-filled), a free-text tip
(location only), validation, the email (office + Michael + salesperson, logged,
HTML-escaped, failure surfaced), every list a tip appears on, closing by visit
(free-text tip tied to the property the wizard created), auto-closing on any
visit to the same property, dismiss (reason required, sales roles only), sales
hold suppression, and the weekly report numbers.

Drives the real routes (test client, forged sessions) against live getagrip.
Resend is monkey-patched, so nothing is ever emailed. Everything created is
hard-deleted in a `finally` block. Run inside the app container:

    docker compose exec -T app python tests/smoke_sales_tips.py
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod  # noqa: E402
from app import get_db_connection, app, _open_tips, _sales_weekly_report_data  # noqa: E402

CK = 'getagrip'


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, username):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = username
        sess['full_name'] = f'Smoke {role}'
        sess['user_role'] = role
        sess['company_access'] = [CK]
    return c


def main():
    conn = get_db_connection(CK)
    cur = conn.cursor()
    sent = []          # (to, subject, html) captured from the fake Resend
    fail_next = {'on': False}
    real_send = appmod._send_email_via_resend

    def fake_send(to_emails, subject, html_body, **kw):
        sent.append((list(to_emails), subject, html_body))
        if fail_next['on']:
            return None, 'smoke-induced rejection'
        return 'smoke-msg-id', None
    appmod._send_email_via_resend = fake_send

    customer_ids, wo_ids, prospect_ids = [], [], []
    tech = client_as('technician', 'smoketiptech')
    sales = client_as('salesperson', 'smoketipsales')
    admin = client_as('admin', 'smoketipadmin')

    def tip_ids():
        cur.execute("SELECT id FROM sales_tips WHERE created_by LIKE 'smoketip%%'")
        return [r['id'] for r in cur.fetchall()]

    try:
        cur.execute("""INSERT INTO customers (property_name, customer_type, status, created_by, updated_by)
                       VALUES ('ZZZ Smoke Tip Property', 'Multi Family', 'Active', 'smoketip', 'smoketip')
                       RETURNING id""")
        cust_id = cur.fetchone()['id']
        customer_ids.append(cust_id)
        cur.execute("""INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
                       VALUES ('ZZZ-SMOKE-TIP1', %s, 'Scheduled', CURRENT_DATE, 'smoketip', 'smoketip') RETURNING id""",
                    (cust_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)
        cur.execute("INSERT INTO work_order_techs (work_order_id, username, is_lead_tech) VALUES (%s, 'smoketiptech', TRUE)",
                    (wo_id,))
        conn.commit()

        print("smoke_sales_tips: a tech sends a tip from a job")
        r = tech.get(f'/{CK}/sales/tips/new?wo={wo_id}')
        check(f"tip form renders for a technician ({r.status_code})", r.status_code == 200)
        html = r.get_data(as_text=True)
        check("job's property is pre-filled", 'ZZZ Smoke Tip Property' in html)
        check("the form is inside the body, not swallowed by an unclosed block",
              html.index('<title>') < html.index('</title>') < html.index('id="tipForm"'))

        r = tech.post(f'/{CK}/sales/tips/new', data={
            'source_work_order_id': wo_id, 'property_type': 'customer', 'property_id': cust_id,
            'notes': 'Rehab under way <script>alert(1)</script> — new cabinets in vacant units',
            'due_date': '', 'return_to': f'/{CK}/myday',
        }, follow_redirects=False)
        check(f"tip saved, back to My Day ({r.status_code} {r.headers.get('Location')})",
              r.status_code == 302 and r.headers['Location'].endswith('/myday'))
        cur.execute("SELECT * FROM sales_tips WHERE created_by = 'smoketiptech' ORDER BY id DESC LIMIT 1")
        tip1 = cur.fetchone()
        check("tied to the job's customer", tip1['property_type'] == 'customer' and tip1['property_id'] == cust_id)
        check("source job recorded", tip1['source_work_order_id'] == wo_id)
        check(f"due on a working day after today ({tip1['due_date']})",
              tip1['due_date'] > date.today() and tip1['due_date'].weekday() < 5)

        to, subject, body = sent[-1]
        check("email goes to the office", 'office@getagripofcharlotte.com' in to, to)
        check("email copies Michael", 'michaelobuckley@yahoo.com' in to, to)
        check("email goes to the salesperson", 'chriso@getagrip.com' in to, to)
        check("subject names the company and property", subject.startswith('[') and 'ZZZ Smoke Tip Property' in subject, subject)
        check("tip text is HTML-escaped in the email", '<script>' not in body and '&lt;script&gt;' in body)
        cur.execute("SELECT status, resend_message_id FROM email_log WHERE kind = 'sales_tip' AND related_id = %s",
                    (tip1['id'],))
        log = cur.fetchone()
        check("send logged to email_log", log and log['status'] == 'sent' and log['resend_message_id'] == 'smoke-msg-id')

        print("smoke_sales_tips: validation and a free-text tip")
        r = tech.post(f'/{CK}/sales/tips/new', data={'notes': 'something'}, follow_redirects=False)
        check("no property and no location -> refused", r.status_code == 200 and 'Say where it is' in r.get_data(as_text=True))
        r = tech.post(f'/{CK}/sales/tips/new', data={'location_text': 'somewhere'}, follow_redirects=False)
        check("no notes -> refused", r.status_code == 200 and 'Say what you saw' in r.get_data(as_text=True))
        r = tech.post(f'/{CK}/sales/tips/new', data={
            'source_work_order_id': wo_id, 'property_type': 'customer', 'property_id': cust_id,
            'different_property': 'on', 'location_text': 'ZZZ complex across the street from the smoke job',
            'notes': 'Big new build going up', 'due_date': date.today().isoformat(),
        }, follow_redirects=False)
        check(f"'different property' tip saved ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT * FROM sales_tips WHERE created_by = 'smoketiptech' ORDER BY id DESC LIMIT 1")
        tip2 = cur.fetchone()
        check("'different property' drops the job's customer", tip2['property_id'] is None and tip2['location_text'])
        check("a weekday due date is kept",
              tip2['due_date'] == date.today() or date.today().weekday() >= 5)

        print("smoke_sales_tips: tips show wherever follow-ups do")
        r = sales.get(f'/{CK}/sales?window=all')
        html = r.get_data(as_text=True)
        check(f"sales dashboard renders ({r.status_code})", r.status_code == 200)
        check("dashboard lists the job tip", 'ZZZ Smoke Tip Property' in html and '🔥 TIP' in html)
        check("dashboard lists the free-text tip", 'ZZZ complex across the street' in html)
        check("dashboard has the + Hot Tip button", f'/{CK}/sales/tips/new' in html)
        r = sales.get(f'/{CK}/sales/followups')
        html = r.get_data(as_text=True)
        check(f"follow-ups page lists tips ({r.status_code})", r.status_code == 200 and 'ZZZ complex across the street' in html)
        r = sales.get('/sales-overview')
        check(f"cross-company overview lists the due-today tip ({r.status_code})",
              r.status_code == 200 and 'ZZZ complex across the street' in r.get_data(as_text=True))
        r = admin.get(f'/{CK}/dashboard')
        check(f"company dashboard renders with tips counted ({r.status_code})", r.status_code == 200)
        r = tech.get(f'/{CK}/myday')
        html = r.get_data(as_text=True)
        check(f"My Day has the tip links ({r.status_code})", r.status_code == 200
              and f'/sales/tips/new?wo={wo_id}' in html and 'Send a sales tip' in html)
        check("a technician can't see the follow-up lists", tech.get(f'/{CK}/sales/followups').status_code == 403)

        print("smoke_sales_tips: a sales hold hides the tip")
        cur.execute("UPDATE customers SET sales_delayed_until = CURRENT_DATE + 30 WHERE id = %s", (cust_id,))
        conn.commit()
        check("held property's tip hidden", tip1['id'] not in [t['id'] for t in _open_tips(cur)])
        check("free-text tip still shown", tip2['id'] in [t['id'] for t in _open_tips(cur)])
        cur.execute("UPDATE customers SET sales_delayed_until = NULL WHERE id = %s", (cust_id,))
        conn.commit()

        print("smoke_sales_tips: logging a visit from a free-text tip closes it and ties the property")
        r = sales.get(f'/{CK}/sales/visits/log?tip={tip2["id"]}')
        html = r.get_data(as_text=True)
        check(f"wizard shows the tip ({r.status_code})", r.status_code == 200 and 'Big new build going up' in html
              and f'name="tip_id" value="{tip2["id"]}"' in html)
        r = sales.post(f'/{CK}/sales/visits/log', data={
            'tip_id': tip2['id'], 'new_prospect_name': 'ZZZ Smoke Tip New Build', 'notes': 'Met the PM',
        }, follow_redirects=False)
        check(f"visit saved ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM sales_prospects WHERE property_name = 'ZZZ Smoke Tip New Build'")
        pid = cur.fetchone()['id']
        prospect_ids.append(pid)
        cur.execute("SELECT * FROM sales_tips WHERE id = %s", (tip2['id'],))
        t2 = cur.fetchone()
        check("tip is done", t2['status'] == 'done' and t2['closed_by'] == 'smoketipsales')
        check("tip tied to the prospect the wizard created",
              t2['property_type'] == 'prospect' and t2['property_id'] == pid)
        cur.execute("SELECT property_id FROM sales_visits WHERE id = %s", (t2['closed_visit_id'],))
        check("closed_visit_id points at that visit", cur.fetchone()['property_id'] == pid)

        print("smoke_sales_tips: any visit to the property closes its open tips")
        r = sales.post(f'/{CK}/sales/visits/log', data={
            'property_type': 'customer', 'property_id': cust_id, 'notes': 'Dropped by',
        }, follow_redirects=False)
        check(f"plain visit saved ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status FROM sales_tips WHERE id = %s", (tip1['id'],))
        check("job tip closed by the visit", cur.fetchone()['status'] == 'done')

        print("smoke_sales_tips: dismiss")
        fail_next['on'] = True
        r = tech.post(f'/{CK}/sales/tips/new', data={'location_text': 'ZZZ dead end', 'notes': 'maybe'},
                      follow_redirects=True)
        fail_next['on'] = False
        check("failed email is surfaced, tip still saved",
              'did NOT go out' in r.get_data(as_text=True))
        cur.execute("SELECT * FROM sales_tips WHERE location_text = 'ZZZ dead end'")
        tip3 = cur.fetchone()
        cur.execute("SELECT status FROM email_log WHERE kind = 'sales_tip' AND related_id = %s", (tip3['id'],))
        check("failed send logged as failed", cur.fetchone()['status'] == 'failed')
        check("a technician can't dismiss", tech.post(f'/{CK}/sales/tips/{tip3["id"]}/dismiss',
                                                      data={'reason': 'x'}).status_code == 403)
        sales.post(f'/{CK}/sales/tips/{tip3["id"]}/dismiss', data={'reason': ''})
        cur.execute("SELECT status FROM sales_tips WHERE id = %s", (tip3['id'],))
        check("dismiss without a reason refused", cur.fetchone()['status'] == 'open')
        sales.post(f'/{CK}/sales/tips/{tip3["id"]}/dismiss', data={'reason': 'Already a customer elsewhere'})
        cur.execute("SELECT status, dismiss_reason FROM sales_tips WHERE id = %s", (tip3['id'],))
        row = cur.fetchone()
        check("dismissed with its reason", row['status'] == 'dismissed' and row['dismiss_reason'])

        print("smoke_sales_tips: weekly report counts tips")
        tips = _sales_weekly_report_data(CK)['tips']
        check(f"report counts sent/visited ({tips})", tips['sent'] >= 3 and tips['visited'] >= 2)

        print("ALL CHECKS PASSED")

    finally:
        appmod._send_email_via_resend = real_send
        conn.rollback()
        ids = tip_ids()
        cur.execute("SELECT id FROM sales_visits WHERE created_by = 'smoketipsales'")
        visit_ids = [r['id'] for r in cur.fetchall()]
        if ids:
            cur.execute("DELETE FROM email_log WHERE kind = 'sales_tip' AND related_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM record_audit WHERE table_name = 'sales_tips' AND record_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM sales_tips WHERE id = ANY(%s)", (ids,))
        if visit_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name = 'sales_visits' AND record_id = ANY(%s)", (visit_ids,))
            cur.execute("DELETE FROM sales_visits WHERE id = ANY(%s)", (visit_ids,))
        if prospect_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name = 'sales_prospects' AND record_id = ANY(%s)", (prospect_ids,))
            cur.execute("DELETE FROM sales_prospects WHERE id = ANY(%s)", (prospect_ids,))
        if wo_ids:
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customer_flags WHERE customer_id = ANY(%s)", (customer_ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(ids)} tip(s), {len(visit_ids)} visit(s), {len(prospect_ids)} prospect(s), "
              f"{len(wo_ids)} work order(s), {len(customer_ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
