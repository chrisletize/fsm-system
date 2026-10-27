"""
Customer category audit (D-119, Chris 2026-10-27).

The ServiceFusion import (phase1/fieldkit_phase1/import_sf_customers.py, June
2026) guessed customer_type from a few keywords in the name and defaulted
everything else to 'Multi Family', so individual people -- homeowners, and
"resident pays" tenants who pay for a cleaning their complex doesn't cover --
were filed as apartment complexes. This module proposes the right category for
every active customer from the evidence FieldKit holds, with a confidence and
the reasons, and changes nothing by itself.

Evidence, strongest first:
  1. The name: property words ("Apartments", "X at Y", "The ..."), contractor
     words, other business words, or a person's name (US Census first-name and
     surname lists in data/).
  2. The building: a person sharing a building with a known property -- the
     same geocoded point, or the same street address nearby -- is a resident
     pays customer. (Chris's insight: residents pay directly when the complex
     doesn't offer the service.)
  3. The address: an apartment/unit number.
  4. Contacts: a contact whose name is the customer's name, personal email
     domains (gmail, yahoo...) versus company domains.

Which individual-customer category a company uses (Chris, 2026-10-27): the
Kleanits file every individual as Resident Pays (no Residential), Get a Grip as
Residential (no Resident Pays), and CTS, the umbrella company, uses both --
Resident Pays for a tenant, Residential for a homeowner. COMPANY_CUSTOMER_TYPES
in app.py is the source; company_type() below maps each proposal onto it.

Run inside the app container:
    docker compose exec -T app python customer_category_audit.py            # report only
    docker compose exec -T app python customer_category_audit.py --csv DIR  # + one CSV per company
    docker compose exec -T app python customer_category_audit.py --apply    # change high+medium,
                                                                             # queue low for review
Back up first (ops/backup/fieldkit-backup.sh). --apply is safe to re-run: it
skips customers someone already decided on the review page.
"""
import csv
import os
import re
import sys
from collections import Counter, defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

CATEGORIES = ('Multi Family', 'Contractors', 'Residential', 'Commercial', 'Resident Pays')
INDIVIDUAL_TYPES = ('Residential', 'Resident Pays')
APPLIED_BY = 'category_audit'


def _load(name):
    with open(os.path.join(DATA_DIR, name)) as fh:
        return {line.strip() for line in fh if line.strip()}


FIRST_NAMES = _load('census1990_first_names.txt')
SURNAMES = _load('census1990_surnames.txt')

# Words that mark an apartment community / property. Matched as whole words.
# STRONG words decide on their own ("Pepper Ridge Apartments, LLC" is a
# property). WEAK words are also common surnames or street words ("Linda Hall",
# "Robert Park"), so a clear person's name beats them.
STRONG_PROPERTY_WORDS = {
    'apartment', 'apartments', 'apts', 'apt', 'townhomes', 'townhome', 'condos', 'condominiums', 'condominium',
    'village', 'villages', 'commons', 'pointe', 'landing', 'landings', 'manor', 'towers', 'flats', 'lofts',
    'loft', 'residences', 'crossing', 'crossings', 'estates', 'villas', 'villa', 'gardens', 'heights',
    'plaza', 'quarters', 'living', 'communities', 'community', 'seniors', 'apartmetns', 'aparments',
}
WEAK_PROPERTY_WORDS = {
    'place', 'park', 'tower', 'ridge', 'crest', 'hills', 'creek', 'grove', 'pines', 'oaks', 'lakes', 'court',
    'courts', 'station', 'square', 'terrace', 'vista', 'preserve', 'reserve', 'trace', 'trails', 'glen',
    'meadows', 'meadow', 'chase', 'mill', 'mills', 'district', 'senior', 'phase', 'harbor', 'harbour', 'bluff',
    'bluffs', 'springs', 'woods', 'forest', 'farms', 'cove', 'shores', 'sound', 'parc', 'lux', 'luxury',
    'collection', 'south', 'uptown', 'midtown', 'southend', 'noda', 'west', 'east', 'north', 'downtown', 'abbey',
    'arbors', 'arbor', 'brook', 'brooke', 'falls', 'hall', 'house', 'lodge', 'row', 'walk', 'yards', 'yard',
    'gateway', 'residence', 'lake', 'view', 'run',
}
PROPERTY_WORDS = STRONG_PROPERTY_WORDS | WEAK_PROPERTY_WORDS
# Apartment brands / management companies that appear as or within names.
PROPERTY_BRANDS = {
    'avana', 'cortland', 'camden', 'maa', 'greystar', 'bell', 'ariel', 'novel', 'solis', 'radius', 'alta',
    'ashford', 'berkshire', 'broadstone', 'crescent', 'elan', 'griffin', 'hawthorne', 'lennox', 'mosaic',
    'nexus', 'the', 'aria', 'ava', 'avalon', 'alexan', 'ironwood', 'lantower', 'roseland', 'ram',
}
# Management/landlord businesses: they hire for their properties -> Multi Family.
MANAGEMENT_WORDS = {'properties', 'property', 'realty', 'management', 'mgmt', 'residential', 'housing',
                    'apartment', 'leasing', 'rentals', 'rental', 'investments', 'capital', 'partners', 'reit'}
