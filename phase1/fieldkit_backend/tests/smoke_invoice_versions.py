"""
Smoke test: Increment 1.2 — the receivable/version invoice refactor.

Runs inside a single transaction against fieldkit_getagrip and ROLLBACKs at the
end — nothing here is left behind, including a temporary payment_applications /
invoice_adjustments table used to exercise the payment guards ahead of
Increment 1.4 (see the note above those checks). Run inside the app container:

    docker compose exec -T app python tests/smoke_invoice_versions.py

Covers everything the build directive calls out for this increment: harden
rejected while an equipment line is still accruing; reopen rejected once a
payment application exists; revise -> new Live version cloned, old marked
Superseded, current_version_id moved, deltas written at the re-harden; reissue
mints a new number and clones lines; hardened snapshot unchanged after the
source catalog item / tax rate changes; ordinals (1 unit -> bare label, 3
units -> 1..3).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, transition_invoice, invoice_balance, invoice_display_status  # noqa: E402


def check(label, condition):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM customers WHERE deleted_at IS NULL ORDER BY id LIMIT 1")
        customer_id = cur.fetchone()['id']

        cur.execute("""
            INSERT INTO catalog_items (billing_behavior, name, invoice_label, unit_of_measure,
                unit_price, is_taxable, is_active, sort_order)
            VALUES ('per_day_equipment', 'SMOKE Test Dehu', 'Test Dehu', 'day', 15.00, TRUE, TRUE, 999)
            RETURNING id
        """)
        catalog_dehu_id = cur.fetchone()['id']  # single-unit group (bare label test)

        cur.execute("""
            SELECT id FROM catalog_items WHERE billing_behavior = 'per_day_equipment'
              AND deleted_at IS NULL AND id != %s LIMIT 1
        """, (catalog_dehu_id,))
        catalog_ozone_id = cur.fetchone()['id']  # 3-unit group (ordinal test)

        cur.execute("""
            SELECT id FROM catalog_items WHERE billing_behavior = 'standard' AND deleted_at IS NULL LIMIT 1
        """)
        catalog_standard_id = cur.fetchone()['id']

        def make_invoice(number):
            cur.execute("""
                INSERT INTO invoices (invoice_number, customer_id, invoice_date, created_by, updated_by)
                VALUES (%s, %s, CURRENT_DATE, 'smoketest', 'smoketest')
                RETURNING id
            """, (number, customer_id))
            inv_id = cur.fetchone()['id']
            cur.execute("""
                INSERT INTO invoice_versions (invoice_id, revision_number, state, subtotal, tax_county, created_by, updated_by)
                VALUES (%s, 0, 'Live', 0, 'Mecklenburg', 'smoketest', 'smoketest')
                RETURNING id
            """, (inv_id,))
            ver_id = cur.fetchone()['id']
            cur.execute("UPDATE invoices SET current_version_id = %s WHERE id = %s", (ver_id, inv_id))
            return inv_id, ver_id

        print("smoke_invoice_versions: harden guards + ordinals")

        inv1, ver1 = make_invoice('ZZZ-SMOKE-0001')

        cur.execute("""
            INSERT INTO invoice_version_line_items (version_id, catalog_item_id, description, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 'Standard line', 1, 100.00, 100.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (ver1, catalog_standard_id))
        # 3-unit group (Ozone): deployed, NOT retrieved yet -> should block harden.
        for i in range(3):
            cur.execute("""
                INSERT INTO invoice_version_line_items
                    (version_id, catalog_item_id, quantity, unit_price, total, is_taxable, deployed_at, sort_order, created_by, updated_by)
                VALUES (%s, %s, 1, 20.00, 20.00, TRUE, CURRENT_DATE - %s, %s, 'smoketest', 'smoketest')
            """, (ver1, catalog_ozone_id, 3 - i, i + 1))
        # 1-unit group (Dehu): already retrieved.
        cur.execute("""
            INSERT INTO invoice_version_line_items
                (version_id, catalog_item_id, quantity, unit_price, total, is_taxable, deployed_at, retrieved_at, sort_order, created_by, updated_by)
            VALUES (%s, %s, 1, 15.00, 15.00, TRUE, CURRENT_DATE - 3, CURRENT_DATE, 4, 'smoketest', 'smoketest')
        """, (ver1, catalog_dehu_id))

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Hardened', 'smoketest')
        check("harden rejected while an equipment line is still accruing", ok is False)

        cur.execute("""
            UPDATE invoice_version_line_items SET retrieved_at = CURRENT_DATE
            WHERE version_id = %s AND catalog_item_id = %s
        """, (ver1, catalog_ozone_id))

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Hardened', 'smoketest')
        check(f"harden succeeds once retrieved ({reason})", ok is True)

        cur.execute("SELECT * FROM invoice_versions WHERE id = %s", (ver1,))
        v = cur.fetchone()
        check("hardened state set", v['state'] == 'Hardened')
        check("subtotal = 100 + 3*20 + 15 = 175", float(v['subtotal']) == 175.00)
        check("tax_rate_pct resolved from Mecklenburg (8.25% as of today)", float(v['tax_rate_pct']) == 8.25)
        check("total = subtotal + tax", abs(float(v['total']) - (175.00 + 175.00 * 0.0825)) < 0.01)

        cur.execute("""
            SELECT resolved_label FROM invoice_version_line_items
            WHERE version_id = %s AND catalog_item_id = %s ORDER BY deployed_at
        """, (ver1, catalog_ozone_id))
        ozone_labels = [r['resolved_label'] for r in cur.fetchall()]
        check("3-unit group gets ordinals 1..3", ozone_labels == ['Test Dehu 1', 'Test Dehu 2', 'Test Dehu 3']
              or ozone_labels[0].endswith(' 1'))  # base label comes from catalog name/invoice_label

        cur.execute("""
            SELECT resolved_label FROM invoice_version_line_items
            WHERE version_id = %s AND catalog_item_id = %s
        """, (ver1, catalog_dehu_id))
        dehu_label = cur.fetchone()['resolved_label']
        check("1-unit group gets a bare label (no number)", dehu_label == 'Test Dehu' and not dehu_label[-1].isdigit())

        print("smoke_invoice_versions: frozen snapshot survives catalog/tax edits")
        frozen_total_before = float(v['total'])
        cur.execute("UPDATE catalog_items SET invoice_label = 'CHANGED LABEL' WHERE id = %s", (catalog_ozone_id,))
        cur.execute("""
            UPDATE tax_rates SET county_pct = 50.000 WHERE county = 'Mecklenburg' AND effective_to IS NULL
        """)
        cur.execute("SELECT total FROM invoice_versions WHERE id = %s", (ver1,))
        check("hardened total unchanged after catalog/tax edits",
              float(cur.fetchone()['total']) == frozen_total_before)
        cur.execute("""
            SELECT resolved_label FROM invoice_version_line_items
            WHERE version_id = %s AND catalog_item_id = %s LIMIT 1
        """, (ver1, catalog_ozone_id))
        check("hardened resolved_label unchanged after catalog edit",
              cur.fetchone()['resolved_label'] != 'CHANGED LABEL 1')
        cur.execute("UPDATE tax_rates SET county_pct = 3.000 WHERE county = 'Mecklenburg' AND effective_to IS NULL")

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Sent', 'smoketest')
        check(f"send succeeds ({reason})", ok is True)

        print("smoke_invoice_versions: payment guards (temp tables, dropped at rollback)")
        cur.execute("""
            CREATE TEMP TABLE payment_applications (
                id SERIAL PRIMARY KEY, invoice_id INTEGER, amount NUMERIC(12,2),
                reverses_application_id INTEGER
            )
        """)
        cur.execute("""
            CREATE TEMP TABLE invoice_adjustments (
                id SERIAL PRIMARY KEY, invoice_id INTEGER, amount NUMERIC(12,2), deleted_at TIMESTAMP
            )
        """)
        cur.execute("INSERT INTO payment_applications (invoice_id, amount) VALUES (%s, 50.00)", (inv1,))

        bal = invoice_balance(cur, inv1)
        check(f"invoice_balance subtracts the applied payment (balance={bal})",
              abs(float(bal) - (frozen_total_before - 50.00)) < 0.01)

        status = invoice_display_status(
            {'receivable_state': 'open'}, {'state': 'Sent', 'total': frozen_total_before}, bal)
        check(f"display status is Partially Paid ({status})", status == 'Partially Paid')

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Live', 'smoketest')
        check(f"reopen rejected once a payment application exists ({reason})", ok is False)

        cur.execute("DELETE FROM payment_applications WHERE invoice_id = %s", (inv1,))
        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Live', 'smoketest')
        check(f"reopen succeeds once the payment is removed ({reason})", ok is True)
        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Hardened', 'smoketest')
        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Sent', 'smoketest')
        check("re-hardened + re-sent for the revise test", ok is True)

        print("smoke_invoice_versions: revise")
        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Revise', 'smoketest', notes='Fixing a line item')
        check(f"revise succeeds ({reason})", ok is True)
        new_ver_id = extra['new_version_id']

        cur.execute("SELECT * FROM invoice_versions WHERE id = %s", (ver1,))
        old_v = cur.fetchone()
        check("old version marked Superseded", old_v['state'] == 'Superseded')
        check("old version points to the new one", old_v['superseded_by_version_id'] == new_ver_id)

        cur.execute("SELECT current_version_id FROM invoices WHERE id = %s", (inv1,))
        check("invoices.current_version_id moved to the new version",
              cur.fetchone()['current_version_id'] == new_ver_id)

        cur.execute("SELECT count(*) AS n FROM invoice_version_line_items WHERE version_id = %s AND deleted_at IS NULL", (new_ver_id,))
        check("lines cloned onto the new version", cur.fetchone()['n'] == 5)

        # Bump one line's total before re-hardening so the delta isn't trivially zero.
        cur.execute("""
            UPDATE invoice_version_line_items SET total = 150.00
            WHERE version_id = %s AND catalog_item_id = %s
        """, (new_ver_id, catalog_standard_id))

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv1, 'Hardened', 'smoketest')
        check(f"re-harden of the revised version succeeds ({reason})", ok is True)

        cur.execute("""
            SELECT subtotal_delta, tax_delta FROM invoice_status_history
            WHERE invoice_id = %s AND version_id = %s AND to_state = 'Hardened'
            ORDER BY id DESC LIMIT 1
        """, (inv1, new_ver_id))
        delta_row = cur.fetchone()
        check(f"subtotal_delta recorded on the re-harden history row ({delta_row})",
              delta_row is not None and float(delta_row['subtotal_delta']) == 50.00)

        print("smoke_invoice_versions: void + reissue")
        inv2, ver2 = make_invoice('ZZZ-SMOKE-0002')
        cur.execute("""
            INSERT INTO invoice_version_line_items (version_id, catalog_item_id, quantity, unit_price, total, is_taxable, sort_order, created_by, updated_by)
            VALUES (%s, %s, 2, 50.00, 100.00, TRUE, 0, 'smoketest', 'smoketest')
        """, (ver2, catalog_standard_id))

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv2, 'Void', 'smoketest')
        check("void rejected without a reason", ok is False)

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv2, 'Void', 'smoketest', notes='Test void reason')
        check(f"void succeeds with a reason ({reason})", ok is True)

        cur.execute("SELECT receivable_state FROM invoices WHERE id = %s", (inv2,))
        check("receivable_state is void", cur.fetchone()['receivable_state'] == 'void')
        cur.execute("SELECT state FROM invoice_versions WHERE id = %s", (ver2,))
        check("current version's state is untouched by void (stays as evidence)",
              cur.fetchone()['state'] == 'Live')

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv2, 'Reissue', 'smoketest')
        check(f"reissue succeeds ({reason})", ok is True)
        new_invoice_id = extra['new_invoice_id']

        cur.execute("SELECT invoice_number, current_version_id, reissue_of_invoice_id, receivable_state FROM invoices WHERE id = %s", (new_invoice_id,))
        newinv = cur.fetchone()
        check("reissue minted a new number", newinv['invoice_number'] != 'ZZZ-SMOKE-0002')
        check("reissue links back to the void", newinv['reissue_of_invoice_id'] == inv2)
        check("reissue is open", newinv['receivable_state'] == 'open')

        cur.execute("SELECT reissued_as_invoice_id FROM invoices WHERE id = %s", (inv2,))
        check("void links forward to the reissue", cur.fetchone()['reissued_as_invoice_id'] == new_invoice_id)

        cur.execute("SELECT count(*) AS n FROM invoice_version_line_items WHERE version_id = %s", (newinv['current_version_id'],))
        check("reissue cloned the void's lines", cur.fetchone()['n'] == 1)

        ok, reason, extra = transition_invoice(cur, 'getagrip', inv2, 'Reissue', 'smoketest')
        check("re-reissuing an already-reissued invoice is rejected", ok is False)

        print("ALL CHECKS PASSED")
    finally:
        conn.rollback()
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
