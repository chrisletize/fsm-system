"""
Smoke test: dispatch-board visit LEDs go dark once the office has closed the
job out (Chris, 2026-10-19: "the light should turn off once the office has
done its work"). A tech's Completed LED pulses to prompt the office; it must
stay lit through invoice creation and hardening, go dark once the invoice is
actually Sent, come back if that invoice is voided, and go dark on No Charge /
Cancelled (nothing will ever be invoiced there).

Drives the real routes (test client, forged admin session) against live
getagrip, reading the LEDs from /dispatch/data exactly as the board does.
Everything created is hard-deleted in a `finally` block. Run inside the app
container:

    docker compose exec -T app python tests/smoke_dispatch_led_closeout.py
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402

TECH = 'smokeledtech'


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids = [], []
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    def led(wo_id):
        r = client.get(f"/getagrip/dispatch/data?date={date.today().isoformat()}")
        assert r.status_code == 200, r.status_code
        block = next(b for b in r.get_json()['blocks'] if b['id'] == wo_id)
        return block['visit_status_by_tech'].get(TECH)

    def make_wo(number, status):
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, start_date,
                                     scheduled_start, estimated_duration_hours, created_by, updated_by)
            VALUES (%s, %s, %s, CURRENT_DATE, CURRENT_DATE + TIME '09:00', 1, 'smoketest', 'smoketest')
            RETURNING id
        """, (number, customer_id, status))
        wid = cur.fetchone()['id']
        wo_ids.append(wid)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity,
                                               unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'LED smoke line', 1, 50.00, 50.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (wid, catalog_id))
        cur.execute("INSERT INTO work_order_techs (work_order_id, username, is_lead_tech) VALUES (%s, %s, TRUE)",
                    (wid, TECH))
        conn.commit()
        # Office logging the tech's Completed on their behalf -- same route My Day uses.
        r = client.post(f'/getagrip/workorders/{wid}/visit-status',
                        data={'status': 'Completed', 'username': TECH}, follow_redirects=False)
        assert r.status_code in (200, 302), r.status_code
        return wid

    def invoice_for(wid):
        r = client.post(f'/getagrip/workorders/{wid}/invoice/new', follow_redirects=False)
        iid = int(r.headers['Location'].rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(iid)
        return iid

    try:
        cur.execute("SELECT id FROM customers WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        customer_id = cur.fetchone()['id']
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        print("smoke_dispatch_led_closeout: LED stays lit until the invoice is actually Sent")
        wo = make_wo('ZZZ-SMOKE-LED1', 'Completed')
        check("tech Completed, office not done -> LED lit", led(wo) == 'Completed', led(wo))
        inv = invoice_for(wo)
        check("invoice created (draft) -> still lit", led(wo) == 'Completed')
        r = client.post(f'/getagrip/invoices/{inv}/harden', follow_redirects=False)
        check(f"harden ok ({r.status_code})", r.status_code == 302)
        check("invoice hardened, not sent -> still lit", led(wo) == 'Completed')
        r = client.post(f'/getagrip/invoices/{inv}/send', data={'sent_to_emails': ''}, follow_redirects=False)
        check(f"Mark Sent (no email) ok ({r.status_code})", r.status_code == 302)
        check("invoice Sent -> LED dark", led(wo) is None, led(wo))

        print("smoke_dispatch_led_closeout: voiding the sent invoice relights it")
        r = client.post(f'/getagrip/invoices/{inv}/void', data={'void_reason': 'smoke LED void'}, follow_redirects=False)
        check(f"void ok ({r.status_code})", r.status_code == 302)
        check("voided invoice -> LED lit again (job needs billing)", led(wo) == 'Completed', led(wo))

        print("smoke_dispatch_led_closeout: No Charge / Cancelled close the job out without an invoice")
        nc = make_wo('ZZZ-SMOKE-LED2', 'No Charge')
        check("No Charge -> LED dark", led(nc) is None, led(nc))
        cx = make_wo('ZZZ-SMOKE-LED3', 'Cancelled')
        check("Cancelled -> LED dark", led(cx) is None, led(cx))

        print("ALL CHECKS PASSED")

    finally:
        conn.rollback()
        for iid in invoice_ids:
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
        if invoice_ids:
            cur.execute("UPDATE invoices SET reissue_of_invoice_id = NULL, reissued_as_invoice_id = NULL WHERE id = ANY(%s)", (invoice_ids,))
            cur.execute("DELETE FROM invoices WHERE id = ANY(%s)", (invoice_ids,))
            cur.execute("DELETE FROM record_audit WHERE table_name = 'invoices' AND record_id = ANY(%s)", (invoice_ids,))
        if wo_ids:
            cur.execute("""DELETE FROM record_audit WHERE table_name = 'work_order_visit_status_log'
                           AND record_id IN (SELECT id FROM work_order_visit_status_log WHERE work_order_id = ANY(%s))""",
                        (wo_ids,))
            cur.execute("DELETE FROM work_order_visit_status_log WHERE work_order_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM record_audit WHERE table_name = 'work_orders' AND record_id = ANY(%s)", (wo_ids,))
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} work order(s) removed.")


if __name__ == '__main__':
    main()
