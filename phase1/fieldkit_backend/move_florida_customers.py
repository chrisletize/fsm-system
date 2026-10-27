"""
Move customers with a Florida address into Kleanit South Florida (Chris,
2026-10-27, D-120).

The ServiceFusion import put ~395 Florida customers into Kleanit Charlotte and
Get a Grip. Each is copied into fieldkit_kleanit_sf -- the customer row, its
active contacts and service locations, and its notes -- with a note on both
sides saying where it went, and the original is soft-deleted (deleted_by =
'florida_move'). Audit rows are written in both databases.

Refuses (skips, and says so) any customer that has history which would have to
move with it -- a row in any other table with a foreign key to customers (work
orders, invoices, payments, estimates, ...) -- or a management company: those
need a person to decide, not a script. Customer flags and ratings are not
copied; the nightly jobs recompute them (a rating with a manager adjustment
blocks the move). Pending category reviews at the source are retired; the
category audit re-queues them at Kleanit SF if still needed.

Run inside the app container, after a backup:
    docker compose exec -T app python move_florida_customers.py           # dry run
    docker compose exec -T app python move_florida_customers.py --commit
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import get_db_connection, normalize_customer_type, _record_audit, DB_CONFIG  # noqa: E402

DEST = 'kleanit_sf'
SOURCES = ('kleanit_charlotte', 'getagrip', 'cts')
MOVED_BY = 'florida_move'
FLORIDA_SQL = "(upper(coalesce(c.state, '')) = 'FL' OR left(coalesce(c.zip, ''), 2) IN ('32', '33', '34'))"
# Tables referencing customers that move with it, or don't need to.
HANDLED = {'customers', 'customer_contacts', 'service_locations', 'customer_notes',
           'customer_flags', 'customer_ratings', 'customer_category_reviews'}
COMPANY_NAMES = {'kleanit_charlotte': 'Kleanit Charlotte', 'getagrip': 'Get a Grip',
                 'cts': 'CTS', 'kleanit_sf': 'Kleanit South Florida'}


def _columns(cur, table):
    cur.execute("""SELECT column_name FROM information_schema.columns
                   WHERE table_name = %s AND table_schema = 'public' ORDER BY ordinal_position""", (table,))
    return [r['column_name'] for r in cur.fetchall()]


def _copy_row(dst_cur, table, row, columns, overrides):
    """Insert `row` into `table` at the destination with a new id. Returns the new row."""
    cols = [c for c in columns if c != 'id' and c in row]
    vals = [overrides.get(c, row[c]) for c in cols]
    dst_cur.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) RETURNING *",
                    vals)
    return dst_cur.fetchone()


def florida_customers(cur):
    cur.execute(f"SELECT c.* FROM customers c WHERE c.deleted_at IS NULL AND {FLORIDA_SQL} ORDER BY c.id")
    return cur.fetchall()


def blocking_fks(cur):
    """(table, column) for every foreign key to customers this script doesn't move."""
    cur.execute("""
        SELECT kcu.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'customers'
        ORDER BY 1, 2
    """)
    return [(r['table_name'], r['column_name']) for r in cur.fetchall() if r['table_name'] not in HANDLED]


def blockers(cur, customer, fks):
    out = []
    for t, col in fks:
        cur.execute(f"SELECT count(*) AS n FROM {t} WHERE {col} = %s", (customer['id'],))
        n = cur.fetchone()['n']
        if n:
            out.append(f'{n} {t}')
    cur.execute("SELECT 1 FROM customer_ratings WHERE customer_id = %s AND manager_adjustment IS NOT NULL",
                (customer['id'],))
    if cur.fetchone():
        out.append('a manager-adjusted rating')
    if customer['management_company_id']:
        out.append('a management company')
    return out


