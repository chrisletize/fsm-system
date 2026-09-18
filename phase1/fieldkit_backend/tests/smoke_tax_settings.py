"""
Smoke test: Increment 1.1 — effective-dated tax rates + company_settings.

Runs inside a single transaction against fieldkit_getagrip and ROLLBACKs at the
end — nothing here is left behind. Run inside the app container:

    docker compose exec -T app python tests/smoke_tax_settings.py

Per the build directive's working protocol (§1.3), this file is part of the
regression suite and should be re-run before every stage commit.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import get_db_connection  # noqa: E402


def check(label, condition):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        raise AssertionError(label)


def main():
    conn = get_db_connection('getagrip')
    cur = conn.cursor()
    try:
        print("smoke_tax_settings: tax_rates effective-dating")

        # Schema: the new columns and constraint exist.
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tax_rates' AND column_name IN ('effective_from', 'effective_to')
        """)
        cols = {r['column_name'] for r in cur.fetchall()}
        check("tax_rates has effective_from and effective_to columns",
              cols == {'effective_from', 'effective_to'})

        cur.execute("""
            SELECT conname FROM pg_constraint WHERE conname = 'tax_rates_county_effective_from_key'
        """)
        check("UNIQUE(county, effective_from) constraint exists", cur.fetchone() is not None)

        cur.execute("""
            SELECT conname FROM pg_constraint WHERE conname = 'tax_rates_county_key'
        """)
        check("old UNIQUE(county) constraint is gone", cur.fetchone() is None)

        # Mecklenburg: two contiguous, non-overlapping rows.
        cur.execute("""
            SELECT state_pct, county_pct, transit_pct, total_pct, effective_from, effective_to, is_active
            FROM tax_rates WHERE county = 'Mecklenburg' ORDER BY effective_from
        """)
        meck = cur.fetchall()
        check("Mecklenburg has exactly 2 rows", len(meck) == 2)
        old, new = meck[0], meck[1]
        check("old Mecklenburg row is 7.25% ending 2026-06-30, inactive",
              float(old['total_pct']) == 7.25 and str(old['effective_to']) == '2026-06-30'
              and old['is_active'] is False)
        check("current Mecklenburg row is 8.25% starting 2026-07-01, open-ended, active",
              float(new['total_pct']) == 8.25 and new['effective_to'] is None
              and str(new['effective_from']) == '2026-07-01' and new['is_active'] is True)

        # Effective-date resolution (the same query _tax_rate_as_of uses).
        def rate_as_of(as_of):
            cur.execute("""
                SELECT total_pct FROM tax_rates
                WHERE county = 'Mecklenburg' AND deleted_at IS NULL
                  AND effective_from <= %s AND (effective_to IS NULL OR effective_to >= %s)
            """, (as_of, as_of))
            row = cur.fetchone()
            return float(row['total_pct']) if row else None

        check("rate on 2026-06-15 resolves to 7.25%", rate_as_of('2026-06-15') == 7.25)
        check("rate on 2026-07-01 resolves to 8.25%", rate_as_of('2026-07-01') == 8.25)
        check("rate on 2026-09-18 (today) resolves to 8.25%", rate_as_of('2026-09-18') == 8.25)

        # UNIQUE(county, effective_from) actually blocks a duplicate.
        cur.execute("SAVEPOINT dupe_check")
        dupe_blocked = False
        try:
            cur.execute("""
                INSERT INTO tax_rates (county, state_pct, county_pct, transit_pct, effective_from)
                VALUES ('Mecklenburg', 4.750, 3.000, 0.500, '2026-07-01')
            """)
        except Exception:
            dupe_blocked = True
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT dupe_check")
        check("duplicate (county, effective_from) is rejected", dupe_blocked)

        print("smoke_tax_settings: company_settings")

        cur.execute("SELECT count(*) AS n FROM company_settings WHERE deleted_at IS NULL")
        check("exactly one company_settings row", cur.fetchone()['n'] == 1)

        cur.execute("SELECT company_name, tax_exempt_by_default FROM company_settings WHERE deleted_at IS NULL")
        row = cur.fetchone()
        check("company_name seeded from COMPANY_BRANDING", row['company_name'] == 'Get a Grip Charlotte')
        check("getagrip is not tax-exempt by default", row['tax_exempt_by_default'] is False)

        # Singleton index actually blocks a second row.
        cur.execute("SAVEPOINT singleton_check")
        second_row_blocked = False
        try:
            cur.execute("INSERT INTO company_settings (company_name) VALUES ('Should Not Insert')")
        except Exception:
            second_row_blocked = True
        finally:
            cur.execute("ROLLBACK TO SAVEPOINT singleton_check")
        check("a second company_settings row is rejected", second_row_blocked)

        print("ALL CHECKS PASSED")
    finally:
        conn.rollback()
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
