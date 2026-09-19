"""
Smoke test: Increment 1.4 — payments, applications, adjustments, credits.

Drives the real Flask routes (test client, forged admin session) against live
getagrip, same approach as smoke_invoice_routes.py. Everything created is
hard-deleted in a `finally` block. Run inside the app container:

    docker compose exec -T app python tests/smoke_payments.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, invoice_balance, customer_unapplied_credit, _remaining_unapplied  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids, payment_ids, adjustment_ids = [], [], [], []

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        cur.execute("SELECT id FROM customers WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        customer_id = cur.fetchone()['id']
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']

        def make_invoice(number, amount):
            cur.execute("""
                INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
                VALUES (%s, %s, 'Completed', 'smoketest', 'smoketest') RETURNING id
            """, (number, customer_id))
            wo_id = cur.fetchone()['id']
            wo_ids.append(wo_id)
            cur.execute("""
                INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
                VALUES (%s, %s, 'Smoke line', 1, %s, %s, FALSE, 0, 'smoketest', 'smoketest')
            """, (wo_id, catalog_id, amount, amount))
            conn.commit()
            r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
            inv_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
            invoice_ids.append(inv_id)
            client.post(f'/getagrip/invoices/{inv_id}/harden')
            client.post(f'/getagrip/invoices/{inv_id}/send')
            return inv_id

        print("smoke_payments: record + apply a partial payment")
        inv1 = make_invoice('ZZZ-PAY-0001', 100.00)
        bal_before = invoice_balance(cur, inv1)
        check(f"invoice balance is 100.00 before any payment ({bal_before})", abs(float(bal_before) - 100.00) < 0.01)

        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'amount': '40.00', 'payment_date': '2026-09-19',
            'apply_to_invoice_id': str(inv1), 'redirect_to': f'/getagrip/invoices/{inv1}',
        }, follow_redirects=False)
        check(f"payment recorded and applied ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM payments WHERE customer_id=%s ORDER BY id DESC LIMIT 1", (customer_id,))
        pay1 = cur.fetchone()['id']
        payment_ids.append(pay1)

        bal_after = invoice_balance(cur, inv1)
        check(f"balance drops to 60.00 ({bal_after})", abs(float(bal_after) - 60.00) < 0.01)

        r = client.get(f'/getagrip/invoices/{inv1}')
        check(f"invoice detail renders ({r.status_code})", r.status_code == 200)
        check("shows Partially Paid", b'Partially Paid' in r.data)

        print("smoke_payments: over-application is rejected")
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'amount': '1000.00', 'payment_date': '2026-09-19',
            'apply_to_invoice_id': str(inv1), 'redirect_to': f'/getagrip/invoices/{inv1}',
        }, follow_redirects=False)
        cur.execute("SELECT id FROM payments WHERE customer_id=%s AND amount=1000.00", (customer_id,))
        over_pay = cur.fetchone()
        if over_pay:
            payment_ids.append(over_pay['id'])
        bal_unchanged = invoice_balance(cur, inv1)
        check(f"balance unaffected by the rejected over-application ({bal_unchanged})", abs(float(bal_unchanged) - 60.00) < 0.01)

        print("smoke_payments: paying in full triggers Paid + celebration")
        inv2 = make_invoice('ZZZ-PAY-0002', 25.00)  # a second open invoice for "next unpaid"
        r = client.post('/getagrip/payments/new', data={
            'customer_id': customer_id, 'amount': '60.00', 'payment_date': '2026-09-19',
            'apply_to_invoice_id': str(inv1), 'redirect_to': f'/getagrip/invoices/{inv1}',
        }, follow_redirects=False)
        cur.execute("SELECT id FROM payments WHERE customer_id=%s AND amount=60.00", (customer_id,))
        pay2 = cur.fetchone()['id']
        payment_ids.append(pay2)
        check("second payment redirects to the invoice (paid in full)", '/invoices/' in r.headers.get('Location', ''))

        bal_zero = invoice_balance(cur, inv1)
        check(f"balance is now zero ({bal_zero})", abs(float(bal_zero)) < 0.01)

        r = client.get(f'/getagrip/invoices/{inv1}')
        check("shows Paid + Next Unpaid Invoice link", b'>Paid<' in r.data and b'Next Unpaid Invoice' in r.data)

        print("smoke_payments: unapply, void, refund")
        cur.execute("SELECT id, amount FROM payment_applications WHERE payment_id=%s AND reverses_application_id IS NULL", (pay2,))
        app_row = cur.fetchone()
        r = client.post(f'/getagrip/payments/{pay2}/unapply/{app_row["id"]}', follow_redirects=False)
        check(f"unapply succeeds ({r.status_code})", r.status_code == 302)
        bal_after_unapply = invoice_balance(cur, inv1)
        check(f"balance restored to 60.00 after unapply ({bal_after_unapply})", abs(float(bal_after_unapply) - 60.00) < 0.01)

        remaining = _remaining_unapplied(cur, pay2)
        check(f"pay2 now fully unapplied ({remaining})", abs(remaining - 60.00) < 0.01)

        credit = customer_unapplied_credit(cur, customer_id)
        check(f"customer_unapplied_credit reflects the unapplied 60.00 ({credit})", credit >= 59.99)

        r = client.get(f'/getagrip/customers/{customer_id}')
        check("customer detail shows the unapplied-credit badge", b'Unapplied credit' in r.data)

        r = client.post(f'/getagrip/payments/{pay2}/refund', data={'amount': '20.00', 'reference': 'smoke-ref'}, follow_redirects=False)
        check(f"partial refund succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT refunded_amount FROM payments WHERE id=%s", (pay2,))
        check("refunded_amount is 20.00", abs(float(cur.fetchone()['refunded_amount']) - 20.00) < 0.01)

        r = client.post(f'/getagrip/payments/{pay2}/void', data={'void_reason': 'smoke test void'}, follow_redirects=False)
        check(f"void succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT status FROM payments WHERE id=%s", (pay2,))
        check("payment status is voided", cur.fetchone()['status'] == 'voided')

        print("smoke_payments: adjustments")
        r = client.post(f'/getagrip/invoices/{inv1}/adjustments/new', data={
            'amount': '10.00', 'adjustment_type': 'write_off', 'reason': 'smoke write-off',
        }, follow_redirects=False)
        check(f"adjustment created ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM invoice_adjustments WHERE invoice_id=%s ORDER BY id DESC LIMIT 1", (inv1,))
        adj_id = cur.fetchone()['id']
        adjustment_ids.append(adj_id)
        bal_with_adj = invoice_balance(cur, inv1)
        check(f"balance reduced by the adjustment ({bal_with_adj})", abs(float(bal_with_adj) - 50.00) < 0.01)

        r = client.post(f'/getagrip/invoices/{inv1}/adjustments/{adj_id}/delete', follow_redirects=False)
        check(f"same-day adjustment delete succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT deleted_at FROM invoice_adjustments WHERE id=%s", (adj_id,))
        check("adjustment soft-deleted (same day, same user)", cur.fetchone()['deleted_at'] is not None)
        bal_restored = invoice_balance(cur, inv1)
        check(f"balance restored after delete ({bal_restored})", abs(float(bal_restored) - 60.00) < 0.01)

        print("smoke_payments: payment list/detail pages render")
        for path in ['/getagrip/payments', '/getagrip/payments?unapplied=1', f'/getagrip/payments/{pay1}']:
            r = client.get(path)
            check(f"{path} -> {r.status_code}", r.status_code == 200)

        print("ALL CHECKS PASSED")

    finally:
        for aid in adjustment_ids:
            cur.execute("DELETE FROM invoice_adjustments WHERE invoice_id = ANY(%s)", (invoice_ids,))
        for pid in payment_ids:
            cur.execute("DELETE FROM payment_status_history WHERE payment_id = %s", (pid,))
            cur.execute("DELETE FROM payment_applications WHERE payment_id = %s", (pid,))
        if payment_ids:
            cur.execute("DELETE FROM payments WHERE id = ANY(%s)", (payment_ids,))
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
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(payment_ids)} payment(s), {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s) removed.")


if __name__ == '__main__':
    main()