CONTRACTOR_WORDS = {
    'construction', 'constructors', 'builders', 'builder', 'building', 'contracting', 'contractor', 'contractors',
    'renovation', 'renovations', 'remodeling', 'remodel', 'restoration', 'restorations', 'roofing', 'plumbing',
    'painting', 'painters', 'flooring', 'floors', 'tile', 'cabinets', 'carpentry', 'drywall', 'electric',
    'electrical', 'hvac', 'mechanical', 'interiors', 'exteriors', 'development', 'developers', 'homebuilders',
    'custom', 'services', 'service', 'solutions', 'maintenance', 'handyman', 'improvement', 'improvements',
    'design', 'designs', 'kitchen', 'bath', 'baths', 'surfaces', 'countertops', 'granite',
}
COMMERCIAL_WORDS = {
    'church', 'ministries', 'school', 'academy', 'university', 'college', 'hotel', 'inn', 'motel', 'restaurant',
    'cafe', 'grill', 'bar', 'clinic', 'dental', 'dentistry', 'medical', 'hospital', 'health', 'office', 'offices',
    'salon', 'spa', 'gym', 'fitness', 'bank', 'store', 'shop', 'market', 'center', 'centre', 'club', 'country',
    'golf', 'airbnb', 'storage', 'warehouse', 'daycare', 'pharmacy', 'vet', 'veterinary', 'hoa',
}
BUSINESS_SUFFIXES = {'llc', 'inc', 'incorporated', 'corp', 'corporation', 'co', 'company', 'ltd', 'lp', 'llp',
                     'pllc', 'pc', 'group', 'enterprises', 'associates', 'holdings', 'trust'}
PERSONAL_EMAIL_DOMAINS = {'gmail.com', 'yahoo.com', 'hotmail.com', 'aol.com', 'icloud.com', 'outlook.com',
                          'live.com', 'msn.com', 'comcast.net', 'att.net', 'bellsouth.net', 'me.com', 'ymail.com',
                          'mac.com', 'protonmail.com', 'charter.net', 'verizon.net', 'sbcglobal.net', 'earthlink.net'}
UNIT_RE = re.compile(r'(\bapt\b|\bapartment\b|\bunit\b|#\s*\w|\bste\b|\bsuite\b|\bbldg\b|\blot\b)', re.I)
PO_BOX_RE = re.compile(r'\bp\.?\s*o\.?\s*box\b', re.I)
# ServiceFusion-era flags typed into names: **OPS**, *FL*, **NEED NEW BILLING** ...
NAME_FLAG_RE = re.compile(r'\*+[^*]*\*+')


def clean_name(name):
    return re.sub(r'\s+', ' ', NAME_FLAG_RE.sub(' ', name or '')).strip()


def words(text):
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", (text or '').lower())


