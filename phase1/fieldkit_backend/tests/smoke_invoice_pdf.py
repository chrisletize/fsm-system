"""
Smoke test: Increment 1.5 — invoice PDF.

Drives the real Flask routes (test client, forged admin session) against live
getagrip. Everything created is hard-deleted in a `finally` block. Run inside
the app container:

    docker compose exec -T app python tests/smoke_invoice_pdf.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, generate_invoice_pdf, _parse_payment_terms_days  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, invoice_ids = [], []
    catalog_id, original_catalog_name = None, None
    eq_unit_id_created = None

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip']

    try:
        print("smoke_invoice_pdf: due-date parsing")
        check("Net 30 -> 30", _parse_payment_terms_days('Net 30') == 30)
        check("Net 15 -> 15", _parse_payment_terms_days('Net 15') == 15)
        check("Due on Receipt -> 0", _parse_payment_terms_days('Due on Receipt') == 0)
        check("unknown -> 30", _parse_payment_terms_days('Whatever') == 30)
        check("None -> 30", _parse_payment_terms_days(None) == 30)

        cur.execute("SELECT id FROM customers WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        customer_id = cur.fetchone()['id']
        cur.execute("SELECT id, name FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL ORDER BY id LIMIT 1")
        catalog_row = cur.fetchone()
        catalog_id, original_catalog_name = catalog_row['id'], catalog_row['name']
        cur.execute("SELECT id, unit_price FROM catalog_items WHERE billing_behavior='per_day_equipment' AND deleted_at IS NULL LIMIT 1")
        eq_cat = cur.fetchone()
        cur.execute("SELECT id FROM equipment_units WHERE catalog_item_id=%s AND deleted_at IS NULL LIMIT 1", (eq_cat['id'],))
        eq_unit = cur.fetchone()
        eq_unit_created = False
        if not eq_unit:
            # getagrip's equipment registry is genuinely empty in production
            # (confirmed, not a bug) — create a throwaway unit so the
            # equipment/day-math/extraction-explainer path actually gets
            # exercised instead of silently skipping.
            cur.execute("""
                INSERT INTO equipment_units (name, catalog_item_id, is_active, created_by, updated_by)
                VALUES ('SMOKE Test Unit', %s, TRUE, 'smoketest', 'smoketest') RETURNING id
            """, (eq_cat['id'],))
            eq_unit = cur.fetchone()
            eq_unit_id_created = eq_unit['id']
        conn.commit()

        cur.execute("""
            INSERT INTO work_orders (work_order_number, customer_id, status, work_site_label, created_by, updated_by)
            VALUES ('ZZZ-PDF-0001', %s, 'Completed', 'Unit #308', 'smoketest', 'smoketest') RETURNING id
        """, (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)
        cur.execute("""
            INSERT INTO work_order_line_items (work_order_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Standard smoke line', 1, 75.00, 75.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (wo_id, catalog_id))
        if eq_unit:
            cur.execute("""
                INSERT INTO work_order_line_items
                    (work_order_id, catalog_item_id, equipment_unit_id, quantity, unit_price, total,
                     is_taxable, deployed_at, retrieved_at, sort_order, created_by, updated_by)
                VALUES (%s, %s, %s, 3, %s, %s, TRUE, CURRENT_DATE - 3, CURRENT_DATE, 1, 'smoketest', 'smoketest')
            """, (wo_id, eq_cat['id'], eq_unit['id'], eq_cat['unit_price'], 3 * float(eq_cat['unit_price'])))
        conn.commit()

        r = client.post(f'/getagrip/workorders/{wo_id}/invoice/new', follow_redirects=False)
        invoice_id = int(r.headers.get('Location', '').rstrip('/').rsplit('/', 1)[-1])
        invoice_ids.append(invoice_id)
        cur.execute("SELECT current_version_id FROM invoices WHERE id=%s", (invoice_id,))
        version_id = cur.fetchone()['current_version_id']
        cur.execute("UPDATE invoices SET wtn_po_number = 'WTN-SMOKE-1' WHERE id = %s", (invoice_id,))
        conn.commit()

        print("smoke_invoice_pdf: Live version PDF")
        pdf_bytes = generate_invoice_pdf('getagrip', version_id)
        check("Live PDF is non-empty PDF bytes", pdf_bytes is not None and pdf_bytes[:4] == b'%PDF')
        check("Live PDF mentions the work site label", b'Unit #308' in pdf_bytes)

        r = client.get(f'/getagrip/invoices/{invoice_id}/pdf')
        check(f"PDF route responds 200 ({r.status_code})", r.status_code == 200)
        check("PDF route returns application/pdf", r.mimetype == 'application/pdf')
        check("PDF route body is valid PDF bytes", r.data[:4] == b'%PDF')

        print("smoke_invoice_pdf: harden, then byte-for-byte reproducibility")
        client.post(f'/getagrip/invoices/{invoice_id}/harden')
        pdf1 = generate_invoice_pdf('getagrip', version_id)
        pdf2 = generate_invoice_pdf('getagrip', version_id)
        check(f"two renders of the same hardened version are byte-identical ({len(pdf1)} vs {len(pdf2)} bytes)",
              pdf1 == pdf2)

        # Mutate the SOURCE catalog item + work order after hardening — a
        # hardened PDF must not change, and generating it must not even
        # touch those tables.
        cur.execute("UPDATE catalog_items SET name = 'CHANGED NAME AFTER HARDEN' WHERE id = %s", (catalog_id,))
        cur.execute("UPDATE work_orders SET work_site_label = 'CHANGED SITE AFTER HARDEN' WHERE id = %s", (wo_id,))
        conn.commit()
        pdf3 = generate_invoice_pdf('getagrip', version_id)
        check("hardened PDF unchanged after editing the source catalog item + work order",
              pdf3 == pdf1)
        check("hardened PDF does NOT show the post-harden site-label edit",
              b'CHANGED SITE AFTER HARDEN' not in pdf3 and b'Unit #308' in pdf3)

        print("smoke_invoice_pdf: extraction explainer + equipment day-math")
        check("hardened PDF mentions the extraction explainer", b'multi-day process' in pdf3 or b'Drying' in pdf3)
        check("hardened PDF shows deployed/retrieved day math, not a registry unit name",
              b'Deployed' in pdf3 and b'Retrieved' in pdf3)
        check("hardened PDF never shows the internal registry unit name",
              b'SMOKE Test Unit' not in pdf3)

        print("smoke_invoice_pdf: version-scoped PDF route")
        r = client.get(f'/getagrip/invoices/{invoice_id}/versions/{version_id}/pdf')
        check(f"version PDF route responds 200 ({r.status_code})", r.status_code == 200)
        check("version PDF route body matches generate_invoice_pdf output", r.data == pdf3)

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
        if catalog_id is not None:
            cur.execute("UPDATE catalog_items SET name = %s WHERE id = %s AND name = 'CHANGED NAME AFTER HARDEN'",
                        (original_catalog_name, catalog_id))
        if eq_unit_id_created is not None:
            cur.execute("DELETE FROM equipment_units WHERE id = %s", (eq_unit_id_created,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(invoice_ids)} invoice(s), {len(wo_ids)} WO(s) removed.")


if __name__ == '__main__':
    main()
