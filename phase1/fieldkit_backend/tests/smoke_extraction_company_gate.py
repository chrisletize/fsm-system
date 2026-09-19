"""
Smoke test: extraction feature gating — Get a Grip does not do water
extraction work (Chris, 2026-09-19) and should have no trace of it: the
queue routes 404, the nav link is absent, and the WO form has neither the
Water Extraction card nor the "Deploy Equipment" line-item option. The
other three companies are unaffected.

No fixtures are created (this test only reads rendered pages/route status),
so there is nothing to clean up. Run inside the app container:

    docker compose exec -T app python tests/smoke_extraction_company_gate.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, COMPANIES_WITHOUT_EXTRACTION  # noqa: E402


def check(label, condition, extra=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label} {extra}")
    if not condition:
        raise AssertionError(f"{label} {extra}")


def main():
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['username'] = 'smoketest'
        sess['user_role'] = 'admin'
        sess['company_access'] = ['getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf']

    check("COMPANIES_WITHOUT_EXTRACTION is exactly {'getagrip'}", COMPANIES_WITHOUT_EXTRACTION == {'getagrip'})

    print("smoke_extraction_company_gate: getagrip — routes gone, UI gone")
    for path in ('/getagrip/extraction', '/getagrip/extraction/log-all',
                 '/getagrip/extraction/pickup-list.pdf'):
        method = client.post if path.endswith('log-all') else client.get
        r = method(path)
        check(f"{path} -> 404 ({r.status_code})", r.status_code == 404)

    r = client.get('/getagrip/dispatch')
    check(f"dispatch renders ({r.status_code})", r.status_code == 200)
    check("no href to /getagrip/extraction in the nav", b'/getagrip/extraction' not in r.data)

    r = client.get('/getagrip/workorders/new')
    check(f"new-WO form renders ({r.status_code})", r.status_code == 200)
    check("no Water Extraction card", b'<h2>Water Extraction</h2>' not in r.data)
    check("no Deploy Equipment button", b'Deploy Equipment' not in r.data)
    check("no chkExtraction checkbox in the DOM", r.data.count(b'id="chkExtraction"') == 0)

    print("smoke_extraction_company_gate: the other three companies are unaffected")
    for company in ('kleanit_charlotte', 'cts', 'kleanit_sf'):
        r = client.get(f'/{company}/extraction')
        check(f"{company}/extraction -> 200 ({r.status_code})", r.status_code == 200)

        r = client.get(f'/{company}/dispatch')
        check(f"{company} dispatch nav still links to extraction",
              f'/{company}/extraction'.encode() in r.data)

        r = client.get(f'/{company}/workorders/new')
        check(f"{company} WO form still has the Water Extraction card",
              b'<h2>Water Extraction</h2>' in r.data)
        check(f"{company} WO form still has Deploy Equipment",
              b'Deploy Equipment' in r.data)

    print("smoke_extraction_company_gate: getagrip's two Ozone catalog items are deactivated")
    from app import get_db_connection
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, is_active FROM catalog_items
        WHERE billing_behavior = 'per_day_equipment'
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    check(f"both Ozone items exist and are inactive ({[(r['name'], r['is_active']) for r in rows]})",
          len(rows) == 2 and all(r['is_active'] is False for r in rows))

    print("ALL CHECKS PASSED")


if __name__ == '__main__':
    main()