def name_kind(raw_name):
    """('property'|'management'|'contractor'|'commercial'|'business'|'person'|'unknown', strength, reasons).

    Order matters: the checks run from the least ambiguous evidence to the most."""
    name = clean_name(raw_name)
    w = words(name)
    ws = set(w)
    if not w:
        return 'unknown', 0, ['no name']
    person, person_why = _looks_like_person(w, original=name)
    # A builder: "TBP Homes of Raleigh", "Ryan Homes" -- but not "Apartment Homes"/"Townhomes".
    if 'homes' in ws and not ws & {'apartment', 'apartments', 'town', 'mobile'}:
        return 'contractor', 2, ['home builder ("Homes")']
    if re.search(r'\b(at|of)\b', name.lower()) and len(w) >= 3 and person < 2:
        return 'property', 2, ['"X at Y" property name']
    strong = ws & STRONG_PROPERTY_WORDS
    if strong:
        return 'property', 2, [f"property word: {', '.join(sorted(strong))}"]
    weak = ws & WEAK_PROPERTY_WORDS
    # Brands like "Ava" and "Bell" are also people's names: "Ava Southend" and
    # "Bell Lake Norman" are complexes, "Ava Smith" is a person.
    if w[0] in PROPERTY_BRANDS - {'the'} and len(w) >= 2 and (person < 2 or weak or len(w) >= 3):
        return 'property', 2, [f'apartment brand: {w[0]}']
    if ws & CONTRACTOR_WORDS:
        return 'contractor', 2, [f"contractor word: {', '.join(sorted(ws & CONTRACTOR_WORDS))}"]
    if ws & COMMERCIAL_WORDS and person < 2:
        return 'commercial', 1, [f"business word: {', '.join(sorted(ws & COMMERCIAL_WORDS))}"]
    if ws & MANAGEMENT_WORDS and ws & BUSINESS_SUFFIXES:
        return 'management', 2, ['management/landlord company']
    if person >= 2:
        # Complexes are often named like people ("Alton Optimist Park"): three or
        # more words with a property word is a property; two words ("Linda Hall")
        # stays a person but needs another clue to be sure.
        if weak and len(w) >= 3:
            return 'property', 1, [f"property word: {', '.join(sorted(weak))}", '…but also reads like a person']
        if weak:
            return 'person', 1, person_why + [f"…but '{', '.join(sorted(weak))}' is also a property word"]
        return 'person', 2, person_why
    if weak and not ws & BUSINESS_SUFFIXES:
        return 'property', 1 if person else 2, [f"property word: {', '.join(sorted(weak))}"] + (
            ['…but also reads like a person'] if person else [])
    if ws & BUSINESS_SUFFIXES:
        return 'business', 1, [f"business suffix: {', '.join(sorted(ws & BUSINESS_SUFFIXES))}"]
    if ws & MANAGEMENT_WORDS:
        return 'management', 1, ['management/landlord word']
    if w[0] == 'the' or any(ch.isdigit() for ch in name):
        return 'property', 1, ['property-style name (The…/number)']
    if person:
        return 'person', person, person_why
    if len(w) == 1 and w[0] in FIRST_NAMES:
        return 'person', 1, [f'a first name only ({w[0]})']
    return 'unknown', 0, ['name not recognised']


def _looks_like_person(w, original=None):
    """(strength 0-2, reasons) for 'Hallie Thurber', 'Ann B Hilton', 'Smith, John'."""
    if original and ',' in original:
        parts = [p.strip() for p in original.split(',', 1)]
        w = words(parts[1]) + words(parts[0])          # "Smith, John" -> john smith
    tokens = [t for t in w if not (len(t) == 1)]      # drop middle initials
    if not 2 <= len(tokens) <= 4 or any(ch.isdigit() for t in tokens for ch in t):
        return 0, []
    first, last = tokens[0], tokens[-1]
    f, l = first in FIRST_NAMES, last in SURNAMES
    if f and l:
        return 2, [f'person name ({first} = first name, {last} = surname)']
    if f and len(tokens) == 2:
        # "Sharon Davoren": a real first name plus one other word is a person;
        # the surname list is truncated, so a miss there means little.
        return 2, [f'person name ({first} = first name)']
    if f:
        return 1, [f'person name ({first} = first name)']
    if l and len(tokens) <= 3:
        return 1, [f'person name ({last} = surname)']
    return 0, []


def _normalize_street(address):
    line = (address.split(',')[0] if address else '').lower()
    line = UNIT_RE.split(line)[0]                     # building, not the unit
    abbrev = {'street': 'st', 'drive': 'dr', 'avenue': 'ave', 'road': 'rd', 'boulevard': 'blvd', 'lane': 'ln',
              'court': 'ct', 'circle': 'cir', 'parkway': 'pkwy', 'place': 'pl', 'north': 'n', 'south': 's',
              'east': 'e', 'west': 'w', 'terrace': 'ter', 'trail': 'trl'}
    return ''.join(abbrev.get(x, x) for x in re.findall(r'[a-z0-9]+', line))


def company_type(allowed, proposed, subtype):
    """Map a proposal onto the categories this company uses. `allowed` is
    customer_types_for(company_key) from app.py."""
    if proposed not in INDIVIDUAL_TYPES:
        return proposed
    if 'Residential' in allowed and 'Resident Pays' in allowed:      # CTS: both
        if subtype:
            return 'Resident Pays' if subtype == 'resident pays' else 'Residential'
        return proposed
    return 'Resident Pays' if 'Resident Pays' in allowed else 'Residential'


