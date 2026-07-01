#!/usr/bin/env python3
"""
FieldKit: Equipment Registry Import — Kleanit Charlotte
Created: 2026-07-01
Purpose: Import the physical equipment fleet from the SF-style inventory
export into equipment_units, linked to the correct per_day_equipment
catalog item.

Classification/naming logic matches the reviewed preview
(equipment_import_final.csv) exactly — brand-qualified names to avoid
cross-brand number collisions (FC Sahara / TD Velopro / Axial / Phoenix
each keep independent numbering — confirmed real, separate machines),
six confirmed duplicate-entry rows merged, "Van Dehu"/"Van Fan" dropped,
bare "Air Scrubber" assigned as unit #02.

Usage:
  Dry run (default — no writes, just prints what would happen):
    docker exec -it fieldkit-prod-app-1 python3 /app/phase1/fieldkit_phase1/import_equipment.py <xlsx_file>

  Real import:
    docker exec -it fieldkit-prod-app-1 python3 /app/phase1/fieldkit_phase1/import_equipment.py <xlsx_file> --commit

Target is hardcoded to kleanit_charlotte — this script is a one-time job
for this specific fleet, not a general-purpose importer.
"""

import sys
import os
import re
import getpass
import openpyxl
import psycopg2
from collections import Counter

DB_NAME = 'fieldkit_kleanit_charlotte'
DB_HOST = 'db'
DB_PORT = 5432
DB_USER = 'fieldkit'

# ============================================================================
# Classification (identical logic to the reviewed preview)
# ============================================================================

EXCLUDE_EXACT = {'fuel surcharge per visit', 'vented ceiling/ran layflat'}

MERGE_DROP = {
    '14 td air max fan 14 w/monitor': '14 TD AirMax Fan 14 w/monitor',
    '01 revolution dehumidifier':     '01 Revolution Dehu01 w/monitor',
    'p2 phoenix airmax':              'P2 AIRMAX FAN',
    'p3 phoenix air max':             'P3 AIRMAX FAN',
    'p6':                             'P6 AIRMAX FAN',
    'p7 phoenix air max':             'P7 AIRMAX FAN',
}

DROP_ENTIRELY = {'van dehu', 'van fan'}

NAMED_OVERRIDE = {
    'air scrubber': ('Air Scrubber #02', 'Air Scrubber'),
}

SINGLETON_OVERRIDE = {
    'set ozone':                      'Ozone',
    'set vortex':                     'Vortex',
    'adea electrostatic air  filter': 'Electrostatic Air Filter',
    'adea electrostatic air filter':  'Electrostatic Air Filter',
}

TYPE_RULES = [
    (re.compile(r'dehu', re.I),          'Dehumidifier'),
    (re.compile(r'scrubber', re.I),      'Air Scrubber'),
    (re.compile(r'ozone', re.I),         'Ozone'),
    (re.compile(r'vortex', re.I),        'Vortex'),
    (re.compile(r'electrostatic', re.I), 'Electrostatic Air Filter'),
    (re.compile(r'fan|air\s?max|air\s?mover', re.I), 'Fan / Air Mover'),
]
PRICE_FALLBACK_TYPE = {30: 'Fan / Air Mover', 110: 'Dehumidifier', 100: 'Air Scrubber',
                        95: 'Ozone', 55: 'Vortex', 49: 'Electrostatic Air Filter'}

BRAND_RULES = [
    (re.compile(r'revolution', re.I), 'Revolution'),
    (re.compile(r'r250', re.I),       'R250'),
    (re.compile(r'r200', re.I),       'R200'),
    (re.compile(r'driz', re.I),       'DRIZ 1200'),
    (re.compile(r'cadpxs', re.I),     'CADPXS'),
    (re.compile(r'dry ?max', re.I),   'DryMax'),
    (re.compile(r'phoenix', re.I),    'Phoenix'),
    (re.compile(r'fc sahara', re.I),  'FC Sahara'),
    (re.compile(r'td velopro', re.I), 'TD Velopro'),
    (re.compile(r'velopro', re.I),    'TD Velopro'),
    (re.compile(r'td air\s?max', re.I), 'TD AirMax'),
    (re.compile(r'axial', re.I),      'Axial'),
]

VAN_RE      = re.compile(r'\bV(\d+)\b', re.I)
PHOENIX_RE  = re.compile(r'\bP(\d+)\b', re.I)
COLOR_RE    = re.compile(r'\b(Red|Blue|Green|Black|White|Yellow)\b', re.I)
SUBUNIT_RE  = re.compile(r'#\s*(\d+)\b')
LEAD_NUM_RE = re.compile(r'^(\d+)')


