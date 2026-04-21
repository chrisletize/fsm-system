"""
FieldKit Flask Application
Phase 1: Authentication & Company Switching
"""

from flask import Flask, request, session, jsonify, render_template, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Database configuration
DB_CONFIG = {
    'getagrip': 'fieldkit_getagrip',
    'kleanit_charlotte': 'fieldkit_kleanit_charlotte',
    'cts': 'fieldkit_cts',
    'kleanit_sf': 'fieldkit_kleanit_sf'
}

DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')

# Company branding configuration
COMPANY_BRANDING = {
    'getagrip': {
        'name': 'Get a Grip Charlotte',
        'short_name': 'Get a Grip',
        'color_primary': '#8B1538',  # Burgundy
        'color_secondary': '#F5F5DC',  # Cream
        'logo_url': '/static/img/getagrip-logo.png'
    },
    'kleanit_charlotte': {
        'name': 'Kleanit Charlotte',
        'short_name': 'Kleanit CLT',
        'color_primary': '#0052CC',  # Blue
        'color_secondary': '#FFFFFF',
        'logo_url': '/static/img/kleanit-clt-logo.png'
    },
    'cts': {
        'name': 'CTS of Raleigh',
        'short_name': 'CTS',
        'color_primary': '#2C2C2C',  # Dark Gray
        'color_secondary': '#F5F5DC',  # Cream
        'logo_url': '/static/img/cts-logo.png'
    },
    'kleanit_sf': {
        'name': 'Kleanit South Florida',
        'short_name': 'Kleanit SF',
        'color_primary': '#00D66C',  # Green
        'color_secondary': '#FFFFFF',
        'logo_url': '/static/img/kleanit-sf-logo.png'
    }
}

# ============================================================================
# Database Connection Management
# ============================================================================

def get_db_connection(company_key):
    """Get connection to specific company database."""
    if company_key not in DB_CONFIG:
        raise ValueError(f"Invalid company key: {company_key}")
    
    return psycopg2.connect(
        dbname=DB_CONFIG[company_key],
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        cursor_factory=RealDictCursor
    )

def get_current_db():
    """Get database connection for current session's company."""
    current_company = session.get('current_company')
    if not current_company:
        raise ValueError("No company selected in session")
    return get_db_connection(current_company)

# ============================================================================
# Authentication Functions
# ============================================================================

def verify_password(plain_password, hashed_password):
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_session_token():
    """Generate secure session token."""
    return secrets.token_urlsafe(32)

def get_user_by_username(username):
    """
    Get user from database. Check all databases since users table is replicated.
    We'll check getagrip database as the canonical source.
    """
    conn = get_db_connection('getagrip')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, email, password_hash, full_name, role, 
               company_access, is_active, last_login
        FROM users
        WHERE username = %s AND is_active = TRUE
    """, (username,))
    
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return user

def create_user_session(user_id, username, current_company):
    """Create session record in database."""
    session_token = create_session_token()
    expires_at = datetime.now() + timedelta(hours=24)
    
    # Store in the current company's database
    conn = get_db_connection(current_company)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO user_sessions 
        (user_id, session_token, ip_address, user_agent, current_company, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        user_id,
        session_token,
        request.remote_addr,
        request.headers.get('User-Agent', '')[:255],
        current_company,
        expires_at
    ))
    
    conn.commit()
    cursor.close()
    conn.close()
    
    return session_token

def update_last_login(username):
    """Update user's last login timestamp."""
    conn = get_db_connection('getagrip')
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET last_login = CURRENT_TIMESTAMP 
        WHERE username = %s
    """, (username,))
    
    conn.commit()
    cursor.close()
    conn.close()

# ============================================================================
# Decorators
# ============================================================================

def login_required(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def company_required(f):
    """Decorator to require company selection."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'current_company' not in session:
            return redirect(url_for('select_company'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorator to require specific role(s)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] not in roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================================================
# Routes - Authentication
# ============================================================================

@app.route('/')
def index():
    """Landing page - redirect based on authentication status."""
    if 'user_id' in session:
        if 'current_company' in session:
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('select_company'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication handler."""
    if request.method == 'GET':
        # Already logged in?
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('login.html')
    
    # Handle POST - authentication
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        return render_template('login.html', error='Username and password required')
    
    # Get user from database
    user = get_user_by_username(username)
    
    if not user:
        return render_template('login.html', error='Invalid username or password')
    
    # Verify password
    if not verify_password(password, user['password_hash']):
        return render_template('login.html', error='Invalid username or password')
    
    # Parse company access
    company_access = user['company_access']
    
    # Set session data
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['user_role'] = user['role']
    session['company_access'] = company_access
    
    # Update last login
    update_last_login(username)
    
    # Single company user - auto-select their company
    if len(company_access) == 1:
        company = company_access[0]
        session['current_company'] = company
        session['session_token'] = create_user_session(user['id'], username, company)
        return redirect(url_for('dashboard'))
    
    # Multi-company user - let them choose
    return redirect(url_for('select_company'))

@app.route('/select-company')
@login_required
def select_company():
    """Company selection page for multi-company users."""
    company_access = session.get('company_access', [])
    
    # Single company? Shouldn't be here, redirect
    if len(company_access) == 1:
        session['current_company'] = company_access[0]
        return redirect(url_for('dashboard'))
    
    # Build company list with branding
    companies = []
    for company_key in company_access:
        if company_key in COMPANY_BRANDING:
            companies.append({
                'key': company_key,
                **COMPANY_BRANDING[company_key]
            })
    
    return render_template('select_company.html', companies=companies)

@app.route('/switch/<company_key>')
@login_required
def switch_company(company_key):
    """Switch to different company (for multi-company users)."""
    company_access = session.get('company_access', [])
    
    # Verify user has access to this company
    if company_key not in company_access:
        return jsonify({'error': 'Access denied'}), 403
    
    # Verify company exists
    if company_key not in DB_CONFIG:
        return jsonify({'error': 'Invalid company'}), 400
    
    # Update session
    session['current_company'] = company_key
    
    # Create new session token for this company
    session['session_token'] = create_user_session(
        session['user_id'],
        session['username'],
        company_key
    )
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Logout and clear session."""
    session.clear()
    return redirect(url_for('login'))

# ============================================================================
# Routes - Dashboard
# ============================================================================

@app.route('/dashboard')
@login_required
@company_required
def dashboard():
    """Main dashboard - shows summary and quick links."""
    current_company = session.get('current_company')
    branding = COMPANY_BRANDING.get(current_company, {})
    
    # Get some quick stats
    conn = get_current_db()
    cursor = conn.cursor()
    
    # Customer count
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM customers 
        WHERE deleted_at IS NULL AND status = 'Active'
    """)
    active_customers = cursor.fetchone()['count']
    
    # Recent customers (last 10)
    cursor.execute("""
        SELECT id, property_name, customer_type, city, status
        FROM customers
        WHERE deleted_at IS NULL
        ORDER BY created_at DESC
        LIMIT 10
    """)
    recent_customers = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html',
                         branding=branding,
                         company_key=current_company,
                         active_customers=active_customers,
                         recent_customers=recent_customers,
                         company_access=session.get('company_access', []),
                         all_companies=COMPANY_BRANDING)

# ============================================================================
# Run Application
# ============================================================================

if __name__ == '__main__':
    # Development server
    app.run(debug=True, host='0.0.0.0', port=5001)
