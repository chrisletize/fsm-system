"""
FieldKit Flask Application
Phase 1: Authentication & Company-in-URL Architecture
"""

from flask import Flask, request, session, jsonify, render_template, redirect, url_for, abort, flash, Response
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import secrets
from datetime import datetime, timedelta, date
from functools import wraps
import json
import math
import os
import re
import io
import zipfile
import base64
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

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

    cur.execute("""
        SELECT id, work_order_number, status, start_date::text AS start_date, work_site_label
        FROM work_orders
        WHERE customer_id = %s AND deleted_at IS NULL
        ORDER BY start_date DESC NULLS LAST, id DESC LIMIT 50
    """, (customer_id,))
    jobs = cur.fetchall()

    cur.execute("""
        SELECT i.id, i.invoice_number, i.invoice_date, i.receivable_state,
               iv.state AS version_state, iv.total, iv.subtotal
        FROM invoices i
        LEFT JOIN invoice_versions iv ON iv.id = i.current_version_id
        WHERE i.customer_id = %s AND i.deleted_at IS NULL
        ORDER BY i.invoice_date DESC, i.id DESC LIMIT 50
    """, (customer_id,))
    customer_invoices = []
    for r in cur.fetchall():
        bal = invoice_balance(cur, r['id'])
        status = invoice_display_status(
            {'receivable_state': r['receivable_state']},
            {'state': r['version_state'], 'total': r['total']} if r['version_state'] else None,
            bal)
        customer_invoices.append({
            'id': r['id'], 'invoice_number': r['invoice_number'], 'invoice_date': r['invoice_date'],
            'display_status': status, 'total': r['total'] if r['total'] is not None else r['subtotal'],
            'balance': bal,
        })

    cur.execute("""
        SELECT p.id, p.payment_date, p.amount, p.status, p.refunded_amount, pm.name AS method_name
        FROM payments p
        LEFT JOIN payment_methods pm ON pm.id = p.payment_method_id
        WHERE p.customer_id = %s AND p.deleted_at IS NULL
        ORDER BY p.payment_date DESC, p.id DESC LIMIT 50
    """, (customer_id,))
    customer_payments = []
    for p in cur.fetchall():
        rem = _remaining_unapplied(cur, p['id']) if p['status'] == 'received' else 0
        customer_payments.append({**p, 'unapplied': rem})

    unapplied_credit = customer_unapplied_credit(cur, customer_id)
    cur.execute("SELECT id, name FROM payment_methods WHERE deleted_at IS NULL ORDER BY sort_order")
    payment_methods = cur.fetchall()

    statement_recipients = _resolve_email_recipients(cur, customer_id, 'statement')
    default_statement_subject = default_statement_body = ''
    if statement_recipients:
        cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
        settings_row = cur.fetchone() or {}
        default_statement_subject = f"Statement from {settings_row.get('company_name') or company_key}"
        default_statement_body = _render_email_template(
            settings_row.get('statement_email_template'), customer['property_name'], '', None, None)

    cur.execute("""
        SELECT * FROM customer_compliance_portals WHERE customer_id = %s ORDER BY is_active DESC, portal_type
    """, (customer_id,))
    compliance_portals = cur.fetchall()

    cur.close(); conn.close()

    return render_template('customer_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        customer=customer, contacts=contacts, notes=notes,
        locations=locations, custom_fields=custom_fields,
        nc_counties=NC_COUNTIES, jobs=jobs, customer_invoices=customer_invoices,
        customer_payments=customer_payments, unapplied_credit=unapplied_credit,
        payment_methods=payment_methods, today=date.today().isoformat(),
        statement_recipients=statement_recipients, resend_configured=bool(RESEND_API_KEY),
        compliance_portals=compliance_portals, portal_types=PORTAL_TYPES,
        default_statement_subject=default_statement_subject, default_statement_body=default_statement_body,
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
# Tax rates & company settings  (admin only)
#   Effective-dated county tax rates (versioned whole-row, not per-component —
#   see migration 009) and the single-row-per-DB company_settings table that
#   the invoice engine (Stage 1) will read for default_tax_county,
#   tax_exempt_by_default, and the email/PDF branding fields.
# ============================================================================

def _tax_rate_county_suggestions(company_key):
    """Existing counties already in this company's tax_rates table, plus the
    full NC county list for the three NC companies. Kleanit South Florida
    uses Florida counties, which aren't enumerated anywhere in this codebase,
    so it only ever suggests counties already entered for it."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT DISTINCT county FROM tax_rates WHERE deleted_at IS NULL ORDER BY county")
    existing = [r['county'] for r in cur.fetchall()]
    cur.close(); conn.close()
    if company_key == 'kleanit_sf':
        return existing
    return sorted(set(existing) | set(NC_COUNTIES))

def _save_tax_rate(company_key, rate_id):
    """Insert (rate_id is None) or update a tax_rates row from request.form.
    Returns an error string, or None on success.

    Editing an existing row is allowed here (nothing today links a hardened
    invoice back to a specific tax_rates row id to guard against), but the
    intended workflow per the build directive is: to actually change a rate,
    End the current row (sets effective_to) and add a New row for the new
    rate/date range, so historical invoices keep resolving to the right
    number via _tax_rate_as_of(). The form carries a warning to that effect."""
    county         = request.form.get('county', '').strip()
    state_pct      = _opt_num(request.form.get('state_pct')) or '0'
    county_pct     = _opt_num(request.form.get('county_pct')) or '0'
    transit_pct    = _opt_num(request.form.get('transit_pct')) or '0'
    effective_from = request.form.get('effective_from', '').strip()
    effective_to   = request.form.get('effective_to', '').strip() or None
    is_active      = request.form.get('is_active') == 'on'

    if not county:
        return 'County is required.'
    if not effective_from:
        return 'Effective-from date is required.'
    if effective_to and effective_to < effective_from:
        return 'Effective-to date cannot be before effective-from.'

    username = session.get('username')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    try:
        if rate_id is None:
            cur.execute("""
                INSERT INTO tax_rates
                    (county, state_pct, county_pct, transit_pct,
                     effective_from, effective_to, is_active, created_by, updated_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (county, state_pct, county_pct, transit_pct,
                  effective_from, effective_to, is_active, username, username))
        else:
            cur.execute("""
                UPDATE tax_rates
                SET county=%s, state_pct=%s, county_pct=%s, transit_pct=%s,
                    effective_from=%s, effective_to=%s, is_active=%s,
                    updated_at=CURRENT_TIMESTAMP, updated_by=%s
                WHERE id=%s AND deleted_at IS NULL
            """, (county, state_pct, county_pct, transit_pct,
                  effective_from, effective_to, is_active, username, rate_id))
    except psycopg2.errors.UniqueViolation:
        conn.rollback(); cur.close(); conn.close()
        return f'{county} already has a rate row effective {effective_from}. Pick a different date or edit that row instead.'
    conn.commit(); cur.close(); conn.close()
    return None

@app.route('/<company_key>/settings/tax')
@login_required
@company_access_required
@with_branding
def tax_rates_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)
    show_all = request.args.get('show_all') == '1'
    as_of    = request.args.get('as_of', '').strip() or date.today().isoformat()

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    if show_all:
        cur.execute("""
            SELECT * FROM tax_rates WHERE deleted_at IS NULL
            ORDER BY county, effective_from DESC
        """)
    else:
        cur.execute("""
            SELECT * FROM tax_rates
            WHERE deleted_at IS NULL
              AND effective_from <= %s
              AND (effective_to IS NULL OR effective_to >= %s)
            ORDER BY county
        """, (as_of, as_of))
    rates = cur.fetchall()
    cur.close(); conn.close()
    return render_template('tax_rates_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        rates=rates, show_all=show_all, as_of=as_of, today=date.today().isoformat(),
    )

