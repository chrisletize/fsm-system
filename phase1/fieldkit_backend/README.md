# FieldKit Phase 1 - Flask Backend

## Authentication & Company Switching System

This is the Flask backend for FieldKit Phase 1, featuring:
- ✅ Bcrypt password authentication
- ✅ Smart company switching (single vs multi-company users)
- ✅ Multiple simultaneous sessions (different companies in different tabs)
- ✅ Color-coded company branding
- ✅ Role-based access control

## Setup Instructions

### 1. Install Dependencies

```bash
cd ~/fieldkit_backend
pip install -r requirements.txt --break-system-packages
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env
```

Update with your PostgreSQL password:
```
DB_PASSWORD=your_actual_postgres_password
FLASK_SECRET_KEY=generate-a-random-secret-key
```

### 3. Test Run (Development)

```bash
python3 app.py
```

Visit: http://localhost:5000

### 4. Production Deployment (Systemd)

Create service file:

```bash
sudo nano /etc/systemd/system/fieldkit.service
```

```ini
[Unit]
Description=FieldKit Flask Application
After=network.target postgresql.service

[Service]
Type=simple
User=chrisletize
WorkingDirectory=/home/chrisletize/fieldkit_backend
Environment="PATH=/usr/bin:/usr/local/bin"
EnvironmentFile=/home/chrisletize/fieldkit_backend/.env
ExecStart=/usr/bin/python3 /home/chrisletize/fieldkit_backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fieldkit
sudo systemctl start fieldkit
sudo systemctl status fieldkit
```

### 5. Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/fieldkit
```

```nginx
server {
    listen 80;
    server_name fieldkit.cletize.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /home/chrisletize/fieldkit_backend/static;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/fieldkit /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## User Authentication

### Default Users (from seed data)

**Password for all users:** `fieldkit2026` (CHANGE THIS!)

**Admins (all companies):**
- `chris` - Chris Letize
- `michele` - Michele
- `mike` - Mike

**Managers (single company):**
- `patrick` - CTS only
- `walter` - Kleanit Charlotte only
- `mikeyc` - Kleanit SF only

**Salespeople (all companies):**
- `chriso` - Chris O

### Login Behaviors

**Single-company user (e.g., Walter):**
1. Login → Automatically goes to Kleanit Charlotte dashboard
2. No company switcher visible
3. Session locked to their one company

**Multi-company user (e.g., Chris, Michele):**
1. Login → Company selection screen
2. Select company → Dashboard with company switcher in top nav
3. Can right-click company switcher → "Open in new tab"
4. Each tab maintains separate session with different company

## Company Switching

The magic happens in the top navigation company switcher:

```
Currently: Get a Grip ▾
  ↓ (dropdown)
  - Get a Grip Charlotte ✓
  - Kleanit Charlotte
  - CTS of Raleigh
  - Kleanit South Florida
```

**Right-click any company** → "Open link in new tab" → New tab with that company!

Each tab gets its own session token and `current_company` value stored in the database.

## Database Structure

The app connects to **four separate databases**:
- `fieldkit_getagrip`
- `fieldkit_kleanit_charlotte`
- `fieldkit_cts`
- `fieldkit_kleanit_sf`

User authentication checks the `users` table (replicated in all databases), then creates sessions in the currently selected company's database.

## File Structure

```
fieldkit_backend/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── .env                   # Your config (not in git)
├── templates/
│   ├── base.html          # Base template with nav/branding
│   ├── login.html         # Login page
│   ├── select_company.html # Company selection
│   └── dashboard.html     # Main dashboard
└── static/                # (future: CSS, JS, images)
```

## API Routes

### Authentication
- `GET/POST /login` - Login page and handler
- `GET /logout` - Logout and clear session
- `GET /select-company` - Company selection (multi-company users)
- `GET /switch/<company>` - Switch to different company

### Dashboard
- `GET /dashboard` - Main dashboard with stats

### Future Routes (Phase 2)
- `/customers` - Customer list
- `/customers/<id>` - Customer detail
- `/customers/new` - Add customer
- `/customers/<id>/edit` - Edit customer

## Security Features

- ✅ Bcrypt password hashing (cost factor 12)
- ✅ Session tokens (32-byte random)
- ✅ 24-hour session expiration
- ✅ Role-based access control
- ✅ Company access verification
- ✅ CSRF protection (Flask built-in)
- ⚠️ TODO: Rate limiting on login
- ⚠️ TODO: HTTPS enforcement in production

## Testing Login

```bash
# Start the app
python3 app.py

# Open browser to http://localhost:5000

# Login as admin (multi-company)
Username: chris
Password: fieldkit2026

# Should see company selection screen

# Login as manager (single-company)
Username: walter
Password: fieldkit2026

# Should go directly to Kleanit Charlotte dashboard
```

## Troubleshooting

### "Cannot connect to database"
Check `.env` file has correct `DB_PASSWORD`

### "Invalid username or password"
Default password is `fieldkit2026` - make sure it hasn't been changed

### "No company selected"
Clear browser cookies and login again

### Company switcher not visible
User only has access to one company (expected behavior)

## Next Steps

After authentication is working:

1. **Change default passwords** for all users
2. **Add customer management routes** (Phase 2)
3. **Build customer CRUD interface**
4. **Add search functionality**
5. **Implement job management** (Phase 4)

---

**FieldKit Phase 1** - Authentication system ready for multi-company operations!