def move_customer(src_key, src_cur, dst_cur, customer, cols):
    """Copy one customer and its contacts/locations/notes; soft-delete the original.
    Returns (new customer id, contacts copied, locations copied)."""
    new = _copy_row(dst_cur, 'customers', customer, cols['customers'], {
        'customer_type': normalize_customer_type(DEST, customer['customer_type']),
        'merged_into_customer_id': None, 'updated_at': None, 'updated_by': MOVED_BY})
    dst_cur.execute("UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING *", (new['id'],))
    new = dst_cur.fetchone()
    _record_audit(dst_cur, 'customers', new['id'], 'create', after=new, changed_by=MOVED_BY)

    n_contacts = n_locations = 0
    for table in ('customer_contacts', 'service_locations'):
        src_cur.execute(f"SELECT * FROM {table} WHERE customer_id = %s AND deleted_at IS NULL ORDER BY id",
                        (customer['id'],))
        for row in src_cur.fetchall():
            _copy_row(dst_cur, table, row, cols[table], {'customer_id': new['id']})
            if table == 'customer_contacts':
                n_contacts += 1
            else:
                n_locations += 1
    src_cur.execute("SELECT * FROM customer_notes WHERE customer_id = %s ORDER BY id", (customer['id'],))
    for row in src_cur.fetchall():
        _copy_row(dst_cur, 'customer_notes', row, cols['customer_notes'], {'customer_id': new['id']})

    dst_cur.execute("""INSERT INTO customer_notes (customer_id, note_text, note_type, created_by)
                       VALUES (%s, %s, 'General', %s)""",
                    (new['id'], f"Moved here from {COMPANY_NAMES[src_key]} (customer #{customer['id']}): "
                                f"Florida address.", MOVED_BY))
    src_cur.execute("""INSERT INTO customer_notes (customer_id, note_text, note_type, created_by)
                       VALUES (%s, %s, 'General', %s)""",
                    (customer['id'], f"Moved to Kleanit South Florida (customer #{new['id']}): Florida address.",
                     MOVED_BY))
    src_cur.execute("""UPDATE customers SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s,
                              updated_at = CURRENT_TIMESTAMP, updated_by = %s
                       WHERE id = %s RETURNING *""", (MOVED_BY, MOVED_BY, customer['id']))
    _record_audit(src_cur, 'customers', customer['id'], 'delete', before=customer, changed_by=MOVED_BY)
    src_cur.execute("""UPDATE customer_category_reviews SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
                       WHERE customer_id = %s AND status = 'pending' AND deleted_at IS NULL""",
                    (MOVED_BY, customer['id']))
    return new['id'], n_contacts, n_locations


def main(commit):
    dst = get_db_connection(DEST)
    dst_cur = dst.cursor()
    cols = {t: _columns(dst_cur, t) for t in ('customers', 'customer_contacts', 'service_locations',
                                              'customer_notes')}
    totals = {'moved': 0, 'skipped': 0, 'contacts': 0, 'locations': 0}
    for src_key in SOURCES:
        assert src_key in DB_CONFIG and src_key != DEST
        src = get_db_connection(src_key)
        src_cur = src.cursor()
        rows = florida_customers(src_cur)
        fks = blocking_fks(src_cur)
        print(f"\n=== {src_key}: {len(rows)} customers with a Florida address")
        moved = []
        try:
            for c in rows:
                why = blockers(src_cur, c, fks)
                if why:
                    print(f"  SKIP #{c['id']} {c['property_name']}: has {', '.join(why)}")
                    totals['skipped'] += 1
                    continue
                new_id, nc, nl = move_customer(src_key, src_cur, dst_cur, c, cols)
                moved.append((c['id'], new_id, c['property_name']))
                totals['contacts'] += nc
                totals['locations'] += nl
            if commit:
                # Destination first: if the source commit then failed, the worst
                # case is a customer in both places, never in neither.
                dst.commit()
                src.commit()
            else:
                dst.rollback()
                src.rollback()
        except Exception:
            dst.rollback()
            src.rollback()
            raise
        finally:
            src_cur.close()
            src.close()
        totals['moved'] += len(moved)
        for old, new, name in moved[:5]:
            print(f"  #{old} -> kleanit_sf #{new if commit else '(new)'}  {name}")
        if len(moved) > 5:
            print(f"  ... and {len(moved) - 5} more")
    dst_cur.close()
    dst.close()
    print(f"\n{'MOVED' if commit else 'DRY RUN, would move'}: {totals['moved']} customers, "
          f"{totals['contacts']} contacts, {totals['locations']} service locations; skipped {totals['skipped']}.")


if __name__ == '__main__':
    main('--commit' in sys.argv)
