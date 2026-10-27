"""
Smoke test: the salesman's view of an existing customer (migration 040, D-116,
Chris 2026-10-21). He visits dormant customers but is locked out of customer
pages, and the price-list request only existed for prospects.

Covers: the sales customer page (read-only, sales-relevant only, modals in the
body), the past-due warning built but OFF by default and admin-switchable, the
customer price-list request (candidates incl. a labelled billing contact, typed
address not written to the customer, its own email_log kind, HTML-escaped,
failure surfaced), the prospect price-list request still working after the
refactor, the links into the page, and role access.

Drives the real routes (test client, forged sessions) against live getagrip.
Resend is monkey-patched, so nothing is ever emailed. Everything created is
hard-deleted, and the company setting is restored, in a `finally` block. Run
inside the app container:

    docker compose exec -T app python tests/smoke_sales_customer_page.py
"""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod  # noqa: E402
from app import get_db_connection, app  # noqa: E402

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
    sent = []
    fail_next = {'on': False}
    real_send = appmod._send_email_via_resend

    def fake_send(to_emails, subject, html_body, **kw):
        sent.append((list(to_emails), subject, html_body))
        if fail_next['on']:
            return None, 'smoke-induced rejection'
        return 'smoke-msg-id', None
    appmod._send_email_via_resend = fake_send

    cur.execute("SELECT sales_past_due_warning_enabled FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    original_setting = cur.fetchone()['sales_past_due_warning_enabled']

    sales = client_as('salesperson', 'smokecustsales')
    admin = client_as('admin', 'smokecustadmin')
    tech = client_as('technician', 'smokecusttech')
    cust_id = prospect_id = wo_id = None
    mc_ids = []

    try:
        cur.execute("""INSERT INTO customers (property_name, customer_type, status, address, city, state,
                           billing_email, created_by, updated_by)
                       VALUES ('ZZZ Smoke Dormant <Tower>', 'Multi Family', 'Active', '1 Smoke St', 'Charlotte',
                               'NC', 'ap@billing.invalid', 'smokecust', 'smokecust') RETURNING id""")
        cust_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO work_orders (work_order_number, customer_id, status, start_date, created_by, updated_by)
                       VALUES ('ZZZ-SMOKE-CUST1', %s, 'Completed', CURRENT_DATE - 400, 'smokecust', 'smokecust')
                       RETURNING id""", (cust_id,))
        wo_id = cur.fetchone()['id']
        cur.execute("""INSERT INTO customer_contacts (customer_id, first_name, last_name, title, office_email,
                           office_phone, is_primary, accepts_billing, created_by)
                       VALUES (%s, 'Pat', 'Manager', 'Property Manager', 'pat@tower.invalid', '704-555-0100',
                               TRUE, FALSE, 'smokecust'),
                              (%s, 'Accounts', 'Payable', NULL, 'ap@avidbill.invalid', NULL,
                               FALSE, TRUE, 'smokecust')""", (cust_id, cust_id))
        cur.execute("""INSERT INTO sales_contacts (first_name, last_name, title, office_email,
                           current_property_id, current_property_type, created_by, updated_by)
                       VALUES ('Sam', 'Leasing', 'Leasing Agent', 'sam@tower.invalid', %s, 'customer',
                               'smokecust', 'smokecust')""", (cust_id,))
        cur.execute("INSERT INTO customer_flags (customer_id, is_delinquent) VALUES (%s, TRUE)", (cust_id,))
        cur.execute("UPDATE company_settings SET sales_past_due_warning_enabled = FALSE WHERE deleted_at IS NULL")
        conn.commit()

        print("smoke_sales_customer_page: the page")
        r = sales.get(f'/{CK}/sales/customers/{cust_id}')
        html = r.get_data(as_text=True)
        check(f"salesperson can open it ({r.status_code})", r.status_code == 200)
        check("name is escaped", 'ZZZ Smoke Dormant &lt;Tower&gt;' in html)
        check("shows it's an existing, dormant customer",
              'Existing customer' in html and 'Dormant' in html and 'Last service' in html)
        check("shows sales contacts and customer contacts", 'Sam Leasing' in html and 'Pat Manager' in html)
        check("billing contact is labelled", 'badge-billing' in html)
        check("no invoices/balances/billing email on the page",
              'ap@billing.invalid' not in html and 'Invoice' not in html and 'balance' not in html.lower())
        check("no link to the office customer record for the salesperson", f'/{CK}/customers/{cust_id}"' not in html)
        check("action buttons present", 'Request Price List' in html and 'Log Visit' in html
              and 'Add Tip' in html and 'Pause Sales' in html)
        check("modals and their script are in the body, not the title",
              html.index('</title>') < html.index('id="priceListModal"') < html.index('function openPriceList'))
        check("past-due warning is OFF by default even though the customer is delinquent",
              'Account past due' not in html)
        check("a technician can't open it", tech.get(f'/{CK}/sales/customers/{cust_id}').status_code == 403)
        check("salesperson is still locked out of the office customer page",
              sales.get(f'/{CK}/customers/{cust_id}').status_code == 403)
        check("managers get a link to the full record",
              f'/{CK}/customers/{cust_id}"' in admin.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True))

        print("smoke_sales_customer_page: the past-due switch")
        check("salesperson can't flip it",
              sales.post(f'/{CK}/settings/company/sales-past-due-warning',
                         data={'sales_past_due_warning_enabled': 'on'}).status_code == 403)
        r = admin.get(f'/{CK}/settings/company')
        check(f"settings page shows the switch, OFF ({r.status_code})",
              r.status_code == 200 and 'Past-due warning on sales customer pages' in r.get_data(as_text=True))
        admin.post(f'/{CK}/settings/company/sales-past-due-warning', data={'sales_past_due_warning_enabled': 'on'})
        html = sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True)
        check("switched on: warning shows, with no amount",
              'Account past due' in html and '$' not in html.split('Account past due')[1][:200])
        admin.post(f'/{CK}/settings/company/sales-past-due-warning', data={})
        check("switched off again: warning gone",
              'Account past due' not in sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True))

        print("smoke_sales_customer_page: requesting a price list for a customer")
        html = sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True)
        check("candidates: sales contact, customer contact, and the AP inbox labelled billing",
              'sam@tower.invalid' in html and 'pat@tower.invalid' in html
              and 'customer contact - billing' in html)
        cur.execute("SELECT COUNT(*) AS n FROM email_log WHERE kind = 'price_list_request' AND related_id = %s",
                    (cust_id,))
        prospect_kind_before = cur.fetchone()['n']
        r = sales.post(f'/{CK}/sales/customers/{cust_id}/request-price-list',
                       data={'send_to': 'pat@tower.invalid'}, follow_redirects=True)
        check(f"request sent ({r.status_code})", r.status_code == 200
              and 'Price list request sent to' in r.get_data(as_text=True))
        to, subject, body = sent[-1]
        check("goes to the office and Michael", 'office@getagripofcharlotte.com' in to and 'michaelobuckley@yahoo.com' in to, to)
        check("says it's an existing customer, with last service", 'existing customer' in body and 'Last service' in body)
        check("property name escaped in the email", '<Tower>' not in body and '&lt;Tower&gt;' in body)
        cur.execute("SELECT price_list_requested_to, price_list_requested_by FROM customers WHERE id = %s", (cust_id,))
        row = cur.fetchone()
        check("recorded on the customer", row['price_list_requested_to'] == 'pat@tower.invalid'
              and row['price_list_requested_by'] == 'smokecustsales')
        cur.execute("""SELECT status FROM email_log WHERE kind = 'customer_price_list' AND related_id = %s
                       ORDER BY sent_at DESC LIMIT 1""", (cust_id,))
        check("logged under its own kind", cur.fetchone()['status'] == 'sent')
        cur.execute("SELECT COUNT(*) AS n FROM email_log WHERE kind = 'price_list_request' AND related_id = %s",
                    (cust_id,))
        check("nothing logged under the prospect kind for this id", cur.fetchone()['n'] == prospect_kind_before)
        html = sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True)
        check("page shows the delivered request", '✓ Price list requested' in html)

        r = sales.post(f'/{CK}/sales/customers/{cust_id}/request-price-list',
                       data={'new_email': 'typed@tower.invalid'}, follow_redirects=False)
        cur.execute("SELECT billing_email, price_list_requested_to FROM customers WHERE id = %s", (cust_id,))
        row = cur.fetchone()
        check("a typed address is used but never written to the customer record",
              row['price_list_requested_to'] == 'typed@tower.invalid' and row['billing_email'] == 'ap@billing.invalid')
        fail_next['on'] = True
        r = sales.post(f'/{CK}/sales/customers/{cust_id}/request-price-list',
                       data={'send_to': 'pat@tower.invalid'}, follow_redirects=True)
        fail_next['on'] = False
        check("a failed send says so", 'FAILED' in r.get_data(as_text=True))
        check("and the page keeps saying so",
              'was NOT emailed' in sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True))
        check("technician can't request one",
              tech.post(f'/{CK}/sales/customers/{cust_id}/request-price-list',
                        data={'send_to': 'pat@tower.invalid'}).status_code == 403)

        print("smoke_sales_customer_page: the prospect request still works after the refactor")
        cur.execute("""INSERT INTO sales_prospects (property_name, general_email, created_by, updated_by)
                       VALUES ('ZZZ Smoke Prospect', 'leasing@prospect.invalid', 'smokecust', 'smokecust')
                       RETURNING id""")
        prospect_id = cur.fetchone()['id']
        conn.commit()
        r = sales.post(f'/{CK}/sales/prospects/{prospect_id}/request-price-list', data={}, follow_redirects=False)
        check(f"one-candidate prospect request ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT price_list_requested_to FROM sales_prospects WHERE id = %s", (prospect_id,))
        check("recorded on the prospect", cur.fetchone()['price_list_requested_to'] == 'leasing@prospect.invalid')
        cur.execute("SELECT COUNT(*) AS n FROM email_log WHERE kind = 'price_list_request' AND related_id = %s",
                    (prospect_id,))
        check("logged under the prospect kind", cur.fetchone()['n'] == 1)
        check("prospect email still says prospect", 'has a prospect' in sent[-1][2])
        html = sales.get(f'/{CK}/sales/prospects/{prospect_id}').get_data(as_text=True)
        check("prospect page still renders its modals in the body",
              html.index('</title>') < html.index('id="priceListModal"') < html.index('function openPriceList'))

        print("smoke_sales_customer_page: changing the management company (D-117)")
        cur.execute("""INSERT INTO management_companies (name, created_by, updated_by)
                       VALUES ('ZZZ Smoke MgmtCo <A>', 'smokecust', 'smokecust'),
                              ('ZZZ Smoke MgmtCo B', 'smokecust', 'smokecust') RETURNING id""")
        mc_ids += [r['id'] for r in cur.fetchall()]
        mc_a, mc_b = mc_ids
        cur.execute("UPDATE customers SET management_company_id = %s WHERE id = %s", (mc_a, cust_id))
        conn.commit()
        html = sales.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True)
        check("page shows the management company and a Change button",
              'ZZZ Smoke MgmtCo &lt;A&gt;' in html and 'openMc()' in html and 'id="mcModal"' in html)
        check("salesperson sees the check-with-a-manager warning", 'Check it with a manager' in html)
        check("the change modal is in the body", html.index('</title>') < html.index('id="mcModal"'))
        check("managers don't get the warning",
              'Check it with a manager' not in admin.get(f'/{CK}/sales/customers/{cust_id}').get_data(as_text=True))

        n_sent = len(sent)
        r = sales.post(f'/{CK}/sales/customers/{cust_id}/management-company',
                       data={'management_company_id': mc_b, 'note': 'new PM said so <b>',
                             'billing_email': 'hacked@evil.invalid', 'property_name': 'Hacked'},
                       follow_redirects=True)
        check(f"salesperson's change saved ({r.status_code})", r.status_code == 200
              and 'The managers have been emailed' in r.get_data(as_text=True))
        cur.execute("SELECT management_company_id, billing_email, property_name FROM customers WHERE id = %s", (cust_id,))
        row = cur.fetchone()
        check("management company changed", row['management_company_id'] == mc_b)
        check("nothing else on the customer can be changed this way",
              row['billing_email'] == 'ap@billing.invalid' and row['property_name'] == 'ZZZ Smoke Dormant <Tower>')
        cur.execute("""SELECT changed_by, diff::text AS diff FROM record_audit WHERE table_name = 'customers'
                       AND record_id = %s ORDER BY id DESC LIMIT 1""", (cust_id,))
        aud = cur.fetchone()
        check("recorded in the customer's audit trail", aud and aud['changed_by'] == 'smokecustsales'
              and 'ZZZ Smoke MgmtCo B' in aud['diff'])
        check("one email to the managers", len(sent) == n_sent + 1)
        to, subject, body = sent[-1]
        check(f"goes to the company's managers/admins ({to})", len(to) >= 1 and 'office@getagripofcharlotte.com' not in to)
        check("subject asks them to confirm", 'Please confirm' in subject and 'ZZZ Smoke Dormant' in subject)
        check("email shows was/now and the note, escaped",
              'ZZZ Smoke MgmtCo &lt;A&gt;' in body and 'ZZZ Smoke MgmtCo B' in body
              and 'new PM said so &lt;b&gt;' in body and '<b>' not in body.split('Their note')[1])
        check("email links to the customer record", f'/{CK}/customers/{cust_id}' in body)
        cur.execute("""SELECT status FROM email_log WHERE kind = 'mgmt_company_change' AND related_id = %s
                       ORDER BY sent_at DESC LIMIT 1""", (cust_id,))
        check("logged to email_log", cur.fetchone()['status'] == 'sent')

        r = sales.post(f'/{CK}/sales/customers/{cust_id}/management-company',
                       data={'management_company_id': mc_b}, follow_redirects=True)
        check("same company again is a no-op, no email",
              'unchanged' in r.get_data(as_text=True) and len(sent) == n_sent + 1)
        r = sales.post(f'/{CK}/sales/customers/{cust_id}/management-company',
                       data={'management_company_id': '999999999'}, follow_redirects=True)
        cur.execute("SELECT management_company_id FROM customers WHERE id = %s", (cust_id,))
        check("a nonexistent company is refused", cur.fetchone()['management_company_id'] == mc_b
              and 'no longer exists' in r.get_data(as_text=True))
        fail_next['on'] = True
        r = sales.post(f'/{CK}/sales/customers/{cust_id}/management-company',
                       data={'management_company_id': ''}, follow_redirects=True)
        fail_next['on'] = False
        cur.execute("SELECT management_company_id FROM customers WHERE id = %s", (cust_id,))
        check("clearing it works (independent)", cur.fetchone()['management_company_id'] is None)
        check("a failed manager email is surfaced, and the change still sticks",
              'FAILED' in r.get_data(as_text=True))
        n_sent = len(sent)
        admin.post(f'/{CK}/sales/customers/{cust_id}/management-company', data={'management_company_id': mc_a})
        cur.execute("SELECT management_company_id FROM customers WHERE id = %s", (cust_id,))
        check("a manager's change needs no confirmation email",
              cur.fetchone()['management_company_id'] == mc_a and len(sent) == n_sent)
        check("a technician can't change it",
              tech.post(f'/{CK}/sales/customers/{cust_id}/management-company',
                        data={'management_company_id': mc_b}).status_code == 403)

        r = sales.post(f'/{CK}/sales/management-companies/new', data={'name': '  zzz smoke mgmtco b '})
        check("adding a name that already exists returns the existing company",
              r.get_json()['id'] == mc_b and r.get_json().get('existing'))
        cur.execute("SELECT COUNT(*) AS n FROM management_companies WHERE lower(name) = 'zzz smoke mgmtco b'")
        check("no duplicate created", cur.fetchone()['n'] == 1)

        print("smoke_sales_customer_page: ways in")
        r = sales.post(f'/{CK}/sales/visits/log', data={
            'property_type': 'customer', 'property_id': cust_id, 'notes': 'Checking in',
        }, follow_redirects=False)
        check(f"logging a customer visit lands on the sales customer page ({r.headers.get('Location')})",
              r.status_code == 302 and r.headers['Location'].endswith(f'/sales/customers/{cust_id}'))
        html = sales.get(f'/{CK}/sales?window=all').get_data(as_text=True)
        check("dashboard links the customer (dormant card / recent visits)",
              f'/{CK}/sales/customers/{cust_id}' in html)
        html = sales.get(f'/{CK}/sales/visits').get_data(as_text=True)
        check("visit log links the customer", f'/{CK}/sales/customers/{cust_id}' in html)
        r = sales.get(f'/{CK}/sales/tips/new?property_type=customer&property_id={cust_id}')
        check("Add Tip pre-fills the customer", 'ZZZ Smoke Dormant &lt;Tower&gt;' in r.get_data(as_text=True))

        print("ALL CHECKS PASSED")

    finally:
        appmod._send_email_via_resend = real_send
        conn.rollback()
        cur.execute("UPDATE company_settings SET sales_past_due_warning_enabled = %s WHERE deleted_at IS NULL",
                    (original_setting,))
        if cust_id:
            cur.execute("DELETE FROM email_log WHERE kind IN ('customer_price_list', 'mgmt_company_change') AND related_id = %s", (cust_id,))
            cur.execute("SELECT id FROM sales_visits WHERE property_type = 'customer' AND property_id = %s", (cust_id,))
            vids = [r['id'] for r in cur.fetchall()]
            if vids:
                cur.execute("DELETE FROM record_audit WHERE table_name = 'sales_visits' AND record_id = ANY(%s)", (vids,))
                cur.execute("DELETE FROM sales_visits WHERE id = ANY(%s)", (vids,))
            cur.execute("DELETE FROM sales_contacts WHERE current_property_type = 'customer' AND current_property_id = %s",
                        (cust_id,))
            cur.execute("DELETE FROM customer_contacts WHERE customer_id = %s", (cust_id,))
            cur.execute("DELETE FROM customer_flags WHERE customer_id = %s", (cust_id,))
        if wo_id:
            cur.execute("DELETE FROM work_orders WHERE id = %s", (wo_id,))
        if cust_id:
            cur.execute("DELETE FROM record_audit WHERE table_name = 'customers' AND record_id = %s", (cust_id,))
            cur.execute("DELETE FROM customers WHERE id = %s", (cust_id,))
        if mc_ids:
            cur.execute("DELETE FROM management_companies WHERE id = ANY(%s) OR name ILIKE 'ZZZ Smoke MgmtCo%%'", (mc_ids,))
        if prospect_id:
            cur.execute("DELETE FROM email_log WHERE kind = 'price_list_request' AND related_id = %s", (prospect_id,))
            cur.execute("DELETE FROM sales_prospects WHERE id = %s", (prospect_id,))
        conn.commit()
        cur.close()
        conn.close()
        print("cleanup done: test customer, prospect, contacts, visits and email log rows removed; setting restored.")


if __name__ == '__main__':
    main()
