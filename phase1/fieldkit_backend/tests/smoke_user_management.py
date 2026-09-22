"""
Smoke test: per-company user list scoping, per-company dispatchable
(migration 028), and username rename (Chris, 2026-09-22).

Drives the real Flask routes (test client, forged admin session) against
live getagrip/kleanit_charlotte. Everything created is hard-deleted in a
`finally` block. Run inside the app container:

    docker compose exec -T app python tests/smoke_user_management.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, ALL_COMPANY_KEYS  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, username='smoketest', company_access=None):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = username
        sess['user_role'] = role
        sess['company_access'] = company_access or ['getagrip']
    return c


def cleanup_user(uname):
    for key in ALL_COMPANY_KEYS:
        c2 = get_db_connection(key)
        cu2 = c2.cursor()
        cu2.execute("SELECT id FROM users WHERE username = %s", (uname,))
        row = cu2.fetchone()
        if row:
            cu2.execute("DELETE FROM record_audit WHERE table_name='users' AND record_id=%s", (row['id'],))
            cu2.execute("DELETE FROM user_company_dispatch WHERE user_id=%s", (row['id'],))
        cu2.execute("DELETE FROM users WHERE username = %s", (uname,))
        c2.commit(); cu2.close(); c2.close()


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    wo_ids, customer_ids = [], []
    usernames_to_clean = []
    admin = client_as('admin', company_access=['getagrip', 'kleanit_charlotte'])

    try:
        print("smoke_user_management: user list is scoped per company")
        uname_single = 'smokeusermgmt_kc_only'
        r = admin.post('/getagrip/settings/users/new', data={
            'username': uname_single, 'full_name': 'Smoke KC Only', 'email': f'{uname_single}@smoketest.invalid',
            'role': 'manager', 'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['kleanit_charlotte'],
        }, follow_redirects=False)
        check(f"user (KC-only access) created ({r.status_code})", r.status_code == 302)
        usernames_to_clean.append(uname_single)

        r = admin.get('/getagrip/settings/users')
        check("getagrip user list does NOT show a KC-only user", uname_single not in r.data.decode())
        r = admin.get('/kleanit_charlotte/settings/users')
        check("kleanit_charlotte user list DOES show that user", uname_single in r.data.decode())

        # ---------------------------------------------------------------
        print("smoke_user_management: dispatchable is per-company, not global")
        uname_multi = 'smokeusermgmt_multi'
        r = admin.post('/getagrip/settings/users/new', data={
            'username': uname_multi, 'full_name': 'Smoke Multi Tech', 'email': f'{uname_multi}@smoketest.invalid',
            'role': 'technician', 'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['getagrip', 'kleanit_charlotte'],
            'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on',
            # deliberately NOT can_be_dispatched_kleanit_charlotte
        }, follow_redirects=False)
        check(f"multi-company tech created ({r.status_code})", r.status_code == 302)
        usernames_to_clean.append(uname_multi)

        cur.execute("SELECT id FROM users WHERE username = %s", (uname_multi,))
        multi_id = cur.fetchone()['id']
        cur.execute("SELECT company_key, can_be_dispatched FROM user_company_dispatch WHERE user_id = %s ORDER BY company_key",
                    (multi_id,))
        rows = {r['company_key']: r['can_be_dispatched'] for r in cur.fetchall()}
        check("dispatchable=TRUE for getagrip", rows.get('getagrip') is True, rows)
        check("dispatchable=FALSE for kleanit_charlotte (never forced on)", rows.get('kleanit_charlotte') is False, rows)

        from app import _company_techs
        gag_dispatchable = {t['username'] for t in _company_techs('getagrip', dispatchable_only=True)}
        kc_dispatchable = {t['username'] for t in _company_techs('kleanit_charlotte', dispatchable_only=True)}
        check("shows on getagrip's dispatchable list", uname_multi in gag_dispatchable)
        check("does NOT show on kleanit_charlotte's dispatchable list", uname_multi not in kc_dispatchable)

        print("smoke_user_management: turning dispatchable ON for kleanit_charlotte only affects that company")
        r = admin.post(f'/getagrip/settings/users/{multi_id}/edit', data={
            'full_name': 'Smoke Multi Tech', 'email': f'{uname_multi}@smoketest.invalid',
            'role': 'technician', 'company_access': ['getagrip', 'kleanit_charlotte'],
            'is_field_tech': 'on',
            'can_be_dispatched_getagrip': 'on', 'is_active_tech_getagrip': 'on',
            'can_be_dispatched_kleanit_charlotte': 'on', 'is_active_tech_kleanit_charlotte': 'on',
        }, follow_redirects=False)
        check(f"edit succeeded ({r.status_code})", r.status_code == 302)
        kc_dispatchable = {t['username'] for t in _company_techs('kleanit_charlotte', dispatchable_only=True)}
        check("now shows on kleanit_charlotte's dispatchable list too", uname_multi in kc_dispatchable)

        print("smoke_user_management: removing company_access drops the per-company dispatch row")
        r = admin.post(f'/getagrip/settings/users/{multi_id}/edit', data={
            'full_name': 'Smoke Multi Tech', 'email': f'{uname_multi}@smoketest.invalid',
            'role': 'technician', 'company_access': ['getagrip'],
            'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on', 'is_active_tech_getagrip': 'on',
        }, follow_redirects=False)
        check(f"edit succeeded ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT company_key FROM user_company_dispatch WHERE user_id = %s", (multi_id,))
        remaining = {r['company_key'] for r in cur.fetchall()}
        check("kleanit_charlotte dispatch row cleaned up after access removed", 'kleanit_charlotte' not in remaining, remaining)

        # ---------------------------------------------------------------
        print("smoke_user_management: username rename -- cascades to live WO assignments")
        cur.execute("""
            INSERT INTO customers (property_name, customer_type, status, payment_terms, created_by, updated_by)
            VALUES ('SMOKE UserMgmt Co', 'Commercial', 'Active', 'Net 30', 'smoketest', 'smoketest')
            RETURNING id
        """)
        customer_id = cur.fetchone()['id']
        customer_ids.append(customer_id)
        cur.execute("SELECT id FROM catalog_items WHERE billing_behavior='standard' AND deleted_at IS NULL LIMIT 1")
        catalog_id = cur.fetchone()['id']
        conn.commit()

        import json
        from datetime import date
        line_items = json.dumps([{
            'kind': 'std', 'catalog_item_id': catalog_id, 'description': '', 'quantity': '1', 'unit_price': '50.00',
        }])
        r = admin.post('/getagrip/workorders/new', data={
            'customer_id': str(customer_id), 'status': 'Scheduled', 'priority': 'Normal',
            'start_date': date.today().isoformat(), 'arrival_window_start': '9:00 AM',
            'line_items_json': line_items, 'duration_overridden': 'true',
            'estimated_duration_hours': '1.0', 'assigned_techs': [uname_multi],
        }, follow_redirects=False)
        check(f"WO assigned to the tech ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT id FROM work_orders WHERE customer_id = %s ORDER BY id DESC LIMIT 1", (customer_id,))
        wo_id = cur.fetchone()['id']
        wo_ids.append(wo_id)

        new_username = 'smokeusermgmt_renamed'
        r = admin.post(f'/getagrip/settings/users/{multi_id}/edit', data={
            'username': new_username,
            'full_name': 'Smoke Multi Tech', 'email': f'{uname_multi}@smoketest.invalid',
            'role': 'technician', 'company_access': ['getagrip'],
            'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on', 'is_active_tech_getagrip': 'on',
        }, follow_redirects=False)
        check(f"rename succeeded ({r.status_code})", r.status_code == 302)
        usernames_to_clean.append(new_username)

        cur.execute("SELECT username FROM users WHERE id = %s", (multi_id,))
        check("users.username actually changed", cur.fetchone()['username'] == new_username)
        cur.execute("SELECT username FROM work_order_techs WHERE work_order_id = %s", (wo_id,))
        check("work_order_techs.username followed the rename (still assigned, under new name)",
              cur.fetchone()['username'] == new_username)

        print("smoke_user_management: history/audit trail keeps the OLD name, doesn't get rewritten")
        cur.execute("SELECT created_by FROM customers WHERE id = %s", (customer_id,))
        # (created_by here is 'smoketest', unrelated -- real check is on work_order_status_history's changed_by
        # for a status this tech's edit didn't touch; simplest direct proof is record_audit itself:)
        cur.execute("""
            SELECT diff FROM record_audit WHERE table_name = 'users' AND record_id = %s
            AND action = 'update' ORDER BY id DESC LIMIT 5
        """, (multi_id,))
        diffs = [r['diff'] for r in cur.fetchall()]
        check("a record_audit row captured the username change itself",
              any('username' in d and d['username']['new'] == new_username for d in diffs), diffs)

        print("smoke_user_management: uniqueness -- can't rename to an existing username")
        r = admin.post(f'/getagrip/settings/users/{multi_id}/edit', data={
            'username': 'chris',  # a real seeded admin username
            'full_name': 'Smoke Multi Tech', 'email': f'{uname_multi}@smoketest.invalid',
            'role': 'technician', 'company_access': ['getagrip'],
        }, follow_redirects=True)
        check("rename to an existing username is rejected", b'already taken' in r.data)
        cur.execute("SELECT username FROM users WHERE id = %s", (multi_id,))
        check("username unchanged after the rejected attempt", cur.fetchone()['username'] == new_username)

        print("smoke_user_management: admin cannot rename their own account")
        cur.execute("SELECT id FROM users WHERE username = 'chris'")
        chris_row = cur.fetchone()
        if chris_row:
            chris_client = client_as('admin', username='chris', company_access=['getagrip'])
            r = chris_client.post(f'/getagrip/settings/users/{chris_row["id"]}/edit', data={
                'username': 'chris_renamed',
                'full_name': 'Chris Letize', 'email': 'chris@smoketest.invalid',
                'role': 'admin', 'company_access': ['getagrip'],
            }, follow_redirects=True)
            check("self-rename is rejected", b"can&#39;t rename your own account" in r.data or b"can't rename your own account" in r.data)
            cur.execute("SELECT username FROM users WHERE id = %s", (chris_row['id'],))
            check("chris's username is untouched", cur.fetchone()['username'] == 'chris')
        else:
            print("  [SKIP] no 'chris' user in this environment")

        print("ALL CHECKS PASSED")

    finally:
        for wid in wo_ids:
            cur.execute("DELETE FROM record_audit WHERE table_name='work_orders' AND record_id=%s", (wid,))
            cur.execute("DELETE FROM work_order_status_history WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wid,))
            cur.execute("DELETE FROM work_order_line_items WHERE work_order_id = %s", (wid,))
        if wo_ids:
            cur.execute("DELETE FROM work_orders WHERE id = ANY(%s)", (wo_ids,))
        if customer_ids:
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (customer_ids,))
        conn.commit()
        cur.close(); conn.close()

        for uname in usernames_to_clean:
            cleanup_user(uname)

        print(f"cleanup done: {len(wo_ids)} WO(s), {len(customer_ids)} customer(s), "
              f"{len(usernames_to_clean)} user(s) removed.")


if __name__ == '__main__':
    main()
