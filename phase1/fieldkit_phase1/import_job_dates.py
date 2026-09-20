#!/usr/bin/env python3
"""
FieldKit: Recency history import (customer_job_dates)
Directive Stage 3, Increment 3.3.

Reads the Phase 0 statements stack's customer_job_dates + customers (the
pre-cutover ServiceFusion job history the recency report unions in for
customers with no FieldKit work order yet), matches each statements customer
to a FieldKit customer by normalized property_name WITHIN the corresponding
company's database, and inserts matched job dates with
source='servicefusion_import'. Never creates a FieldKit customer — an
unmatched statements customer is logged to a CSV for Chris/Michele to
resolve by hand.

Network note: statements-db-1 and the FieldKit app container are on separate
Docker networks (separate docker-compose projects, no published host port on
either database) — this script must run from something that can reach BOTH.
Bridge them for the run, then disconnect:

    docker network connect statements_default fieldkit-prod-app-1
    docker compose exec -T app python phase1/fieldkit_phase1/import_job_dates.py --dry-run
    docker network disconnect statements_default fieldkit-prod-app-1

DRY RUN IS THE DEFAULT AND, per Chris (2026-09-19), THE ONLY MODE TO ACTUALLY
RUN RIGHT NOW — imports are on hold until the site is ready for day-to-day
testing (see docs/DECISIONS-MADE-DURING-BUILD.md D-038/D-065-era notes). Pass
--commit only when Chris has reviewed the dry-run counts and says to proceed.
"""
import sys
import os
import re
import csv
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor

STATEMENTS_DB = dict(dbname='fsm_prod', user='fsm_user', password='FieldKit2026!Prod',
                      host='statements-db-1', port=5432)

FIELDKIT_DB_HOST = 'db'
FIELDKIT_DB_USER = 'fieldkit'
FIELDKIT_DB_CONFIG = {
    'getagrip':          'fieldkit_getagrip',
    'kleanit_charlotte': 'fieldkit_kleanit_charlotte',
    'cts':               'fieldkit_cts',
    'kleanit_sf':        'fieldkit_kleanit_sf',
}

# Phase 0 statements companies.id -> FieldKit company_key (confirmed 2026-09-19:
# 1=Kleanit Charlotte, 2=Get a Grip Resurfacing of Charlotte, 3=CTS of Raleigh,
# 4=Kleanit South Florida).
STATEMENTS_COMPANY_TO_FIELDKIT = {
    1: 'kleanit_charlotte',
    2: 'getagrip',
    3: 'cts',
    4: 'kleanit_sf',
}


def normalize_name(name):
    """Lowercase, collapse whitespace, strip common punctuation. Exact-match
    only after normalization — no fuzzy matching, per the directive's own
    'log unmatched... do not create customers' instruction (same discipline
    as Increment 1.9's cutover import design)."""
    if not name:
        return ''
    s = name.strip().lower()
    s = re.sub(r"[.,'\"]", '', s)
    s = re.sub(r'\s+', ' ', s)
    return s


def connect_fieldkit(company_key, password):
    return psycopg2.connect(
        dbname=FIELDKIT_DB_CONFIG[company_key], user=FIELDKIT_DB_USER, password=password,
        host=FIELDKIT_DB_HOST, port=5432, cursor_factory=RealDictCursor,
    )


def connect_statements():
    return psycopg2.connect(**STATEMENTS_DB, cursor_factory=RealDictCursor)


def run(dry_run, fieldkit_password, out_dir):
    stmt_conn = connect_statements()
    stmt_cur = stmt_conn.cursor()
    stmt_cur.execute("""
        SELECT cjd.customer_id, c.customer_name, c.company_id, cjd.job_date
        FROM customer_job_dates cjd JOIN customers c ON c.id = cjd.customer_id
    """)
    stmt_rows = stmt_cur.fetchall()
    stmt_cur.close(); stmt_conn.close()

    by_company = {}
    for row in stmt_rows:
        by_company.setdefault(row['company_id'], {}).setdefault(row['customer_name'], []).append(row['job_date'])

    print(f"Statements DB: {len(stmt_rows)} customer_job_dates rows across {len(by_company)} compan(y/ies).\n")

    grand_matched_customers = grand_inserted_dates = grand_unmatched = 0
    for stmt_company_id, customer_dates in by_company.items():
        company_key = STATEMENTS_COMPANY_TO_FIELDKIT.get(stmt_company_id)
        if not company_key:
            print(f"  Skipping unknown statements company_id={stmt_company_id}")
            continue

        fk_conn = connect_fieldkit(company_key, fieldkit_password)
        fk_cur = fk_conn.cursor()
        fk_cur.execute("SELECT id, property_name FROM customers WHERE deleted_at IS NULL")
        fk_by_name = {normalize_name(r['property_name']): r['id'] for r in fk_cur.fetchall()}

        matched_customers = inserted_dates = 0
        unmatched = []
        for stmt_name, dates in customer_dates.items():
            fk_id = fk_by_name.get(normalize_name(stmt_name))
            if fk_id is None:
                unmatched.append((stmt_name, len(dates)))
                continue
            matched_customers += 1
            for d in dates:
                if dry_run:
                    inserted_dates += 1
                else:
                    fk_cur.execute("""
                        INSERT INTO customer_job_dates (customer_id, job_date, source, created_by)
                        VALUES (%s, %s, 'servicefusion_import', 'import_job_dates.py')
                        ON CONFLICT (customer_id, job_date) DO NOTHING
                        RETURNING id
                    """, (fk_id, d))
                    if fk_cur.fetchone():
                        inserted_dates += 1

        if not dry_run:
            fk_conn.commit()
        fk_cur.close(); fk_conn.close()

        print(f"[{company_key}] {matched_customers} customer(s) matched, "
              f"{inserted_dates} job date row(s) {'would be inserted' if dry_run else 'inserted'}, "
              f"{len(unmatched)} unmatched customer name(s).")
        grand_matched_customers += matched_customers
        grand_inserted_dates += inserted_dates
        grand_unmatched += len(unmatched)

        if unmatched:
            path = os.path.join(out_dir, f'unmatched_job_dates_{company_key}.csv')
            with open(path, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['statements_customer_name', 'job_date_count'])
                for name, count in sorted(unmatched, key=lambda x: -x[1]):
                    w.writerow([name, count])
            print(f"    Unmatched names logged to {path}")

    print(f"\nTOTAL: {grand_matched_customers} customer(s) matched, "
          f"{grand_inserted_dates} job date row(s) {'would be inserted' if dry_run else 'inserted'}, "
          f"{grand_unmatched} unmatched customer name(s).")
    if dry_run:
        print("\nDRY RUN — nothing was written. Re-run with --commit once Chris has reviewed these counts.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', action='store_true',
                         help='Actually write the import. Without this flag, runs as a dry run (default).')
    parser.add_argument('--out-dir', default='/tmp', help='Where to write unmatched-name CSVs (default /tmp).')
    args = parser.parse_args()

    fk_password = os.environ.get('DB_PASSWORD') or os.environ.get('FIELDKIT_DB_PASSWORD')
    if not fk_password:
        print("Set DB_PASSWORD (or FIELDKIT_DB_PASSWORD) in the environment before running.", file=sys.stderr)
        sys.exit(1)

    run(dry_run=not args.commit, fieldkit_password=fk_password, out_dir=args.out_dir)
