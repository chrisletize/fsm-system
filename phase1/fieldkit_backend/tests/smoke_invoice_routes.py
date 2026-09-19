"""
Smoke test: Increment 1.3 — create invoice from work order + invoice UI/routes.

Unlike the other smoke tests, this one drives the REAL Flask routes (via
app.test_client() with a forged admin session) against the live getagrip DB,
because the whole point is testing routes + templates + transition_invoice()
wired together end to end, not just the DB layer in isolation. Everything it
creates is explicitly cleaned up in a `finally` block (hard-deleted — these
are throwaway fixtures, not user data). Run inside the app container:

    docker compose exec -T app python tests/smoke_invoice_routes.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids = []
    invoice_ids = []

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
        catalog_std_id = cur.fetchone()['id']
        cur.execute("SELECT id, unit_price FROM catalog_items WHERE billing_behavior='per_day_equipment' AND deleted_at IS NULL LIMIT 1")
        eq_cat = cur.fetchone()
        cur.execute("SELECT id FROM equipment_units WHERE catalog_item_id=%s AND deleted_at IS NULL LIMIT 1", (eq_cat['id'],))
        eq_unit = cur.fetchone()

        print("smoke_invoice_routes: create invoice from a Completed work order")

        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-SMOKE-9001', %s, 'Completed', 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Standard smoke line', 2, 40.00, 80.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (wo_id, catalog_std_id))
        if eq_unit:
            cur.execute("""
                INSERT INTO work_order_line_items
                    (work_order_id, catalog_item_id, equipment_unit_id, quantity, unit_price, total,
                     is_taxable, deployed_at, retrieved_at, sort_order, created_by, updated_by)
                VALUES (%s, %s, %s, 2, %s, %s, TRUE, CURRENT_DATE - 2, CURRENT_DATE, 1, 'smoketest', 'smoketest')
            """, (wo_id, eq_cat['id'], eq_unit['id'], eq_cat['unit_price'], 2 * float(eq_cat['unit_price'])))
        conn.commit()

        # No-Charge WOs are refused.
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-SMOKE-9002', %s, 'No Charge', 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        wo_nc_id = cur.fetchone()['id']
        wo_ids.append(wo_nc_id)
        conn.commit()
        r = client.post(f'/getagrip/workorders/{wo_nc_id}/invoice/new', follow_redirects=False)
        check("No Charge WO redirected back, not invoiced", r.status_code == 302 and 'invoices/' not in r.headers.get('Location', ''))
        cur.execute("SELECT count(*) AS n FROM invoices WHERE work_order_id = %s", (wo_nc_id,))
        check("No Charge WO has zero invoices", cur.fetchone()['n'] == 0)

        r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        loc = r.headers.get('Location', '')
        check(f"invoice created, redirected to detail ({loc})", r.status_code == 302 and '/invoices/' in loc)
        invoice_id = int(loc.rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(invoice_id)

        cur.execute("SELECT status FROM work_orders WHERE id = %s", (wo_id,))
        check("WO status flipped to Invoiced", cur.fetchone()['status'] == 'Invoiced')

        cur.execute("SELECT current_version_id, subtotal FROM invoices i JOIN invoice_versions iv ON iv.id = i.current_version_id WHERE i.id = %s", (invoice_id,))
        row = cur.fetchone()
        expected_subtotal = 80.00 + (2 * float(eq_cat['unit_price']) if eq_unit else 0)
        check(f"subtotal matches snapshot ({row['subtotal']} vs {expected_subtotal})", abs(float(row['subtotal']) - expected_subtotal) < 0.01)

        # Second attempt redirects to the SAME invoice rather than creating another.
        r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        loc2 = r.headers.get('Location', '')
        check("second invoice/new redirects to the existing invoice, not a new one", loc2 == loc)
        cur.execute("SELECT count(*) AS n FROM invoices WHERE work_order_id = %s", (wo_id,))
        check("still exactly one invoice for this WO", cur.fetchone()['n'] == 1)

        print("smoke_invoice_routes: pages render")
        for path in [
            '/getagrip/invoices',
            '/getagrip/invoices?status=Draft',
            '/getagrip/invoices?with_balance=1',
            f'/getagrip/invoices/{invoice_id}',
            f'/getagrip/invoices/{invoice_id}/edit',
            f'/getagrip/workorders/{wo_id}',
            f'/getagrip/customers/{customer_id}',
        ]:
            r = client.get(path)
            check(f"{path} -> {r.status_code}", r.status_code == 200)

        print("smoke_invoice_routes: edit, harden, send, revise")
        r = client.post(f'/getagrip/invoices/{invoice_id}/edit', data={
            'invoice_date': '', 'tax_county': 'Mecklenburg', 'notes_to_customer': 'Thanks!',
        }, follow_redirects=False)
        check(f"edit save redirects ({r.status_code})", r.status_code == 302)

        r = client.post(f'/getagrip/invoices/{invoice_id}/harden', follow_redirects=False)
        check(f"harden succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT iv.state, iv.total FROM invoices i JOIN invoice_versions iv ON iv.id=i.current_version_id WHERE i.id=%s", (invoice_id,))
        v = cur.fetchone()
        check("version is Hardened with a total", v['state'] == 'Hardened' and v['total'] is not None)

        r = client.post(f'/getagrip/invoices/{invoice_id}/send', data={'sent_to_emails': 'test@example.com'}, follow_redirects=False)
        check(f"send succeeds ({r.status_code})", r.status_code == 302)

        r = client.post(f'/getagrip/invoices/{invoice_id}/revise', data={'revision_reason': 'smoke test revision'}, follow_redirects=False)
        check(f"revise succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT current_version_id FROM invoices WHERE id=%s", (invoice_id,))
        new_ver_id = cur.fetchone()['current_version_id']
        check("current_version_id moved after revise", new_ver_id != v.get('id'))

        r = client.get(f'/getagrip/invoices/{invoice_id}')
        check(f"detail page renders after revise ({r.status_code})", r.status_code == 200)

        print("smoke_invoice_routes: void + reissue via routes")
        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, created_by, updated_by)
            VALUES ('ZZZ-SMOKE-9003', %s, 'Completed', 'smoketest', 'smoketest')
            RETURNING id
        """, (customer_id,))
        wo2_id = cur.fetchone()['id']
        wo_ids.append(wo2_id)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Line for void test', 1, 25.00, 25.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (wo2_id, catalog_std_id))
        conn.commit()

        r = client.post(f'/getagrip/workorders/{wo2_id}/invoice/new', follow_redirects=False)
        inv2_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(inv2_id)

        r = client.post(f'/getagrip/invoices/{inv2_id}/void', data={'void_reason': 'smoke test void'}, follow_redirects=False)
        check(f"void succeeds ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT receivable_state FROM invoices WHERE id=%s", (inv2_id,))
        check("receivable is void", cur.fetchone()['receivable_state'] == 'void')

        r = client.post(f'/getagrip/invoices/{inv2_id}/reissue', follow_redirects=False)
        loc3 = r.headers.get('Location', '')
        check(f"reissue succeeds, redirects to a new invoice ({loc3})", r.status_code == 302 and '/invoices/' in loc3)
        reissued_id = int(loc3.rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(reissued_id)
        check("reissue got a different id than the void", reissued_id != inv2_id)

        r = client.get(f'/getagrip/invoices/{reissued_id}')
        check(f"reissued invoice detail renders ({r.status_code})", r.status_code == 200)

        print("ALL CHECKS PASSED")

    finally:
        for iid in invoice_ids:
            cur.execute("DELETE FROM invoice_status_history WHERE invoice_id = %s", (iid,))
            cur.execute("DELETE FROM invoice_version_line_items WHERE version_id IN (SELECT id FROM invoice_versions WHERE invoice_id = %s)", (iid,))
            cur.execute("UPDATE invoices SET current_version_id = NULL WHERE id = %s", (iid,))
            cur.execute("DELETE FROM invoice_versions WHERE invoice_id = %s", (iid,))
        if invoice_ids:
            cur.execute("UPDATE invoices SET reissue_of_invoice_id = NULL, reissued_as_invoice_id = NULL WHERE id = ANY(%s)", (invoice_ids,))
            cur.execute("DELETE FROM invoices WHERE id = ANY(%s)", (invoice_ids,))
        for wid in wo_ids:
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} work order(s) removed.")


if __name__ == '__main__':
    main()
