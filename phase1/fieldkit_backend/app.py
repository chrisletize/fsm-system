"""
FieldKit Flask Application
Phase 1: Authentication & Company-in-URL Architecture
"""

from flask import Flask, request, session, jsonify, render_template, redirect, url_for, abort
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
import json
import math
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

DB_CONFIG = {
    'getagrip':           'fieldkit_getagrip',
    'kleanit_charlotte':  'fieldkit_kleanit_charlotte',
    'cts':                'fieldkit_cts',
    'kleanit_sf':         'fieldkit_kleanit_sf',
}

DB_USER     = os.environ.get('DB_USER',     'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST     = os.environ.get('DB_HOST',     'localhost')
DB_PORT     = os.environ.get('DB_PORT',     '5432')

COMPANY_BRANDING = {
    'getagrip': {
        'name': 'Get a Grip Charlotte', 'short_name': 'Get a Grip',
        'color_primary': '#8B1538', 'color_secondary': '#F5F5DC',
        'logo_url': '/static/img/getagrip-logo.png',
    },
    'kleanit_charlotte': {
        'name': 'Kleanit Charlotte', 'short_name': 'Kleanit CLT',
        'color_primary': '#0052CC', 'color_secondary': '#FFFFFF',
        'logo_url': '/static/img/kleanit-clt-logo.png',
    },
    'cts': {
        'name': 'CTS of Raleigh', 'short_name': 'CTS',
        'color_primary': '#2C2C2C', 'color_secondary': '#F5F5DC',
        'logo_url': '/static/img/cts-logo.png',
    },
    'kleanit_sf': {
        'name': 'Kleanit South Florida', 'short_name': 'Kleanit SF',
        'color_primary': '#00D66C', 'color_secondary': '#FFFFFF',
        'logo_url': '/static/img/kleanit-sf-logo.png',
    },
}

NC_COUNTIES = [
    'Alamance','Alexander','Alleghany','Anson','Ashe','Avery','Beaufort',
    'Bertie','Bladen','Brunswick','Buncombe','Burke','Cabarrus','Caldwell',
    'Camden','Carteret','Caswell','Catawba','Chatham','Cherokee','Chowan',
    'Clay','Cleveland','Columbus','Craven','Cumberland','Currituck','Dare',
    'Davidson','Davie','Duplin','Durham','Edgecombe','Forsyth','Franklin',
    'Gaston','Gates','Graham','Granville','Greene','Guilford','Halifax',
    'Harnett','Haywood','Henderson','Hertford','Hoke','Hyde','Iredell',
    'Jackson','Johnston','Jones','Lee','Lenoir','Lincoln','Macon','Madison',
    'Martin','McDowell','Mecklenburg','Mitchell','Montgomery','Moore','Nash',
    'New Hanover','Northampton','Onslow','Orange','Pamlico','Pasquotank',
    'Pender','Perquimans','Person','Pitt','Polk','Randolph','Richmond',
    'Robeson','Rockingham','Rowan','Rutherford','Sampson','Scotland','Stanly',
    'Stokes','Surry','Swain','Transylvania','Tyrrell','Union','Vance','Wake',
    'Warren','Washington','Watauga','Wayne','Wilkes','Wilson','Yadkin','Yancey'
]

# ============================================================================
# Database helpers
# ============================================================================

def get_db_connection(company_key):
    if company_key not in DB_CONFIG:
        raise ValueError(f"Invalid company key: {company_key}")
    return psycopg2.connect(
        dbname=DB_CONFIG[company_key],
        user=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT,
        cursor_factory=RealDictCursor
    )

def get_user_by_username(username):
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, username, email, password_hash, full_name, role,
               company_access, is_active, last_login
        FROM users WHERE username = %s AND is_active = TRUE
    """, (username,))
    user = cur.fetchone()
    cur.close(); conn.close()
    return user

def update_last_login(username):
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s", (username,))
    conn.commit(); cur.close(); conn.close()

def get_customer_count(company_key):
    try:
        conn = get_db_connection(company_key)
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM customers WHERE deleted_at IS NULL AND status = 'Active'")
        count = cur.fetchone()['count']
        cur.close(); conn.close()
        return count
    except Exception:
        return 0

def get_management_companies(conn):
    """Get all management companies for a company database."""
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM management_companies WHERE deleted_at IS NULL ORDER BY name ASC")
    result = cur.fetchall()
    cur.close()
    return result

# ============================================================================
# Custom field helpers
# ============================================================================

def get_custom_fields(conn, customer_id):
    """Customer-level custom fields (not location-scoped)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.id as definition_id, fd.field_name, fd.field_type,
               fd.display_order, fd.is_active,
               COALESCE(fv.value, '') as value
        FROM customer_field_definitions fd
        LEFT JOIN customer_field_values fv
            ON fv.field_definition_id = fd.id
            AND fv.customer_id = %s
            AND fv.location_id IS NULL
        WHERE fd.is_active = TRUE
        ORDER BY fd.display_order ASC
    """, (customer_id,))
    fields = cur.fetchall()
    cur.close()
    return fields

def get_location_custom_fields(conn, location_id):
    """Location-scoped custom field values."""
    cur = conn.cursor()
    cur.execute("""
        SELECT fd.id as definition_id, fd.field_name, fd.field_type,
               fd.display_order,
               COALESCE(fv.value, '') as value
        FROM customer_field_definitions fd
        LEFT JOIN customer_field_values fv
            ON fv.field_definition_id = fd.id
            AND fv.location_id = %s
        WHERE fd.is_active = TRUE
        ORDER BY fd.display_order ASC
    """, (location_id,))
    fields = cur.fetchall()
    cur.close()
    return fields

def get_field_definitions(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, field_name, field_type, display_order, is_active
        FROM customer_field_definitions
        ORDER BY display_order ASC
    """)
    defs = cur.fetchall()
    cur.close()
    return defs

def save_custom_fields(conn, customer_id, form_data, username, location_id=None):
    """Upsert custom field values. If location_id provided, scopes to location."""
    cur = conn.cursor()
    for key, value in form_data.items():
        if key.startswith('field_'):
            try:
                definition_id = int(key.replace('field_', ''))
                if location_id:
                    cur.execute("""
                        INSERT INTO customer_field_values
                            (customer_id, field_definition_id, location_id, value, updated_by)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (customer_id, field_definition_id)
                        DO UPDATE SET value = EXCLUDED.value,
                                      location_id = EXCLUDED.location_id,
                                      updated_at = CURRENT_TIMESTAMP,
                                      updated_by = EXCLUDED.updated_by
                    """, (customer_id, definition_id, location_id, value.strip(), username))
                else:
                    cur.execute("""
                        INSERT INTO customer_field_values
                            (customer_id, field_definition_id, value, updated_by)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (customer_id, field_definition_id)
                        DO UPDATE SET value = EXCLUDED.value,
                                      updated_at = CURRENT_TIMESTAMP,
                                      updated_by = EXCLUDED.updated_by
                    """, (customer_id, definition_id, value.strip(), username))
            except (ValueError, Exception):
                continue
    cur.close()

# ============================================================================
# Decorators
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def company_access_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        company_key = kwargs.get('company_key')
        if company_key not in DB_CONFIG:
            abort(404)
        if company_key not in session.get('company_access', []):
            abort(403)
        return f(*args, **kwargs)
    return decorated