def classify(name, price):
    raw = name.strip()
    lower = raw.lower()

    if lower in EXCLUDE_EXACT or lower in DROP_ENTIRELY:
        return None
    if lower in MERGE_DROP:
        return None
    if lower in NAMED_OVERRIDE:
        clean_name, type_name = NAMED_OVERRIDE[lower]
        return {'clean_name': clean_name, 'unit_type': type_name,
                'notes': f'Imported from SF inventory export. Original name: "{raw}".'}
    if lower in SINGLETON_OVERRIDE:
        type_name = SINGLETON_OVERRIDE[lower]
        return {'clean_name': type_name, 'unit_type': type_name,
                'notes': f'Imported from SF inventory export. Original name: "{raw}". Only unit of this type in the fleet.'}
    if 'set' in lower:
        return None  # billing template, handled separately in catalog import

    unit_type = next((t for pat, t in TYPE_RULES if pat.search(raw)), None)
    van_m, ph_m = VAN_RE.search(raw), PHOENIX_RE.search(raw)
    if unit_type is None and (van_m or ph_m) and price in PRICE_FALLBACK_TYPE:
        unit_type = PRICE_FALLBACK_TYPE[price]
    if unit_type is None:
        print(f"  WARNING: could not classify '{raw}' — skipping (needs manual add)")
        return None

    brand = next((b for pat, b in BRAND_RULES if pat.search(raw)), None)
    color = COLOR_RE.search(raw)
    color = color.group(1).title() if color else None
    sub_m = SUBUNIT_RE.search(raw)
    lead_m = LEAD_NUM_RE.match(raw)

    if van_m:
        number, subunit = int(van_m.group(1)), (int(sub_m.group(1)) if sub_m else None)
        clean = f"{unit_type} (Van V{number})" + (f" #{subunit}" if subunit else "")
    elif ph_m:
        number = int(ph_m.group(1))
        clean = f"{unit_type} (Phoenix) #P{number}"
    elif lead_m:
        number = int(lead_m.group(1))
        brand_part = f" ({brand})" if brand else ""
        num_str = f"{number:02d}" if number < 100 else str(number)
        clean = f"{unit_type}{brand_part} #{num_str}"
        if color:
            clean += f" [{color}]"
    else:
        print(f"  WARNING: no number found for '{raw}' — skipping (needs manual add)")
        return None

    return {
        'clean_name': clean, 'unit_type': unit_type,
        'notes': f'Imported from SF inventory export. Original name: "{raw}".',
    }


def parse_inventory(filepath):
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active
    units = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        name, price, active = row[1], row[7], row[10]
        if active != 'Yes' or not name:
            continue
        result = classify(name, price)
        if result:
            units.append(result)
    return units


# ============================================================================
# Database
# ============================================================================

def connect_db(password):
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=password,
                             host=DB_HOST, port=DB_PORT)


def get_billing_type_map(cursor):
    """type name -> catalog_item_id, for all live per_day_equipment items."""
    cursor.execute("""
        SELECT id, name FROM catalog_items
        WHERE billing_behavior = 'per_day_equipment' AND deleted_at IS NULL
    """)
    return {row[1]: row[0] for row in cursor.fetchall()}


def get_existing_names(cursor):
    cursor.execute("SELECT name FROM equipment_units WHERE deleted_at IS NULL")
    return {row[0] for row in cursor.fetchall()}


def run_import(units, password, commit):
    conn = connect_db(password)
    cursor = conn.cursor()

    billing_types = get_billing_type_map(cursor)
    print(f"\nCatalog billing types found: {billing_types}")

    missing_types = {u['unit_type'] for u in units} - set(billing_types.keys())
    if missing_types:
        print(f"\nERROR: no catalog_item found for: {missing_types}")
        print("Add these to the Service Catalog (per_day_equipment) before importing.")
        cursor.close(); conn.close()
        return 1

    existing_names = get_existing_names(cursor)
    print(f"{len(existing_names)} equipment units already in the registry — duplicates will be skipped")

    imported, skipped_dup, skipped_err = 0, 0, 0

    for u in units:
        if u['clean_name'] in existing_names:
            skipped_dup += 1
            continue
        try:
            if commit:
                cursor.execute("""
                    INSERT INTO equipment_units
                        (name, catalog_item_id, notes, is_active, created_by, updated_by)
                    VALUES (%s, %s, %s, TRUE, %s, %s)
                """, (u['clean_name'], billing_types[u['unit_type']], u['notes'],
                      'equipment_import', 'equipment_import'))
                conn.commit()
            imported += 1
            existing_names.add(u['clean_name'])
        except Exception as e:
            conn.rollback()
            print(f"  Warning: failed to import '{u['clean_name']}': {e}")
            skipped_err += 1

    cursor.close(); conn.close()

    mode = "COMMITTED" if commit else "DRY RUN — nothing written"
    print(f"\n{'=' * 60}")
    print(f"  Kleanit Charlotte Equipment Import — {mode}")
    print(f"{'=' * 60}")
    print(f"  Would import / Imported:  {imported}")
    print(f"  Skipped (dupes):          {skipped_dup}")
    print(f"  Skipped (errors):         {skipped_err}")
    print(f"\n  By type:")
    for t, c in sorted(Counter(u['unit_type'] for u in units).items()):
        print(f"    {t:28} {c}")
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import_equipment.py <xlsx_file> [--commit]")
        return 1

    filepath = sys.argv[1]
    commit = '--commit' in sys.argv

    if not os.path.exists(filepath):
        print(f"Error: file not found: {filepath}")
        return 1

    print("=" * 60)
    print("FieldKit: Equipment Registry Import — Kleanit Charlotte")
    print("=" * 60)
    print(f"Mode: {'COMMIT (writes to database)' if commit else 'DRY RUN (no writes)'}")

    units = parse_inventory(filepath)
    print(f"\nParsed {len(units)} importable units from {filepath}")

    password = getpass.getpass(f"\nPostgreSQL password for user '{DB_USER}': ")

    return run_import(units, password, commit)


if __name__ == "__main__":
    sys.exit(main())
