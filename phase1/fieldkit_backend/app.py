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

# ============================================================================
# Custom field helpers
# ============================================================================

def get_custom_fields(conn, customer_id):
    """Get all active field definitions with customer's current values."""
    cur = conn.cursor()
    cur.execute("""
        SELECT
            fd.id as definition_id,
            fd.field_name,
            fd.field_type,
            fd.display_order,
            fd.is_active,
            COALESCE(fv.value, '') as value
        FROM customer_field_definitions fd
        LEFT JOIN customer_field_values fv
            ON fv.field_definition_id = fd.id
            AND fv.customer_id = %s
        WHERE fd.is_active = TRUE
        ORDER BY fd.display_order ASC
    """, (customer_id,))
    fields = cur.fetchall()
    cur.close()
    return fields

def get_field_definitions(conn):
    """Get all field definitions for a company (active and inactive)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, field_name, field_type, display_order, is_active
        FROM customer_field_definitions
        ORDER BY display_order ASC
    """)
    defs = cur.fetchall()
    cur.close()
    return defs

def save_custom_fields(conn, customer_id, form_data, username):
    """Upsert custom field values from form submission."""
    cur = conn.cursor()
    for key, value in form_data.items():
        if key.startswith('field_'):
            try:
                definition_id = int(key.replace('field_', ''))
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

    custom_fields = get_custom_fields(conn, customer_id)
    cur.close(); conn.close()

    return render_template('customer_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, contacts=contacts, notes=notes,
        custom_fields=custom_fields,
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
    field_defs = get_field_definitions(conn)

    if request.method == 'POST':
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO customers (
                    property_name, customer_type, status,
                    address, address_2, city, state, zip,
                    billing_email, payment_terms, notes,
                    is_taxable, tax_county,
                    created_by, updated_by
                ) VALUES (
                    %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                ) RETURNING id
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
                field_values={}, nc_counties=NC_COUNTIES, error=str(e),
            )

    conn.close()
    return render_template('customer_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=None, field_defs=field_defs,
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

    field_defs    = get_field_definitions(conn)
    custom_fields = get_custom_fields(conn, customer_id)
    field_values  = {f['definition_id']: f['value'] for f in custom_fields}

    if request.method == 'POST':
        try:
            cur.execute("""
                UPDATE customers SET
                    property_name = %s, customer_type = %s, status = %s,
                    address = %s, address_2 = %s, city = %s, state = %s, zip = %s,
                    billing_email = %s, payment_terms = %s, notes = %s,
                    is_taxable = %s, tax_county = %s,
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
                field_values=field_values, nc_counties=NC_COUNTIES, error=str(e),
            )

    cur.close(); conn.close()
    return render_template('customer_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, field_defs=field_defs,
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
    if session.get('user_role') not in ('admin', 'manager'):
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
    if session.get('user_role') not in ('admin', 'manager'):
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
    if session.get('user_role') not in ('admin', 'manager'):
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
# Run
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
