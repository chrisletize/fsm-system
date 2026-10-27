"""
Smoke test: customer categories (D-119, Chris 2026-10-27).

  * Each company offers its own categories: the Kleanits use Resident Pays
    instead of Residential, Get a Grip uses Residential only, CTS both.
  * The audit's name rules sort people, properties and contractors, and map
    the proposal onto the company's categories.
  * apply_company changes confident proposals (with an audit row) and queues
    low ones; the review page accepts, corrects or keeps them, admin/manager only.

Uses three throwaway kleanit_charlotte customers, hard-deleted in `finally`.
Run inside the app container:

    docker compose exec -T app python tests/smoke_customer_categories.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import (get_db_connection, app, customer_types_for, normalize_customer_type,  # noqa: E402
                 _record_audit)
import customer_category_audit as audit  # noqa: E402

CK = 'kleanit_charlotte'


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def login(client, role):
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['full_name'] = 'Smoke Test'
        sess['user_role'] = role
        sess['company_access'] = [CK]


def main():
    print("smoke_customer_categories: per-company category lists")
    check("Kleanit: Resident Pays, no Residential",
          'Resident Pays' in customer_types_for(CK) and 'Residential' not in customer_types_for(CK))
    check("Get a Grip: Residential, no Resident Pays",
          'Residential' in customer_types_for('getagrip') and 'Resident Pays' not in customer_types_for('getagrip'))
    check("CTS: both", {'Residential', 'Resident Pays'} <= set(customer_types_for('cts')))
    check("Residential -> Resident Pays at Kleanit", normalize_customer_type(CK, 'Residential') == 'Resident Pays')
    check("Resident Pays -> Residential at Get a Grip",
          normalize_customer_type('getagrip', 'Resident Pays') == 'Residential')
    check("unknown value -> default", normalize_customer_type(CK, 'Bogus') == 'Multi Family')

    print("smoke_customer_categories: name rules and mapping")
    for name, kind in [('Willow Creek Apartments', 'property'), ('Linda Hall', 'person'),
                       ('Smith Construction LLC', 'contractor'), ('The Vue at Ballantyne', 'property')]:
        got = audit.name_kind(name)[0]
        check(f"name_kind({name!r}) = {kind}", got == kind, got)
    kl, cts = customer_types_for(CK), customer_types_for('cts')
    check("Kleanit homeowner -> Resident Pays", audit.company_type(kl, 'Residential', 'homeowner') == 'Resident Pays')
    check("CTS tenant -> Resident Pays", audit.company_type(cts, 'Residential', 'resident pays') == 'Resident Pays')
    check("CTS homeowner -> Residential", audit.company_type(cts, 'Residential', 'homeowner') == 'Residential')
    check("non-individual untouched", audit.company_type(kl, 'Contractors', '') == 'Contractors')

    conn = get_db_connection(CK)
    cur = conn.cursor()
    ids = []
    try:
        for name, ctype in [('Zzsmoke Brookfield Apartments', 'Multi Family'),
                            ('Margaret Zzsmoketest', 'Multi Family'),
                            ('Zzsmoke Quintessa', 'Multi Family')]:
            cur.execute("""INSERT INTO customers (property_name, customer_type, status, address, city, state, zip,
                                                  created_by, updated_by)
                           VALUES (%s, %s, 'Active', '1 Zzsmoke Way Apt 4', 'Charlotte', 'NC', '28202',
                                   'smoketest', 'smoketest') RETURNING id""", (name, ctype))
            ids.append(cur.fetchone()['id'])
        conn.commit()

        print("smoke_customer_categories: apply changes confident rows, queues low ones")
        rows = [r for r in audit.classify_company(conn, CK, kl) if r['id'] in ids]
        by_id = {r['id']: r for r in rows}
        check("person in a unit -> Resident Pays", by_id[ids[1]]['proposed'] == 'Resident Pays', by_id[ids[1]])
        check("property name stays Multi Family", not by_id[ids[0]]['changes'], by_id[ids[0]])
        # Force the third into the low-confidence queue regardless of the rules.
        by_id[ids[2]].update(proposed='Commercial', confidence='low', changes=True, reasons='smoke')
        changed, queued = audit.apply_company(conn, CK, rows, _record_audit)
        cur.execute("SELECT id, customer_type, updated_by FROM customers WHERE id = ANY(%s)", (ids,))
        live = {r['id']: r for r in cur.fetchall()}
        check("person re-filed", live[ids[1]]['customer_type'] == 'Resident Pays' and
              live[ids[1]]['updated_by'] == audit.APPLIED_BY, live[ids[1]])
        cur.execute("SELECT count(*) AS n FROM record_audit WHERE table_name='customers' AND record_id=%s"
                    " AND changed_by=%s", (ids[1], audit.APPLIED_BY))
        check("audit row written", cur.fetchone()['n'] == 1)
        cur.execute("SELECT id FROM customer_category_reviews WHERE customer_id=%s AND status='pending'", (ids[2],))
        review = cur.fetchone()
        check("low proposal queued", review is not None and queued >= 1)
        changed2, queued2 = audit.apply_company(conn, CK, rows, _record_audit)
        check("re-run queues nothing twice", queued2 == 0, (changed2, queued2))

        print("smoke_customer_categories: review page")
        client = app.test_client()
        login(client, 'salesperson')
        r = client.get(f'/{CK}/settings/customer-categories')
        check(f"salesperson blocked ({r.status_code})", r.status_code in (302, 403))
        login(client, 'manager')
        r = client.get(f'/{CK}/settings/customer-categories')
        body = r.get_data(as_text=True)
        check(f"manager sees the page ({r.status_code})", r.status_code == 200 and 'Zzsmoke Quintessa' in body)
        check("dropdown offers Resident Pays, not Residential",
              '>Resident Pays<' in body and '>Residential<' not in body)
        r = client.post(f"/{CK}/settings/customer-categories/{review['id']}",
                        data={'action': 'save', 'customer_type': 'Residential'})
        check(f"category not offered here refused ({r.status_code})", r.status_code == 400)
        r = client.post(f"/{CK}/settings/customer-categories/{review['id']}",
                        data={'action': 'save', 'customer_type': 'Contractors'})
        check(f"save redirects ({r.status_code})", r.status_code == 302)
        cur.execute("SELECT customer_type FROM customers WHERE id=%s", (ids[2],))
        check("customer changed", cur.fetchone()['customer_type'] == 'Contractors')
        cur.execute("SELECT status, decided_type, decided_by FROM customer_category_reviews WHERE id=%s",
                    (review['id'],))
        rv = cur.fetchone()
        check("review marked changed", rv['status'] == 'changed' and rv['decided_type'] == 'Contractors'
              and rv['decided_by'] == 'smoketest', rv)
        changed3, queued3 = audit.apply_company(conn, CK, rows, _record_audit)
        cur.execute("SELECT customer_type FROM customers WHERE id=%s", (ids[2],))
        check("apply leaves a decided customer alone", cur.fetchone()['customer_type'] == 'Contractors')

        print("smoke_customer_categories: forms use the company's list")
        login(client, 'admin')
        body = client.get(f'/{CK}/customers/new').get_data(as_text=True)
        check("Kleanit new-customer form: Resident Pays, no Residential",
              'Resident Pays' in body and 'value="Residential"' not in body)
        with client.session_transaction() as sess:
            sess['company_access'] = ['getagrip']
        body = client.get('/getagrip/customers/new').get_data(as_text=True)
        check("Get a Grip new-customer form: Residential, no Resident Pays",
              'value="Residential"' in body and 'Resident Pays' not in body)
        body = client.get('/getagrip/settings').get_data(as_text=True)
        check("settings landing links the page", '/settings/customer-categories' in body)

        print("ALL CHECKS PASSED")
    finally:
        conn.rollback()
        if ids:
            cur.execute("DELETE FROM customer_category_reviews WHERE customer_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM record_audit WHERE table_name='customers' AND record_id = ANY(%s)", (ids,))
            cur.execute("DELETE FROM customers WHERE id = ANY(%s)", (ids,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"cleanup done: {len(ids)} customer(s) removed.")


if __name__ == '__main__':
    main()