def classify_company(conn, company_key, allowed=None):
    """One proposal per active customer. Returns a list of dicts. `allowed` is
    the company's category list (customer_types_for); None skips the mapping."""
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.property_name, c.customer_type, c.address, c.city, c.state, c.zip,
               c.latitude, c.longitude, c.management_company_id,
               EXISTS (SELECT 1 FROM customer_compliance_portals p WHERE p.customer_id = c.id
                         AND p.is_active) AS has_portal
        FROM customers c WHERE c.deleted_at IS NULL AND c.status = 'Active' ORDER BY c.id
    """)
    customers = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT customer_id, first_name, last_name, office_email
        FROM customer_contacts WHERE deleted_at IS NULL
    """)
    contacts = defaultdict(list)
    for r in cur.fetchall():
        contacts[r['customer_id']].append(r)
    cur.close()

    for c in customers:
        c['kind'], c['strength'], c['reasons'] = name_kind(c['property_name'])
        c['street'] = _normalize_street(c['address'])

    # Buildings: which known properties sit at each street / point.
    property_streets = defaultdict(list)
    property_points = []
    for c in customers:
        if c['kind'] == 'property' and c['strength'] >= 1:
            if c['street']:
                property_streets[(c['street'], (c['zip'] or '')[:3])].append(c['property_name'])
            if c['latitude'] is not None:
                property_points.append((float(c['latitude']), float(c['longitude']), c['property_name']))
    grid = defaultdict(list)
    for lat, lng, nm in property_points:
        grid[(round(lat, 3), round(lng, 3))].append((lat, lng, nm))

    def building_of(c):
        """Name of a known property at this customer's building, if any."""
        if c['street']:
            hit = property_streets.get((c['street'], (c['zip'] or '')[:3]))
            if hit:
                return hit[0]
        if c['latitude'] is not None:
            lat, lng = float(c['latitude']), float(c['longitude'])
            for dy in (-0.001, 0, 0.001):
                for dx in (-0.001, 0, 0.001):
                    for plat, plng, nm in grid.get((round(lat + dy, 3), round(lng + dx, 3)), []):
                        if abs(plat - lat) < 0.0006 and abs(plng - lng) < 0.0006:   # ~60 m
                            return nm
        return None

    out = []
    for c in customers:
        kind, strength, reasons = c['kind'], c['strength'], list(c['reasons'])
        cname = clean_name(c['property_name']).lower()
        cons = contacts.get(c['id'], [])
        domains = {(x['office_email'] or '').split('@')[-1].lower() for x in cons if '@' in (x['office_email'] or '')}
        personal = bool(domains) and domains <= PERSONAL_EMAIL_DOMAINS
        self_contact = any(f"{(x['first_name'] or '').strip()} {(x['last_name'] or '').strip()}".strip().lower()
                           == cname for x in cons)
        has_unit = bool(c['address'] and UNIT_RE.search(c['address']) and not PO_BOX_RE.search(c['address']))
        building = building_of(c) if kind in ('person', 'unknown') else None
        if building and building.lower() == cname:
            building = None

        business_contacts = bool(domains - PERSONAL_EMAIL_DOMAINS) and not self_contact
        subtype = None
        if kind == 'person' or (kind == 'unknown' and (building or self_contact or personal or has_unit)):
            proposed = 'Residential'
            score = strength
            if business_contacts and not building and not has_unit:
                reasons.append('…but its contacts use a company email domain (may be a property)')
                score -= 2
            if building:
                reasons.append(f'shares a building with "{building}"'); score += 2
            if has_unit:
                reasons.append('apartment/unit number in address'); score += 1
            if self_contact:
                reasons.append("contact's name is the customer's name"); score += 1
            if personal:
                reasons.append('personal email domain'); score += 1
            subtype = 'resident pays' if (building or has_unit) else 'homeowner'
            confidence = 'high' if score >= 3 else 'medium' if score >= 2 else 'low'
        elif kind == 'property':
            proposed, confidence = 'Multi Family', 'high' if strength >= 2 else 'medium'
        elif kind == 'management':
            proposed, confidence = 'Multi Family', 'high' if strength >= 2 else 'medium'
        elif kind == 'contractor':
            proposed, confidence = 'Contractors', 'high' if strength >= 2 else 'medium'
        elif kind == 'commercial':
            proposed, confidence = 'Commercial', 'medium'
        elif kind == 'business':
            proposed, confidence = 'Commercial', 'low'
        else:
            proposed, confidence = c['customer_type'], 'low'
            reasons.append('no clear evidence: left as it is')
        if c['has_portal'] and proposed != 'Multi Family':
            reasons.append('enrolled in a compliance portal (usually a property)')
            confidence = 'low'
        if allowed:
            raw = proposed
            proposed = company_type(allowed, proposed, subtype)
            if raw == c['customer_type'] and proposed != raw:
                # Same evidence-free answer, but the current category isn't one
                # this company uses any more: a rename, not a judgement call.
                reasons.append(f'{raw} is not a category at this company: renamed to {proposed}')
                confidence = 'high'
        fl = (c['state'] or '').upper() == 'FL' or (c['zip'] or '')[:2] in ('32', '33', '34')
        out.append({
            'company': company_key, 'id': c['id'], 'name': c['property_name'], 'address': c['address'] or '',
            'city': c['city'] or '', 'state': c['state'] or '', 'zip': c['zip'] or '',
            'current': c['customer_type'], 'proposed': proposed, 'subtype': subtype or '',
            'confidence': confidence, 'changes': proposed != c['customer_type'],
            'florida_address': bool(fl and company_key != 'kleanit_sf'),
            'reasons': '; '.join(reasons),
        })
    return out


