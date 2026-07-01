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