@app.route('/<company_key>/settings/tax/new', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def tax_rate_new(company_key, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)
    error = None
    if request.method == 'POST':
        error = _save_tax_rate(company_key, rate_id=None)
        if not error:
            return redirect(f'/{company_key}/settings/tax')
    return render_template('tax_rate_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        rate=None, error=error,
        county_suggestions=_tax_rate_county_suggestions(company_key),
        today=date.today().isoformat(),
    )

@app.route('/<company_key>/settings/tax/<int:rate_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def tax_rate_edit(company_key, rate_id, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)
    if request.method == 'POST':
        error = _save_tax_rate(company_key, rate_id=rate_id)
        if not error:
            return redirect(f'/{company_key}/settings/tax')
    else:
        error = None
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT * FROM tax_rates WHERE id = %s AND deleted_at IS NULL", (rate_id,))
    rate = cur.fetchone()
    cur.close(); conn.close()
    if not rate:
        abort(404)
    return render_template('tax_rate_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        rate=rate, error=error,
        county_suggestions=_tax_rate_county_suggestions(company_key),
        today=date.today().isoformat(),
    )

@app.route('/<company_key>/settings/tax/<int:rate_id>/end', methods=['POST'])
@login_required
@company_access_required
def tax_rate_end(company_key, rate_id):
    if session.get('user_role') != 'admin':
        abort(403)
    effective_to = request.form.get('effective_to', '').strip() or date.today().isoformat()
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT effective_from FROM tax_rates WHERE id = %s AND deleted_at IS NULL", (rate_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        abort(404)
    if effective_to < row['effective_from'].isoformat():
        cur.close(); conn.close()
        return redirect(f'/{company_key}/settings/tax')
    cur.execute("""
        UPDATE tax_rates
        SET effective_to = %s, is_active = FALSE,
            updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (effective_to, session.get('username'), rate_id))
    conn.commit(); cur.close(); conn.close()
    return redirect(f'/{company_key}/settings/tax')

def _save_company_settings(company_key):
    """Update the single company_settings row from request.form.
    Returns an error string, or None on success."""
    company_name    = request.form.get('company_name', '').strip()
    if not company_name:
        return 'Company name is required.'

    fields = {
        'company_name':          company_name,
        'legal_name':            request.form.get('legal_name', '').strip() or None,
        'address':               request.form.get('address', '').strip() or None,
        'address_2':             request.form.get('address_2', '').strip() or None,
        'city':                  request.form.get('city', '').strip() or None,
        'state':                 request.form.get('state', '').strip().upper()[:2] or None,
        'zip':                   request.form.get('zip', '').strip() or None,
        'phone':                 request.form.get('phone', '').strip() or None,
        'email_from_name':       request.form.get('email_from_name', '').strip() or None,
        'email_reply_to':        request.form.get('email_reply_to', '').strip() or None,
        'alert_email':           request.form.get('alert_email', '').strip() or None,
        'default_tax_county':    request.form.get('default_tax_county', '').strip() or None,
        'tax_exempt_by_default': request.form.get('tax_exempt_by_default') == 'on',
        'state_base_rate':       _opt_num(request.form.get('state_base_rate')),
        'business_hours_start':  request.form.get('business_hours_start') or '08:00',
        'business_hours_end':    request.form.get('business_hours_end') or '17:00',
        'remit_to_text':         request.form.get('remit_to_text', '').strip() or None,
        'invoice_footer_text':   request.form.get('invoice_footer_text', '').strip() or None,
        'extraction_explainer_text': request.form.get('extraction_explainer_text', '').strip() or None,
        'invoice_email_template':   request.form.get('invoice_email_template', '').strip() or None,
        'statement_email_template': request.form.get('statement_email_template', '').strip() or None,
    }

    username = session.get('username')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE company_settings
        SET company_name=%s, legal_name=%s, address=%s, address_2=%s, city=%s,
            state=%s, zip=%s, phone=%s, email_from_name=%s, email_reply_to=%s,
            alert_email=%s, default_tax_county=%s, tax_exempt_by_default=%s,
            state_base_rate=%s, business_hours_start=%s, business_hours_end=%s,
            remit_to_text=%s, invoice_footer_text=%s, extraction_explainer_text=%s,
            invoice_email_template=%s, statement_email_template=%s,
            updated_at=CURRENT_TIMESTAMP, updated_by=%s
        WHERE deleted_at IS NULL
    """, (fields['company_name'], fields['legal_name'], fields['address'], fields['address_2'],
          fields['city'], fields['state'], fields['zip'], fields['phone'],
          fields['email_from_name'], fields['email_reply_to'], fields['alert_email'],
          fields['default_tax_county'], fields['tax_exempt_by_default'], fields['state_base_rate'],
          fields['business_hours_start'], fields['business_hours_end'],
          fields['remit_to_text'], fields['invoice_footer_text'],
          fields['extraction_explainer_text'], fields['invoice_email_template'],
          fields['statement_email_template'], username))
    conn.commit(); cur.close(); conn.close()
    return None

@app.route('/<company_key>/settings/company', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def company_settings_edit(company_key, branding, all_companies, company_access):
    if session.get('user_role') != 'admin':
        abort(403)
    error = None
    if request.method == 'POST':
        error = _save_company_settings(company_key)
        if not error:
            return redirect(f'/{company_key}/settings/company')
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    settings = cur.fetchone()
    cur.close(); conn.close()
    return render_template('company_settings_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        settings=settings, error=error,
    )

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
# One number per RECEIVABLE, forever — a revision stays under the same number
# (it's a new invoice_versions row); only a void+reissue consumes a new one.
INVOICE_NUMBER_PREFIXES = WO_NUMBER_PREFIXES  # same mapping, one source of truth

# invoice_versions.state values. The DB CHECK constraint is the real guarantee;
# this tuple is for readable membership tests in Python. 'Paid' and 'Revision'
# are intentionally gone — Paid is derived (see invoice_display_status), and a
# revision is just a new version, not a state a version sits in.
INVOICE_VERSION_STATES = ('Live', 'Hardened', 'Sent', 'Superseded')

# The six operations transition_invoice() supports. Not a from_state->to_state
# adjacency map like the old single-table engine — the receivable/version split
# means the guards are heterogeneous per operation (see the directive's table:
# some check the receivable, some the current version, one needs a payment
# check), so each is its own branch in transition_invoice() below. 'Reissue'
# and 'Revise' are operation names, not states a row is ever literally set to —
# they each mint a NEW row rather than flipping the current one.
INVOICE_TRANSITIONS_IMPLEMENTED = {'Hardened', 'Live', 'Sent', 'Void', 'Reissue', 'Revise'}


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
    Sequence resets each year; the UNIQUE(invoice_number) constraint on the
    receivable is the real guarantee. Every receivable consumes one — a
    revision does NOT (it's a new invoice_versions row under the same
    invoice_number); only a fresh Void->Reissue calls this again.
    NOTE: Increment 1.9's cutover import will relax the LIKE/ORDER-BY-id
    assumption here so imported ServiceFusion numbers can't collide with or
    advance this sequence — not needed yet since nothing is imported."""
    prefix = INVOICE_NUMBER_PREFIXES.get(company_key, company_key.upper()[:3])
    year   = datetime.now().year
    like   = f'{prefix}-{year}-%'
    cur.execute("""
        SELECT invoice_number FROM invoices
        WHERE invoice_number LIKE %s
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


def _tax_rate_as_of(cur, county, as_of):
    """The tax_rates row effective for `county` on date `as_of`, or None.
    Single source of truth for effective-dated rate lookups — anything that
    needs "what rate applied on this date" (invoice hardening, the tax
    report, the /settings/tax page's "active as of" filter) goes through
    this, never a bare `WHERE is_active = TRUE` query (is_active marks
    "currently the live row for editing purposes", not "in range on a given
    date" — a row can be is_active=FALSE and still be the correct historical
    answer for an old date, as Mecklenburg's pre-2026-07-01 row is)."""
    cur.execute("""
        SELECT * FROM tax_rates
        WHERE county = %s AND deleted_at IS NULL
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
    """, (county, as_of, as_of))
    return cur.fetchone()

def _compute_invoice_tax(cur, invoice_id, version_id):
    """Resolve and total the tax for one invoice VERSION from the county rate
    that was effective on the receivable's invoice_date. Returns
    (tax_rate_pct, subtotal, tax_total, total).

    Anchoring on invoice_date (not "today") is what makes a later correction
    to tax_rates (e.g. NC changing a county's rate) never change a version
    that was hardened under the old rate — the freeze happens because the
    caller writes these resolved numbers onto the version at harden time, not
    because this function is only ever called once. A county with no row
    effective on that date resolves to 0% (a valid un-taxed invoice, e.g.
    Florida before its rate table is filled in) rather than failing; the
    absence shows as tax_rate_pct = None for optional flagging."""
    cur.execute("""
        SELECT invoice_date FROM invoices WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        return None, None, None, None
    as_of = inv['invoice_date']

    cur.execute("SELECT tax_county FROM invoice_versions WHERE id = %s", (version_id,))
    ver = cur.fetchone()
    county = ver['tax_county'] if ver else None

    cur.execute("""
        SELECT
            COALESCE(SUM(total), 0)                            AS subtotal,
            COALESCE(SUM(total) FILTER (WHERE is_taxable), 0)  AS taxable_base
        FROM invoice_version_line_items
        WHERE version_id = %s AND deleted_at IS NULL
    """, (version_id,))
    sums = cur.fetchone()
    subtotal     = sums['subtotal']
    taxable_base = sums['taxable_base']

    rate_pct = None
    if county and as_of:
        r = _tax_rate_as_of(cur, county, as_of)
        if r:
            rate_pct = r['total_pct']

    effective_rate = rate_pct if rate_pct is not None else 0
    tax_total = (taxable_base * effective_rate) / 100
    total     = subtotal + tax_total
    return rate_pct, subtotal, tax_total, total


def _resolve_equipment_labels(cur, version_id):
    """Single source of truth for per_day_equipment line labels on one
    invoice VERSION.

    Groups the version's per_day_equipment lines by billing type
    (catalog_item_id), orders each group by (deployed_at ASC, line id ASC),
    and applies the ordinal rule:
      * group of 1  -> bare customer label ("Set Dehu", no number)
      * group of N  -> "Set Dehu 1" .. "Set Dehu N"
    The ordinal is the Nth machine of that TYPE on THIS version — never the
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
        SELECT ivli.id,
               ivli.catalog_item_id,
               ivli.deployed_at,
               COALESCE(ci.invoice_label, ci.name) AS base_label
        FROM invoice_version_line_items ivli
        JOIN catalog_items ci ON ci.id = ivli.catalog_item_id
        WHERE ivli.version_id = %s
          AND ivli.deleted_at IS NULL
          AND ci.billing_behavior = 'per_day_equipment'
        ORDER BY ivli.catalog_item_id,
                 ivli.deployed_at ASC NULLS LAST,
                 ivli.id ASC
    """, (version_id,))
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


def _payments_tables_exist(cur):
    """True once migration 011 (Increment 1.4) has created payment_applications
    and invoice_adjustments. Guards the reopen/void payment checks and
    invoice_balance() below so they work correctly BOTH before 1.4 ships
    (vacuously: no payments can exist yet, so nothing to guard against) AND
    after (real check, no code change needed) — see
    docs/DECISIONS-MADE-DURING-BUILD.md for why this is guarded rather than
    just written against tables that don't exist yet."""
    cur.execute("""
        SELECT to_regclass('payment_applications') IS NOT NULL
           AND to_regclass('invoice_adjustments') IS NOT NULL AS both_exist
    """)
    return cur.fetchone()['both_exist']


def invoice_balance(cur, invoice_id):
    """The single source of truth for an invoice's balance due, used
    everywhere a balance is shown: current version's total (or subtotal if
    not yet hardened) minus non-reversed payment applications minus
    adjustments. Returns None if the invoice or its current version can't be
    found, otherwise always a plain float — psycopg2 hands back NUMERIC
    columns as Decimal, which raises TypeError when mixed with a float in
    arithmetic (comparisons are fine, `+`/`-` are not); casting once here
    means every caller can freely do arithmetic with the result."""
    cur.execute("""
        SELECT iv.total, iv.subtotal
        FROM invoices i JOIN invoice_versions iv ON iv.id = i.current_version_id
        WHERE i.id = %s AND i.deleted_at IS NULL
    """, (invoice_id,))
    row = cur.fetchone()
    if not row:
        return None
    base = row['total'] if row['total'] is not None else row['subtotal']

    applied = 0
    adjusted = 0
    if _payments_tables_exist(cur):
        # SUM across ALL rows (originals + reversals) — a reversal's negative
        # amount is what nets an original back out; filtering to
        # reverses_application_id IS NULL would only ever count originals and
        # never see that one was reversed.
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS n FROM payment_applications
            WHERE invoice_id = %s
        """, (invoice_id,))
        applied = cur.fetchone()['n'] or 0
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) AS n FROM invoice_adjustments
            WHERE invoice_id = %s AND deleted_at IS NULL
        """, (invoice_id,))
        adjusted = cur.fetchone()['n'] or 0

    return float(base) - float(applied) - float(adjusted)


def invoice_display_status(receivable, version, balance):
    """Derived display status — Draft / Hardened / Sent / Partially Paid /
    Paid / Void. Nothing above stores a status string; this is the only
    place that computes one, so list pages and detail pages can never
    disagree. `receivable` is an invoices row, `version` is its current
    invoice_versions row (or None), `balance` is invoice_balance()'s result."""
    if receivable['receivable_state'] == 'void':
        return 'Void'
    if version is None or version['state'] == 'Live':
        return 'Draft'
    if version['state'] == 'Hardened':
        return 'Hardened'
    # Sent (Superseded should never be the CURRENT version, but falls through
    # safely to 'Sent' rather than raising if it somehow is).
    if version['total'] is not None and balance is not None:
        if balance <= 0:
            return 'Paid'
        if balance < version['total']:
            return 'Partially Paid'
    return 'Sent'


def _reissue_invoice(cur, company_key, old_invoice_id, username):
    """Void -> Reissue. Mints a brand-new RECEIVABLE (new invoice_number) with
    a fresh Live rev-0 version, CLONING the void receivable's current
    version's line items as the editable starting point. The void receivable
    is retained untouched (receivable_state stays 'void'; its current
    version's state is NOT changed — it stays as evidence). Links are wired
    both directions (reissue_of_invoice_id / reissued_as_invoice_id) and
    history rows are written on both invoices. Returns the new invoice id.
    Caller owns the transaction/commit.

    Body policy = CLONE: the new receivable begins as a faithful copy of the
    void's lines, editable while Live until the office re-hardens it.
    Deliberate resets on the copy: fresh invoice_number; revision_number = 0;
    frozen figures (tax_rate_pct/tax_total/total) stay NULL until the new
    harden re-resolves them; resolved_label -> NULL on every cloned line
    (Live derives ordinals fresh; they re-bake at the next harden). No
    payment/adjustment data carries over — nothing was ever applied to a
    receivable that was void before any payment could attach to it (Void
    itself requires zero non-reversed applications).
    invoice_date is preserved from the source (the work's effective date,
    Pattern 4) and remains editable while Live."""
    cur.execute("""
        SELECT work_order_id, customer_id, service_location_id, invoice_date, notes, work_site_label
        FROM invoices WHERE id = %s AND deleted_at IS NULL
    """, (old_invoice_id,))
    src = cur.fetchone()

    cur.execute("""
        SELECT iv.* FROM invoices i JOIN invoice_versions iv ON iv.id = i.current_version_id
        WHERE i.id = %s
    """, (old_invoice_id,))
    old_ver = cur.fetchone()

    new_number = _next_invoice_number(cur, company_key)

    cur.execute("""
        INSERT INTO invoices
            (invoice_number, work_order_id, customer_id, service_location_id,
             invoice_date, notes, work_site_label, reissue_of_invoice_id, source, created_by, updated_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'fieldkit', %s, %s)
        RETURNING id
    """, (new_number, src['work_order_id'], src['customer_id'], src['service_location_id'],
          src['invoice_date'], src['notes'], src['work_site_label'], old_invoice_id, username, username))
    new_invoice_id = cur.fetchone()['id']

    cur.execute("""
        INSERT INTO invoice_versions
            (invoice_id, revision_number, state, subtotal, tax_county, created_by, updated_by)
        VALUES (%s, 0, 'Live', %s, %s, %s, %s)
        RETURNING id
    """, (new_invoice_id, old_ver['subtotal'] if old_ver else 0,
          old_ver['tax_county'] if old_ver else None, username, username))
    new_version_id = cur.fetchone()['id']

    cur.execute("""
        UPDATE invoices SET current_version_id = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (new_version_id, username, new_invoice_id))

    if old_ver:
        # Clone the line items (resolved_label cleared; audit stamped to the actor).
        cur.execute("""
            INSERT INTO invoice_version_line_items
                (version_id, catalog_item_id, equipment_unit_id, description,
                 resolved_label, quantity, unit_price, total, is_taxable,
                 deployed_at, retrieved_at, sort_order, created_by, updated_by)
            SELECT %s, catalog_item_id, equipment_unit_id, description,
                   NULL, quantity, unit_price, total, is_taxable,
                   deployed_at, retrieved_at, sort_order, %s, %s
            FROM invoice_version_line_items
            WHERE version_id = %s AND deleted_at IS NULL
        """, (new_version_id, username, username, old_ver['id']))

    # Close the forward link on the retained void.
    cur.execute("""
        UPDATE invoices
        SET reissued_as_invoice_id = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (new_invoice_id, username, old_invoice_id))

    # History on BOTH invoices: the void points forward, the new points back.
    cur.execute("""
        INSERT INTO invoice_status_history (invoice_id, state, from_state, to_state, changed_by, notes)
        VALUES (%s, 'Void', 'void', 'void', %s, %s)
    """, (old_invoice_id, username, f'Reissued as {new_number} (id {new_invoice_id}).'))
    cur.execute("""
        INSERT INTO invoice_status_history (invoice_id, state, version_id, to_state, changed_by, notes)
        VALUES (%s, 'Live', %s, 'Live', %s, %s)
    """, (new_invoice_id, new_version_id, username,
          f'Created via reissue of voided invoice id {old_invoice_id}.'))

    return new_invoice_id


def transition_invoice(cur, company_key, invoice_id, to_state, username, notes=None):
    """Move one invoice via to_state: the single choke point for every
    invoice lifecycle change, at either level. The receivable id is always
    the handle; version-level operations act on its current_version_id.
    Does NOT commit — the calling route owns the transaction (same
    convention as the work-order save path).

    `notes` is contextual per to_state: the void reason for Void, the
    revision reason for Revise, an optional comma-separated recipient list
    for Sent, an optional free note for Live (reopen).

    Returns a 3-tuple (ok, reason, extra):
      * ok     — True on success, False on rejection.
      * reason — human-readable rejection reason, or None on success.
      * extra  — dict of side-effect outputs, or None. Reissue returns
                 {'new_invoice_id': <id>}; Revise returns
                 {'new_version_id': <id>}; every other operation returns None."""
    if to_state not in INVOICE_TRANSITIONS_IMPLEMENTED:
        return False, f'Unknown or unimplemented operation "{to_state}".', None

    cur.execute("""
        SELECT id, receivable_state, current_version_id, invoice_number, reissued_as_invoice_id
        FROM invoices WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        return False, 'Invoice not found.', None

    # ---- Receivable-level operations (no current version required) ----

    if to_state == 'Void':
        if inv['receivable_state'] != 'open':
            return False, f'Invoice is already {inv["receivable_state"]}.', None
        void_reason = (notes or '').strip()
        if not void_reason:
            return False, 'A void reason is required.', None
        if _payments_tables_exist(cur):
            # SUM across ALL rows (originals + reversals), no reverses_application_id
            # filter: a reversal's negative amount is what nets an original back to
            # zero, so filtering to "reverses_application_id IS NULL" here would only
            # ever count originals and never see that a reversal cancelled one out.
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS applied FROM payment_applications
                WHERE invoice_id = %s
            """, (invoice_id,))
            if (cur.fetchone()['applied'] or 0) > 0:
                return False, ('This invoice has a payment applied. Un-apply it '
                               'before voiding.'), None
        cur.execute("""
            UPDATE invoices
            SET receivable_state = 'void', voided_at = CURRENT_TIMESTAMP,
                voided_by = %s, void_reason = %s,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, void_reason, username, invoice_id))
        cur.execute("""
            INSERT INTO invoice_status_history (invoice_id, state, from_state, to_state, changed_by, notes)
            VALUES (%s, 'Void', 'open', 'void', %s, %s)
        """, (invoice_id, username, void_reason))
        return True, None, None

    if to_state == 'Reissue':
        if inv['receivable_state'] != 'void':
            return False, 'Only a voided invoice can be reissued.', None
        if inv['reissued_as_invoice_id']:
            return False, 'This invoice has already been reissued.', None
        new_id = _reissue_invoice(cur, company_key, invoice_id, username)
        return True, None, {'new_invoice_id': new_id}

    # ---- Version-level operations: Hardened, Live (reopen), Sent, Revise ----

    if not inv['current_version_id']:
        return False, 'This invoice has no current version.', None
    cur.execute("SELECT * FROM invoice_versions WHERE id = %s AND deleted_at IS NULL",
                (inv['current_version_id'],))
    ver = cur.fetchone()
    if not ver:
        return False, 'Current version not found.', None

    if to_state == ver['state']:
        return False, f'Invoice is already {to_state}.', None

    if to_state == 'Hardened':
        if ver['state'] != 'Live':
            return False, f'Version must be Live to harden (currently {ver["state"]}).', None
        cur.execute("""
            SELECT count(*) AS n FROM invoice_version_line_items
            WHERE version_id = %s AND deleted_at IS NULL
              AND deployed_at IS NOT NULL AND retrieved_at IS NULL
        """, (ver['id'],))
        if cur.fetchone()['n'] > 0:
            return False, ('Cannot harden: one or more equipment lines have '
                           'not been retrieved yet.'), None

        rate_pct, subtotal, tax_total, total = _compute_invoice_tax(cur, invoice_id, ver['id'])
        cur.execute("""
            UPDATE invoice_versions
            SET subtotal = %s, tax_rate_pct = %s, tax_total = %s, total = %s,
                state = 'Hardened', hardened_at = CURRENT_TIMESTAMP, hardened_by = %s,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (subtotal, rate_pct, tax_total, total, username, username, ver['id']))
        # Bake equipment-ordinal labels into the frozen snapshot so a reprint
        # years later is byte-identical (same freeze discipline as the tax rate).
        for _li_id, _label in _resolve_equipment_labels(cur, ver['id']).items():
            cur.execute("""
                UPDATE invoice_version_line_items
                SET resolved_label = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE id = %s
            """, (_label, username, _li_id))

        # Compliance portal: hardening is "ready to submit" for an enrolled
        # customer. Auto-assign the portal if the customer has exactly one
        # active enrollment and none was already picked on the invoice form;
        # with 0 or 2+ enrollments, leave portal_id for the office to choose
        # (via invoice edit) rather than guessing.
        cur.execute("SELECT customer_id, portal_id FROM invoices WHERE id = %s", (invoice_id,))
        inv_row = cur.fetchone()
        portal_id = inv_row['portal_id']
        if not portal_id:
            cur.execute("""
                SELECT id FROM customer_compliance_portals
                WHERE customer_id = %s AND is_active = TRUE
            """, (inv_row['customer_id'],))
            enrollments = cur.fetchall()
            if len(enrollments) == 1:
                portal_id = enrollments[0]['id']
                cur.execute("UPDATE invoices SET portal_id = %s WHERE id = %s", (portal_id, invoice_id))
        if portal_id:
            cur.execute("""
                UPDATE invoices SET portal_status = 'pending', updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE id = %s
            """, (username, invoice_id))

        # Revision deltas: if this version supersedes a prior one, this is
        # where the accountant-friendly dated delta gets written (§2.2 Q4) —
        # at THIS harden, on THIS version's history row, never retroactively
        # on the old one.
        subtotal_delta = tax_delta = None
        if ver['revision_number'] > 0:
            cur.execute("""
                SELECT subtotal, tax_total FROM invoice_versions
                WHERE invoice_id = %s AND revision_number = %s AND state = 'Superseded'
            """, (invoice_id, ver['revision_number'] - 1))
            prior = cur.fetchone()
            if prior:
                subtotal_delta = subtotal - (prior['subtotal'] or 0)
                tax_delta = (tax_total or 0) - (prior['tax_total'] or 0)

        cur.execute("""
            INSERT INTO invoice_status_history
                (invoice_id, state, version_id, from_state, to_state,
                 subtotal_delta, tax_delta, effective_date, changed_by, notes)
            VALUES (%s, 'Hardened', %s, 'Live', 'Hardened', %s, %s, CURRENT_DATE, %s, %s)
        """, (invoice_id, ver['id'], subtotal_delta, tax_delta, username, notes))
        return True, None, None

    if to_state == 'Sent':
        if ver['state'] != 'Hardened':
            return False, f'Version must be Hardened to send (currently {ver["state"]}).', None
        sent_to_emails = (notes or '').strip() or None
        cur.execute("""
            UPDATE invoice_versions
            SET state = 'Sent', sent_at = CURRENT_TIMESTAMP, sent_by = %s, sent_to_emails = %s,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, sent_to_emails, username, ver['id']))
        cur.execute("""
            INSERT INTO invoice_status_history (invoice_id, state, version_id, from_state, to_state, changed_by, notes)
            VALUES (%s, 'Sent', %s, 'Hardened', 'Sent', %s, %s)
        """, (invoice_id, ver['id'], username,
              f'Sent to {sent_to_emails}' if sent_to_emails else None))
        return True, None, None

    if to_state == 'Live':  # reopen
        if ver['state'] not in ('Hardened', 'Sent'):
            return False, (f'Version must be Hardened or Sent to reopen '
                           f'(currently {ver["state"]}).'), None
        if _payments_tables_exist(cur):
            # See the Void branch above for why this sums ALL rows, not just
            # reverses_application_id IS NULL ones.
            cur.execute("""
                SELECT COALESCE(SUM(amount), 0) AS applied FROM payment_applications
                WHERE invoice_id = %s
            """, (invoice_id,))
            if (cur.fetchone()['applied'] or 0) > 0:
                return False, ('This invoice has a payment applied and can no longer '
                               'be reopened. Use Void or Revise instead.'), None

        history_note = notes or ''
        if ver['total'] is not None:
            prior_bit = (f'Prior frozen total: ${ver["total"]:.2f} '
                         f'(tax ${ver["tax_total"] or 0:.2f} @ {ver["tax_rate_pct"] or 0}%).')
            history_note = f'{history_note} {prior_bit}'.strip()

        cur.execute("""
            UPDATE invoice_versions
            SET state = 'Live', tax_rate_pct = NULL, tax_total = NULL, total = NULL,
                hardened_at = NULL, hardened_by = NULL,
                sent_at = NULL, sent_by = NULL, sent_to_emails = NULL,
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (username, ver['id']))
        cur.execute("""
            UPDATE invoice_version_line_items
            SET resolved_label = NULL, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE version_id = %s AND deleted_at IS NULL
        """, (username, ver['id']))
        cur.execute("""
            INSERT INTO invoice_status_history (invoice_id, state, version_id, from_state, to_state, changed_by, notes)
            VALUES (%s, 'Live', %s, %s, 'Live', %s, %s)
        """, (invoice_id, ver['id'], ver['state'], username, history_note or None))
        return True, None, None

    if to_state == 'Revise':
        if ver['state'] != 'Sent':
            return False, f'Version must be Sent to revise (currently {ver["state"]}).', None
        revision_reason = (notes or '').strip()
        if not revision_reason:
            return False, 'A revision reason is required.', None

        new_rev_num = ver['revision_number'] + 1
        cur.execute("""
            INSERT INTO invoice_versions
                (invoice_id, revision_number, state, subtotal, tax_county,
                 notes_to_customer, revision_reason, created_by, updated_by)
            VALUES (%s, %s, 'Live', %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (invoice_id, new_rev_num, ver['subtotal'], ver['tax_county'],
              ver['notes_to_customer'], revision_reason, username, username))
        new_version_id = cur.fetchone()['id']

        cur.execute("""
            INSERT INTO invoice_version_line_items
                (version_id, catalog_item_id, equipment_unit_id, description,
                 resolved_label, quantity, unit_price, total, is_taxable,
                 deployed_at, retrieved_at, sort_order, created_by, updated_by)
            SELECT %s, catalog_item_id, equipment_unit_id, description,
                   NULL, quantity, unit_price, total, is_taxable,
                   deployed_at, retrieved_at, sort_order, %s, %s
            FROM invoice_version_line_items
            WHERE version_id = %s AND deleted_at IS NULL
        """, (new_version_id, username, username, ver['id']))

        cur.execute("""
            UPDATE invoice_versions
            SET state = 'Superseded', superseded_at = CURRENT_TIMESTAMP,
                superseded_by_version_id = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (new_version_id, username, ver['id']))

        cur.execute("""
            UPDATE invoices SET current_version_id = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (new_version_id, username, invoice_id))

        # Receivable-level event, dated today. Subtotal/tax deltas aren't known
        # yet — those are written on the NEW version's Hardened history row
        # once it re-hardens (see the Hardened branch above).
        cur.execute("""
            INSERT INTO invoice_status_history
                (invoice_id, state, version_id, from_state, to_state, effective_date, changed_by, notes)
            VALUES (%s, 'Live', %s, 'Sent', 'Live', CURRENT_DATE, %s, %s)
        """, (invoice_id, new_version_id, username, revision_reason))

        return True, None, {'new_version_id': new_version_id}

    return False, f'Unhandled operation "{to_state}".', None



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
    unapplied_credit = customer_unapplied_credit(cur, customer_id)
    cur.close(); conn.close()
    return jsonify({
        'customer_type': cust['customer_type'],
        'site_label': label,
        'site_prefill_from_location': prefill,
        'locations': locations,
        'contacts': contacts,
        'unapplied_credit': unapplied_credit,
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

    # Drive the "Generate invoice now?" / "not invoiced yet" / "View Invoice"
    # banner. Follows any reissue chain so a voided-and-reissued invoice
    # still links to the LIVE one, not the dead end.
    cur.execute("""
        SELECT id, reissued_as_invoice_id FROM invoices
        WHERE work_order_id = %s AND deleted_at IS NULL ORDER BY id LIMIT 1
    """, (wo_id,))
    inv_row = cur.fetchone()
    invoice_id = None
    if inv_row:
        invoice_id, seen = inv_row['id'], {inv_row['id']}
        nxt = inv_row['reissued_as_invoice_id']
        while nxt and nxt not in seen:
            invoice_id = nxt
            seen.add(nxt)
            cur.execute("SELECT reissued_as_invoice_id FROM invoices WHERE id = %s", (invoice_id,))
            row = cur.fetchone()
            nxt = row['reissued_as_invoice_id'] if row else None

    cur.close(); conn.close()
    return render_template('workorder_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        wo=wo, site_label=label, line_items=line_items, subtotal=subtotal,
        accruing=accruing, techs=techs, history=history, invoice_id=invoice_id,
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
        new_status = request.form.get('status', 'Scheduled')
        _, error = _save_work_order(company_key, wo_id=wo_id)
        if not error:
            # Completed is the moment a WO becomes invoiceable — land on the
            # detail page so the "Generate invoice now?" banner is right there.
            if new_status == 'Completed':
                return redirect(f'/{company_key}/workorders/{wo_id}')
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
# Invoices  (admin + manager + office)
#   Create-from-work-order + the receivable/version UI on top of Increment
#   1.2's schema and transition_invoice(). Single-WO invoices only — multi-WO
#   batch invoicing is deferred (migration 007's own note, restated in the
#   build directive).
# ============================================================================

def _resolve_invoice_tax_context(cur, customer_id, service_location_id):
    """(tax_county, customer_taxable, location_taxable) for a new invoice, per
    the directive's fallback chain: service location county -> customer
    tax_county -> company_settings.default_tax_county."""
    cur.execute("SELECT is_taxable, tax_county FROM customers WHERE id = %s", (customer_id,))
    cust = cur.fetchone() or {}
    loc = None
    if service_location_id:
        cur.execute("SELECT is_taxable, county FROM service_locations WHERE id = %s", (service_location_id,))
        loc = cur.fetchone()

    tax_county = (loc['county'] if loc and loc.get('county') else None) or cust.get('tax_county')
    if not tax_county:
        cur.execute("SELECT default_tax_county FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
        cs = cur.fetchone()
        tax_county = cs['default_tax_county'] if cs else None

    customer_taxable = cust.get('is_taxable') if cust.get('is_taxable') is not None else True
    location_taxable = loc['is_taxable'] if loc and loc.get('is_taxable') is not None else True
    return tax_county, customer_taxable, location_taxable


def _snapshot_wo_lines_to_version(cur, wo_id, version_id, customer_taxable, location_taxable, username):
    """Copy work_order_line_items onto an invoice version, applying the
    three-layer exemption (catalog item -> customer -> location: any one
    False makes the line non-taxable). quantity/total for per-day equipment
    lines are already the billable-days figures _save_work_order computed
    (max(days, 1) once retrieved, NULL/still-accruing otherwise) — copied
    as-is, not recomputed, so an invoice created before retrieval correctly
    starts as still-accruing and Hardened's guard catches it."""
    cur.execute("""
        SELECT catalog_item_id, equipment_unit_id, description, quantity, unit_price,
               total, is_taxable, deployed_at, retrieved_at, sort_order
        FROM work_order_line_items
        WHERE work_order_id = %s AND deleted_at IS NULL
        ORDER BY sort_order, id
    """, (wo_id,))
    for li in cur.fetchall():
        is_taxable = bool(li['is_taxable']) and customer_taxable and location_taxable
        cur.execute("""
            INSERT INTO invoice_version_line_items
                (version_id, catalog_item_id, equipment_unit_id, description,
                 quantity, unit_price, total, is_taxable, deployed_at, retrieved_at,
                 sort_order, created_by, updated_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (version_id, li['catalog_item_id'], li['equipment_unit_id'], li['description'],
              li['quantity'], li['unit_price'], li['total'], is_taxable,
              li['deployed_at'], li['retrieved_at'], li['sort_order'], username, username))


def _recompute_version_subtotal(cur, version_id, username):
    cur.execute("""
        SELECT COALESCE(SUM(total), 0) AS subtotal FROM invoice_version_line_items
        WHERE version_id = %s AND deleted_at IS NULL
    """, (version_id,))
    subtotal = cur.fetchone()['subtotal']
    cur.execute("""
        UPDATE invoice_versions SET subtotal = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (subtotal, username, version_id))
    return subtotal


def _create_invoice_from_wo(cur, company_key, wo, username):
    """Creates the receivable + Live rev-0 version + snapshotted lines for a
    Completed work order. `wo` needs id/customer_id/service_location_id.
    Returns the new invoice id. Caller owns the transaction/commit and the
    WO status flip."""
    tax_county, cust_taxable, loc_taxable = _resolve_invoice_tax_context(
        cur, wo['customer_id'], wo['service_location_id'])

    # Snapshotted (not live-joined from work_orders) so a hardened+ invoice's
    # PDF never has to read the work order — see migration 012's header.
    cur.execute("SELECT work_site_label FROM work_orders WHERE id = %s", (wo['id'],))
    wo_row = cur.fetchone()
    work_site_label = wo_row['work_site_label'] if wo_row else None

    new_number = _next_invoice_number(cur, company_key)
    cur.execute("""
        INSERT INTO invoices
            (invoice_number, work_order_id, customer_id, service_location_id,
             invoice_date, source, work_site_label, created_by, updated_by)
        VALUES (%s, %s, %s, %s, CURRENT_DATE, 'fieldkit', %s, %s, %s)
        RETURNING id
    """, (new_number, wo['id'], wo['customer_id'], wo['service_location_id'],
          work_site_label, username, username))
    invoice_id = cur.fetchone()['id']

    cur.execute("""
        INSERT INTO invoice_versions (invoice_id, revision_number, state, subtotal, tax_county, created_by, updated_by)
        VALUES (%s, 0, 'Live', 0, %s, %s, %s)
        RETURNING id
    """, (invoice_id, tax_county, username, username))
    version_id = cur.fetchone()['id']

    cur.execute("UPDATE invoices SET current_version_id = %s WHERE id = %s", (version_id, invoice_id))
    _snapshot_wo_lines_to_version(cur, wo['id'], version_id, cust_taxable, loc_taxable, username)
    _recompute_version_subtotal(cur, version_id, username)

    cur.execute("""
        INSERT INTO invoice_status_history (invoice_id, state, version_id, to_state, changed_by, notes)
        VALUES (%s, 'Live', %s, 'Live', %s, %s)
    """, (invoice_id, version_id, username, f'Created from work order.'))

    return invoice_id


@app.route('/<company_key>/workorders/<int:wo_id>/invoice/new', methods=['POST'])
@login_required
@company_access_required
def workorder_invoice_new(company_key, wo_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, status, customer_id, service_location_id FROM work_orders
        WHERE id = %s AND deleted_at IS NULL
    """, (wo_id,))
    wo = cur.fetchone()
    if not wo:
        cur.close(); conn.close()
        abort(404)

    # One invoice per WO. If one already exists, follow any reissue chain to
    # the latest and redirect there instead of creating a second.
    cur.execute("""
        SELECT id, reissued_as_invoice_id FROM invoices
        WHERE work_order_id = %s AND deleted_at IS NULL ORDER BY id LIMIT 1
    """, (wo_id,))
    existing = cur.fetchone()
    if existing:
        target, seen = existing['id'], {existing['id']}
        nxt = existing['reissued_as_invoice_id']
        while nxt and nxt not in seen:
            target = nxt
            seen.add(nxt)
            cur.execute("SELECT reissued_as_invoice_id FROM invoices WHERE id = %s", (target,))
            row = cur.fetchone()
            nxt = row['reissued_as_invoice_id'] if row else None
        cur.close(); conn.close()
        flash('This work order already has an invoice.', 'info')
        return redirect(f'/{company_key}/invoices/{target}')

    if wo['status'] == 'No Charge':
        cur.close(); conn.close()
        flash('No-charge work orders are not invoiced.', 'error')
        return redirect(f'/{company_key}/workorders/{wo_id}')
    if wo['status'] != 'Completed':
        cur.close(); conn.close()
        flash('Work order must be Completed before it can be invoiced.', 'error')
        return redirect(f'/{company_key}/workorders/{wo_id}')

    username = session.get('username')
    invoice_id = _create_invoice_from_wo(cur, company_key, wo, username)

    cur.execute("""
        UPDATE work_orders SET status = 'Invoiced', updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (username, wo_id))
    cur.execute("""
        INSERT INTO work_order_status_history (work_order_id, status, changed_by, notes)
        VALUES (%s, 'Invoiced', %s, 'Invoice created.')
    """, (wo_id, username))

    conn.commit()
    cur.close(); conn.close()
    return redirect(f'/{company_key}/invoices/{invoice_id}')


@app.route('/<company_key>/invoices')
@login_required
@company_access_required
@with_branding
def invoices_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    search        = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    date_from     = request.args.get('date_from', '').strip()
    date_to       = request.args.get('date_to', '').strip()
    balance_only  = request.args.get('with_balance') == '1'

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    conditions = ["i.deleted_at IS NULL"]
    params = []
    if search:
        conditions.append("(i.invoice_number ILIKE %s OR c.property_name ILIKE %s)")
        params += [f'%{search}%', f'%{search}%']
    if date_from:
        conditions.append("i.invoice_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("i.invoice_date <= %s"); params.append(date_to)
    where = " AND ".join(conditions)

    # Status/balance filters are applied in Python below — display status and
    # balance are derived (invoice_display_status/invoice_balance), not
    # stored, and until Increment 1.4's v_invoice_balances view exists this
    # is the honest way to filter on them without duplicating that logic in
    # raw SQL. Fine at today's invoice volumes; revisit once that view lands.
    cur.execute(f"""
        SELECT i.id, i.invoice_number, i.invoice_date, i.receivable_state, i.portal_status,
               c.property_name AS customer_name,
               iv.state AS version_state, iv.total, iv.subtotal
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN invoice_versions iv ON iv.id = i.current_version_id
        WHERE {where}
        ORDER BY i.invoice_date DESC, i.id DESC
    """, params)
    rows = cur.fetchall()

    invoices = []
    for r in rows:
        bal = invoice_balance(cur, r['id'])
        status = invoice_display_status(
            {'receivable_state': r['receivable_state']},
            {'state': r['version_state'], 'total': r['total']} if r['version_state'] else None,
            bal)
        if status_filter and status != status_filter:
            continue
        if balance_only and not (bal is not None and bal > 0):
            continue
        invoices.append({
            'id': r['id'], 'invoice_number': r['invoice_number'], 'invoice_date': r['invoice_date'],
            'customer_name': r['customer_name'], 'display_status': status,
            'total': r['total'] if r['total'] is not None else r['subtotal'],
            'balance': bal, 'portal_status': r['portal_status'],
        })
    cur.close(); conn.close()
    return render_template('invoices_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        invoices=invoices, search=search, status_filter=status_filter,
        date_from=date_from, date_to=date_to, balance_only=balance_only,
        statuses=['Draft', 'Hardened', 'Sent', 'Partially Paid', 'Paid', 'Void'],
    )


@app.route('/<company_key>/invoices/<int:invoice_id>')
@login_required
@company_access_required
@with_branding
def invoice_detail(company_key, invoice_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT i.*, c.property_name AS customer_name,
               sl.location_name, wo.work_order_number
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN service_locations sl ON sl.id = i.service_location_id
        LEFT JOIN work_orders wo ON wo.id = i.work_order_id
        WHERE i.id = %s AND i.deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        cur.close(); conn.close()
        abort(404)

    ver = None
    if inv['current_version_id']:
        cur.execute("SELECT * FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
        ver = cur.fetchone()

    line_items = []
    if ver:
        cur.execute("""
            SELECT ivli.*, ci.name AS catalog_name, ci.billing_behavior
            FROM invoice_version_line_items ivli
            JOIN catalog_items ci ON ci.id = ivli.catalog_item_id
            WHERE ivli.version_id = %s AND ivli.deleted_at IS NULL
            ORDER BY ivli.sort_order, ivli.id
        """, (ver['id'],))
        line_items = [dict(r) for r in cur.fetchall()]
        if ver['state'] == 'Live':
            # Live ordinals are derived, not stored yet — render the SAME
            # resolver harden will bake in, so the preview never disagrees
            # with the eventual print.
            live_labels = _resolve_equipment_labels(cur, ver['id'])
            for li in line_items:
                if li['id'] in live_labels:
                    li['resolved_label'] = live_labels[li['id']]

    cur.execute("SELECT * FROM invoice_versions WHERE invoice_id = %s ORDER BY revision_number", (invoice_id,))
    versions = cur.fetchall()

    cur.execute("""
        SELECT *, to_char(changed_at, 'Mon DD, YYYY HH12:MI AM') AS changed_at_display
        FROM invoice_status_history WHERE invoice_id = %s ORDER BY changed_at DESC, id DESC
    """, (invoice_id,))
    history = cur.fetchall()

    balance = invoice_balance(cur, invoice_id)
    display_status = invoice_display_status(inv, ver, balance)

    cur.execute("""
        SELECT pa.*, p.payment_date, p.reference_number, pm.name AS method_name
        FROM payment_applications pa
        JOIN payments p ON p.id = pa.payment_id
        LEFT JOIN payment_methods pm ON pm.id = p.payment_method_id
        WHERE pa.invoice_id = %s
        ORDER BY pa.id
    """, (invoice_id,))
    applications = cur.fetchall()

    cur.execute("""
        SELECT * FROM invoice_adjustments WHERE invoice_id = %s AND deleted_at IS NULL ORDER BY id
    """, (invoice_id,))
    adjustments = cur.fetchall()

    unapplied_credit = customer_unapplied_credit(cur, inv['customer_id'])
    credit_payments = []
    if unapplied_credit > 0.005:
        cur.execute("""
            SELECT p.id, p.payment_date, p.amount, p.reference_number
            FROM payments p WHERE p.customer_id = %s AND p.status = 'received' AND p.deleted_at IS NULL
            ORDER BY p.payment_date
        """, (inv['customer_id'],))
        for p in cur.fetchall():
            rem = _remaining_unapplied(cur, p['id'])
            if rem and rem > 0.005:
                credit_payments.append({**p, 'unapplied': rem})

    next_unpaid_id = None
    if display_status == 'Paid':
        next_unpaid_id = _next_unpaid_invoice(cur, invoice_id, customer_id=inv['customer_id'])

    cur.execute("SELECT id, name FROM payment_methods WHERE deleted_at IS NULL ORDER BY sort_order")
    payment_methods = cur.fetchall()

    # Send-dialog context — only meaningful once Hardened (the only state Send
    # is offered from).
    email_recipients, default_subject, default_body = [], '', ''
    if ver and ver['state'] == 'Hardened':
        email_recipients = _resolve_email_recipients(cur, inv['customer_id'], 'invoice')
        cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
        settings_row = cur.fetchone() or {}
        default_subject = f"Invoice {inv['invoice_number']} from {settings_row.get('company_name') or company_key}"
        default_body = _render_email_template(
            settings_row.get('invoice_email_template'), inv['customer_name'],
            inv['invoice_number'], ver['total'], balance)

    cur.close(); conn.close()
    return render_template('invoice_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        inv=inv, ver=ver, line_items=line_items, versions=versions,
        history=history, balance=balance, display_status=display_status,
        applications=applications, adjustments=adjustments,
        unapplied_credit=unapplied_credit, credit_payments=credit_payments,
        next_unpaid_id=next_unpaid_id, payment_methods=payment_methods,
        email_recipients=email_recipients, default_subject=default_subject,
        default_body=default_body, resend_configured=bool(RESEND_API_KEY),
    )


@app.route('/<company_key>/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
@company_access_required
@with_branding
def invoice_edit(company_key, invoice_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT * FROM invoices WHERE id = %s AND deleted_at IS NULL", (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        cur.close(); conn.close()
        abort(404)
    ver = None
    if inv['current_version_id']:
        cur.execute("SELECT * FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
        ver = cur.fetchone()
    if not ver or ver['state'] != 'Live':
        cur.close(); conn.close()
        flash('Only a Live invoice can be edited.', 'error')
        return redirect(f'/{company_key}/invoices/{invoice_id}')

    error = None
    if request.method == 'POST':
        username = session.get('username')
        invoice_date      = request.form.get('invoice_date', '').strip() or None
        tax_county        = request.form.get('tax_county', '').strip() or None
        notes_to_customer = request.form.get('notes_to_customer', '').strip() or None
        wtn_po_number     = request.form.get('wtn_po_number', '').strip() or None
        portal_id         = _opt_num(request.form.get('portal_id'))

        line_ids     = request.form.getlist('line_id')
        descriptions = request.form.getlist('description')
        quantities   = request.form.getlist('quantity')
        prices       = request.form.getlist('unit_price')
        removed      = request.form.getlist('removed_line_id')

        try:
            for i, lid in enumerate(line_ids):
                qty   = float(quantities[i])
                price = float(prices[i])
                if qty <= 0 or price < 0:
                    error = 'Quantity must be positive and price cannot be negative.'
                    break
                is_tax = request.form.get(f'taxable_{lid}') == 'on'
                total = round(qty * price, 2)
                cur.execute("""
                    UPDATE invoice_version_line_items
                    SET description = %s, quantity = %s, unit_price = %s, total = %s,
                        is_taxable = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
                    WHERE id = %s AND version_id = %s
                """, (descriptions[i].strip(), qty, price, total, is_tax, username, int(lid), ver['id']))
        except (ValueError, IndexError):
            error = 'Could not read the line items.'

        if not error and removed:
            cur.execute("""
                UPDATE invoice_version_line_items
                SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
                WHERE id = ANY(%s) AND version_id = %s
            """, (username, [int(x) for x in removed], ver['id']))

        new_catalog_id = _opt_num(request.form.get('new_catalog_item_id'))
        if not error and new_catalog_id:
            cur.execute("""
                SELECT id, name, invoice_label, unit_price, is_taxable FROM catalog_items
                WHERE id = %s AND deleted_at IS NULL AND billing_behavior = 'standard'
            """, (new_catalog_id,))
            cat = cur.fetchone()
            if not cat:
                error = 'Choose a catalog item from the list.'
            else:
                cur.execute("""
                    SELECT COALESCE(MAX(sort_order), 0) + 1 AS n FROM invoice_version_line_items
                    WHERE version_id = %s
                """, (ver['id'],))
                next_sort = cur.fetchone()['n']
                cur.execute("""
                    INSERT INTO invoice_version_line_items
                        (version_id, catalog_item_id, description, quantity, unit_price, total,
                         is_taxable, sort_order, created_by, updated_by)
                    VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s)
                """, (ver['id'], cat['id'], cat['invoice_label'] or cat['name'],
                      cat['unit_price'], cat['unit_price'], cat['is_taxable'],
                      next_sort, username, username))

        if not error:
            _recompute_version_subtotal(cur, ver['id'], username)
            cur.execute("""
                UPDATE invoice_versions
                SET tax_county = %s, notes_to_customer = %s,
                    updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE id = %s
            """, (tax_county, notes_to_customer, username, ver['id']))
            cur.execute("""
                UPDATE invoices
                SET invoice_date = COALESCE(%s, invoice_date), wtn_po_number = %s, portal_id = %s,
                    updated_at = CURRENT_TIMESTAMP, updated_by = %s
                WHERE id = %s
            """, (invoice_date, wtn_po_number, portal_id, username, invoice_id))
            conn.commit()
            cur.close(); conn.close()
            flash('Invoice saved.', 'success')
            return redirect(f'/{company_key}/invoices/{invoice_id}')

    cur.execute("""
        SELECT ivli.*, ci.name AS catalog_name FROM invoice_version_line_items ivli
        JOIN catalog_items ci ON ci.id = ivli.catalog_item_id
        WHERE ivli.version_id = %s AND ivli.deleted_at IS NULL
        ORDER BY ivli.sort_order, ivli.id
    """, (ver['id'],))
    line_items = cur.fetchall()
    cur.execute("""
        SELECT id, name, invoice_label, unit_price, is_taxable FROM catalog_items
        WHERE billing_behavior = 'standard' AND is_active = TRUE AND deleted_at IS NULL
        ORDER BY name
    """)
    catalog_options = [{'id': r['id'], 'name': r['invoice_label'] or r['name']} for r in cur.fetchall()]
    cur.execute("""
        SELECT id, portal_type, portal_label FROM customer_compliance_portals
        WHERE customer_id = %s AND is_active = TRUE ORDER BY portal_type
    """, (inv['customer_id'],))
    portal_options = cur.fetchall()
    cur.close(); conn.close()
    return render_template('invoice_form.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        inv=inv, ver=ver, line_items=line_items, error=error,
        catalog_options=catalog_options, portal_options=portal_options,
    )


@app.route('/<company_key>/invoices/<int:invoice_id>/regenerate', methods=['POST'])
@login_required
@company_access_required
def invoice_regenerate(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT current_version_id, work_order_id, customer_id, service_location_id
        FROM invoices WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv or not inv['work_order_id']:
        cur.close(); conn.close()
        abort(404)
    cur.execute("SELECT state FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
    ver = cur.fetchone()
    if not ver or ver['state'] != 'Live':
        cur.close(); conn.close()
        flash('Only a Live invoice can be regenerated.', 'error')
        return redirect(f'/{company_key}/invoices/{invoice_id}')

    username = session.get('username')
    cur.execute("""
        UPDATE invoice_version_line_items SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s
        WHERE version_id = %s AND deleted_at IS NULL
    """, (username, inv['current_version_id']))

    _, cust_taxable, loc_taxable = _resolve_invoice_tax_context(cur, inv['customer_id'], inv['service_location_id'])
    _snapshot_wo_lines_to_version(cur, inv['work_order_id'], inv['current_version_id'], cust_taxable, loc_taxable, username)
    _recompute_version_subtotal(cur, inv['current_version_id'], username)

    conn.commit()
    cur.close(); conn.close()
    flash('Lines regenerated from the work order.', 'success')
    return redirect(f'/{company_key}/invoices/{invoice_id}/edit')


def _do_invoice_transition(company_key, invoice_id, to_state, notes):
    """Shared thin dispatcher for every invoice transition route below —
    routes stay dumb, all the logic is transition_invoice()'s."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    ok, reason, extra = transition_invoice(cur, company_key, invoice_id, to_state, session.get('username'), notes=notes)
    if ok:
        conn.commit()
    else:
        conn.rollback()
    cur.close(); conn.close()
    if not ok:
        flash(reason or 'That action could not be completed.', 'error')
        return redirect(f'/{company_key}/invoices/{invoice_id}')
    if extra and extra.get('new_invoice_id'):
        flash('Invoice reissued.', 'success')
        return redirect(f'/{company_key}/invoices/{extra["new_invoice_id"]}')
    flash(f'Invoice moved to {to_state}.', 'success')
    return redirect(f'/{company_key}/invoices/{invoice_id}')


@app.route('/<company_key>/invoices/<int:invoice_id>/harden', methods=['POST'])
@login_required
@company_access_required
def invoice_harden(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Hardened', request.form.get('notes'))

@app.route('/<company_key>/invoices/<int:invoice_id>/reopen', methods=['POST'])
@login_required
@company_access_required
def invoice_reopen(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Live', request.form.get('notes'))

@app.route('/<company_key>/invoices/<int:invoice_id>/send', methods=['POST'])
@login_required
@company_access_required
def invoice_send(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Sent', request.form.get('sent_to_emails'))

@app.route('/<company_key>/invoices/<int:invoice_id>/void', methods=['POST'])
@login_required
@company_access_required
def invoice_void(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Void', request.form.get('void_reason'))

@app.route('/<company_key>/invoices/<int:invoice_id>/reissue', methods=['POST'])
@login_required
@company_access_required
def invoice_reissue(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Reissue', None)

@app.route('/<company_key>/invoices/<int:invoice_id>/revise', methods=['POST'])
@login_required
@company_access_required
def invoice_revise(company_key, invoice_id):
    return _do_invoice_transition(company_key, invoice_id, 'Revise', request.form.get('revision_reason'))

# ============================================================================
# Invoice PDF  (admin + manager + office)
#   Generated on demand, nothing stored to disk. A Hardened/Sent/Superseded
#   version reads ONLY invoices/invoice_versions/invoice_version_line_items
#   (plus customers/service_locations/company_settings/payment_applications,
#   which are never mutated in a way that would change a past invoice's
#   printed content) — never work_orders or catalog_items — so re-downloading
#   the same version's PDF next year is byte-for-byte identical. A Live
#   version additionally live-resolves equipment ordinals (not frozen yet)
#   via _resolve_equipment_labels, which does read catalog_items; that's fine
#   because a Live version's PDF has no reproducibility guarantee to keep.
# ============================================================================

def _parse_payment_terms_days(terms):
    """'Net 30' -> 30, 'Net 15' -> 15, 'Due on Receipt' -> 0, unknown/unset -> 30."""
    if not terms:
        return 30
    t = terms.strip().lower()
    if 'receipt' in t:
        return 0
    m = re.search(r'(\d+)', t)
    return int(m.group(1)) if m else 30


def generate_invoice_pdf(company_key, version_id):
    """Render one invoice version to PDF bytes. Returns None if the version
    doesn't exist."""
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT iv.*, i.invoice_number, i.invoice_date, i.work_site_label, i.wtn_po_number,
               i.customer_id, i.service_location_id,
               c.property_name AS customer_name, c.address AS customer_address,
               c.address_2 AS customer_address_2, c.city AS customer_city,
               c.state AS customer_state, c.zip AS customer_zip, c.payment_terms,
               sl.location_name, sl.address AS location_address, sl.city AS location_city,
               sl.state AS location_state, sl.zip AS location_zip
        FROM invoice_versions iv
        JOIN invoices i ON i.id = iv.invoice_id
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN service_locations sl ON sl.id = i.service_location_id
        WHERE iv.id = %s AND iv.deleted_at IS NULL
    """, (version_id,))
    data = cur.fetchone()
    if not data:
        cur.close(); conn.close()
        return None

    cur.execute("""
        SELECT id, description, resolved_label, quantity, unit_price, total, is_taxable,
               deployed_at, retrieved_at
        FROM invoice_version_line_items
        WHERE version_id = %s AND deleted_at IS NULL
        ORDER BY sort_order, id
    """, (version_id,))
    lines = cur.fetchall()

    live_labels = {}
    if data['state'] == 'Live':
        live_labels = _resolve_equipment_labels(cur, version_id)

    cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    settings = cur.fetchone() or {}

    applications = []
    if _payments_tables_exist(cur):
        cur.execute("""
            SELECT amount, applied_date FROM payment_applications
            WHERE invoice_id = %s ORDER BY id
        """, (data['invoice_id'],))
        applications = cur.fetchall()

    balance = invoice_balance(cur, data['invoice_id'])
    cur.close(); conn.close()

    branding = COMPANY_BRANDING.get(company_key, {})
    primary_hex = branding.get('color_primary', '#2C2C2C')
    primary = colors.HexColor(primary_hex)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             rightMargin=0.6*inch, leftMargin=0.6*inch,
                             topMargin=0.6*inch, bottomMargin=0.6*inch,
                             pageCompression=0)  # uncompressed content streams; a one-page
                                                  # invoice is tiny either way, and this keeps
                                                  # the output diffable/greppable for testing
    # ReportLab stamps CreationDate/ModDate/a fresh document ID by default,
    # which would make two calls for the SAME hardened version produce
    # different bytes purely from timestamps — defeating the "byte-for-byte
    # reproducible" requirement. `invariant` fixes those to constant
    # placeholder values so identical content really does produce identical
    # bytes.
    doc.invariant = 1
    styles = getSampleStyleSheet()
    normal = styles['Normal']
    small  = ParagraphStyle('small', parent=normal, fontSize=8, textColor=colors.grey)
    h2     = ParagraphStyle('h2', parent=styles['Heading2'], textColor=primary, fontSize=11)

    elements = []

    company_name = settings.get('legal_name') or settings.get('company_name') or branding.get('name', company_key)
    company_lines = [f'<b>{company_name}</b>']
    if settings.get('address'):
        addr = settings['address']
        if settings.get('address_2'):
            addr += ', ' + settings['address_2']
        company_lines.append(addr)
    city_line = ', '.join(x for x in [settings.get('city'), settings.get('state')] if x)
    if city_line or settings.get('zip'):
        company_lines.append((city_line + ' ' + (settings.get('zip') or '')).strip())
    if settings.get('phone'):
        company_lines.append(settings['phone'])

    rev_bit = f' Rev {data["revision_number"]}' if data['revision_number'] > 0 else ''
    header_data = [[
        Paragraph('<br/>'.join(company_lines), normal),
        Paragraph(
            f'<para alignment="right"><font size="22" color="{primary_hex}"><b>INVOICE</b></font><br/>'
            f'{data["invoice_number"]}{rev_bit}</para>', normal
        ),
    ]]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.4*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))

    due_days = _parse_payment_terms_days(data.get('payment_terms'))
    due_date = data['invoice_date'] + timedelta(days=due_days)

    meta_rows = [['Invoice Date', str(data['invoice_date'])], ['Due Date', str(due_date)]]
    if data.get('wtn_po_number'):
        meta_rows.append(['PO / WTN', data['wtn_po_number']])

    cust_lines = [f"<b>{data['customer_name']}</b>"]
    if data.get('location_name') or data.get('location_address'):
        if data.get('location_name'):
            cust_lines.append(data['location_name'])
        if data.get('location_address'):
            cust_lines.append(data['location_address'])
        loc_city_line = ', '.join(x for x in [data.get('location_city'), data.get('location_state')] if x)
        if loc_city_line:
            cust_lines.append(loc_city_line + (' ' + data['location_zip'] if data.get('location_zip') else ''))
    elif data.get('customer_address'):
        cust_lines.append(data['customer_address'])
    if data.get('work_site_label'):
        cust_lines.append(f"Site: {data['work_site_label']}")

    info_data = [[
        Paragraph('<br/>'.join(l for l in cust_lines if l), normal),
        Table([[k, v] for k, v in meta_rows], colWidths=[1.1*inch, 1.6*inch],
              style=TableStyle([('FONTSIZE', (0, 0), (-1, -1), 9), ('ALIGN', (1, 0), (1, -1), 'RIGHT')])),
    ]]
    info_table = Table(info_data, colWidths=[3.5*inch, 3.4*inch])
    info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.25*inch))

    # ---- Line items ----
    # Per-day equipment lines show their own day math ("Deployed ... - Retrieved
    # ...") in the description rather than a registry unit name — each row is
    # already one physical unit (the resolved_label ordinal handles "which
    # one"), so there is no single grouped "N units" figure to show here; see
    # docs/DECISIONS-MADE-DURING-BUILD.md for why this departs from the
    # directive's literal "3 units x 4 days" example.
    has_equipment_line = False
    table_data = [['Description', 'Qty', 'Unit', 'Price', 'Total']]
    for li in lines:
        is_equipment = li['deployed_at'] is not None
        if is_equipment:
            has_equipment_line = True
        label = li['resolved_label'] or live_labels.get(li['id']) or li['description'] or ''
        desc_parts = [f'<font size="9">{label}</font>']
        if is_equipment:
            if li['retrieved_at']:
                desc_parts.append(f'<font size="8" color="grey">Deployed {li["deployed_at"]} &ndash; Retrieved {li["retrieved_at"]}</font>')
            else:
                desc_parts.append(f'<font size="8" color="grey">Deployed {li["deployed_at"]} (in progress)</font>')
        elif li['description'] and li['description'] != label:
            desc_parts.append(f'<font size="8" color="grey">{li["description"]}</font>')
        unit = 'day' if is_equipment else 'ea'
        qty = li['quantity'] if li['quantity'] is not None else '—'
        total_disp = f"${li['total']:.2f}" if li['total'] is not None else 'TBD'
        table_data.append([
            Paragraph('<br/>'.join(desc_parts), normal),
            str(qty), unit, f"${li['unit_price']:.2f}", total_disp,
        ])

    line_table = Table(table_data, colWidths=[3.2*inch, 0.6*inch, 0.6*inch, 0.9*inch, 0.9*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.15*inch))

    # ---- Totals ----
    totals_rows = [['Subtotal', f"${data['subtotal']:.2f}"]]
    if data['total'] is not None:
        tax_label = f"Tax ({data['tax_rate_pct'] or 0}%"
        if data.get('tax_county'):
            tax_label += f" — {data['tax_county']}"
        tax_label += ')'
        totals_rows.append([tax_label, f"${data['tax_total'] or 0:.2f}"])
        totals_rows.append(['Total', f"${data['total']:.2f}"])
        if applications:
            paid_total = sum(float(a['amount']) for a in applications)
            totals_rows.append(['Payments Applied', f"-${paid_total:.2f}"])
        if balance is not None:
            totals_rows.append(['Balance Due', f"${balance:.2f}"])

    totals_table = Table(totals_rows, colWidths=[5.3*inch, 0.9*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 0.75, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.25*inch))

    if has_equipment_line and settings.get('extraction_explainer_text'):
        elements.append(Paragraph('Drying &amp; Monitoring Process', h2))
        elements.append(Paragraph(settings['extraction_explainer_text'], small))
        elements.append(Spacer(1, 0.2*inch))

    if data.get('notes_to_customer'):
        elements.append(Paragraph(data['notes_to_customer'], normal))
        elements.append(Spacer(1, 0.15*inch))

    if settings.get('remit_to_text'):
        elements.append(Paragraph('Remit To', h2))
        elements.append(Paragraph(settings['remit_to_text'].replace('\n', '<br/>'), small))
        elements.append(Spacer(1, 0.15*inch))

    if settings.get('invoice_footer_text'):
        elements.append(Spacer(1, 0.2*inch))
        elements.append(Paragraph(settings['invoice_footer_text'].replace('\n', '<br/>'), small))

    doc.build(elements)
    return buf.getvalue()


@app.route('/<company_key>/invoices/<int:invoice_id>/pdf')
@login_required
@company_access_required
def invoice_pdf(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT current_version_id, invoice_number FROM invoices
        WHERE id = %s AND deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    cur.close(); conn.close()
    if not inv or not inv['current_version_id']:
        abort(404)
    pdf_bytes = generate_invoice_pdf(company_key, inv['current_version_id'])
    if pdf_bytes is None:
        abort(404)
    return Response(pdf_bytes, mimetype='application/pdf',
                     headers={'Content-Disposition': f'inline; filename="{inv["invoice_number"]}.pdf"'})


@app.route('/<company_key>/invoices/<int:invoice_id>/versions/<int:version_id>/pdf')
@login_required
@company_access_required
def invoice_version_pdf(company_key, invoice_id, version_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT iv.id, i.invoice_number, iv.revision_number
        FROM invoice_versions iv JOIN invoices i ON i.id = iv.invoice_id
        WHERE iv.id = %s AND iv.invoice_id = %s AND iv.deleted_at IS NULL
    """, (version_id, invoice_id))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        abort(404)
    pdf_bytes = generate_invoice_pdf(company_key, version_id)
    if pdf_bytes is None:
        abort(404)
    filename = row['invoice_number'] + (f'-rev{row["revision_number"]}' if row['revision_number'] else '') + '.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                     headers={'Content-Disposition': f'inline; filename="{filename}"'})

# ============================================================================
# Payments, applications, adjustments  (admin + manager + office)
#   "Unapplied amount on a payment IS the credit" — no separate credits table.
#   payment_applications is append-only: un-apply inserts a reversal row,
#   never mutates. See migration 011 and docs/DECISIONS-MADE-DURING-BUILD.md.
# ============================================================================

def _remaining_unapplied(cur, payment_id):
    """A payment's unapplied balance = amount - refunded_amount - SUM(ALL
    applications, originals + reversals). This number IS the credit —
    nothing else stores it. Returns None if the payment doesn't exist.
    Summing ALL rows (not just reverses_application_id IS NULL ones) is
    deliberate: a reversal's negative amount is what nets an original back
    out when un-applied — filtering it away would make an un-apply never
    actually restore the unapplied balance."""
    cur.execute("SELECT amount, refunded_amount FROM payments WHERE id = %s AND deleted_at IS NULL", (payment_id,))
    p = cur.fetchone()
    if not p:
        return None
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS n FROM payment_applications
        WHERE payment_id = %s
    """, (payment_id,))
    applied = float(cur.fetchone()['n'] or 0)
    return float(p['amount']) - float(p['refunded_amount'] or 0) - applied


def customer_unapplied_credit(cur, customer_id):
    """Total unapplied credit across a customer's received payments — drives
    the red "Unapplied credit $X — resolve" badge everywhere a customer
    appears (directive §2.4: credits are never quiet)."""
    cur.execute("""
        SELECT p.id, p.amount, p.refunded_amount,
               COALESCE((SELECT SUM(pa.amount) FROM payment_applications pa
                         WHERE pa.payment_id = p.id), 0) AS applied
        FROM payments p
        WHERE p.customer_id = %s AND p.status = 'received' AND p.deleted_at IS NULL
    """, (customer_id,))
    total = 0.0
    for p in cur.fetchall():
        total += float(p['amount']) - float(p['refunded_amount'] or 0) - float(p['applied'])
    return total


def _apply_payment(cur, payment_id, invoice_id, amount, applied_date, username, reason=None):
    """Apply `amount` of `payment_id` to `invoice_id`. Rejected if it would
    exceed EITHER the invoice's remaining balance or the payment's remaining
    unapplied amount (directive §2.4). Returns (ok, error)."""
    amount = round(float(amount), 2)
    if amount <= 0:
        return False, 'Application amount must be positive.'
    remaining = _remaining_unapplied(cur, payment_id)
    if remaining is None:
        return False, 'Payment not found.'
    if amount > remaining + 0.005:
        return False, f'Amount exceeds this payment\'s unapplied balance (${remaining:.2f}).'
    bal = invoice_balance(cur, invoice_id)
    if bal is None:
        return False, 'Invoice not found.'
    if amount > bal + 0.005:
        return False, f'Amount exceeds the invoice balance (${bal:.2f}).'
    cur.execute("""
        INSERT INTO payment_applications (payment_id, invoice_id, amount, applied_date, reason, created_by)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (payment_id, invoice_id, amount, applied_date, reason, username))
    return True, None


def _record_payment(cur, customer_id, payment_date, amount, payment_method_id,
                     reference_number, notes, username, apply_to_invoice_id=None):
    """Insert a payment (against a customer) and, optionally, one initial
    application. Returns (payment_id, error). Caller owns commit."""
    amount = round(float(amount), 2)
    if amount <= 0:
        return None, 'Payment amount must be positive.'
    cur.execute("""
        INSERT INTO payments (customer_id, payment_date, amount, payment_method_id,
                               reference_number, notes, created_by, updated_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
    """, (customer_id, payment_date, amount, payment_method_id, reference_number, notes, username, username))
    payment_id = cur.fetchone()['id']
    cur.execute("""
        INSERT INTO payment_status_history (payment_id, event, changed_by, notes)
        VALUES (%s, 'received', %s, %s)
    """, (payment_id, username, f'${amount:.2f} recorded.'))

    if apply_to_invoice_id:
        ok, err = _apply_payment(cur, payment_id, apply_to_invoice_id, amount, payment_date, username)
        if not ok:
            return payment_id, err
    return payment_id, None


def _unapply_payment(cur, application_id, username, reason=None):
    """Insert a reversal row for one application. Never mutates/deletes the
    original — the append-only ledger is the point."""
    cur.execute("""
        SELECT id, payment_id, invoice_id, amount FROM payment_applications
        WHERE id = %s AND reverses_application_id IS NULL
    """, (application_id,))
    app = cur.fetchone()
    if not app:
        return False, 'Application not found.'
    cur.execute("SELECT id FROM payment_applications WHERE reverses_application_id = %s", (application_id,))
    if cur.fetchone():
        return False, 'This application has already been un-applied.'
    cur.execute("""
        INSERT INTO payment_applications
            (payment_id, invoice_id, amount, applied_date, reverses_application_id, reason, created_by)
        VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s)
    """, (app['payment_id'], app['invoice_id'], -app['amount'], application_id, reason, username))
    return True, None


def _void_payment(cur, payment_id, username, reason):
    """status='voided' + a reversal row for every still-active application.
    Reason required — voiding a payment is never silent."""
    reason = (reason or '').strip()
    if not reason:
        return False, 'A void reason is required.'
    cur.execute("SELECT status FROM payments WHERE id = %s AND deleted_at IS NULL", (payment_id,))
    p = cur.fetchone()
    if not p:
        return False, 'Payment not found.'
    if p['status'] == 'voided':
        return False, 'Payment is already voided.'

    cur.execute("""
        SELECT pa.id FROM payment_applications pa
        WHERE pa.payment_id = %s AND pa.reverses_application_id IS NULL
          AND NOT EXISTS (SELECT 1 FROM payment_applications r WHERE r.reverses_application_id = pa.id)
    """, (payment_id,))
    for app in cur.fetchall():
        _unapply_payment(cur, app['id'], username, reason=f'Voided: {reason}')

    cur.execute("""
        UPDATE payments
        SET status = 'voided', voided_at = CURRENT_TIMESTAMP, voided_by = %s, void_reason = %s,
            updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (username, reason, username, payment_id))
    cur.execute("""
        INSERT INTO payment_status_history (payment_id, event, changed_by, notes)
        VALUES (%s, 'voided', %s, %s)
    """, (payment_id, username, reason))
    return True, None


def _refund_payment(cur, payment_id, amount, reference, notes, username):
    """A customer who is owed money is refunded, not written off — this is
    the only disposition for a payment's unapplied balance besides applying
    it elsewhere (directive §2.4)."""
    amount = round(float(amount), 2) if amount else 0
    if amount <= 0:
        return False, 'Refund amount must be positive.'
    remaining = _remaining_unapplied(cur, payment_id)
    if remaining is None:
        return False, 'Payment not found.'
    if amount > remaining + 0.005:
        return False, f'Amount exceeds the unapplied balance (${remaining:.2f}).'
    cur.execute("""
        UPDATE payments
        SET refunded_amount = refunded_amount + %s, refunded_at = CURRENT_TIMESTAMP,
            refund_reference = %s, refund_notes = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s
    """, (amount, reference, notes, username, payment_id))
    cur.execute("""
        INSERT INTO payment_status_history (payment_id, event, changed_by, notes)
        VALUES (%s, 'refunded', %s, %s)
    """, (payment_id, username, f'${amount:.2f} refunded' + (f' ({reference})' if reference else '')))
    return True, None


def _next_unpaid_invoice(cur, exclude_invoice_id, customer_id=None):
    """Next open receivable with balance > 0 — same customer first (oldest
    invoice_date), else company-wide oldest. Powers the "Next Unpaid Invoice"
    link after a payment pays one off in full."""
    def scan(cust_filter):
        where = "i.deleted_at IS NULL AND i.receivable_state = 'open' AND i.id != %s"
        params = [exclude_invoice_id]
        if cust_filter:
            where += " AND i.customer_id = %s"
            params.append(cust_filter)
        cur.execute(f"SELECT i.id FROM invoices i WHERE {where} ORDER BY i.invoice_date ASC, i.id ASC", params)
        for row in cur.fetchall():
            bal = invoice_balance(cur, row['id'])
            if bal is not None and bal > 0.005:
                return row['id']
        return None
    if customer_id:
        found = scan(customer_id)
        if found:
            return found
    return scan(None)


@app.route('/<company_key>/payments/new', methods=['POST'])
@login_required
@company_access_required
def payment_new(company_key):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    customer_id       = _opt_num(request.form.get('customer_id'))
    payment_date      = request.form.get('payment_date', '').strip() or datetime.now().date().isoformat()
    amount            = _opt_num(request.form.get('amount'))
    payment_method_id = _opt_num(request.form.get('payment_method_id'))
    reference_number  = request.form.get('reference_number', '').strip() or None
    notes             = request.form.get('notes', '').strip() or None
    apply_to_invoice_id = _opt_num(request.form.get('apply_to_invoice_id'))
    redirect_to       = request.form.get('redirect_to') or f'/{company_key}/payments'

    if not customer_id or not amount:
        flash('Customer and an amount are required.', 'error')
        return redirect(redirect_to)

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    username = session.get('username')
    payment_id, err = _record_payment(cur, customer_id, payment_date, amount, payment_method_id,
                                       reference_number, notes, username,
                                       apply_to_invoice_id=apply_to_invoice_id)
    if err:
        conn.rollback()
        cur.close(); conn.close()
        flash(err, 'error')
        return redirect(redirect_to)
    conn.commit()

    if apply_to_invoice_id:
        bal = invoice_balance(cur, apply_to_invoice_id)
        cur.close(); conn.close()
        if bal is not None and bal <= 0.005:
            flash('Payment recorded — invoice paid in full! 🎉', 'success')
        else:
            flash('Payment recorded.', 'success')
        return redirect(f'/{company_key}/invoices/{apply_to_invoice_id}')

    cur.close(); conn.close()
    flash('Payment recorded.', 'success')
    return redirect(redirect_to)


@app.route('/<company_key>/invoices/<int:invoice_id>/payments/apply', methods=['POST'])
@login_required
@company_access_required
def invoice_payment_apply(company_key, invoice_id):
    """Apply an EXISTING payment's unapplied balance to this invoice — the
    route behind the invoice detail "Apply Existing Credit" action."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    payment_id = _opt_num(request.form.get('payment_id'))
    amount     = _opt_num(request.form.get('amount'))
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    if not payment_id or not amount:
        cur.close(); conn.close()
        flash('Choose a payment and an amount.', 'error')
        return redirect(f'/{company_key}/invoices/{invoice_id}')
    ok, err = _apply_payment(cur, payment_id, invoice_id, amount, datetime.now().date().isoformat(), session.get('username'))
    if ok:
        conn.commit()
        flash('Credit applied.', 'success')
    else:
        conn.rollback()
        flash(err, 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/invoices/{invoice_id}')


@app.route('/<company_key>/payments')
@login_required
@company_access_required
@with_branding
def payments_list(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    search        = request.args.get('search', '').strip()
    method_filter = _opt_num(request.args.get('method'))
    date_from     = request.args.get('date_from', '').strip()
    date_to       = request.args.get('date_to', '').strip()
    unapplied_only = request.args.get('unapplied') == '1'

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    conditions = ["p.deleted_at IS NULL"]
    params = []
    if search:
        conditions.append("(c.property_name ILIKE %s OR p.reference_number ILIKE %s)")
        params += [f'%{search}%', f'%{search}%']
    if method_filter:
        conditions.append("p.payment_method_id = %s"); params.append(method_filter)
    if date_from:
        conditions.append("p.payment_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("p.payment_date <= %s"); params.append(date_to)
    where = " AND ".join(conditions)

    cur.execute(f"""
        SELECT p.id, p.payment_date, p.amount, p.status, p.refunded_amount,
               c.property_name AS customer_name, pm.name AS method_name
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN payment_methods pm ON pm.id = p.payment_method_id
        WHERE {where}
        ORDER BY p.payment_date DESC, p.id DESC
    """, params)
    rows = cur.fetchall()
    payments = []
    for r in rows:
        remaining = _remaining_unapplied(cur, r['id']) if r['status'] == 'received' else 0
        if unapplied_only and not (remaining and remaining > 0.005):
            continue
        payments.append({**r, 'unapplied': remaining})

    cur.execute("SELECT id, name FROM payment_methods WHERE deleted_at IS NULL ORDER BY sort_order")
    methods = cur.fetchall()
    cur.close(); conn.close()
    return render_template('payments_list.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        payments=payments, methods=methods, search=search, method_filter=method_filter,
        date_from=date_from, date_to=date_to, unapplied_only=unapplied_only,
    )


@app.route('/<company_key>/payments/<int:payment_id>')
@login_required
@company_access_required
@with_branding
def payment_detail(company_key, payment_id, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT p.*, c.property_name AS customer_name, pm.name AS method_name
        FROM payments p
        JOIN customers c ON c.id = p.customer_id
        LEFT JOIN payment_methods pm ON pm.id = p.payment_method_id
        WHERE p.id = %s AND p.deleted_at IS NULL
    """, (payment_id,))
    payment = cur.fetchone()
    if not payment:
        cur.close(); conn.close()
        abort(404)

    cur.execute("""
        SELECT pa.*, i.invoice_number
        FROM payment_applications pa
        JOIN invoices i ON i.id = pa.invoice_id
        WHERE pa.payment_id = %s
        ORDER BY pa.id
    """, (payment_id,))
    applications = cur.fetchall()
    reversed_ids = {a['reverses_application_id'] for a in applications if a['reverses_application_id']}

    cur.execute("""
        SELECT *, to_char(changed_at, 'Mon DD, YYYY HH12:MI AM') AS changed_at_display
        FROM payment_status_history WHERE payment_id = %s ORDER BY changed_at DESC, id DESC
    """, (payment_id,))
    history = cur.fetchall()

    remaining = _remaining_unapplied(cur, payment_id)

    # Open receivables for this customer, for the "apply elsewhere" picker.
    cur.execute("""
        SELECT i.id, i.invoice_number FROM invoices i
        WHERE i.customer_id = %s AND i.deleted_at IS NULL AND i.receivable_state = 'open'
        ORDER BY i.invoice_date
    """, (payment['customer_id'],))
    open_invoices = cur.fetchall()

    cur.close(); conn.close()
    return render_template('payment_detail.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        payment=payment, applications=applications, reversed_ids=reversed_ids,
        history=history, remaining=remaining, open_invoices=open_invoices,
    )


@app.route('/<company_key>/payments/<int:payment_id>/unapply/<int:application_id>', methods=['POST'])
@login_required
@company_access_required
def payment_unapply(company_key, payment_id, application_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    ok, err = _unapply_payment(cur, application_id, session.get('username'), reason=request.form.get('reason'))
    if ok:
        conn.commit()
        flash('Application un-applied.', 'success')
    else:
        conn.rollback()
        flash(err, 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/payments/{payment_id}')


@app.route('/<company_key>/payments/<int:payment_id>/void', methods=['POST'])
@login_required
@company_access_required
def payment_void(company_key, payment_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    ok, err = _void_payment(cur, payment_id, session.get('username'), request.form.get('void_reason'))
    if ok:
        conn.commit()
        flash('Payment voided.', 'success')
    else:
        conn.rollback()
        flash(err, 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/payments/{payment_id}')


@app.route('/<company_key>/payments/<int:payment_id>/refund', methods=['POST'])
@login_required
@company_access_required
def payment_refund(company_key, payment_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    ok, err = _refund_payment(cur, payment_id, request.form.get('amount'),
                               request.form.get('reference', '').strip() or None,
                               request.form.get('notes', '').strip() or None,
                               session.get('username'))
    if ok:
        conn.commit()
        flash('Refund recorded.', 'success')
    else:
        conn.rollback()
        flash(err, 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/payments/{payment_id}')


@app.route('/<company_key>/invoices/<int:invoice_id>/adjustments/new', methods=['POST'])
@login_required
@company_access_required
def invoice_adjustment_new(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    amount          = _opt_num(request.form.get('amount'))
    adjustment_type = request.form.get('adjustment_type', 'other')
    reason          = request.form.get('reason', '').strip()

    error = None
    if not amount or float(amount) <= 0:
        error = 'A positive amount is required.'
    elif adjustment_type not in ('write_off', 'discount', 'late_fee', 'other'):
        error = 'Invalid adjustment type.'
    elif not reason:
        error = 'A reason is required.'

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    if error:
        cur.close(); conn.close()
        flash(error, 'error')
        return redirect(f'/{company_key}/invoices/{invoice_id}')

    username = session.get('username')
    cur.execute("""
        INSERT INTO invoice_adjustments
            (invoice_id, effective_date, amount, adjustment_type, reason, created_by, updated_by)
        VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s)
    """, (invoice_id, amount, adjustment_type, reason, username, username))
    conn.commit()
    cur.close(); conn.close()
    flash('Adjustment recorded.', 'success')
    return redirect(f'/{company_key}/invoices/{invoice_id}')


@app.route('/<company_key>/invoices/<int:invoice_id>/adjustments/<int:adjustment_id>/delete', methods=['POST'])
@login_required
@company_access_required
def invoice_adjustment_delete(company_key, invoice_id, adjustment_id):
    """Soft-delete only if created today by this same user; otherwise a
    reversal row (directive §2.4's adjustment audit rule)."""
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    username = session.get('username')
    cur.execute("""
        SELECT id, effective_date, amount, adjustment_type, created_by, created_at::date AS created_date
        FROM invoice_adjustments WHERE id = %s AND invoice_id = %s AND deleted_at IS NULL
    """, (adjustment_id, invoice_id))
    adj = cur.fetchone()
    if not adj:
        cur.close(); conn.close()
        abort(404)
    if adj['created_by'] == username and adj['created_date'] == datetime.now().date():
        cur.execute("""
            UPDATE invoice_adjustments SET deleted_at = CURRENT_TIMESTAMP, deleted_by = %s WHERE id = %s
        """, (username, adjustment_id))
        flash('Adjustment removed.', 'success')
    else:
        cur.execute("""
            INSERT INTO invoice_adjustments
                (invoice_id, effective_date, amount, adjustment_type, reason, created_by, updated_by)
            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s)
        """, (invoice_id, -adj['amount'], adj['adjustment_type'],
              f'Reversal of adjustment #{adjustment_id}', username, username))
        flash('Adjustment reversed (it was created on an earlier day).', 'success')
    conn.commit()
    cur.close(); conn.close()
    return redirect(f'/{company_key}/invoices/{invoice_id}')

# ============================================================================
# Statements  (admin + manager + office)
#   Replaces the Phase 0 statement generator — Michele's customers already
#   recognize that layout, so this deliberately echoes its visual language
#   (scripts/generate_pdf_statement.py in ~/docker/statements) rather than
#   inventing a new look: same title treatment, same customer-info box style,
#   same per-invoice table shape, same payment-due notice.
# ============================================================================

def _aging_bucket_label(days):
    """Same buckets the Phase 0 statement (and the future AR aging report,
    Increment 1.8) use: Current (0-30) / 31-60 / 61-90 / 90+, aged from
    invoice_date (Net 30 assumption per the directive's AR aging spec)."""
    if days < 0:
        return 'FUTURE'
    elif days <= 30:
        return 'CURRENT'
    elif days <= 60:
        return '31-60 DAYS'
    elif days <= 90:
        return '61-90 DAYS'
    else:
        return '90+ DAYS'


def _sanitize_filename(name):
    """Strip filesystem-unsafe characters — in particular the '*' Kleanit
    property names sometimes carry (the Phase 0 FL-vs-Charlotte marker
    convention) — and collapse whitespace to underscores."""
    name = re.sub(r'[\\/*?:"<>|]', '', name or '')
    name = re.sub(r'\s+', '_', name.strip())
    return name or 'customer'


def generate_statement_pdf(company_key, customer_id, as_of_date=None):
    """All of one customer's open receivables with balance > 0, aged from
    invoice_date into Current/31-60/61-90/90+, plus any unapplied credit
    shown as a negative line with a note. Returns (pdf_bytes, customer_name),
    or (None, None) if the customer doesn't exist."""
    if as_of_date is None:
        as_of_date = date.today()
    elif isinstance(as_of_date, str):
        as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        SELECT id, property_name, address, address_2, city, state, zip, billing_email
        FROM customers WHERE id = %s AND deleted_at IS NULL
    """, (customer_id,))
    customer = cur.fetchone()
    if not customer:
        cur.close(); conn.close()
        return None, None

    cur.execute("""
        SELECT i.id, i.invoice_number, i.invoice_date, i.current_version_id
        FROM invoices i
        WHERE i.customer_id = %s AND i.deleted_at IS NULL AND i.receivable_state = 'open'
        ORDER BY i.invoice_date
    """, (customer_id,))

    rows = []
    aging_totals = {'CURRENT': 0.0, '31-60 DAYS': 0.0, '61-90 DAYS': 0.0, '90+ DAYS': 0.0}
    for inv in cur.fetchall():
        bal = invoice_balance(cur, inv['id'])
        if bal is None or bal <= 0.005:
            continue
        gross = None
        if inv['current_version_id']:
            cur.execute("SELECT total, subtotal FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
            v = cur.fetchone()
            if v:
                gross = float(v['total']) if v['total'] is not None else float(v['subtotal'])
        days = (as_of_date - inv['invoice_date']).days
        bucket = _aging_bucket_label(days)
        aging_totals[bucket if bucket != 'FUTURE' else 'CURRENT'] = \
            aging_totals.get(bucket if bucket != 'FUTURE' else 'CURRENT', 0) + bal
        rows.append({
            'number': inv['invoice_number'], 'date': inv['invoice_date'],
            'gross': gross, 'due': bal, 'days': days, 'bucket': bucket,
        })

    unapplied_credit = customer_unapplied_credit(cur, customer_id)
    if unapplied_credit > 0.005:
        rows.append({
            'number': 'CREDIT', 'date': None, 'gross': None, 'due': -unapplied_credit,
            'days': None, 'bucket': 'Unapplied credit on account — contact the office to apply or refund',
        })

    total_due = sum(r['due'] for r in rows)

    cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    settings = cur.fetchone() or {}
    cur.close(); conn.close()

    branding = COMPANY_BRANDING.get(company_key, {})
    primary_hex = branding.get('color_primary', '#2C2C2C')
    primary = colors.HexColor(primary_hex)
    secondary = colors.HexColor(branding.get('color_secondary', '#F5F5DC'))
    company_name = settings.get('legal_name') or settings.get('company_name') or branding.get('name', company_key)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                             rightMargin=0.6*inch, leftMargin=0.6*inch,
                             topMargin=0.6*inch, bottomMargin=0.6*inch,
                             pageCompression=0)
    doc.invariant = 1
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('title', parent=styles['Heading1'], fontSize=18,
                                  textColor=primary, spaceAfter=6, alignment=TA_CENTER)
    heading_style = ParagraphStyle('heading', parent=styles['Heading2'], fontSize=12,
                                    textColor=primary, spaceAfter=12)
    date_style = ParagraphStyle('date', parent=styles['Normal'], alignment=TA_RIGHT)
    notice_style = ParagraphStyle('notice', parent=styles['Normal'], fontSize=11,
                                   textColor=primary, alignment=TA_CENTER, spaceAfter=10)

    elements = [
        Paragraph(f'<b>{company_name}</b>', title_style),
        Paragraph('ACCOUNT STATEMENT', title_style),
        Spacer(1, 0.2*inch),
        Paragraph(f'Statement Date: {as_of_date.strftime("%B %d, %Y")}', date_style),
        Spacer(1, 0.3*inch),
    ]

    # ---- Customer info box (same visual shape as the Phase 0 statement) ----
    customer_data = [['Customer Information'], ['Account Name:', customer['property_name']]]
    if customer.get('address'):
        addr = customer['address'] + (', ' + customer['address_2'] if customer.get('address_2') else '')
        customer_data.append(['Address:', addr])
        city_line = ', '.join(x for x in [customer.get('city'), customer.get('state')] if x)
        customer_data.append(['', (city_line + ' ' + (customer.get('zip') or '')).strip()])
    if customer.get('billing_email'):
        customer_data.append(['Email:', customer['billing_email']])

    customer_table = Table(customer_data, colWidths=[1.5*inch, 4.4*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), primary),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (1, 0), 'CENTER'),
        ('SPAN', (0, 0), (1, 0)),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (1, 0), 12),
        ('BACKGROUND', (0, 1), (1, -1), secondary),
        ('GRID', (0, 0), (1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (1, -1), 10),
        ('TOPPADDING', (0, 1), (1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (1, -1), 6),
    ]))
    elements.append(customer_table)
    elements.append(Spacer(1, 0.25*inch))

    # ---- Aging summary strip ----
    aging_data = [
        ['Current', '31-60 Days', '61-90 Days', '90+ Days'],
        [f"${aging_totals['CURRENT']:,.2f}", f"${aging_totals['31-60 DAYS']:,.2f}",
         f"${aging_totals['61-90 DAYS']:,.2f}", f"${aging_totals['90+ DAYS']:,.2f}"],
    ]
    aging_table = Table(aging_data, colWidths=[1.475*inch]*4)
    aging_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(aging_table)
    elements.append(Spacer(1, 0.3*inch))

    # ---- Invoice details ----
    elements.append(Paragraph('<b>INVOICE DETAILS</b>', heading_style))
    invoice_data = [['Invoice #', 'Date', 'Original Amount', 'Amount Due', 'Days', 'Age']]
    for r in rows:
        invoice_data.append([
            str(r['number']),
            r['date'].strftime('%m/%d/%Y') if r['date'] else '—',
            f"${r['gross']:,.2f}" if r['gross'] is not None else '—',
            f"${r['due']:,.2f}",
            str(r['days']) if r['days'] is not None else '—',
            r['bucket'],
        ])
    invoice_data.append(['TOTAL', '', '', f"${total_due:,.2f}", '', ''])

    invoice_table = Table(invoice_data, colWidths=[0.9*inch, 0.85*inch, 1.15*inch, 1.05*inch, 0.5*inch, 1.45*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -2), secondary),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'CENTER'),
        ('FONTSIZE', (0, 1), (-1, -2), 8.5),
        ('TOPPADDING', (0, 1), (-1, -2), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 4),
        ('BACKGROUND', (0, -1), (-1, -1), primary),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 10.5),
        ('SPAN', (0, -1), (2, -1)),
        ('ALIGN', (0, -1), (0, -1), 'CENTER'),
    ]))
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))

    if total_due > 0.005:
        elements.append(Paragraph('PAYMENT REQUIRED', notice_style))
        elements.append(Paragraph(f'Please remit payment of <b>${total_due:,.2f}</b> to the address below.',
                                   styles['Normal']))
        elements.append(Spacer(1, 0.15*inch))

    if settings.get('remit_to_text'):
        elements.append(Paragraph('<b>Remit To</b>', heading_style))
        elements.append(Paragraph(settings['remit_to_text'].replace('\n', '<br/>'), styles['Normal']))

    doc.build(elements)
    return buf.getvalue(), customer['property_name']


@app.route('/<company_key>/customers/<int:customer_id>/statement')
@login_required
@company_access_required
def customer_statement_pdf(company_key, customer_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    as_of = request.args.get('as_of', '').strip() or None
    pdf_bytes, cust_name = generate_statement_pdf(company_key, customer_id, as_of)
    if pdf_bytes is None:
        abort(404)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("UPDATE customers SET last_statement_at = CURRENT_TIMESTAMP WHERE id = %s", (customer_id,))
    conn.commit()
    cur.close(); conn.close()
    filename = f'{_sanitize_filename(cust_name)}_statement.pdf'
    return Response(pdf_bytes, mimetype='application/pdf',
                     headers={'Content-Disposition': f'inline; filename="{filename}"'})


@app.route('/<company_key>/billing/statements', methods=['POST'])
@login_required
@company_access_required
def billing_statements_batch(company_key):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    customer_ids = request.form.getlist('customer_ids')
    as_of = request.form.get('as_of', '').strip() or None
    if not customer_ids:
        flash('Select at least one customer.', 'error')
        return redirect(f'/{company_key}/billing')

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    buf = io.BytesIO()
    generated = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for cid in customer_ids:
            pdf_bytes, cust_name = generate_statement_pdf(company_key, int(cid), as_of)
            if pdf_bytes is None:
                continue
            filename = f'{_sanitize_filename(cust_name)}_statement_{(as_of or date.today().isoformat())}.pdf'
            zf.writestr(filename, pdf_bytes)
            cur.execute("UPDATE customers SET last_statement_at = CURRENT_TIMESTAMP WHERE id = %s", (int(cid),))
            generated += 1
    conn.commit()
    cur.close(); conn.close()

    if generated == 0:
        flash('No statements were generated — none of the selected customers were found.', 'error')
        return redirect(f'/{company_key}/billing')

    buf.seek(0)
    return Response(buf.getvalue(), mimetype='application/zip',
                     headers={'Content-Disposition': f'attachment; filename="statements_{date.today().isoformat()}.zip"'})

# ============================================================================
# Billing — Michele's batch billing page
# ============================================================================

def _customer_aging_summary(cur, customer_id):
    """One customer's open receivables with balance > 0, bucketed the same
    way generate_statement_pdf ages a statement (_aging_bucket_label).
    Returns (buckets_dict, total_due, oldest_invoice_date_or_None). Shared by
    the billing page and the A/R aging report so the two can never disagree."""
    cur.execute("""
        SELECT id, invoice_date FROM invoices
        WHERE customer_id = %s AND deleted_at IS NULL AND receivable_state = 'open'
        ORDER BY invoice_date
    """, (customer_id,))
    buckets = {'CURRENT': 0.0, '31-60 DAYS': 0.0, '61-90 DAYS': 0.0, '90+ DAYS': 0.0}
    total = 0.0
    oldest = None
    today = date.today()
    for inv in cur.fetchall():
        bal = invoice_balance(cur, inv['id'])
        if bal is None or bal <= 0.005:
            continue
        days = (today - inv['invoice_date']).days
        bucket = _aging_bucket_label(days)
        buckets[bucket if bucket != 'FUTURE' else 'CURRENT'] += bal
        total += bal
        if oldest is None or inv['invoice_date'] < oldest:
            oldest = inv['invoice_date']
    return buckets, total, oldest


# Delinquent threshold: 90 days past invoice date, per Chris's 2026-09-18 answer
# (directive's own default was 60 — see docs/DECISIONS-MADE-DURING-BUILD.md D-001).
DELINQUENT_DAYS_PAST_INVOICE = 90


@app.route('/<company_key>/billing')
@login_required
@company_access_required
@with_branding
def billing(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    filter_type = request.args.get('filter', 'all')
    search = request.args.get('search', '').strip()

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    conditions = ["c.deleted_at IS NULL", "c.status = 'Active'"]
    params = []
    if search:
        conditions.append("c.property_name ILIKE %s")
        params.append(f'%{search}%')
    where = " AND ".join(conditions)
    cur.execute(f"""
        SELECT
            c.id, c.property_name, c.customer_type, c.last_statement_at,
            mc.name as management_company_name,
            COUNT(cc.id) FILTER (
                WHERE cc.accepts_billing = TRUE AND cc.deleted_at IS NULL
            ) as billing_contact_count,
            STRING_AGG(
                cc.office_email, ', ' ORDER BY cc.is_primary DESC, cc.last_name ASC
            ) FILTER (
                WHERE cc.accepts_billing = TRUE AND cc.deleted_at IS NULL AND cc.office_email IS NOT NULL
            ) as billing_emails,
            MAX(cc.first_name || ' ' || cc.last_name)
                FILTER (WHERE cc.accepts_billing = TRUE AND cc.is_primary = TRUE AND cc.deleted_at IS NULL)
                as primary_billing_name
        FROM customers c
        LEFT JOIN management_companies mc ON c.management_company_id = mc.id
        LEFT JOIN customer_contacts cc ON cc.customer_id = c.id
        WHERE {where}
        GROUP BY c.id, c.property_name, c.customer_type, c.last_statement_at, mc.name
        ORDER BY c.property_name ASC
    """, params)
    raw_customers = cur.fetchall()

    today = date.today()
    rows = []
    for c in raw_customers:
        buckets, total_due, oldest = _customer_aging_summary(cur, c['id'])
        unapplied = customer_unapplied_credit(cur, c['id'])
        delinquent = oldest is not None and (today - oldest).days > DELINQUENT_DAYS_PAST_INVOICE
        cur.execute("""
            SELECT 1 FROM customer_compliance_portals
            WHERE customer_id = %s AND is_active = TRUE AND portal_is_primary_billing = TRUE
            LIMIT 1
        """, (c['id'],))
        portal_billed = cur.fetchone() is not None

        if filter_type == 'balance' and total_due <= 0.005:
            continue
        if filter_type == 'delinquent' and not delinquent:
            continue
        if filter_type == 'no_contact' and c['billing_contact_count'] > 0:
            continue
        if filter_type == 'portal' and not portal_billed:
            continue

        open_invoices = []
        if total_due > 0.005:
            cur.execute("""
                SELECT id, invoice_number FROM invoices
                WHERE customer_id = %s AND deleted_at IS NULL AND receivable_state = 'open'
                ORDER BY invoice_date
            """, (c['id'],))
            for inv in cur.fetchall():
                bal = invoice_balance(cur, inv['id'])
                if bal and bal > 0.005:
                    open_invoices.append({'id': inv['id'], 'number': inv['invoice_number'], 'balance': round(bal, 2)})

        rows.append({
            'id': c['id'], 'property_name': c['property_name'], 'customer_type': c['customer_type'],
            'management_company_name': c['management_company_name'],
            'billing_contact_count': c['billing_contact_count'], 'billing_emails': c['billing_emails'],
            'primary_billing_name': c['primary_billing_name'], 'last_statement_at': c['last_statement_at'],
            'current': buckets['CURRENT'], 'b31_60': buckets['31-60 DAYS'], 'b61_90': buckets['61-90 DAYS'],
            'b90_plus': buckets['90+ DAYS'], 'total_due': total_due, 'oldest': oldest,
            'unapplied_credit': unapplied, 'delinquent': delinquent, 'portal_billed': portal_billed,
            'open_invoices': open_invoices,
        })

    total_outstanding = sum(r['total_due'] for r in rows)
    customers_with_balance = sum(1 for r in rows if r['total_due'] > 0.005)
    count_90_plus = sum(1 for r in rows if r['b90_plus'] > 0.005)
    open_credits = [r for r in rows if r['unapplied_credit'] > 0.005]

    cur.close(); conn.close()
    return render_template('billing.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        rows=rows, filter_type=filter_type, search=search,
        total_outstanding=total_outstanding, customers_with_balance=customers_with_balance,
        count_90_plus=count_90_plus, open_credits=open_credits,
        resend_configured=bool(RESEND_API_KEY),
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
# A/R Aging report  (admin + manager + office)
#   Ports docs/../FIELDKIT_SONNET_TASK_ar-aging-report.md (a Phase 0 spec) onto
#   live FieldKit data: same bucket definitions, column order, drill-down, and
#   print-detail approach, but no staleness banner — that spec's whole reason
#   for one was an imported snapshot; FieldKit's balances are always live.
# ============================================================================

def _customer_receivables_detail(cur, customer_id):
    """Every open receivable with balance > 0 for one customer, WITH per-
    invoice aging detail (unlike the lighter _customer_aging_summary the
    billing page uses, which only needs the totals). Returns
    (detail_rows, buckets, total_due, oldest_invoice_date_or_None)."""
    cur.execute("""
        SELECT i.id, i.invoice_number, i.invoice_date, i.current_version_id
        FROM invoices i
        WHERE i.customer_id = %s AND i.deleted_at IS NULL AND i.receivable_state = 'open'
        ORDER BY i.invoice_date
    """, (customer_id,))
    today = date.today()
    buckets = {'CURRENT': 0.0, '31-60 DAYS': 0.0, '61-90 DAYS': 0.0, '90+ DAYS': 0.0}
    detail, total, oldest = [], 0.0, None
    for inv in cur.fetchall():
        bal = invoice_balance(cur, inv['id'])
        if bal is None or bal <= 0.005:
            continue
        gross = None
        if inv['current_version_id']:
            cur.execute("SELECT total, subtotal FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
            v = cur.fetchone()
            if v:
                gross = float(v['total']) if v['total'] is not None else float(v['subtotal'])
        days = (today - inv['invoice_date']).days
        bucket = _aging_bucket_label(days)
        bucket_key = bucket if bucket != 'FUTURE' else 'CURRENT'
        buckets[bucket_key] += bal
        total += bal
        if oldest is None or inv['invoice_date'] < oldest:
            oldest = inv['invoice_date']
        detail.append({
            'id': inv['id'], 'number': inv['invoice_number'], 'date': inv['invoice_date'],
            'days': days, 'bucket': bucket_key, 'gross': gross, 'due': bal,
        })
    return detail, buckets, total, oldest


@app.route('/<company_key>/reports/aging')
@login_required
@company_access_required
@with_branding
def report_aging(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    sort = request.args.get('sort', 'total')  # 'total' (default) or '90plus'

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT id, property_name FROM customers WHERE deleted_at IS NULL ORDER BY property_name")
    customers = cur.fetchall()

    rows = []
    for c in customers:
        detail, buckets, total, oldest = _customer_receivables_detail(cur, c['id'])
        if total <= 0.005:
            continue
        rows.append({
            'id': c['id'], 'name': c['property_name'], 'total_due': total,
            'not_due': buckets['CURRENT'], 'b30': buckets['31-60 DAYS'],
            'b60': buckets['61-90 DAYS'], 'b90_plus': buckets['90+ DAYS'],
            'oldest': oldest, 'detail': detail,
        })

    rows.sort(key=lambda r: (r['b90_plus'] if sort == '90plus' else r['total_due']), reverse=True)

    totals = {
        'total_due': sum(r['total_due'] for r in rows),
        'not_due': sum(r['not_due'] for r in rows),
        'b30': sum(r['b30'] for r in rows),
        'b60': sum(r['b60'] for r in rows),
        'b90_plus': sum(r['b90_plus'] for r in rows),
    }

    cur.close(); conn.close()
    return render_template('aging_report.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        rows=rows, totals=totals, sort=sort, run_date=date.today(),
    )

# ============================================================================
# Compliance portals  (admin + manager + office)
#   CRUD on customer_compliance_portals + the /compliance export workbench.
#   Exporters all emit the same generic column set until Chris/Michele supply
#   the real OPS import template and VendorCafe field list — see D-033.
# ============================================================================

PORTAL_TYPES = ['OPS', 'VendorCafe', 'Paymode-X']

GENERIC_PORTAL_COLUMNS = [
    'Invoice Number', 'Invoice Date', 'Due Date', 'Property/Client ID',
    'Vendor Account Number', 'WTN/PO', 'Work Site Label', 'Description',
    'Subtotal', 'Tax', 'Total',
]


def _save_compliance_portal(cur, customer_id, portal_id, username):
    """Insert (portal_id is None) or update a compliance portal enrollment
    from request.form. Returns an error string, or None on success."""
    portal_type = request.form.get('portal_type', '').strip()
    if portal_type not in PORTAL_TYPES:
        return 'Choose a valid portal type.'
    portal_label          = request.form.get('portal_label', '').strip() or None
    vendor_account_number = request.form.get('vendor_account_number', '').strip() or None
    property_client_id    = request.form.get('property_client_id', '').strip() or None
    wtn_required          = request.form.get('wtn_required') == 'on'
    portal_is_primary_billing = request.form.get('portal_is_primary_billing') == 'on'
    notes                 = request.form.get('notes', '').strip() or None

    if portal_id is None:
        cur.execute("""
            INSERT INTO customer_compliance_portals
                (customer_id, portal_type, portal_label, vendor_account_number, property_client_id,
                 wtn_required, portal_is_primary_billing, notes, created_by, updated_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (customer_id, portal_type, portal_label, vendor_account_number, property_client_id,
              wtn_required, portal_is_primary_billing, notes, username, username))
    else:
        cur.execute("""
            UPDATE customer_compliance_portals
            SET portal_type=%s, portal_label=%s, vendor_account_number=%s, property_client_id=%s,
                wtn_required=%s, portal_is_primary_billing=%s, notes=%s,
                updated_at=CURRENT_TIMESTAMP, updated_by=%s
            WHERE id=%s AND customer_id=%s
        """, (portal_type, portal_label, vendor_account_number, property_client_id,
              wtn_required, portal_is_primary_billing, notes, username, portal_id, customer_id))
    return None


@app.route('/<company_key>/customers/<int:customer_id>/compliance-portals/new', methods=['POST'])
@login_required
@company_access_required
def compliance_portal_new(company_key, customer_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    err = _save_compliance_portal(cur, customer_id, None, session.get('username'))
    if err:
        conn.rollback()
        flash(err, 'error')
    else:
        conn.commit()
        flash('Portal enrollment added.', 'success')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')


@app.route('/<company_key>/customers/<int:customer_id>/compliance-portals/<int:portal_id>/edit', methods=['POST'])
@login_required
@company_access_required
def compliance_portal_edit(company_key, customer_id, portal_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    err = _save_compliance_portal(cur, customer_id, portal_id, session.get('username'))
    if err:
        conn.rollback()
        flash(err, 'error')
    else:
        conn.commit()
        flash('Portal enrollment updated.', 'success')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')


@app.route('/<company_key>/customers/<int:customer_id>/compliance-portals/<int:portal_id>/toggle', methods=['POST'])
@login_required
@company_access_required
def compliance_portal_toggle(company_key, customer_id, portal_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE customer_compliance_portals
        SET is_active = NOT is_active, updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s AND customer_id = %s
    """, (session.get('username'), portal_id, customer_id))
    conn.commit()
    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')


def _portal_export_rows(cur, invoice_ids):
    """Shared row-gathering for all three exporters — same generic columns
    for every portal type until Chris/Michele supply the real templates."""
    rows = []
    for iid in invoice_ids:
        cur.execute("""
            SELECT i.invoice_number, i.invoice_date, i.work_site_label, i.wtn_po_number,
                   i.customer_id, i.portal_id, iv.total, iv.subtotal, iv.tax_total
            FROM invoices i LEFT JOIN invoice_versions iv ON iv.id = i.current_version_id
            WHERE i.id = %s AND i.deleted_at IS NULL
        """, (iid,))
        inv = cur.fetchone()
        if not inv:
            continue
        cur.execute("SELECT payment_terms FROM customers WHERE id = %s", (inv['customer_id'],))
        cust = cur.fetchone()
        due_days = _parse_payment_terms_days(cust['payment_terms'] if cust else None)
        due_date = inv['invoice_date'] + timedelta(days=due_days)

        property_client_id = vendor_account = ''
        if inv['portal_id']:
            cur.execute("""
                SELECT property_client_id, vendor_account_number FROM customer_compliance_portals WHERE id = %s
            """, (inv['portal_id'],))
            p = cur.fetchone()
            if p:
                property_client_id = p['property_client_id'] or ''
                vendor_account = p['vendor_account_number'] or ''

        rows.append([
            inv['invoice_number'], inv['invoice_date'].isoformat(), due_date.isoformat(),
            property_client_id, vendor_account, inv['wtn_po_number'] or '',
            inv['work_site_label'] or '', '',
            float(inv['subtotal'] or 0), float(inv['tax_total'] or 0),
            float(inv['total'] if inv['total'] is not None else (inv['subtotal'] or 0)),
        ])
    return rows


def _build_portal_xlsx(cur, invoice_ids, sheet_title):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append(GENERIC_PORTAL_COLUMNS)
    for row in _portal_export_rows(cur, invoice_ids):
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _export_ops(cur, invoice_ids):
    return _build_portal_xlsx(cur, invoice_ids, 'OPS Export')

def _export_vendorcafe(cur, invoice_ids):
    return _build_portal_xlsx(cur, invoice_ids, 'VendorCafe Export')

def _export_paymode(cur, invoice_ids):
    return _build_portal_xlsx(cur, invoice_ids, 'Paymode Export')

PORTAL_EXPORTERS = {'OPS': _export_ops, 'VendorCafe': _export_vendorcafe, 'Paymode-X': _export_paymode}


@app.route('/<company_key>/compliance')
@login_required
@company_access_required
@with_branding
def compliance_page(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    portal_type = request.args.get('portal_type', '')
    date_from   = request.args.get('date_from', '').strip()
    date_to     = request.args.get('date_to', '').strip()

    conn = get_db_connection(company_key)
    cur  = conn.cursor()

    conditions = ["i.deleted_at IS NULL", "i.portal_status = 'pending'"]
    params = []
    if portal_type:
        conditions.append("p.portal_type = %s")
        params.append(portal_type)
    if date_from:
        conditions.append("i.invoice_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("i.invoice_date <= %s"); params.append(date_to)
    where = " AND ".join(conditions)
    cur.execute(f"""
        SELECT i.id, i.invoice_number, i.invoice_date, c.property_name AS customer_name,
               p.portal_type, iv.total, iv.subtotal
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN customer_compliance_portals p ON p.id = i.portal_id
        LEFT JOIN invoice_versions iv ON iv.id = i.current_version_id
        WHERE {where}
        ORDER BY i.invoice_date
    """, params)
    pending = cur.fetchall()

    cur.execute("""
        SELECT i.id, i.invoice_number, c.property_name AS customer_name, p.portal_type,
               i.portal_status, i.portal_submitted_at, i.portal_submission_notes
        FROM invoices i
        JOIN customers c ON c.id = i.customer_id
        LEFT JOIN customer_compliance_portals p ON p.id = i.portal_id
        WHERE i.deleted_at IS NULL AND i.portal_status IN ('submitted', 'accepted', 'rejected')
        ORDER BY i.portal_submitted_at DESC NULLS LAST LIMIT 50
    """)
    recent = cur.fetchall()

    cur.close(); conn.close()
    return render_template('compliance.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        pending=pending, recent=recent, portal_types=PORTAL_TYPES,
        portal_type=portal_type, date_from=date_from, date_to=date_to,
    )


@app.route('/<company_key>/compliance/export', methods=['POST'])
@login_required
@company_access_required
def compliance_export(company_key):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    portal_type = request.form.get('portal_type', '')
    invoice_ids = request.form.getlist('invoice_ids')
    if not invoice_ids or portal_type not in PORTAL_EXPORTERS:
        flash('Choose a portal type and at least one invoice.', 'error')
        return redirect(f'/{company_key}/compliance')

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    xlsx_bytes = PORTAL_EXPORTERS[portal_type](cur, invoice_ids)
    cur.execute("""
        UPDATE invoices
        SET portal_status = 'submitted', portal_submitted_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = ANY(%s) AND deleted_at IS NULL
    """, (session.get('username'), [int(i) for i in invoice_ids]))
    conn.commit()
    cur.close(); conn.close()

    filename = f"{portal_type}_export_{date.today().isoformat()}.xlsx"
    return Response(xlsx_bytes,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@app.route('/<company_key>/compliance/<int:invoice_id>/accept', methods=['POST'])
@login_required
@company_access_required
def compliance_accept(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE invoices SET portal_status = 'accepted', updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (session.get('username'), invoice_id))
    conn.commit()
    cur.close(); conn.close()
    flash('Marked accepted.', 'success')
    return redirect(f'/{company_key}/compliance')


@app.route('/<company_key>/compliance/<int:invoice_id>/reject', methods=['POST'])
@login_required
@company_access_required
def compliance_reject(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    notes = request.form.get('notes', '').strip()
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("""
        UPDATE invoices
        SET portal_status = 'rejected', portal_submission_notes = %s,
            updated_at = CURRENT_TIMESTAMP, updated_by = %s
        WHERE id = %s AND deleted_at IS NULL
    """, (notes or None, session.get('username'), invoice_id))
    conn.commit()
    cur.close(); conn.close()
    flash('Marked rejected.', 'success')
    return redirect(f'/{company_key}/compliance')

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
# Invoice & statement email delivery  (admin + manager + office)
#   Reuses the existing Resend integration above (send_reset_email). The
#   actual network call is isolated in _send_email_via_resend() so tests can
#   monkey-patch _resend.Emails.send and never touch the network — real
#   customer email addresses live in this database, so nothing here may ever
#   fire for real outside an explicit user action against production.
# ============================================================================

def _resolve_email_recipients(cur, customer_id, kind):
    """kind: 'invoice' -> accepts_billing contacts, 'statement' -> accepts_statements."""
    col = 'accepts_billing' if kind == 'invoice' else 'accepts_statements'
    cur.execute(f"""
        SELECT office_email FROM customer_contacts
        WHERE customer_id = %s AND deleted_at IS NULL AND {col} = TRUE
          AND office_email IS NOT NULL AND office_email <> ''
        ORDER BY is_primary DESC, last_name
    """, (customer_id,))
    return [r['office_email'] for r in cur.fetchall()]


def _render_email_template(template, customer_name, number, total, balance):
    tmpl = template or 'Hi {customer}, please find attached {number}.'
    return (tmpl.replace('{customer}', customer_name or '')
                .replace('{number}', number or '')
                .replace('{total}', f'${total:.2f}' if total is not None else '')
                .replace('{balance}', f'${balance:.2f}' if balance is not None else ''))


def _log_email(cur, kind, related_id, to_emails, subject, message_id, status, error, username):
    cur.execute("""
        INSERT INTO email_log (kind, related_id, to_emails, subject, resend_message_id, status, error, sent_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (kind, related_id, ', '.join(to_emails) if isinstance(to_emails, list) else to_emails,
          subject, message_id, status, error, username))


def _send_email_via_resend(to_emails, subject, html_body, attachment_bytes=None,
                            attachment_filename=None, reply_to=None, from_name=None, bcc=None):
    """The ONE place that calls the Resend API. Isolated so smoke tests can
    monkey-patch _resend.Emails.send and guarantee nothing ever reaches the
    network. Returns (message_id, error) — error is a human string, never an
    exception (a failed send must never 500 a request)."""
    if not RESEND_API_KEY:
        return None, 'Email sending is not configured (RESEND_API_KEY is not set).'
    payload = {
        'from': f'{from_name} <{RESEND_FROM}>' if from_name else RESEND_FROM,
        'to': to_emails,
        'subject': subject,
        'html': html_body,
    }
    if reply_to:
        payload['reply_to'] = reply_to
    if bcc:
        payload['bcc'] = [bcc] if isinstance(bcc, str) else bcc
    if attachment_bytes is not None:
        payload['attachments'] = [{
            'filename': attachment_filename or 'attachment.pdf',
            'content': base64.b64encode(attachment_bytes).decode('ascii'),
        }]
    try:
        result = _resend.Emails.send(payload)
        return (result.get('id') if isinstance(result, dict) else None), None
    except Exception as e:
        print(f"RESEND ERROR: {type(e).__name__}: {e}", flush=True)
        return None, str(e)


def _send_invoice_email(cur, company_key, invoice_id, extra_emails, subject_override, body_override, username):
    """Resolves recipients (accepts_billing contacts + extra addresses from
    the send dialog), renders subject/body, sends via Resend with the PDF
    attached, logs to email_log, and — only on a successful send — transitions
    the invoice to Sent. Returns (ok, error_or_recipients)."""
    cur.execute("""
        SELECT i.*, c.property_name AS customer_name
        FROM invoices i JOIN customers c ON c.id = i.customer_id
        WHERE i.id = %s AND i.deleted_at IS NULL
    """, (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        return False, 'Invoice not found.'
    cur.execute("SELECT * FROM invoice_versions WHERE id = %s", (inv['current_version_id'],))
    ver = cur.fetchone()
    if not ver or ver['state'] != 'Hardened':
        return False, f'Invoice must be Hardened to send (currently {ver["state"] if ver else "no version"}).'

    recipients = list(dict.fromkeys(_resolve_email_recipients(cur, inv['customer_id'], 'invoice') + (extra_emails or [])))
    if not recipients:
        return False, 'NO_BILLING_CONTACT'

    cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    settings = cur.fetchone() or {}
    balance = invoice_balance(cur, invoice_id)

    default_subject = f"Invoice {inv['invoice_number']} from {settings.get('company_name') or company_key}"
    subject = subject_override or default_subject
    body = body_override or _render_email_template(
        settings.get('invoice_email_template'), inv['customer_name'], inv['invoice_number'],
        ver['total'], balance)

    pdf_bytes = generate_invoice_pdf(company_key, ver['id'])
    message_id, err = _send_email_via_resend(
        recipients, subject, body.replace('\n', '<br/>'),
        attachment_bytes=pdf_bytes, attachment_filename=f"{inv['invoice_number']}.pdf",
        reply_to=settings.get('email_reply_to'), from_name=settings.get('email_from_name'),
        bcc=settings.get('email_reply_to'))

    _log_email(cur, 'invoice', invoice_id, recipients, subject, message_id,
               'failed' if err else 'sent', err, username)
    if err:
        return False, err

    ok, reason, extra = transition_invoice(cur, company_key, invoice_id, 'Sent', username,
                                            notes=', '.join(recipients))
    return ok, (reason if not ok else recipients)


def _send_statement_email(cur, company_key, customer_id, extra_emails, subject_override, body_override, username, as_of=None):
    """Same shape as _send_invoice_email for statements. Returns (ok, error_or_recipients)."""
    cur.execute("SELECT property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (customer_id,))
    cust = cur.fetchone()
    if not cust:
        return False, 'Customer not found.'

    recipients = list(dict.fromkeys(_resolve_email_recipients(cur, customer_id, 'statement') + (extra_emails or [])))
    if not recipients:
        return False, 'NO_BILLING_CONTACT'

    cur.execute("SELECT * FROM company_settings WHERE deleted_at IS NULL LIMIT 1")
    settings = cur.fetchone() or {}

    pdf_bytes, cust_name = generate_statement_pdf(company_key, customer_id, as_of)
    if pdf_bytes is None:
        return False, 'Could not generate the statement.'

    default_subject = f"Statement from {settings.get('company_name') or company_key}"
    subject = subject_override or default_subject
    body = body_override or _render_email_template(settings.get('statement_email_template'), cust_name, '', None, None)

    message_id, err = _send_email_via_resend(
        recipients, subject, body.replace('\n', '<br/>'),
        attachment_bytes=pdf_bytes, attachment_filename=f"{_sanitize_filename(cust_name)}_statement.pdf",
        reply_to=settings.get('email_reply_to'), from_name=settings.get('email_from_name'),
        bcc=settings.get('email_reply_to'))

    _log_email(cur, 'statement', customer_id, recipients, subject, message_id,
               'failed' if err else 'sent', err, username)
    if err:
        return False, err

    cur.execute("UPDATE customers SET last_statement_at = CURRENT_TIMESTAMP WHERE id = %s", (customer_id,))
    return True, recipients


def _parse_extra_emails(raw):
    """Free-typed extra addresses from a send dialog textarea — comma or
    newline separated, trimmed, empties dropped. No format validation beyond
    that; a typo'd address just bounces at Resend and shows up in email_log."""
    if not raw:
        return []
    parts = re.split(r'[,\n]', raw)
    return [p.strip() for p in parts if p.strip()]


@app.route('/<company_key>/invoices/<int:invoice_id>/send-email', methods=['POST'])
@login_required
@company_access_required
def invoice_send_email(company_key, invoice_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    extra_emails = _parse_extra_emails(request.form.get('extra_emails', ''))
    checked = set(request.form.getlist('recipients'))
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    cur.execute("SELECT customer_id FROM invoices WHERE id = %s AND deleted_at IS NULL", (invoice_id,))
    inv = cur.fetchone()
    if not inv:
        cur.close(); conn.close()
        abort(404)
    resolved = _resolve_email_recipients(cur, inv['customer_id'], 'invoice')
    # Only the boxes the office actually left checked go out, plus anything
    # freshly typed into the extra-addresses field.
    use_recipients = [e for e in resolved if e in checked] + extra_emails

    ok, result = _send_invoice_email(cur, company_key, invoice_id, use_recipients,
                                      request.form.get('subject', '').strip() or None,
                                      request.form.get('body', '').strip() or None,
                                      session.get('username'))
    if ok:
        conn.commit()
        flash(f"Invoice sent to {', '.join(result)}.", 'success')
    else:
        # Commit, not rollback: a failed-send attempt still writes an
        # email_log row (status='failed') that must persist — that's the
        # whole point of logging failures, not just successes. The
        # NO_BILLING_CONTACT path never wrote anything, so this is a no-op.
        conn.commit()
        if result == 'NO_BILLING_CONTACT':
            flash('No billing contact selected — add one or check a recipient.', 'error')
        else:
            flash(f'Send failed: {result}', 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/invoices/{invoice_id}')


@app.route('/<company_key>/customers/<int:customer_id>/send-statement', methods=['POST'])
@login_required
@company_access_required
def customer_send_statement(company_key, customer_id):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    extra_emails = _parse_extra_emails(request.form.get('extra_emails', ''))
    checked = set(request.form.getlist('recipients'))
    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    resolved = _resolve_email_recipients(cur, customer_id, 'statement')
    use_recipients = [e for e in resolved if e in checked] + extra_emails

    ok, result = _send_statement_email(cur, company_key, customer_id, use_recipients,
                                        request.form.get('subject', '').strip() or None,
                                        request.form.get('body', '').strip() or None,
                                        session.get('username'))
    if ok:
        conn.commit()
        flash(f"Statement sent to {', '.join(result)}.", 'success')
    else:
        # See the analogous comment in invoice_send_email — commit so a
        # failed-send's email_log row persists.
        conn.commit()
        if result == 'NO_BILLING_CONTACT':
            flash('No statement contact selected — add one or check a recipient.', 'error')
        else:
            flash(f'Send failed: {result}', 'error')
    cur.close(); conn.close()
    return redirect(f'/{company_key}/customers/{customer_id}')


@app.route('/<company_key>/billing/send-statements', methods=['POST'])
@login_required
@company_access_required
@with_branding
def billing_send_statements(company_key, branding, all_companies, company_access):
    if session.get('user_role') not in ('admin', 'manager', 'office'):
        abort(403)
    customer_ids = request.form.getlist('customer_ids')
    if not customer_ids:
        flash('Select at least one customer.', 'error')
        return redirect(f'/{company_key}/billing')

    conn = get_db_connection(company_key)
    cur  = conn.cursor()
    sent, failed, skipped = [], [], []
    for cid in customer_ids:
        cid = int(cid)
        cur.execute("SELECT property_name FROM customers WHERE id = %s AND deleted_at IS NULL", (cid,))
        cust = cur.fetchone()
        name = cust['property_name'] if cust else f'#{cid}'
        recipients = _resolve_email_recipients(cur, cid, 'statement')
        if not recipients:
            skipped.append(name)
            continue
        ok, result = _send_statement_email(cur, company_key, cid, [], None, None, session.get('username'))
        if ok:
            sent.append((name, result))
        else:
            failed.append((name, result))
    conn.commit()
    cur.close(); conn.close()

    return render_template('billing_send_summary.html',
        branding=branding, company_key=company_key,
        company_access=company_access, all_companies=all_companies,
        sent=sent, failed=failed, skipped=skipped,
    )

# ============================================================================
# Run
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