def apply_company(conn, company_key, rows, record_audit):
    """Change high+medium proposals; queue low ones on the review page.
    Customers someone already decided on (a non-pending review) are left alone.
    `record_audit` is app._record_audit. Commits. Returns (changed, queued)."""
    cur = conn.cursor()
    cur.execute("""SELECT customer_id, status FROM customer_category_reviews
                   WHERE deleted_at IS NULL""")
    decided, pending = set(), set()
    for r in cur.fetchall():
        (pending if r['status'] == 'pending' else decided).add(r['customer_id'])
    changed = queued = 0
    for r in rows:
        if not r['changes'] or r['id'] in decided:
            continue
        if r['confidence'] in ('high', 'medium'):
            cur.execute("SELECT * FROM customers WHERE id = %s AND deleted_at IS NULL", (r['id'],))
            before = cur.fetchone()
            if not before or before['customer_type'] != r['current']:
                continue                      # changed since the audit read it
            cur.execute("""UPDATE customers SET customer_type = %s, updated_at = CURRENT_TIMESTAMP,
                                  updated_by = %s
                           WHERE id = %s RETURNING *""", (r['proposed'], APPLIED_BY, r['id']))
            record_audit(cur, 'customers', r['id'], 'update', before, cur.fetchone(), changed_by=APPLIED_BY)
            if r['id'] in pending:            # an older low-confidence question is now settled
                cur.execute("""UPDATE customer_category_reviews
                               SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
                               WHERE customer_id = %s AND status = 'pending' AND deleted_at IS NULL""",
                            (APPLIED_BY, r['id']))
            changed += 1
        elif r['id'] not in pending:
            cur.execute("""INSERT INTO customer_category_reviews
                               (customer_id, current_type, proposed_type, confidence, reasons,
                                created_by, updated_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (r['id'], r['current'], r['proposed'], r['confidence'], r['reasons'],
                         APPLIED_BY, APPLIED_BY))
            queued += 1
    conn.commit()
    cur.close()
    return changed, queued


def summarize(rows):
    s = Counter()
    for r in rows:
        s[(r['current'], r['proposed'], r['confidence'], r['subtype'])] += 1
    return s


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app import get_db_connection, ALL_COMPANY_KEYS, customer_types_for, _record_audit
    csv_dir = sys.argv[sys.argv.index('--csv') + 1] if '--csv' in sys.argv else None
    for ck in ALL_COMPANY_KEYS:
        conn = get_db_connection(ck)
        rows = classify_company(conn, ck, customer_types_for(ck))
        if '--apply' in sys.argv:
            changed, queued = apply_company(conn, ck, rows, _record_audit)
            print(f"\n=== {ck}: APPLIED {changed} changes, {queued} queued for review")
        conn.close()
        changes = [r for r in rows if r['changes']]
        print(f"\n=== {ck}: {len(rows)} active customers, {len(changes)} proposed changes")
        for (cur_t, prop_t, conf, sub), n in sorted(summarize(rows).items(), key=lambda kv: -kv[1]):
            if cur_t != prop_t:
                print(f"  {n:5d}  {cur_t} -> {prop_t}{' (' + sub + ')' if sub else ''}  [{conf}]")
        unchanged = sum(1 for r in rows if not r['changes'])
        print(f"  {unchanged:5d}  unchanged")
        fl = sum(1 for r in rows if r['florida_address'])
        if fl:
            print(f"  ! {fl} have a Florida address but live in {ck}")
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
            path = os.path.join(csv_dir, f'category_audit_{ck}.csv')
            with open(path, 'w', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else ['id'])
                w.writeheader()
                w.writerows(rows)
            print(f"  -> {path}")
