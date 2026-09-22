"""
Smoke test: an admin/manager marked "Field tech" shows up on the dispatch
board (Chris, 2026-09-22) -- _company_techs() used to hard-require
role='technician', so the "Field tech" checkbox silently did nothing for
any other role. Real-world trigger: Chris himself (role=admin,
is_field_tech=true) was invisible on the getagrip dispatch board.

Drives the real Flask routes/helpers (test client, forged admin session)
against live getagrip. Everything created is hard-deleted in a `finally`
block. Run inside the app container:

    docker compose exec -T app python tests/smoke_field_tech_dispatch.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection, app, _company_techs, ALL_COMPANY_KEYS  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def client_as(role, username='smoketest'):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = username
        sess['user_role'] = role
        sess['company_access'] = ['getagrip']
    return c


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    usernames = []
    admin = client_as('admin')

    try:
        print("smoke_field_tech_dispatch: an admin marked Field tech now appears in _company_techs()")
        uname = 'smokefieldadmin'
        r = admin.post('/getagrip/settings/users/new', data={
            'username': uname, 'full_name': 'Smoke Field Admin', 'email': f'{uname}@smoketest.invalid',
            'role': 'admin', 'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['getagrip'], 'is_field_tech': 'on', 'can_be_dispatched_getagrip': 'on',
        }, follow_redirects=False)
        check(f"field-tech admin created ({r.status_code})", r.status_code == 302)
        usernames.append(uname)

        techs = {t['username'] for t in _company_techs('getagrip')}
        check("appears in the full tech list (not just role='technician')", uname in techs, techs)

        dispatchable = {t['username'] for t in _company_techs('getagrip', dispatchable_only=True)}
        check("appears in the dispatchable-only list too", uname in dispatchable, dispatchable)

        print("smoke_field_tech_dispatch: dispatch board's tech rows include them")
        from datetime import date
        r = admin.get(f"/getagrip/dispatch/data?date={date.today().isoformat()}")
        check(f"dispatch data 200 ({r.status_code})", r.status_code == 200)
        row_usernames = {row['username'] for row in r.get_json()['techs']}
        check("field-tech admin has a row on the dispatch board", uname in row_usernames, row_usernames)

        print("smoke_field_tech_dispatch: an admin WITHOUT is_field_tech does NOT appear")
        uname2 = 'smokeofficeadmin'
        r = admin.post('/getagrip/settings/users/new', data={
            'username': uname2, 'full_name': 'Smoke Office Admin', 'email': f'{uname2}@smoketest.invalid',
            'role': 'admin', 'password': 'testpass123', 'confirm_password': 'testpass123',
            'company_access': ['getagrip'],
        }, follow_redirects=False)
        check(f"office-only admin created ({r.status_code})", r.status_code == 302)
        usernames.append(uname2)
        techs = {t['username'] for t in _company_techs('getagrip')}
        check("office-only admin does NOT appear", uname2 not in techs)

        print("smoke_field_tech_dispatch: an inactive field-tech admin is excluded (is_active still gates)")
        cur.execute("UPDATE users SET is_active = FALSE WHERE username = %s", (uname,))
        conn.commit()
        techs = {t['username'] for t in _company_techs('getagrip')}
        check("deactivated field-tech admin drops off the list", uname not in techs)
        cur.execute("UPDATE users SET is_active = TRUE WHERE username = %s", (uname,))
        conn.commit()

        print("ALL CHECKS PASSED")

    finally:
        for uname in usernames:
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
        cur.close(); conn.close()
        print(f"cleanup done: {len(usernames)} user(s) removed.")


if __name__ == '__main__':
    main()