def with_branding(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        company_key = kwargs.get('company_key')
        kwargs['branding']       = COMPANY_BRANDING.get(company_key, {})
        kwargs['all_companies']  = COMPANY_BRANDING
        kwargs['company_access'] = session.get('company_access', [])
        return f(*args, **kwargs)
    return decorated

# ============================================================================
# Auth routes
# ============================================================================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    company_access = session.get('company_access', [])
    if len(company_access) == 1:
        return redirect(url_for('dashboard', company_key=company_access[0]))
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        return render_template('login.html', error='Username and password required')

    user = get_user_by_username(username)
    if not user:
        return render_template('login.html', error='Invalid username or password')
    if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        return render_template('login.html', error='Invalid username or password')

    session['user_id']        = user['id']
    session['username']       = user['username']
    session['full_name']      = user['full_name']
    session['user_role']      = user['role']
    session['company_access'] = user['company_access']
    update_last_login(username)

    company_access = user['company_access']
    if len(company_access) == 1:
        return redirect(url_for('dashboard', company_key=company_access[0]))
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============================================================================
# Home — multi-company launch pad
# ============================================================================

@app.route('/home')
@login_required
def home():
    company_access = session.get('company_access', [])
    if len(company_access) == 1:
        return redirect(url_for('dashboard', company_key=company_access[0]))

    companies = []
    for key in company_access:
        if key in COMPANY_BRANDING:
            companies.append({
                'key':   key,
                'count': get_customer_count(key),
                **COMPANY_BRANDING[key],
            })

    import datetime as _dt
    return render_template('home.html',
        now_hour=_dt.datetime.now().hour,
        companies=companies,
        full_name=session.get('full_name'),
    )

# ============================================================================
# Dashboard
# ============================================================================

@app.route('/<company_key>/')
@app.route('/<company_key>/dashboard')
@login_required
@company_access_required
@with_branding
def dashboard(company_key, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) as count FROM customers WHERE deleted_at IS NULL AND status = 'Active'")
    active_customers = cur.fetchone()['count']

    cur.execute("""
        SELECT id, property_name, customer_type, city, status
        FROM customers WHERE deleted_at IS NULL
        ORDER BY created_at DESC LIMIT 10
    """)
    recent_customers = cur.fetchall()
    cur.close(); conn.close()

    return render_template('dashboard.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        active_customers=active_customers, recent_customers=recent_customers,
    )

# ============================================================================
# Customers — list
# ============================================================================

@app.route('/<company_key>/customers')
@login_required
@company_access_required
@with_branding
def customers(company_key, branding, all_companies, company_access):
    search        = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'Active')
    type_filter   = request.args.get('type', '')
    page          = max(1, request.args.get('page', 1, type=int))
    per_page      = 50

    conditions = ["deleted_at IS NULL"]
    params     = []

    if search:
        conditions.append("to_tsvector('english', property_name) @@ plainto_tsquery('english', %s)")
        params.append(search)
    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)
    if type_filter:
        conditions.append("customer_type = %s")
        params.append(type_filter)

    where  = " AND ".join(conditions)
    offset = (page - 1) * per_page

    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute(f"SELECT COUNT(*) as count FROM customers WHERE {where}", params)
    total       = cur.fetchone()['count']
    total_pages = max(1, (total + per_page - 1) // per_page)

    cur.execute(f"""
        SELECT id, property_name, customer_type, city, state, status,
               billing_email, created_at
        FROM customers WHERE {where}
        ORDER BY property_name ASC
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    customer_list = cur.fetchall()
    cur.close(); conn.close()

    return render_template('customers.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customers=customer_list,
        search=search, status_filter=status_filter, type_filter=type_filter,
        page=page, total_pages=total_pages, total=total,
    )


@app.route('/<company_key>/customers/search')
@login_required
@company_access_required
def customers_search(company_key):
    """JSON endpoint for live customer search — returns matching rows."""
    search        = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'Active')
    type_filter   = request.args.get('type', '')

    conditions = ["deleted_at IS NULL"]
    params     = []

    if search:
        conditions.append("property_name ILIKE %s")
        params.append(f'%{search}%')
    if status_filter:
        conditions.append("status = %s")
        params.append(status_filter)
    if type_filter:
        conditions.append("customer_type = %s")
        params.append(type_filter)

    where = " AND ".join(conditions)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT id, property_name, customer_type, city, state, status
        FROM customers WHERE {where}
        ORDER BY property_name ASC
        LIMIT 100
    """, params)
    rows = cur.fetchall()

    cur.execute(f"SELECT COUNT(*) as count FROM customers WHERE {where}", params)
    total = cur.fetchone()['count']
    cur.close(); conn.close()

    return jsonify({
        'total': total,
        'customers': [dict(r) for r in rows],
    })


# ============================================================================
# Customers — detail
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>')
@login_required
@company_access_required
@with_branding
def customer_detail(company_key, customer_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("""
        SELECT c.*, mc.name as management_company_name
        FROM customers c
        LEFT JOIN management_companies mc ON c.management_company_id = mc.id
        WHERE c.id = %s AND c.deleted_at IS NULL
    """, (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    cur.execute("""
        SELECT * FROM customer_contacts
        WHERE customer_id = %s AND deleted_at IS NULL
        ORDER BY is_primary DESC, last_name ASC
    """, (customer_id,))
    contacts = cur.fetchall()

    cur.execute("""
        SELECT * FROM customer_notes
        WHERE customer_id = %s
        ORDER BY created_at DESC LIMIT 50
    """, (customer_id,))
    notes = cur.fetchall()

    cur.execute("""
        SELECT * FROM service_locations
        WHERE customer_id = %s AND deleted_at IS NULL
        ORDER BY is_primary DESC, location_name ASC
    """, (customer_id,))
    locations_raw = cur.fetchall()

    locations = []
    for loc in locations_raw:
        loc_dict = dict(loc)
        loc_dict['custom_fields'] = get_location_custom_fields(conn, loc['id'])
        locations.append(loc_dict)

    custom_fields = get_custom_fields(conn, customer_id)
    cur.close(); conn.close()

    return render_template('customer_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, contacts=contacts, notes=notes,
        locations=locations, custom_fields=custom_fields,
        nc_counties=NC_COUNTIES,
    )

# ============================================================================
# Customers — add note
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/notes', methods=['POST'])
@login_required
@company_access_required
def add_note(company_key, customer_id):
    note_text = request.form.get('note_text', '').strip()
    note_type = request.form.get('note_type', 'General')
    if not note_text:
        return redirect(f'/{company_key}/customers/{customer_id}')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO customer_notes (customer_id, note_text, note_type, created_by)
        VALUES (%s, %s, %s, %s)
    """, (customer_id, note_text, note_type, session.get('username')))
    conn.commit()
    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')

# ============================================================================
# Customers — new
# ============================================================================

@app.route('/<company_key>/customers/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def customer_new(company_key, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    field_defs          = get_field_definitions(conn)
    management_companies = get_management_companies(conn)

    if request.method == 'POST':
        cur = conn.cursor()
        try:
            mgmt_id = request.form.get('management_company_id') or None
            if mgmt_id:
                mgmt_id = int(mgmt_id)

            cur.execute("""
                INSERT INTO customers (
                    property_name, customer_type, status,
                    address, address_2, city, state, zip,
                    billing_email, payment_terms, notes,
                    is_taxable, tax_county, management_company_id,
                    created_by, updated_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                request.form.get('property_name','').strip(),
                request.form.get('customer_type','Multi Family'),
                request.form.get('status','Active'),
                request.form.get('address','').strip(),
                request.form.get('address_2','').strip(),
                request.form.get('city','').strip(),
                request.form.get('state','').strip(),
                request.form.get('zip','').strip(),
                request.form.get('billing_email','').strip(),
                request.form.get('payment_terms','Net 30'),
                request.form.get('notes','').strip(),
                request.form.get('is_taxable') == 'on',
                request.form.get('tax_county','').strip() or None,
                mgmt_id,
                session.get('username'),
                session.get('username'),
            ))
            customer_id = cur.fetchone()['id']
            save_custom_fields(conn, customer_id, request.form, session.get('username'))
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('customer_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=None, field_defs=field_defs,
                management_companies=management_companies,
                field_values={}, nc_counties=NC_COUNTIES, error=str(e),
            )

    conn.close()
    return render_template('customer_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=None, field_defs=field_defs,
        management_companies=management_companies,
        field_values={}, nc_counties=NC_COUNTIES, error=None,
    )

# ============================================================================
# Customers — edit
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def customer_edit(company_key, customer_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT * FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    field_defs           = get_field_definitions(conn)
    management_companies = get_management_companies(conn)
    custom_fields        = get_custom_fields(conn, customer_id)
    field_values         = {f['definition_id']: f['value'] for f in custom_fields}

    if request.method == 'POST':
        try:
            mgmt_id = request.form.get('management_company_id') or None
            if mgmt_id:
                mgmt_id = int(mgmt_id)

            cur.execute("""
                UPDATE customers SET
                    property_name = %s, customer_type = %s, status = %s,
                    address = %s, address_2 = %s, city = %s, state = %s, zip = %s,
                    billing_email = %s, payment_terms = %s, notes = %s,
                    is_taxable = %s, tax_county = %s, management_company_id = %s,
                    updated_by = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                request.form.get('property_name','').strip(),
                request.form.get('customer_type','Multi Family'),
                request.form.get('status','Active'),
                request.form.get('address','').strip(),
                request.form.get('address_2','').strip(),
                request.form.get('city','').strip(),
                request.form.get('state','').strip(),
                request.form.get('zip','').strip(),
                request.form.get('billing_email','').strip(),
                request.form.get('payment_terms','Net 30'),
                request.form.get('notes','').strip(),
                request.form.get('is_taxable') == 'on',
                request.form.get('tax_county','').strip() or None,
                mgmt_id,
                session.get('username'),
                customer_id,
            ))
            save_custom_fields(conn, customer_id, request.form, session.get('username'))
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('customer_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=customer, field_defs=field_defs,
                management_companies=management_companies,
                field_values=field_values, nc_counties=NC_COUNTIES, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('customer_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, field_defs=field_defs,
        management_companies=management_companies,
        field_values=field_values, nc_counties=NC_COUNTIES, error=None,
    )

# ============================================================================
# Service Locations — new
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/locations/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def location_new(company_key, customer_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT id, property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    field_defs = get_field_definitions(conn)

    if request.method == 'POST':
        try:
            cur.execute("SELECT COUNT(*) as count FROM service_locations WHERE customer_id = %s AND deleted_at IS NULL", (customer_id,))
            is_first = cur.fetchone()['count'] == 0

            cur.execute("""
                INSERT INTO service_locations (
                    customer_id, location_name, address, address_2,
                    city, state, zip, county, is_taxable, is_primary,
                    notes, created_by, updated_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (
                customer_id,
                request.form.get('location_name','').strip() or None,
                request.form.get('address','').strip(),
                request.form.get('address_2','').strip(),
                request.form.get('city','').strip(),
                request.form.get('state','').strip(),
                request.form.get('zip','').strip(),
                request.form.get('county','').strip() or None,
                request.form.get('is_taxable') == 'on',
                is_first,
                request.form.get('notes','').strip(),
                session.get('username'),
                session.get('username'),
            ))
            location_id = cur.fetchone()['id']
            save_custom_fields(conn, customer_id, request.form, session.get('username'), location_id=location_id)
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('location_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=customer, location=None, field_defs=field_defs,
                field_values={}, nc_counties=NC_COUNTIES, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('location_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, location=None, field_defs=field_defs,
        field_values={}, nc_counties=NC_COUNTIES, error=None,
    )

# ============================================================================
# Service Locations — edit
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/locations/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def location_edit(company_key, customer_id, location_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT id, property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    cur.execute("SELECT * FROM service_locations WHERE id = %s AND customer_id = %s AND deleted_at IS NULL", (location_id, customer_id))
    location = cur.fetchone()
    if not location:
        cur.close(); conn.close(); abort(404)

    field_defs   = get_field_definitions(conn)
    loc_fields   = get_location_custom_fields(conn, location_id)
    field_values = {f['definition_id']: f['value'] for f in loc_fields}

    if request.method == 'POST':
        try:
            cur.execute("""
                UPDATE service_locations SET
                    location_name = %s, address = %s, address_2 = %s,
                    city = %s, state = %s, zip = %s, county = %s,
                    is_taxable = %s, notes = %s,
                    updated_by = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                request.form.get('location_name','').strip() or None,
                request.form.get('address','').strip(),
                request.form.get('address_2','').strip(),
                request.form.get('city','').strip(),
                request.form.get('state','').strip(),
                request.form.get('zip','').strip(),
                request.form.get('county','').strip() or None,
                request.form.get('is_taxable') == 'on',
                request.form.get('notes','').strip(),
                session.get('username'),
                location_id,
            ))
            save_custom_fields(conn, customer_id, request.form, session.get('username'), location_id=location_id)
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('location_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=customer, location=location, field_defs=field_defs,
                field_values=field_values, nc_counties=NC_COUNTIES, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('location_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, location=location, field_defs=field_defs,
        field_values=field_values, nc_counties=NC_COUNTIES, error=None,
    )

# ============================================================================
# Custom field settings
# ============================================================================

@app.route('/<company_key>/settings/fields')
@login_required
@company_access_required
@with_branding
def field_settings(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    field_defs = get_field_definitions(conn)
    conn.close()
    return render_template('field_settings.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        field_defs=field_defs,
    )

@app.route('/<company_key>/settings/fields/add', methods=['POST'])
@login_required
@company_access_required
def field_add(company_key):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    field_name = request.form.get('field_name','').strip()
    field_type = request.form.get('field_type','text')
    if not field_name:
        return redirect(f'/{company_key}/settings/fields')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO customer_field_definitions (field_name, field_type, display_order, created_by)
        VALUES (%s, %s,
            (SELECT COALESCE(MAX(display_order),0)+1 FROM customer_field_definitions),
            %s)
    """, (field_name, field_type, session.get('username')))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/settings/fields')

@app.route('/<company_key>/settings/fields/<int:field_id>/toggle', methods=['POST'])
@login_required
@company_access_required
def field_toggle(company_key, field_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE customer_field_definitions
        SET is_active = NOT is_active WHERE id = %s
    """, (field_id,))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/settings/fields')

# ============================================================================
# Service catalog settings  (admin + manager)
# ============================================================================

VALID_BILLING_BEHAVIORS = ('standard', 'per_day_equipment')
VALID_UNITS = ('each', 'sq ft', 'hour', 'flat rate', 'day')

def _opt_num(value):
    """Empty string -> None; otherwise the stripped string (psycopg2 casts NUMERIC/INT)."""
    value = (value or '').strip()
    return value if value != '' else None

def _save_catalog_item(company_key, item_id):
    """Insert (item_id is None) or update a catalog item from request.form.
    Returns an error string, or None on success."""
    name              = request.form.get('name', '').strip()
    billing_behavior  = request.form.get('billing_behavior', 'standard')
    category          = request.form.get('category', '').strip() or None
    unit_of_measure   = request.form.get('unit_of_measure', 'each')
    unit_price        = _opt_num(request.form.get('unit_price')) or '0'
    cost              = _opt_num(request.form.get('cost'))
    estimated_minutes = _opt_num(request.form.get('estimated_minutes'))
    minimum_quantity  = _opt_num(request.form.get('minimum_quantity'))
    billing_increment = _opt_num(request.form.get('billing_increment'))
    default_desc      = request.form.get('default_description', '').strip() or None
    is_taxable        = request.form.get('is_taxable') == 'on'
    is_catch_all      = request.form.get('is_catch_all') == 'on'
    is_active         = request.form.get('is_active') == 'on'

    if not name:
        return 'Item name is required.'
    if billing_behavior not in VALID_BILLING_BEHAVIORS:
        return 'Invalid billing behavior.'
    if unit_of_measure not in VALID_UNITS:
        return 'Invalid unit of measure.'

    # Per-day equipment never carries a labor-time estimate.
    if billing_behavior == 'per_day_equipment':
        estimated_minutes = None

    username = session.get('username')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    if item_id is None:
        cur.execute("""
            INSERT INTO catalog_items
                (billing_behavior, name, default_description, category,
                 unit_price, unit_of_measure, estimated_minutes,
                 minimum_quantity, billing_increment, is_taxable, cost,
                 is_catch_all, sort_order, is_active, created_by, updated_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    (SELECT COALESCE(MAX(sort_order),0)+1 FROM catalog_items WHERE deleted_at IS NULL),
                    %s,%s,%s)
        """, (billing_behavior, name, default_desc, category,
              unit_price, unit_of_measure, estimated_minutes,
              minimum_quantity, billing_increment, is_taxable, cost,
              is_catch_all, is_active, username, username))
    else:
        cur.execute("""
            UPDATE catalog_items
            SET billing_behavior=%s, name=%s, default_description=%s, category=%s,
                unit_price=%s, unit_of_measure=%s, estimated_minutes=%s,
                minimum_quantity=%s, billing_increment=%s, is_taxable=%s, cost=%s,
                is_catch_all=%s, is_active=%s,
                updated_at=CURRENT_TIMESTAMP, updated_by=%s
            WHERE id=%s AND deleted_at IS NULL
        """, (billing_behavior, name, default_desc, category,
              unit_price, unit_of_measure, estimated_minutes,
              minimum_quantity, billing_increment, is_taxable, cost,
              is_catch_all, is_active, username, item_id))
    conn.commit(); cur.close(); conn.close()
    return None

def _catalog_categories(company_key):
    """Distinct, non-empty catalog categories for autocomplete suggestions."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT DISTINCT category FROM catalog_items
        WHERE deleted_at IS NULL AND category IS NOT NULL AND category <> ''
        ORDER BY category
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [r['category'] for r in rows]

@app.route('/<company_key>/settings/catalog')
@login_required
@company_access_required
@with_branding
def catalog_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, name, category, billing_behavior, unit_of_measure,
               unit_price, estimated_minutes, is_taxable, is_active, sort_order
        FROM catalog_items
        WHERE deleted_at IS NULL
        ORDER BY is_active DESC, sort_order, name
    """)
    items = cur.fetchall()
    cur.close(); conn.close()
    return render_template('catalog_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        items=items,
    )

@app.route('/<company_key>/settings/catalog/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def catalog_new(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    error = None
    if request.method == 'POST':
        error = _save_catalog_item(company_key, item_id=None)
        if not error:
            return redirect(f'/{company_key}/settings/catalog')
    categories = _catalog_categories(company_key)
    return render_template('catalog_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        item=None, error=error, categories=categories,
        valid_units=VALID_UNITS, valid_behaviors=VALID_BILLING_BEHAVIORS,
    )

@app.route('/<company_key>/settings/catalog/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def catalog_edit(company_key, item_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    if request.method == 'POST':
        error = _save_catalog_item(company_key, item_id=item_id)
        if not error:
            return redirect(f'/{company_key}/settings/catalog')
    else:
        error = None
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT * FROM catalog_items WHERE id = %s AND deleted_at IS NULL", (item_id,))
    item = cur.fetchone()
    cur.close(); conn.close()
    if not item:
        abort(404)
    categories = _catalog_categories(company_key)
    return render_template('catalog_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        item=item, error=error, categories=categories,
        valid_units=VALID_UNITS, valid_behaviors=VALID_BILLING_BEHAVIORS,
    )

@app.route('/<company_key>/settings/catalog/<int:item_id>/delete', methods=['POST'])
@login_required
@company_access_required
def catalog_delete(company_key, item_id):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE catalog_items
        SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (session.get('username'), item_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/settings/catalog')

# ============================================================================
# Equipment registry  (admin + manager)
#   Physical units ("Ozone #2", "Medusa #1") that each bill as a
#   per_day_equipment catalog item. Mirrors the catalog CRUD above.
# ============================================================================

def _billing_type_options(company_key):
    """per_day_equipment catalog items, for the restricted billing-type combo."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, name, category FROM catalog_items
        WHERE billing_behavior = 'per_day_equipment' AND deleted_at IS NULL
        ORDER BY name
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{'id': r['id'], 'name': r['name'], 'category': r['category']} for r in rows]

def _save_equipment_unit(company_key, unit_id):
    """Insert (unit_id is None) or update an equipment unit from request.form.
    Returns an error string, or None on success."""
    name            = request.form.get('name', '').strip()
    catalog_item_id = _opt_num(request.form.get('catalog_item_id'))
    notes           = request.form.get('notes', '').strip() or None
    is_active       = request.form.get('is_active') == 'on'

    if not name:
        return 'Equipment name is required.'
    if not catalog_item_id:
        return 'Choose a billing type from the list.'

    # Re-validate server-side: the id must still be a live per_day_equipment
    # catalog item. The combo restricts this client-side, but the client is
    # never trusted for the actual guarantee.
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id FROM catalog_items
        WHERE id = %s AND billing_behavior = 'per_day_equipment' AND deleted_at IS NULL
    """, (catalog_item_id,))
    if not cur.fetchone():
        cur.close(); conn.close()
        return 'Selected billing type is not a valid per-day equipment item.'

    username = session.get('username')
    if unit_id is None:
        cur.execute("""
            INSERT INTO equipment_units
                (name, catalog_item_id, notes, is_active, created_by, updated_by)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (name, catalog_item_id, notes, is_active, username, username))
    else:
        cur.execute("""
            UPDATE equipment_units
            SET name=%s, catalog_item_id=%s, notes=%s, is_active=%s,
                updated_at=CURRENT_TIMESTAMP, updated_by=%s
            WHERE id=%s AND deleted_at IS NULL
        """, (name, catalog_item_id, notes, is_active, username, unit_id))
    conn.commit(); cur.close(); conn.close()
    return None

@app.route('/<company_key>/settings/equipment')
@login_required
@company_access_required
@with_branding
def equipment_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT eu.id, eu.name, eu.is_active, eu.notes,
               ci.name AS billing_type_name, ci.category AS billing_type_category
        FROM equipment_units eu
        JOIN catalog_items ci ON ci.id = eu.catalog_item_id
        WHERE eu.deleted_at IS NULL
        ORDER BY eu.is_active DESC, eu.name
    """)
    units = cur.fetchall()
    cur.close(); conn.close()
    return render_template('equipment_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        units=units,
    )

@app.route('/<company_key>/settings/equipment/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def equipment_new(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    error = None
    if request.method == 'POST':
        error = _save_equipment_unit(company_key, unit_id=None)
        if not error:
            return redirect(f'/{company_key}/settings/equipment')
    billing_types = _billing_type_options(company_key)
    return render_template('equipment_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        unit=None, error=error, billing_types=billing_types,
    )

@app.route('/<company_key>/settings/equipment/<int:unit_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def equipment_edit(company_key, unit_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    if request.method == 'POST':
        error = _save_equipment_unit(company_key, unit_id=unit_id)
        if not error:
            return redirect(f'/{company_key}/settings/equipment')
    else:
        error = None
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT eu.*, ci.name AS billing_type_name, ci.category AS billing_type_category
        FROM equipment_units eu
        JOIN catalog_items ci ON ci.id = eu.catalog_item_id
        WHERE eu.id = %s AND eu.deleted_at IS NULL
    """, (unit_id,))
    unit = cur.fetchone()
    cur.close(); conn.close()
    if not unit:
        abort(404)
    billing_types = _billing_type_options(company_key)
    return render_template('equipment_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        unit=unit, error=error, billing_types=billing_types,
    )

@app.route('/<company_key>/settings/equipment/<int:unit_id>/delete', methods=['POST'])
@login_required
@company_access_required
def equipment_delete(company_key, unit_id):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE equipment_units
        SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (session.get('username'), unit_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/settings/equipment')

# ============================================================================
# Work orders  (admin + manager + office)
#   Core create/edit/list. Dispatch board, extraction queue, and reports are
#   Phase 4 items built on top of this later.
# ============================================================================

# Hardcoded per-company prefixes (configurable-later principle).
WO_NUMBER_PREFIXES = {
    'getagrip':          'GAG',
    'kleanit_charlotte': 'KC',
    'cts':               'CTS',
    'kleanit_sf':        'KSF',
}

# Office-settable statuses. On The Way / In Progress arrive with the mobile
# app; Invoiced with Phase 5; Extraction Active with the extraction queue.
WO_OFFICE_STATUSES = ('Scheduled', 'Completed', 'No Charge', 'Cancelled')

WO_JOB_SOURCES = ('Phone', 'Email', 'Website', 'Referral', 'Salesperson')
WO_PRIORITIES  = ('Normal', 'High', 'Urgent')

# Arrival time suggestions for the Brick #1 autocomplete (free text allowed;
# anything typed is parsed by _parse_arrival_time before it reaches the DB).
WO_ARRIVAL_SUGGESTIONS = [
    f'{(h - 1) % 12 + 1}:{m:02d} {"AM" if h < 12 else "PM"}'
    for h in range(6, 19) for m in (0, 30)
][:-1]  # 6:00 AM .. 6:00 PM, half-hour steps

# customer_type -> (work-site field label, prefill from service location?)
# Commercial and Contractors are interchangeable for this operation -> "Job Site".
WORK_SITE_LABELS = {
    'Multi Family': ('Unit Number', False),
    'Residential':  ('Job Address', True),
    'Commercial':   ('Job Site',    False),
    'Contractors':  ('Job Site',    False),
}

# Invoices reuse the same per-company prefixes as work orders (GAG/KC/CTS/KSF).
# The number is shared across revisions of one invoice; a void+reissue gets a
# brand-new number. See _next_invoice_number.
INVOICE_NUMBER_PREFIXES = WO_NUMBER_PREFIXES  # same mapping, one source of truth

# The lifecycle states. The DB CHECK constraint on invoices.state is the real
# guarantee; this tuple is for readable membership tests in Python.
INVOICE_STATES = ('Live', 'Hardened', 'Sent', 'Paid', 'Void', 'Revision')

# Legal transitions: from_state -> set of allowed to_states. Single source of
# truth for "what moves are possible." The transition function consults it;
# routes never hardcode their own edges. Void/Revision targets are listed so
# the map is complete, but their handlers arrive in steps 4 & 5.
INVOICE_TRANSITIONS = {
    'Live':     {'Hardened'},
    'Hardened': {'Live', 'Sent'},                       # Hardened->Live = reopen
    'Sent':     {'Live', 'Paid', 'Void', 'Revision'},   # Sent->Live = reopen
    'Paid':     {'Void', 'Revision'},                   # no reopen once paid
    'Void':     {'Live'},                               # reissue (step 4)
    'Revision': {'Live'},                               # new version (step 5)
}

# Transitions implemented in THIS step. Anything legal-but-not-here returns a
# clear "not yet implemented" so we never silently do nothing.
INVOICE_TRANSITIONS_IMPLEMENTED = {
    ('Live', 'Hardened'),
    ('Hardened', 'Live'),
    ('Hardened', 'Sent'),
    ('Sent', 'Live'),
    ('Sent', 'Paid'),
}


def _next_wo_number(cur, company_key):
    """Next per-company work order number, e.g. GAG-2026-0007.
    Sequence resets each year; the UNIQUE constraint is the real guarantee."""
    prefix = WO_NUMBER_PREFIXES.get(company_key, company_key.upper()[:3])
    year   = datetime.now().year
    like   = f'{prefix}-{year}-%'
    cur.execute("""
        SELECT work_order_number FROM work_orders
        WHERE work_order_number LIKE %s
        ORDER BY id DESC LIMIT 1
    """, (like,))
    row = cur.fetchone()
    seq = 1
    if row:
        try:
            seq = int(row['work_order_number'].rsplit('-', 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f'{prefix}-{year}-{seq:04d}'

def _next_invoice_number(cur, company_key):
    """Next per-company invoice number, e.g. GAG-2026-0007.
    Sequence resets each year; the UNIQUE(invoice_number, revision_number)
    constraint is the real guarantee. Only original rows (revision_number = 1)
    advance the sequence — revisions reuse their parent's number."""
    prefix = INVOICE_NUMBER_PREFIXES.get(company_key, company_key.upper()[:3])
    year   = datetime.now().year
    like   = f'{prefix}-{year}-%'
    cur.execute("""
        SELECT invoice_number FROM invoices
        WHERE invoice_number LIKE %s AND revision_number = 1
        ORDER BY id DESC LIMIT 1
    """, (like,))
    row = cur.fetchone()
    seq = 1
    if row:
        try:
            seq = int(row['invoice_number'].rsplit('-', 1)[1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f'{prefix}-{year}-{seq:04d}'


def _compute_invoice_tax(cur, invoice_id):
    """Resolve and total the tax for an invoice from its CURRENT county rate.
    Returns (tax_rate_pct, subtotal, tax_total, total).

    Reads the live tax_rates table — this is the freeze-at-harden read. Once
    the caller writes these onto the invoice, later edits to tax_rates never
    change this invoice (Pattern 4: effective-time pinning). A county with no
    row resolves to 0% (a valid un-taxed invoice, e.g. Florida) rather than
    failing; the absence shows as tax_rate_pct = None for optional flagging."""
    cur.execute("""
        SELECT tax_county FROM invoices WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        return None, None, None, None
    county = inv['tax_county']

    cur.execute("""
        SELECT
            COALESCE(SUM(total), 0)                            AS subtotal,
            COALESCE(SUM(total) FILTER (WHERE is_taxable), 0)  AS taxable_base
        FROM invoice_line_items
        WHERE invoice_id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    sums = cur.fetchone()
    subtotal     = sums['subtotal']
    taxable_base = sums['taxable_base']

    rate_pct = None
    if county:
        cur.execute("""
            SELECT total_pct FROM tax_rates
            WHERE county = %s AND is_active = TRUE AND deleted_at IS NULL
        """, (county,))
        r = cur.fetchone()
        if r:
            rate_pct = r['total_pct']

    effective_rate = rate_pct if rate_pct is not None else 0
    tax_total = (taxable_base * effective_rate) / 100
    total     = subtotal + tax_total
    return rate_pct, subtotal, tax_total, total


def _resolve_equipment_labels(cur, invoice_id):
    """Single source of truth for per_day_equipment line labels on an invoice.

    Groups the invoice's per_day_equipment lines by billing type
    (catalog_item_id), orders each group by (deployed_at ASC, line id ASC),
    and applies the ordinal rule:
      * group of 1  -> bare customer label ("Set Dehu", no number)
      * group of N  -> "Set Dehu 1" .. "Set Dehu N"
    The ordinal is the Nth machine of that TYPE on THIS invoice — never the
    registry unit identity (equipment_unit.name stays internal and unshown).

    Customer-facing base text is catalog_items.invoice_label, falling back to
    catalog_items.name when invoice_label is unset.

    Returns {line_item_id: resolved_label}. Used both for live rendering
    (derive fresh every time, so edits renumber cleanly 1..N with no stale
    gaps) and for baking the frozen snapshot at harden — same logic both ways,
    so a live preview and the hardened print can never disagree.

    Non-equipment lines are simply absent from the returned map; callers render
    those from their own description as usual.
    """
    cur.execute("""
        SELECT ili.id,
               ili.catalog_item_id,
               ili.deployed_at,
               COALESCE(ci.invoice_label, ci.name) AS base_label
        FROM invoice_line_items ili
        JOIN catalog_items ci ON ci.id = ili.catalog_item_id
        WHERE ili.invoice_id = %s
          AND ili.deleted_at IS NULL
          AND ci.billing_behavior = 'per_day_equipment'
        ORDER BY ili.catalog_item_id,
                 ili.deployed_at ASC NULLS LAST,
                 ili.id ASC
    """, (invoice_id,))
    rows = cur.fetchall()

    # Bucket by billing type, preserving the ORDER BY sequence within each type.
    groups = {}
    for r in rows:
        groups.setdefault(r['catalog_item_id'], []).append(r)

    labels = {}
    for _cat_id, members in groups.items():
        n = len(members)
        for idx, m in enumerate(members, start=1):
            base = m['base_label']
            labels[m['id']] = base if n == 1 else f'{base} {idx}'
    return labels


def transition_invoice(cur, company_key, invoice_id, to_state, username, notes=None):
    """Move one invoice to to_state: the single choke point for every invoice
    state change. Validates legality + guards, runs the state's side effects,
    and appends an invoice_status_history row. Does NOT commit — the calling
    route owns the transaction (same convention as the work-order save path).
    Returns (True, None) on success or (False, "human reason") on rejection."""
    if to_state not in INVOICE_STATES:
        return False, f'Unknown target state "{to_state}".'

    cur.execute("""
        SELECT id, state, amount_paid, invoice_number, revision_number
        FROM invoices
        WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        return False, 'Invoice not found.'

    from_state = inv['state']
    if from_state == to_state:
        return False, f'Invoice is already {to_state}.'

    # (a) Legality: is this edge allowed at all?
    if to_state not in INVOICE_TRANSITIONS.get(from_state, set()):
        return False, f'Cannot move an invoice from {from_state} to {to_state}.'

    # Implemented-in-this-step gate (honest partial build).
    if (from_state, to_state) not in INVOICE_TRANSITIONS_IMPLEMENTED:
        return False, (f'{from_state} -> {to_state} is a valid transition but '
                       f'is not implemented yet.')

    # (b) Guards.
    is_reopen = (to_state == 'Live')
    if is_reopen:
        # THE governing guard: once any payment attaches, reopen is gone. This
        # prevents a payment application from ever being orphaned by an in-place
        # edit. amount_paid > 0 is the trip wire.
        if inv['amount_paid'] and inv['amount_paid'] > 0:
            return False, ('This invoice has a payment applied and can no longer '
                           'be reopened. Use Void or Revision to correct it.')

    # (c) State-specific side effects.
    history_note = notes

    if to_state == 'Hardened':
        # Freeze tax from the CURRENT county rate. After this write the invoice
        # total is pinned regardless of later tax_rates edits.
        rate_pct, subtotal, tax_total, total = _compute_invoice_tax(cur, invoice_id)
        cur.execute("""
            UPDATE invoices
            SET subtotal = %s, tax_rate_pct = %s, tax_total = %s, total = %s,
                hardened_at = CURRENT_TIMESTAMP, hardened_by = %s,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (subtotal, rate_pct, tax_total, total, username, username, invoice_id))
        # Bake equipment-ordinal labels into the frozen snapshot so a reprint
        # years later is byte-identical (same freeze discipline as the tax rate).
        # Derived from the SAME resolver used for live rendering, so preview and
        # print never disagree.
        for _li_id, _label in _resolve_equipment_labels(cur, invoice_id).items():
            cur.execute("""
                UPDATE invoice_line_items
                SET resolved_label = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE id = %s
            """, (_label, username, _li_id))

    elif to_state == 'Sent':
        cur.execute("""
            UPDATE invoices
            SET sent_at = CURRENT_TIMESTAMP, sent_by = %s,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, username, invoice_id))

    elif to_state == 'Paid':
        # This step marks the state only. Recording the actual payment amount
        # (which sets amount_paid and thereby closes the reopen gate) is the
        # payment-recording increment. Marking Paid here is the state flip.
        cur.execute("""
            UPDATE invoices
            SET updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, invoice_id))

    elif to_state == 'Live':  # reopen
        # Read frozen figures BEFORE clearing, to preserve them in the audit
        # trail (the "always keep it referenceable" decision).
        cur.execute("""
            SELECT tax_rate_pct, tax_total, total FROM invoices WHERE id = %s
        """, (invoice_id,))
        prior = cur.fetchone()
        if prior and prior['total'] is not None:
            prior_bit = (f'Prior frozen total: ${prior["total"]:.2f} '
                         f'(tax ${prior["tax_total"] or 0:.2f} '
                         f'@ {prior["tax_rate_pct"] or 0}%).')
            history_note = f'{notes + " " if notes else ""}{prior_bit}'
        # Clear frozen values — Live means not-yet-determined.
        cur.execute("""
            UPDATE invoices
            SET tax_rate_pct = NULL, tax_total = NULL, total = NULL,
                hardened_at = NULL, hardened_by = NULL,
                sent_at = NULL, sent_by = NULL,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, invoice_id))

    # Flip the state itself (all paths).
    cur.execute("""
        UPDATE invoices SET state = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (to_state, username, invoice_id))

    # (d) Append history. Always, on every real transition.
    cur.execute("""
        INSERT INTO invoice_status_history (invoice_id, state, changed_by, notes)
        VALUES (%s, %s, %s, %s)
    """, (invoice_id, to_state, username,
          history_note or f'Changed from {from_state}'))

    return True, None



def _parse_arrival_time(raw):
    """Normalize a typed arrival time ('8:15 am', '815', '8', '14:30') to
    'HH:MM' 24-hour for the TIME column. Returns (value, error)."""
    s = raw.strip().upper().replace('.', '')
    if not s:
        return None, None
    # '815' / '0815' -> '8:15'
    if s.isdigit() and len(s) in (3, 4):
        s = s[:-2] + ':' + s[-2:]
    for fmt in ('%I:%M %p', '%I:%M%p', '%I %p', '%I%p', '%H:%M', '%H'):
        try:
            return datetime.strptime(s, fmt).strftime('%H:%M'), None
        except ValueError:
            continue
    return None, f'Arrival time "{raw}" could not be read — try a format like 8:30 AM.'

def _wo_form_data(company_key):
    """Everything the work order form needs embedded: standard catalog items,
    equipment units (joined to their billing type/rate), and technicians."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, name, category, unit_price, unit_of_measure,
               default_description, estimated_minutes, is_taxable, is_catch_all,
               minimum_quantity, billing_increment
        FROM catalog_items
        WHERE billing_behavior = 'standard' AND is_active = TRUE AND deleted_at IS NULL
        ORDER BY sort_order, name
    """)
    catalog_std = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT eu.id, eu.name, ci.id AS catalog_item_id, ci.name AS billing_type_name,
               ci.category, ci.unit_price AS daily_rate, ci.is_taxable
        FROM equipment_units eu
        JOIN catalog_items ci ON ci.id = eu.catalog_item_id
        WHERE eu.is_active = TRUE AND eu.deleted_at IS NULL
          AND ci.deleted_at IS NULL
        ORDER BY eu.name
    """)
    equipment = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT username, full_name FROM users
        WHERE role = 'technician' AND is_active = TRUE
        ORDER BY full_name
    """)
    techs = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    # NUMERIC comes back as Decimal — make everything JSON-safe for tojson.
    for c in catalog_std:
        for k in ('unit_price', 'minimum_quantity', 'billing_increment'):
            if c.get(k) is not None:
                c[k] = float(c[k])
    for e in equipment:
        if e.get('daily_rate') is not None:
            e['daily_rate'] = float(e['daily_rate'])
    return catalog_std, equipment, techs

def _load_wo_customers(company_key):
    """Active customers for the customer combobox (id, name, type)."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, property_name AS name, customer_type AS category
        FROM customers
        WHERE deleted_at IS NULL AND status = 'Active'
        ORDER BY property_name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return rows

def _parse_wo_line_items(company_key, raw_json):
    """Parse and validate the line_items_json blob from the form.
    Returns (lines, error). Totals/quantities are always computed server-side.
    Line dict shapes:
      standard:  {id?, kind:'std', catalog_item_id, description, quantity, unit_price}
      equipment: {id?, kind:'eq',  equipment_unit_id, description, deployed_at, retrieved_at}
    """
    try:
        submitted = json.loads(raw_json or '[]')
    except (ValueError, TypeError):
        return None, 'Line items could not be read. Refresh and try again.'
    if not isinstance(submitted, list):
        return None, 'Line items could not be read. Refresh and try again.'
    if len(submitted) == 0:
        return None, 'A work order needs at least one line item.'

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    lines = []
    try:
        for idx, item in enumerate(submitted, start=1):
            kind = item.get('kind')
            line_id = item.get('id') or None

            if kind == 'std':
                catalog_item_id = item.get('catalog_item_id')
                cur.execute("""
                    SELECT id, name, unit_price, cost, is_taxable, is_catch_all,
                           minimum_quantity, billing_increment
                    FROM catalog_items
                    WHERE id = %s AND billing_behavior = 'standard' AND deleted_at IS NULL
                """, (catalog_item_id,))
                cat = cur.fetchone()
                if not cat:
                    return None, f'Line {idx}: pick a service from the catalog.'
                description = (item.get('description') or '').strip()
                if cat['is_catch_all'] and not description:
                    return None, f'Line {idx}: Custom Service requires a description.'
                try:
                    quantity   = float(item.get('quantity'))
                    unit_price = float(item.get('unit_price'))
                except (TypeError, ValueError):
                    return None, f'Line {idx}: quantity and price must be numbers.'
                if quantity <= 0:
                    return None, f'Line {idx}: quantity must be greater than zero.'
                if unit_price < 0:
                    return None, f'Line {idx}: price cannot be negative.'
                # Catalog minimum + rounding increment (water extraction service).
                if cat['minimum_quantity'] is not None:
                    quantity = max(quantity, float(cat['minimum_quantity']))
                if cat['billing_increment'] is not None:
                    inc = float(cat['billing_increment'])
                    if inc > 0:
                        quantity = math.ceil(round(quantity / inc, 6)) * inc
                total = round(quantity * unit_price, 2)
                lines.append({
                    'id': line_id, 'catalog_item_id': cat['id'],
                    'equipment_unit_id': None, 'description': description or None,
                    'quantity': quantity, 'unit_price': unit_price, 'total': total,
                    'cost': cat['cost'], 'is_taxable': cat['is_taxable'],
                    'deployed_at': None, 'retrieved_at': None,
                })

            elif kind == 'eq':
                equipment_unit_id = item.get('equipment_unit_id')
                cur.execute("""
                    SELECT eu.id, eu.name, ci.id AS catalog_item_id,
                           ci.unit_price AS daily_rate, ci.cost, ci.is_taxable
                    FROM equipment_units eu
                    JOIN catalog_items ci ON ci.id = eu.catalog_item_id
                    WHERE eu.id = %s AND eu.deleted_at IS NULL
                      AND ci.billing_behavior = 'per_day_equipment' AND ci.deleted_at IS NULL
                """, (equipment_unit_id,))
                eq = cur.fetchone()
                if not eq:
                    return None, f'Line {idx}: pick a unit from the equipment registry.'
                deployed_at  = (item.get('deployed_at') or '').strip() or None
                retrieved_at = (item.get('retrieved_at') or '').strip() or None
                if not deployed_at:
                    return None, f'Line {idx}: equipment needs a deployed date.'
                quantity = None
                total    = None
                if retrieved_at:
                    try:
                        d0 = datetime.strptime(deployed_at, '%Y-%m-%d').date()
                        d1 = datetime.strptime(retrieved_at, '%Y-%m-%d').date()
                    except ValueError:
                        return None, f'Line {idx}: dates could not be read.'
                    if d1 < d0:
                        return None, f'Line {idx}: retrieved date is before deployed date.'
                    quantity = max((d1 - d0).days, 1)   # same-day set-and-pull bills 1 day
                    total    = round(quantity * float(eq['daily_rate']), 2)
                description = (item.get('description') or '').strip() or eq['name']
                lines.append({
                    'id': line_id, 'catalog_item_id': eq['catalog_item_id'],
                    'equipment_unit_id': eq['id'], 'description': description,
                    'quantity': quantity, 'unit_price': float(eq['daily_rate']),
                    'total': total, 'cost': eq['cost'], 'is_taxable': eq['is_taxable'],
                    'deployed_at': deployed_at, 'retrieved_at': retrieved_at,
                })
            else:
                return None, f'Line {idx}: unknown line type.'
    finally:
        cur.close(); conn.close()
    return lines, None

def _save_work_order(company_key, wo_id):
    """Insert (wo_id is None) or update a work order + line items + techs +
    status history from request.form. Returns (wo_id, error)."""
    customer_id         = _opt_num(request.form.get('customer_id'))
    service_location_id = _opt_num(request.form.get('service_location_id'))
    primary_contact_id  = _opt_num(request.form.get('primary_contact_id'))
    status              = request.form.get('status', 'Scheduled')
    work_site_label     = request.form.get('work_site_label', '').strip() or None
    auto_description    = request.form.get('auto_description', '').strip() or None
    occ_vac             = request.form.get('description_occ_vac') or None
    am_pm               = request.form.get('description_am_pm') or None
    gated               = request.form.get('description_gated') == 'on'
    followup            = request.form.get('description_followup') == 'on'
    special_notes       = request.form.get('description_special_notes', '').strip() or None
    internal_notes      = request.form.get('internal_notes', '').strip() or None
    notes_for_techs     = request.form.get('notes_for_techs', '').strip() or None
    po_number           = request.form.get('po_number', '').strip() or None
    job_source          = request.form.get('job_source') or None
    priority            = request.form.get('priority', 'Normal')
    start_date          = request.form.get('start_date', '').strip() or None
    end_date            = request.form.get('end_date', '').strip() or None
    arrival_start       = request.form.get('arrival_window_start', '').strip() or None
    arrival_end         = request.form.get('arrival_window_end', '').strip() or None
    est_duration        = _opt_num(request.form.get('estimated_duration_hours'))
    assigned_techs      = request.form.getlist('assigned_techs')

    if not customer_id:
        return None, 'Pick a customer from the list.'
    if status not in WO_OFFICE_STATUSES:
        return None, 'Invalid status.'
    if priority not in WO_PRIORITIES:
        return None, 'Invalid priority.'
    if job_source and job_source not in WO_JOB_SOURCES:
        return None, 'Invalid job source.'
    if occ_vac and occ_vac not in ('OCC', 'VAC'):
        return None, 'Invalid occupancy value.'
    if am_pm and am_pm not in ('AM', 'PM'):
        return None, 'Invalid AM/PM value.'
    if not start_date:
        return None, 'A start date is required.'
    arrival_start, time_err = _parse_arrival_time(arrival_start or '')
    if time_err:
        return None, time_err

    lines, line_error = _parse_wo_line_items(company_key, request.form.get('line_items_json'))
    if line_error:
        return None, line_error

    username = session.get('username')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    try:
        # Validate customer + location + contact belong together.
        cur.execute("SELECT id, customer_type FROM customers WHERE id = %s AND deleted_at IS NULL",
                    (customer_id,))
        cust = cur.fetchone()
        if not cust:
            return None, 'Pick a customer from the list.'
        tax_county = None
        if service_location_id:
            cur.execute("""
                SELECT id, county FROM service_locations
                WHERE id = %s AND customer_id = %s AND deleted_at IS NULL
            """, (service_location_id, customer_id))
            loc = cur.fetchone()
            if not loc:
                return None, 'Service location does not belong to that customer.'
            tax_county = loc['county']
        if primary_contact_id:
            cur.execute("""
                SELECT id FROM customer_contacts
                WHERE id = %s AND customer_id = %s
            """, (primary_contact_id, customer_id))
            if not cur.fetchone():
                return None, 'Contact does not belong to that customer.'

        prev_status = None
        if wo_id is None:
            wo_number = _next_wo_number(cur, company_key)
            cur.execute("""
                INSERT INTO work_orders
                    (work_order_number, customer_id, service_location_id, primary_contact_id,
                     status, work_site_label, auto_description,
                     description_occ_vac, description_am_pm, description_gated,
                     description_followup, description_special_notes,
                     internal_notes, notes_for_techs, po_number, job_source, priority,
                     start_date, end_date, arrival_window_start, arrival_window_end,
                     estimated_duration_hours, created_by, updated_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (wo_number, customer_id, service_location_id, primary_contact_id,
                  status, work_site_label, auto_description,
                  occ_vac, am_pm, gated, followup, special_notes,
                  internal_notes, notes_for_techs, po_number, job_source, priority,
                  start_date, end_date, arrival_start, arrival_end,
                  est_duration, username, username))
            wo_id = cur.fetchone()['id']
        else:
            cur.execute("""
                SELECT status FROM work_orders WHERE id = %s AND deleted_at IS NULL
            """, (wo_id,))
            existing = cur.fetchone()
            if not existing:
                return None, 'Work order not found.'
            prev_status = existing['status']
            cur.execute("""
                UPDATE work_orders
                SET customer_id=%s, service_location_id=%s, primary_contact_id=%s,
                    status=%s, work_site_label=%s, auto_description=%s,
                    description_occ_vac=%s, description_am_pm=%s, description_gated=%s,
                    description_followup=%s, description_special_notes=%s,
                    internal_notes=%s, notes_for_techs=%s, po_number=%s,
                    job_source=%s, priority=%s,
                    start_date=%s, end_date=%s,
                    arrival_window_start=%s, arrival_window_end=%s,
                    estimated_duration_hours=%s,
                    updated_at=CURRENT_TIMESTAMP, updated_by=%s
                WHERE id=%s AND deleted_at IS NULL
            """, (customer_id, service_location_id, primary_contact_id,
                  status, work_site_label, auto_description,
                  occ_vac, am_pm, gated, followup, special_notes,
                  internal_notes, notes_for_techs, po_number, job_source, priority,
                  start_date, end_date, arrival_start, arrival_end,
                  est_duration, username, wo_id))

        # ---- Line items: update by id, insert new, soft-delete missing. ----
        cur.execute("""
            SELECT id FROM work_order_line_items
            WHERE work_order_id = %s AND deleted_at IS NULL
        """, (wo_id,))
        existing_ids  = {r['id'] for r in cur.fetchall()}
        submitted_ids = set()
        for sort_order, ln in enumerate(lines):
            if ln['id'] and int(ln['id']) in existing_ids:
                lid = int(ln['id'])
                submitted_ids.add(lid)
                cur.execute("""
                    UPDATE work_order_line_items
                    SET catalog_item_id=%s, equipment_unit_id=%s, description=%s,
                        quantity=%s, unit_price=%s, total=%s, cost=%s, is_taxable=%s,
                        tax_county=%s, deployed_at=%s, retrieved_at=%s, sort_order=%s,
                        updated_at=CURRENT_TIMESTAMP, updated_by=%s
                    WHERE id=%s AND work_order_id=%s AND deleted_at IS NULL
                """, (ln['catalog_item_id'], ln['equipment_unit_id'], ln['description'],
                      ln['quantity'], ln['unit_price'], ln['total'], ln['cost'],
                      ln['is_taxable'], tax_county, ln['deployed_at'], ln['retrieved_at'],
                      sort_order, username, lid, wo_id))
            else:
                cur.execute("""
                    INSERT INTO work_order_line_items
                        (work_order_id, catalog_item_id, equipment_unit_id, description,
                         quantity, unit_price, total, cost, is_taxable, tax_county,
                         deployed_at, retrieved_at, sort_order, created_by, updated_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (wo_id, ln['catalog_item_id'], ln['equipment_unit_id'], ln['description'],
                      ln['quantity'], ln['unit_price'], ln['total'], ln['cost'],
                      ln['is_taxable'], tax_county, ln['deployed_at'], ln['retrieved_at'],
                      sort_order, username, username))
        removed = existing_ids - submitted_ids
        if removed:
            cur.execute("""
                UPDATE work_order_line_items
                SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
                WHERE id = ANY(%s) AND work_order_id = %s
            """, (username, list(removed), wo_id))

        # ---- Techs: replace assignments (join table, hard replace). ----
        cur.execute("DELETE FROM work_order_techs WHERE work_order_id = %s", (wo_id,))
        for tech in assigned_techs:
            tech = tech.strip()
            if tech:
                cur.execute("""
                    INSERT INTO work_order_techs (work_order_id, username)
                    VALUES (%s, %s)
                    ON CONFLICT (work_order_id, username) DO NOTHING
                """, (wo_id, tech))

        # ---- Status history: on create, or on status change. ----
        if prev_status is None or prev_status != status:
            cur.execute("""
                INSERT INTO work_order_status_history
                    (work_order_id, status, changed_by, notes)
                VALUES (%s, %s, %s, %s)
            """, (wo_id, status,  username,
                  'Created' if prev_status is None else f'Changed from {prev_status}'))

        conn.commit()
        return wo_id, None
    finally:
        cur.close(); conn.close()

@app.route('/<company_key>/workorders')
@login_required
@company_access_required
@with_branding
def workorder_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    search        = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    conditions = ["wo.deleted_at IS NULL"]
    params     = []
    if search:
        conditions.append("""(wo.work_order_number ILIKE %s
                              OR c.property_name ILIKE %s
                              OR wo.work_site_label ILIKE %s)""")
        params.extend([f'%{search}%'] * 3)
    if status_filter:
        conditions.append("wo.status = %s")
        params.append(status_filter)
    where = " AND ".join(conditions)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT wo.id, wo.work_order_number, wo.status, wo.priority,
               wo.work_site_label, wo.start_date,
               c.property_name AS customer_name,
               (SELECT COALESCE(SUM(li.total), 0)
                FROM work_order_line_items li
                WHERE li.work_order_id = wo.id AND li.deleted_at IS NULL) AS order_total,
               (SELECT COUNT(*)
                FROM work_order_line_items li
                WHERE li.work_order_id = wo.id AND li.deleted_at IS NULL
                  AND li.equipment_unit_id IS NOT NULL
                  AND li.retrieved_at IS NULL) AS accruing_count
        FROM work_orders wo
        JOIN customers c ON c.id = wo.customer_id
        WHERE {where}
        ORDER BY wo.start_date DESC NULLS LAST, wo.id DESC
        LIMIT 200
    """, params)
    workorders = cur.fetchall()
    cur.execute(f"""
        SELECT COUNT(*) AS count
        FROM work_orders wo JOIN customers c ON c.id = wo.customer_id
        WHERE {where}
    """, params)
    total = cur.fetchone()['count']
    cur.close(); conn.close()
    return render_template('workorder_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        workorders=workorders, total=total,
        search=search, status_filter=status_filter,
        statuses=WO_OFFICE_STATUSES,
    )

@app.route('/<company_key>/workorders/search')
@login_required
@company_access_required
def workorders_search(company_key):
    """JSON endpoint for live work order search — mirrors customers_search."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    search        = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    conditions = ["wo.deleted_at IS NULL"]
    params     = []
    if search:
        conditions.append("""(wo.work_order_number ILIKE %s
                              OR c.property_name ILIKE %s
                              OR wo.work_site_label ILIKE %s)""")
        params.extend([f'%{search}%'] * 3)
    if status_filter:
        conditions.append("wo.status = %s")
        params.append(status_filter)
    where = " AND ".join(conditions)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT wo.id, wo.work_order_number, wo.status, wo.priority,
               wo.work_site_label, wo.start_date::text AS start_date,
               c.property_name AS customer_name,
               (SELECT COALESCE(SUM(li.total), 0)
                FROM work_order_line_items li
                WHERE li.work_order_id = wo.id AND li.deleted_at IS NULL)::float AS order_total,
               (SELECT COUNT(*)
                FROM work_order_line_items li
                WHERE li.work_order_id = wo.id AND li.deleted_at IS NULL
                  AND li.equipment_unit_id IS NOT NULL
                  AND li.retrieved_at IS NULL)::int AS accruing_count
        FROM work_orders wo
        JOIN customers c ON c.id = wo.customer_id
        WHERE {where}
        ORDER BY wo.start_date DESC NULLS LAST, wo.id DESC
        LIMIT 200
    """, params)
    rows = cur.fetchall()
    cur.execute(f"""
        SELECT COUNT(*) AS count
        FROM work_orders wo JOIN customers c ON c.id = wo.customer_id
        WHERE {where}
    """, params)
    total = cur.fetchone()['count']
    cur.close(); conn.close()
    return jsonify({'total': total, 'workorders': rows})

@app.route('/<company_key>/workorders/customer/<int:customer_id>/context')
@login_required
@company_access_required
def workorder_customer_context(company_key, customer_id):
    """JSON: everything the form needs after a customer is picked — type-driven
    work-site label + prefill flag, service locations, contacts."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, property_name, customer_type FROM customers
        WHERE id = %s AND deleted_at IS NULL
    """, (customer_id,))
    cust = cur.fetchone()
    if not cust:
        cur.close(); conn.close()
        abort(404)
    label, prefill = WORK_SITE_LABELS.get(cust['customer_type'], ('Work Site', False))
    cur.execute("""
        SELECT id, location_name, address, city, state, is_primary
        FROM service_locations
        WHERE customer_id = %s AND deleted_at IS NULL
        ORDER BY is_primary DESC, location_name NULLS LAST, address
    """, (customer_id,))
    locations = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT id, first_name, last_name, title
        FROM customer_contacts
        WHERE customer_id = %s
        ORDER BY last_name, first_name
    """, (customer_id,))
    contacts = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify({
        'customer_type': cust['customer_type'],
        'site_label': label,
        'site_prefill_from_location': prefill,
        'locations': locations,
        'contacts': contacts,
    })

@app.route('/<company_key>/workorders/dupe_check')
@login_required
@company_access_required
def workorder_dupe_check(company_key):
    """Double-booking detection: same customer + service location + normalized
    work_site_label, dated within the last 4 weeks or any time in the future.
    Non-blocking — the form shows a banner, staff decide."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    customer_id         = _opt_num(request.args.get('customer_id'))
    service_location_id = _opt_num(request.args.get('service_location_id'))
    site                = (request.args.get('site') or '').strip()
    exclude_id          = _opt_num(request.args.get('exclude_id'))
    if not customer_id or not site:
        return jsonify({'matches': []})

    params = [customer_id, site]
    loc_clause = "service_location_id IS NULL" if not service_location_id \
                 else "service_location_id = %s"
    if service_location_id:
        params.append(service_location_id)
    exclude_clause = ""
    if exclude_id:
        exclude_clause = "AND id <> %s"
        params.append(exclude_id)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute(f"""
        SELECT id, work_order_number, work_site_label, status,
               start_date::text AS start_date
        FROM work_orders
        WHERE deleted_at IS NULL
          AND customer_id = %s
          AND lower(regexp_replace(work_site_label, '[^a-zA-Z0-9]', '', 'g')) =
              lower(regexp_replace(%s,              '[^a-zA-Z0-9]', '', 'g'))
          AND {loc_clause}
          {exclude_clause}
          AND status NOT IN ('Cancelled')
          AND (start_date IS NULL OR start_date >= CURRENT_DATE - INTERVAL '28 days')
        ORDER BY start_date DESC NULLS LAST
        LIMIT 5
    """, params)
    matches = cur.fetchall()
    cur.close(); conn.close()
    return jsonify({'matches': matches})

@app.route('/<company_key>/workorders/<int:wo_id>')
@login_required
@company_access_required
@with_branding
def workorder_detail(company_key, wo_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT wo.*, wo.start_date::text AS start_date, wo.end_date::text AS end_date,
               to_char(wo.arrival_window_start, 'HH12:MI AM') AS arrival_time,
               to_char(wo.created_at, 'Mon DD, YYYY HH12:MI AM') AS created_at_display,
               c.property_name AS customer_name, c.customer_type,
               sl.location_name, sl.address AS location_address,
               sl.city AS location_city, sl.state AS location_state,
               cc.first_name AS contact_first, cc.last_name AS contact_last,
               cc.title AS contact_title
        FROM work_orders wo
        JOIN customers c ON c.id = wo.customer_id
        LEFT JOIN service_locations sl ON sl.id = wo.service_location_id
        LEFT JOIN customer_contacts cc ON cc.id = wo.primary_contact_id
        WHERE wo.id = %s AND wo.deleted_at IS NULL
    """, (wo_id,))
    wo = cur.fetchone()
    if not wo:
        cur.close(); conn.close()
        abort(404)
    label, _ = WORK_SITE_LABELS.get(wo['customer_type'], ('Work Site', False))
    cur.execute("""
        SELECT li.description, li.quantity::float AS quantity,
               li.unit_price::float AS unit_price, li.total::float AS total,
               li.deployed_at::text AS deployed_at, li.retrieved_at::text AS retrieved_at,
               li.equipment_unit_id,
               ci.name AS catalog_name, ci.billing_behavior, ci.unit_of_measure,
               eu.name AS equipment_name
        FROM work_order_line_items li
        JOIN catalog_items ci ON ci.id = li.catalog_item_id
        LEFT JOIN equipment_units eu ON eu.id = li.equipment_unit_id
        WHERE li.work_order_id = %s AND li.deleted_at IS NULL
        ORDER BY li.sort_order, li.id
    """, (wo_id,))
    line_items = cur.fetchall()
    subtotal = sum(li['total'] for li in line_items if li['total'] is not None)
    accruing = [li for li in line_items
                if li['equipment_unit_id'] and not li['retrieved_at']]
    cur.execute("""
        SELECT wt.username, COALESCE(u.full_name, wt.username) AS full_name
        FROM work_order_techs wt
        LEFT JOIN users u ON u.username = wt.username
        WHERE wt.work_order_id = %s
        ORDER BY full_name
    """, (wo_id,))
    techs = cur.fetchall()
    cur.execute("""
        SELECT status, extraction_status, changed_by, notes,
               to_char(changed_at, 'Mon DD, YYYY HH12:MI AM') AS changed_at_display
        FROM work_order_status_history
        WHERE work_order_id = %s
        ORDER BY changed_at DESC, id DESC
    """, (wo_id,))
    history = cur.fetchall()
    cur.close(); conn.close()
    return render_template('workorder_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        wo=wo, site_label=label, line_items=line_items, subtotal=subtotal,
        accruing=accruing, techs=techs, history=history,
    )

@app.route('/<company_key>/workorders/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def workorder_new(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    error = None
    if request.method == 'POST':
        new_id, error = _save_work_order(company_key, wo_id=None)
        if not error:
            return redirect(f'/{company_key}/workorders')
    catalog_std, equipment, techs = _wo_form_data(company_key)
    customers = _load_wo_customers(company_key)
    return render_template('workorder_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        wo=None, line_items=[], wo_techs=[], error=error,
        customers=customers, catalog_std=catalog_std, equipment=equipment,
        techs=techs, statuses=WO_OFFICE_STATUSES,
        job_sources=WO_JOB_SOURCES, priorities=WO_PRIORITIES,
        arrival_suggestions=WO_ARRIVAL_SUGGESTIONS,
        site_labels=WORK_SITE_LABELS,
    )

@app.route('/<company_key>/workorders/<int:wo_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def workorder_edit(company_key, wo_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    error = None
    if request.method == 'POST':
        _, error = _save_work_order(company_key, wo_id=wo_id)
        if not error:
            return redirect(f'/{company_key}/workorders')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT wo.*, c.property_name AS customer_name, c.customer_type,
               wo.start_date::text AS start_date, wo.end_date::text AS end_date,
               to_char(wo.arrival_window_start, 'FMHH12:MI AM') AS arrival_window_start,
               wo.arrival_window_end::text AS arrival_window_end
        FROM work_orders wo
        JOIN customers c ON c.id = wo.customer_id
        WHERE wo.id = %s AND wo.deleted_at IS NULL
    """, (wo_id,))
    wo = cur.fetchone()
    if not wo:
        cur.close(); conn.close()
        abort(404)
    cur.execute("""
        SELECT li.id, li.catalog_item_id, li.equipment_unit_id, li.description,
               li.quantity::float AS quantity, li.unit_price::float AS unit_price,
               li.total::float AS total, li.is_taxable,
               li.deployed_at::text AS deployed_at, li.retrieved_at::text AS retrieved_at,
               ci.name AS catalog_name, ci.billing_behavior,
               eu.name AS equipment_name
        FROM work_order_line_items li
        JOIN catalog_items ci ON ci.id = li.catalog_item_id
        LEFT JOIN equipment_units eu ON eu.id = li.equipment_unit_id
        WHERE li.work_order_id = %s AND li.deleted_at IS NULL
        ORDER BY li.sort_order, li.id
    """, (wo_id,))
    line_items = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT username FROM work_order_techs WHERE work_order_id = %s
    """, (wo_id,))
    wo_techs = [r['username'] for r in cur.fetchall()]
    cur.close(); conn.close()
    catalog_std, equipment, techs = _wo_form_data(company_key)
    customers = _load_wo_customers(company_key)
    # Merge in anything this WO already references that the active-only option
    # lists don't contain (retired units, deactivated items, inactive customers).
    # Without this, the restricted combobox would silently clear them on edit.
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    missing_cats = ({li['catalog_item_id'] for li in line_items
                     if li['billing_behavior'] == 'standard'}
                    - {c['id'] for c in catalog_std})
    if missing_cats:
        cur.execute("""
            SELECT id, name, category, unit_price::float AS unit_price,
                   unit_of_measure, default_description, estimated_minutes,
                   is_taxable, is_catch_all,
                   minimum_quantity::float AS minimum_quantity,
                   billing_increment::float AS billing_increment
            FROM catalog_items WHERE id = ANY(%s)
        """, (list(missing_cats),))
        catalog_std.extend(dict(r) for r in cur.fetchall())
    missing_eq = ({li['equipment_unit_id'] for li in line_items
                   if li['equipment_unit_id']}
                  - {e['id'] for e in equipment})
    if missing_eq:
        cur.execute("""
            SELECT eu.id, eu.name, ci.id AS catalog_item_id,
                   ci.name AS billing_type_name, ci.category,
                   ci.unit_price::float AS daily_rate, ci.is_taxable
            FROM equipment_units eu
            JOIN catalog_items ci ON ci.id = eu.catalog_item_id
            WHERE eu.id = ANY(%s)
        """, (list(missing_eq),))
        equipment.extend(dict(r) for r in cur.fetchall())
    cur.close(); conn.close()
    if wo['customer_id'] not in {c['id'] for c in customers}:
        customers.append({'id': wo['customer_id'], 'name': wo['customer_name'],
                          'category': wo['customer_type']})
    return render_template('workorder_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        wo=wo, line_items=line_items, wo_techs=wo_techs, error=error,
        customers=customers, catalog_std=catalog_std, equipment=equipment,
        techs=techs, statuses=WO_OFFICE_STATUSES,
        job_sources=WO_JOB_SOURCES, priorities=WO_PRIORITIES,
        arrival_suggestions=WO_ARRIVAL_SUGGESTIONS,
        site_labels=WORK_SITE_LABELS,
    )

@app.route('/<company_key>/workorders/<int:wo_id>/delete', methods=['POST'])
@login_required
@company_access_required
def workorder_delete(company_key, wo_id):
    if session.get('user_role') not in ('admin', 'manager'):
        abort(403)
    username = session.get('username')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE work_orders
        SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (username, wo_id))
    cur.execute("""
        UPDATE work_order_line_items
        SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
        WHERE work_order_id = %s AND deleted_at IS NULL
    """, (username, wo_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/workorders')

# ============================================================================
# Contacts — new
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/contacts/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def contact_new(company_key, customer_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT id, property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    if request.method == 'POST':
        try:
            # Checkbox fields: only present in form data if checked
            is_primary       = request.form.get('is_primary')       == 'on'
            accepts_billing  = request.form.get('accepts_billing')  == 'on'
            accepts_statements = request.form.get('accepts_statements') == 'on'
            accepts_general  = request.form.get('accepts_general')  == 'on'

            # If setting this contact as primary, clear primary flag on all others first
            if is_primary:
                cur.execute("""
                    UPDATE customer_contacts SET is_primary = FALSE
                    WHERE customer_id = %s AND deleted_at IS NULL
                """, (customer_id,))

            # Check if this is the first contact — auto-set as billing if so
            cur.execute("""
                SELECT COUNT(*) as count FROM customer_contacts
                WHERE customer_id = %s AND deleted_at IS NULL
            """, (customer_id,))
            is_first = cur.fetchone()['count'] == 0
            if is_first:
                accepts_billing = True
                accepts_general = True

            cur.execute("""
                INSERT INTO customer_contacts (
                    customer_id, first_name, last_name, title,
                    office_phone, mobile_phone, office_email,
                    is_primary, contact_type,
                    accepts_billing, accepts_statements, accepts_general,
                    notes, created_by, updated_by
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                customer_id,
                request.form.get('first_name', '').strip(),
                request.form.get('last_name', '').strip(),
                request.form.get('title', '').strip() or None,
                request.form.get('office_phone', '').strip() or None,
                request.form.get('mobile_phone', '').strip() or None,
                request.form.get('office_email', '').strip() or None,
                is_primary,
                request.form.get('contact_type', 'general'),
                accepts_billing,
                accepts_statements,
                accepts_general,
                request.form.get('notes', '').strip() or None,
                session.get('username'),
                session.get('username'),
            ))
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('contact_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=customer, contact=None, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('contact_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, contact=None, error=None,
    )


# ============================================================================
# Contacts — edit
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def contact_edit(company_key, customer_id, contact_id, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("SELECT id, property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close(); abort(404)

    cur.execute("""
        SELECT * FROM customer_contacts
        WHERE id = %s AND customer_id = %s AND deleted_at IS NULL
    """, (contact_id, customer_id))
    contact = cur.fetchone()
    if not contact:
        cur.close(); conn.close(); abort(404)

    if request.method == 'POST':
        try:
            is_primary         = request.form.get('is_primary')         == 'on'
            accepts_billing    = request.form.get('accepts_billing')    == 'on'
            accepts_statements = request.form.get('accepts_statements') == 'on'
            accepts_general    = request.form.get('accepts_general')    == 'on'

            # If setting as primary, clear flag on all other contacts first
            if is_primary:
                cur.execute("""
                    UPDATE customer_contacts SET is_primary = FALSE
                    WHERE customer_id = %s AND id != %s AND deleted_at IS NULL
                """, (customer_id, contact_id))

            cur.execute("""
                UPDATE customer_contacts SET
                    first_name         = %s,
                    last_name          = %s,
                    title              = %s,
                    office_phone       = %s,
                    mobile_phone       = %s,
                    office_email       = %s,
                    is_primary         = %s,
                    contact_type       = %s,
                    accepts_billing    = %s,
                    accepts_statements = %s,
                    accepts_general    = %s,
                    notes              = %s,
                    updated_by         = %s,
                    updated_at         = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                request.form.get('first_name', '').strip(),
                request.form.get('last_name', '').strip(),
                request.form.get('title', '').strip() or None,
                request.form.get('office_phone', '').strip() or None,
                request.form.get('mobile_phone', '').strip() or None,
                request.form.get('office_email', '').strip() or None,
                is_primary,
                request.form.get('contact_type', 'general'),
                accepts_billing,
                accepts_statements,
                accepts_general,
                request.form.get('notes', '').strip() or None,
                session.get('username'),
                contact_id,
            ))
            conn.commit()
            cur.close(); conn.close()
            return redirect(f'/{company_key}/customers/{customer_id}')
        except Exception as e:
            conn.rollback()
            cur.close(); conn.close()
            return render_template('contact_form.html',
                branding=branding, company_key=company_key,
                company_access=company_access, all_companies=all_companies,
                customer=customer, contact=contact, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('contact_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, contact=contact, error=None,
    )


# ============================================================================
# Contacts — delete (soft)
# ============================================================================

@app.route('/<company_key>/customers/<int:customer_id>/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
@company_access_required
def contact_delete(company_key, customer_id, contact_id):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    # Safety: don't delete the last contact
    cur.execute("""
        SELECT COUNT(*) as count FROM customer_contacts
        WHERE customer_id = %s AND deleted_at IS NULL
    """, (customer_id,))
    count = cur.fetchone()['count']

    if count > 1:
        cur.execute("""
            UPDATE customer_contacts
            SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
            WHERE id = %s AND customer_id = %s
        """, (session.get('username'), contact_id, customer_id))
        conn.commit()

    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')

# ============================================================================
# Billing — Michele's batch billing page
# ============================================================================

@app.route('/<company_key>/billing')
@login_required
@company_access_required
@with_branding
def billing(company_key, branding, all_companies, company_access):
    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    # Get all active customers with their billing contacts
    cur.execute("""
        SELECT
            c.id,
            c.property_name,
            c.customer_type,
            c.status,
            c.payment_terms,
            mc.name as management_company_name,
            -- Count of billing contacts
            COUNT(cc.id) FILTER (
                WHERE cc.accepts_billing = TRUE AND cc.deleted_at IS NULL
            ) as billing_contact_count,
            -- Aggregate billing emails into a comma-separated string
            STRING_AGG(
                cc.office_email,
                ', '
                ORDER BY cc.is_primary DESC, cc.last_name ASC
            ) FILTER (
                WHERE cc.accepts_billing = TRUE
                  AND cc.deleted_at IS NULL
                  AND cc.office_email IS NOT NULL
            ) as billing_emails,
            -- Primary billing contact name
            MAX(cc.first_name || ' ' || cc.last_name)
                FILTER (WHERE cc.accepts_billing = TRUE AND cc.is_primary = TRUE AND cc.deleted_at IS NULL)
                as primary_billing_name
        FROM customers c
        LEFT JOIN management_companies mc ON c.management_company_id = mc.id
        LEFT JOIN customer_contacts cc ON cc.customer_id = c.id
        WHERE c.deleted_at IS NULL
          AND c.status = 'Active'
        GROUP BY c.id, c.property_name, c.customer_type, c.status,
                 c.payment_terms, mc.name
        ORDER BY c.property_name ASC
    """)
    customers = cur.fetchall()
    cur.close(); conn.close()

    # Split into has-billing and missing-billing for the warning section
    ready     = [c for c in customers if c['billing_contact_count'] > 0]
    no_billing = [c for c in customers if c['billing_contact_count'] == 0]

    return render_template('billing.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        ready=ready, no_billing=no_billing,
        ready_count=len(ready), no_billing_count=len(no_billing),
    )


@app.route('/<company_key>/billing/export', methods=['POST'])
@login_required
@company_access_required
def billing_export(company_key):
    """Generate a CSV of selected customers for batch billing."""
    import csv, io
    from flask import Response

    selected_ids = request.form.getlist('customer_ids')
    if not selected_ids:
        return redirect(f'/{company_key}/billing')

    # Convert to ints safely
    try:
        selected_ids = [int(i) for i in selected_ids]
    except ValueError:
        return redirect(f'/{company_key}/billing')

    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            c.id,
            c.property_name,
            c.customer_type,
            c.payment_terms,
            mc.name as management_company_name,
            STRING_AGG(
                cc.office_email,
                '; '
                ORDER BY cc.is_primary DESC, cc.last_name ASC
            ) FILTER (
                WHERE cc.accepts_billing = TRUE
                  AND cc.deleted_at IS NULL
                  AND cc.office_email IS NOT NULL
            ) as billing_emails,
            STRING_AGG(
                cc.first_name || ' ' || cc.last_name,
                '; '
                ORDER BY cc.is_primary DESC, cc.last_name ASC
            ) FILTER (
                WHERE cc.accepts_billing = TRUE AND cc.deleted_at IS NULL
            ) as billing_contacts
        FROM customers c
        LEFT JOIN management_companies mc ON c.management_company_id = mc.id
        LEFT JOIN customer_contacts cc ON cc.customer_id = c.id
        WHERE c.id = ANY(%s) AND c.deleted_at IS NULL
        GROUP BY c.id, c.property_name, c.customer_type, c.payment_terms, mc.name
        ORDER BY c.property_name ASC
    """, (selected_ids,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Customer ID', 'Property Name', 'Customer Type',
        'Management Company', 'Payment Terms',
        'Billing Contacts', 'Billing Emails'
    ])
    for row in rows:
        writer.writerow([
            row['id'],
            row['property_name'],
            row['customer_type'],
            row['management_company_name'] or '',
            row['payment_terms'] or '',
            row['billing_contacts'] or '',
            row['billing_emails'] or '',
        ])

    output.seek(0)
    from datetime import date
    filename = f"billing_export_{company_key}_{date.today().isoformat()}.csv"

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

# ============================================================================
# User Management — admin only
# Users are replicated across all 4 company databases.
# getagrip is the canonical read source; all writes go to all 4 DBs.
# ============================================================================

VALID_ROLES = ['admin', 'manager', 'office', 'salesperson', 'technician']
ALL_COMPANY_KEYS = list(DB_CONFIG.keys())  # ['getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf']


def write_to_all_dbs(sql, params):
    """Execute a write (INSERT/UPDATE) against all 4 company databases."""
    errors = []
    for key in ALL_COMPANY_KEYS:
        try:
            conn = get_db_connection(key)
            cur  = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            errors.append(f"{key}: {e}")
    return errors


def get_all_users():
    """Fetch all users from the canonical (getagrip) database."""
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, username, email, full_name, role,
               company_access, is_active, last_login, created_at
        FROM users
        ORDER BY full_name ASC
    """)
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


def get_user_by_id(user_id):
    """Fetch a single user by ID from the canonical database."""
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, username, email, full_name, role,
               company_access, is_active, last_login, created_at
        FROM users
        WHERE id = %s
    """, (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


@app.route('/<company_key>/settings/users')
@login_required
@company_access_required
@with_branding
def user_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)

    users = get_all_users()

    return render_template('user_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        users=users,
        all_company_keys=ALL_COMPANY_KEYS,
        company_branding=COMPANY_BRANDING,
    )


@app.route('/<company_key>/settings/users/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def user_new(company_key, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)

    error = None

    if request.method == 'POST':
        username     = request.form.get('username', '').strip().lower()
        full_name    = request.form.get('full_name', '').strip()
        email        = request.form.get('email', '').strip().lower()
        role         = request.form.get('role', 'tech')
        password     = request.form.get('password', '')
        confirm_pw   = request.form.get('confirm_password', '')
        co_access    = request.form.getlist('company_access')  # multi-select checkboxes

        # Validation
        if not username or not full_name or not password or not email:
            error = 'Username, full name, email, and password are required.'
        elif len(username) < 3:
            error = 'Username must be at least 3 characters.'
        elif password != confirm_pw:
            error = 'Passwords do not match.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif role not in VALID_ROLES:
            error = 'Invalid role selected.'
        elif not co_access:
            error = 'At least one company must be selected.'
        else:
            # Check username uniqueness in canonical DB
            conn = get_db_connection('getagrip')
            cur  = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                error = f'Username "{username}" is already taken.'
            cur.close()
            conn.close()

        if not error:
            pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
            errs = write_to_all_dbs("""
                INSERT INTO users (username, email, full_name, role, password_hash,
                                   company_access, is_active, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s)
                ON CONFLICT (username) DO NOTHING
            """, (username, email, full_name, role, pw_hash,
                  json.dumps(co_access), session.get('username')))

            if errs:
                error = 'User created but errors syncing to some databases: ' + '; '.join(errs)
                # Still redirect — getagrip (canonical) succeeded
                return redirect(f'/{company_key}/settings/users')
            return redirect(f'/{company_key}/settings/users')

    return render_template('user_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        user=None, error=error,
        all_company_keys=ALL_COMPANY_KEYS,
        company_branding=COMPANY_BRANDING,
        valid_roles=VALID_ROLES,
    )


@app.route('/<company_key>/settings/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def user_edit(company_key, user_id, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)

    user  = get_user_by_id(user_id)
    if not user:
        abort(404)

    error = None

    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        email      = request.form.get('email', '').strip().lower()
        role       = request.form.get('role', 'tech')
        co_access  = request.form.getlist('company_access')

        if not full_name:
            error = 'Full name is required.'
        elif role not in VALID_ROLES:
            error = 'Invalid role selected.'
        elif not co_access:
            error = 'At least one company must be selected.'

        if not error:
            errs = write_to_all_dbs("""
                UPDATE users
                SET full_name = %s, email = %s, role = %s,
                    company_access = %s, updated_at = CURRENT_TIMESTAMP
                WHERE username = %s
            """, (full_name, email if email else user['email'], role, json.dumps(co_access), user['username']))

            if errs:
                error = 'Saved but errors syncing: ' + '; '.join(errs)
            else:
                return redirect(f'/{company_key}/settings/users')

    return render_template('user_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        user=user, error=error,
        all_company_keys=ALL_COMPANY_KEYS,
        company_branding=COMPANY_BRANDING,
        valid_roles=VALID_ROLES,
    )


@app.route('/<company_key>/settings/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@company_access_required
def user_reset_password(company_key, user_id):
    if session.get('user_role') != 'admin':
        abort(403)

    user = get_user_by_id(user_id)
    if not user:
        abort(404)

    password   = request.form.get('new_password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not password or password != confirm_pw or len(password) < 8:
        # Redirect back to edit page with a query param error signal
        return redirect(f'/{company_key}/settings/users/{user_id}/edit?pw_error=1')

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
    write_to_all_dbs("""
        UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
        WHERE username = %s
    """, (pw_hash, user['username']))

    return redirect(f'/{company_key}/settings/users')


@app.route('/<company_key>/settings/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@company_access_required
def user_toggle_active(company_key, user_id):
    if session.get('user_role') != 'admin':
        abort(403)

    user = get_user_by_id(user_id)
    if not user:
        abort(404)

    # Prevent deactivating yourself
    if user['username'] == session.get('username'):
        return redirect(f'/{company_key}/settings/users')

    write_to_all_dbs("""
        UPDATE users SET is_active = NOT is_active, updated_at = CURRENT_TIMESTAMP
        WHERE username = %s
    """, (user['username'],))

    return redirect(f'/{company_key}/settings/users')

# ============================================================================
# Password Reset — email-based token flow
# ============================================================================

import resend as _resend

RESEND_API_KEY   = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM      = os.environ.get('RESEND_FROM_EMAIL', 'noreply@cletize.com')
APP_BASE_URL     = os.environ.get('APP_BASE_URL', 'https://app.fieldkit.cletize.com')

_resend.api_key  = RESEND_API_KEY


def create_reset_token(user_id, admin_username, company_key):
    """
    Generate a secure reset token, store it in the given company DB,
    and return the token string. Tokens expire in 24 hours.
    Existing unused tokens for the same user are invalidated first.
    """
    token      = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(hours=24)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    # Invalidate any existing unused tokens for this user
    cur.execute("""
        UPDATE password_reset_tokens
        SET used_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND used_at IS NULL AND expires_at > CURRENT_TIMESTAMP
    """, (user_id,))

    cur.execute("""
        INSERT INTO password_reset_tokens (user_id, token, expires_at, created_by)
        VALUES (%s, %s, %s, %s)
    """, (user_id, token, expires_at, admin_username))

    conn.commit()
    cur.close()
    conn.close()
    return token


def send_reset_email(to_email, full_name, token):
    """Send password reset email via Resend. Returns (success, error_message)."""
    reset_url = f"{APP_BASE_URL}/reset-password/{token}"

    html_body = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:520px;margin:0 auto;padding:2rem;">
        <h2 style="color:#8B1538;margin-bottom:0.5rem;">FieldKit</h2>
        <p style="color:#6b7280;margin-top:0;margin-bottom:2rem;font-size:0.9rem;">
            Field Service Management
        </p>

        <p>Hi {full_name},</p>
        <p>Someone requested a password reset for your FieldKit account.
           Click the button below to set a new password.</p>

        <div style="text-align:center;margin:2rem 0;">
            <a href="{reset_url}"
               style="background:#8B1538;color:white;padding:0.85rem 2rem;
                      border-radius:6px;text-decoration:none;font-weight:600;
                      display:inline-block;">
                Set New Password
            </a>
        </div>

        <p style="font-size:0.85rem;color:#6b7280;">
            This link expires in 24 hours. If you didn't request a password reset,
            you can ignore this email — your password won't change.
        </p>
        <p style="font-size:0.85rem;color:#6b7280;">
            Or copy this link into your browser:<br>
            <span style="color:#8B1538;">{reset_url}</span>
        </p>
    </div>
    """

    try:
        _resend.Emails.send({
            "from":    RESEND_FROM,
            "to":      [to_email],
            "subject": "Reset your FieldKit password",
            "html":    html_body,
        })
        return True, None
    except Exception as e:
        print(f"RESEND ERROR: {type(e).__name__}: {e}", flush=True)
        return False, str(e)


def get_valid_reset_token(token):
    """
    Look up a token across all company DBs (stored in getagrip as canonical).
    Returns the token row + user row if valid, else (None, None).
    Token must be unused and not expired.
    """
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("""
        SELECT t.id as token_id, t.user_id, t.token, t.expires_at,
               u.username, u.full_name, u.email
        FROM password_reset_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = %s
          AND t.used_at IS NULL
          AND t.expires_at > CURRENT_TIMESTAMP
    """, (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


@app.route('/<company_key>/settings/users/<int:user_id>/send-reset', methods=['POST'])
@login_required
@company_access_required
def user_send_reset(company_key, user_id):
    """Admin triggers a password reset email for a user."""
    if session.get('user_role') != 'admin':
        abort(403)

    user = get_user_by_id(user_id)
    if not user:
        abort(404)

    if not user.get('email'):
        return redirect(f'/{company_key}/settings/users?reset_error=no_email&user={user_id}')

    token = create_reset_token(user['id'], session.get('username'), 'getagrip')
    success, err = send_reset_email(user['email'], user['full_name'], token)

    if success:
        return redirect(f'/{company_key}/settings/users?reset_sent={user_id}')
    else:
        return redirect(f'/{company_key}/settings/users?reset_error=send_failed&user={user_id}')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    Public route — no login required.
    GET:  show the set-password form (if token valid)
    POST: validate token, set new password, mark token used
    """
    row = get_valid_reset_token(token)

    if not row:
        return render_template('reset_password.html',
            token=token, state='invalid',
            full_name=None, error=None,
        )

    if request.method == 'GET':
        return render_template('reset_password.html',
            token=token, state='form',
            full_name=row['full_name'], error=None,
        )

    # POST — set the new password
    password   = request.form.get('password', '')
    confirm_pw = request.form.get('confirm_password', '')

    if not password or len(password) < 8:
        return render_template('reset_password.html',
            token=token, state='form',
            full_name=row['full_name'],
            error='Password must be at least 8 characters.',
        )
    if password != confirm_pw:
        return render_template('reset_password.html',
            token=token, state='form',
            full_name=row['full_name'],
            error='Passwords do not match.',
        )

    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')

    # Update password in all DBs
    write_to_all_dbs("""
        UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
        WHERE username = %s
    """, (pw_hash, row['username']))

    # Mark token as used (only in getagrip / canonical DB)
    conn = get_db_connection('getagrip')
    cur  = conn.cursor()
    cur.execute("""
        UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP
        WHERE token = %s
    """, (token,))
    conn.commit()
    cur.close()
    conn.close()

    return render_template('reset_password.html',
        token=token, state='success',
        full_name=row['full_name'], error=None,
    )

# ============================================================================
# Run
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
