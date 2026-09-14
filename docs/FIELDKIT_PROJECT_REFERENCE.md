# FieldKit — Claude Project Reference
*Generated: 2026-03-29 | Source: GitHub chrisletize/fsm-system + conversation history*

---

## 1. What This Project Is

Chris Letize is building **FieldKit**, a custom Field Service Management system to replace ServiceFusion across four service companies. The primary driver is eliminating ~$1,500/month in SaaS costs ($18k+/year) while gaining full control over features and data.

**The four companies:**
| ID | Company | Type | Location | Notes |
|----|---------|------|----------|-------|
| 1 | Kleanit Charlotte | Carpet Cleaning | Charlotte, NC | Original location |
| 2 | Get a Grip Resurfacing of Charlotte | Surface Resurfacing | Charlotte, NC | Chris's primary company |
| 3 | CTS of Raleigh | Umbrella (Get a Grip franchise + Kleanit) | Raleigh, NC | |
| 4 | Kleanit South Florida | Carpet Cleaning | South Florida | Split from Kleanit Charlotte via `*FL*` marker |

Kleanit Charlotte and South Florida **share one ServiceFusion account** but are split in FieldKit by the `*FL*` prefix in customer names.

**Key people:**
- **Michele** — AR manager, primary daily user; generates statements, handles AR, processes tax reports. Multi-company access is critical. Prefers separate browser tabs per company.
- **Mike** — Business partner; non-technical; responds to ROI demos.
- **Chris O** — Field salesperson; informed the sales CRM design.

---

## 2. Infrastructure (Current as of March 2026)

### Production Server — Phase 0 (Statement Generator)
- **Host:** `ubuntu1` — original dev/prod server
- **Path:** `/home/chrisletize/fsm-system`
- **Service:** `fsm-statements` systemd service, port 5000
- **URL:** `statements.cletize.com` (via Nginx reverse proxy)
- **Database:** PostgreSQL 16, single database `fsm_system`
- **GitHub:** `chrisletize/fsm-system` (public repo)

### New Production VM — Phase 1+ Target (FieldKit)
- **VM:** `ubuntu-business`, VM ID 101 on Proxmox (LetizeCompute)
- **IP:** `10.83.70.10` (static, VLAN70 DMZ)
- **OS:** Ubuntu 24.04 LTS
- **Resources:** 4 vCPU, 8GB RAM
- **Docker:** 29.3.1 installed, Compose v5.1.1
- **User:** `letize` (in docker group)
- **SSH:** `ssh letize@10.83.70.10` from VLAN20 (Chris's workstation)
- **Internet exit:** AirVPN NYC1 — `curl -s ifconfig.me` should return `198.44.159.35`
- **Deployment dirs:** `~/docker/fieldkit-prod` and `~/docker/fieldkit-staging` (created, empty)
- **Ports:** Prod = 3000, Staging = 3001

### Reverse Proxy (NPM on ubuntu-services, 10.83.30.10, VLAN30)
- `fieldkit.cletize.com` → `10.83.70.10:3000` — **proxy host NOT yet created**
- `staging.fieldkit.cletize.com` → `10.83.70.10:3001` — **proxy host NOT yet created**
- Wildcard SSL `*.cletize.com` already exists in NPM
- Pi-hole DNS records for both subdomains **NOT yet created** (both should → `10.83.30.10`)

### Homelab Firewall — Still Needed (tracked separately)
- Create OPNsense aliases `FIELDKIT_PORTS` (3000, 3001) and `DMZ_MGMT_PORTS` (22, 3000, 3001)
- Tighten VLAN20→VLAN70 rule to `DMZ_MGMT_PORTS`
- Tighten VLAN30→VLAN70 rule to `FIELDKIT_PORTS`

---

## 3. Current Codebase — Phase 0 Statement Generator

### Tech Stack
- **Backend:** Python 3 + Flask, psycopg2, openpyxl, ReportLab
- **Database:** PostgreSQL 16 (single DB `fsm_system`)
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **PDF:** ReportLab (programmatic) + html2canvas (for recency report)
- **Deployment:** systemd service on ubuntu1

### File Structure
```
/home/chrisletize/fsm-system/
├── backend/api/
│   ├── app.py                    ← Main Flask app (all routes)
│   ├── branding.py               ← Company color/logo config
│   ├── nc_tax_rates.py           ← NC county tax rate definitions
│   ├── tax_processor.py          ← Cash-basis tax report processing
│   ├── templates/
│   │   ├── index.html            ← Main AR/statements page
│   │   ├── upload.html           ← Invoice Excel upload page
│   │   ├── tax-report.html       ← Tax reporting page
│   │   └── recency_report.html   ← Customer recency report page
│   └── static/                   ← Company logos, CSS assets
├── scripts/
│   ├── generate_pdf_statement.py ← ReportLab PDF generator
│   ├── generate_test_statement.py
│   └── import_sf_data.py
├── database/migrations/
│   └── 001_initial_schema.sql    ← companies, customers, invoices tables
└── docs/PROJECT-KNOWLEDGE/       ← Living documentation (somewhat stale)
```

### Database Schema (fsm_system)
**companies** — 4 rows, IDs 1–4 as above  
**customers** — `id, company_id, account_number, customer_name, contact_email, contact_phone, service_location_*`  
**invoices** — `id, company_id, customer_id, invoice_number, invoice_date, invoice_status, invoice_total, invoice_total_due, tax_total, tax_rate_name, job_number, job_date, ...`  
**tax_transactions** — `id, company_id, county, invoice_date, invoice_number, customer_name, job_number, total_sales, taxable_amount, tax_rate, tax_collected`  
**customer_job_dates** — `id, customer_id, job_date, source, created_at, created_by` (added for recency report)

### Key Design Decisions (Phase 0)
- **Single DB** for Phase 0 (all companies share `fsm_system`, filtered by `company_id`)
- **Four separate DBs** planned for Phase 1 (`fieldkit_getagrip`, `fieldkit_kleanit_charlotte`, `fieldkit_cts`, `fieldkit_kleanit_sf`)
- **FL auto-split:** When uploading to company_id=1 (Kleanit Charlotte), customers with `*FL*` in name are automatically routed to company_id=4 (Kleanit South Florida)
- **Cash-basis tax:** NC compliance requires reporting tax based on payment collection date, not invoice date. `tax_processor.py` matches Tax Report + Transaction Report by Job# to determine payment date.
- **Company branding:** CSS variables swapped dynamically per company selection. Prevents cross-company errors.
- **Import all invoices** (paid + unpaid) — statements filter for `invoice_total_due > 0`, tax report uses paid only

### Branding Colors
| Company | Primary | Secondary | Background |
|---------|---------|-----------|------------|
| LKit (none selected) | `#8b7a9e` lavender | `#b8a3d1` | `#ede5f5` |
| Kleanit Charlotte (1) | `#0052CC` blue | `#00D66C` green | `#e6f2ff` |
| Get a Grip (2) | `#8B1538` burgundy | `#F5F5DC` cream | `#FFF5F0` |
| CTS Raleigh (3) | `#2C2C2C` dark gray | `#F5F5DC` cream | `#F5F5F5` |
| Kleanit SF (4) | `#00D66C` green | `#0052CC` blue | `#e6ffe6` |

---

## 4. Features Built and Working

### Statement Generator ✅
- Import invoices from ServiceFusion Excel exports (all companies)
- Parse logic: row 6 = headers, data starts row 7, 42 columns
- Auto-split Kleanit by `*FL*` marker at import time
- Generate individual PDF statements (ReportLab, branded per company)
- Batch statement generation → ZIP download
- Clear data per company (double-confirm)
- Aging buckets: current / 31–60 / 61–90 / 90+ days

### Tax Reporting ✅
- Upload ServiceFusion Tax Report + Transaction Report (two separate Excel files)
- `tax_processor.py` matches by Job# to get payment date (cash-basis compliance)
- Breaks down by county: state tax (4.75%) + county tax + transit tax
- NC counties with transit tax: Mecklenburg, Wake, Durham, Orange
- Export to Excel
- Clear tax data per company

### Customer Recency Report ✅
- Upload ServiceFusion Customer Revenue Report Excel (has corrupt XML comments — handled by stripping comment XML from ZIP before openpyxl loads)
- UPSERT job dates to `customer_job_dates` table
- Buckets: 1–2mo, 3–6mo, 6–12mo, 12+mo since last service
- "Days since last service" calculated from report-generation date (not upload date)
- Pre-upload validation: checks geographic state data and customer name match rates to prevent wrong-company uploads
- Batch delete by upload timestamp
- PDF generation and print

### Excel Upload Quirks (Known Issues Solved)
- ServiceFusion Customer Revenue Reports contain **corrupt comment XML** in the `.xlsx` ZIP archive — causes openpyxl "Value must be a sequence" error. Fix: strip `comments*.xml` files from ZIP before parsing.
- Footer/summary rows at end of invoice exports cause "tuple index out of range" — fix: skip rows with fewer than 5 non-null values.
- Column mismatches between different ServiceFusion report types require careful column mapping.

---

## 5. The Docker Migration (What We're Doing Now)

### Goal
Port the Phase 0 FSM Statement Generator from its current systemd/bare-metal setup on `ubuntu1` to Docker Compose on `ubuntu-business` (`10.83.70.10`). This establishes the deployment pattern for all future FieldKit development.

### Target State
```
ubuntu-business (10.83.70.10)
├── ~/docker/fieldkit-prod/
│   ├── docker-compose.yml        ← Flask app + PostgreSQL
│   ├── .env                      ← Prod secrets (DB password, secret key)
│   └── Dockerfile                ← Python/Flask container
└── ~/docker/fieldkit-staging/
    ├── docker-compose.yml        ← Same stack, different port/DB
    ├── .env                      ← Staging secrets
    └── Dockerfile
```

**Prod:** port 3000, database `fsm_prod`  
**Staging:** port 3001, database `fsm_staging`

### What Needs to Happen
1. Pull code from GitHub onto ubuntu-business
2. Write `Dockerfile` for the Flask app
3. Write `docker-compose.yml` for prod stack (Flask + PostgreSQL + volume for DB persistence)
4. Write `.env` template for secrets
5. Initialize database (run `001_initial_schema.sql` inside container)
6. Copy static assets (company logos) into container
7. Test: `curl http://10.83.70.10:3000` from VLAN30, SSH from VLAN20
8. Duplicate for staging (port 3001, separate DB)
9. Wire up NPM proxy hosts (done on ubuntu-services separately)

### Key Gotchas to Handle in Docker
- The app currently hardcodes `/home/chrisletize/fsm-system/scripts` in `sys.path.insert()` — needs to become a relative or container-native path
- `/tmp/uploads`, `/tmp/statements`, `/tmp/batch_statements` — these work fine in a container but are ephemeral; that's acceptable for temp processing
- Static assets path for logos: currently `backend/api/static/` — needs to be in the container
- systemd service on ubuntu1 will remain running until the Docker deployment is validated

---

## 6. Established Working Patterns

- **Examine complete files before making changes** — never modify based on partial context
- **Use GitHub as source of truth** — load files at session start via raw URLs
- **One change at a time** — Chris prefers receiving changes sequentially, not multiple files at once
- **sed commands for targeted edits** on the server — preferred for small changes
- **Test with real data** — validate against actual ServiceFusion exports
- **Human oversight on consequential actions** — email drafts not auto-sent, approval queues for data changes
- **Comprehensive session documentation** — commit all changes and decisions to GitHub at end of session

---

## 7. Roadmap (Beyond Current Work)

**Phase 1 — Core FieldKit FSM**
- Full customer/job/invoice management replacing ServiceFusion
- Four separate PostgreSQL databases (one per company)
- Role-based auth, multi-company user support
- Start with Get a Grip Charlotte

**Phase 2+ — Advanced Features**
- Drag-and-drop scheduling calendar (horizontal timeline, tech rows × time columns — React/DnD Kit prototype exists)
- Sales CRM / salesperson webpage (prospect DB, visit logging, dormancy detection — designed around Chris O's workflow)
- Mobile app — photo upload target 2–5 sec vs ServiceFusion's ~30 sec
- Business card scanning → OCR → customer DB import (Google Cloud Vision API)
- Public estimate request forms (per-company branded, feeds Estimate Request Queue)
- Customer rating system (job volume + payment timeliness + manager-input factors)
- n8n workflow automation (quality control layer, Outlook email triage)

**LKit Business Concept**
- Chris's father ran a similar small-client hosting/software business for 30 years
- Vision: solo micro-hosting company from home infrastructure, first 3 clients = Chris's own companies
- FieldKit adapted per client rather than made fully universal
- Basement server room planned with dedicated circuit + UPS + fiber + Starlink failover

---

## 8. Session Start Checklist

When beginning a new session on this project:

1. Load these GitHub URLs for current code state:
   - `https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/app.py`
   - `https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/branding.py`
   - `https://raw.githubusercontent.com/chrisletize/fsm-system/main/backend/api/tax_processor.py`
   - `https://raw.githubusercontent.com/chrisletize/fsm-system/main/docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md`
   - Any template files relevant to the session's work

2. Check what the active work is (ask Chris or read ACTIVE-SPRINT.md)

3. Verify current server state before modifying anything

4. Make changes one file at a time

---

*This reference was compiled from GitHub source files and conversation history on 2026-03-29.*
*The docs/PROJECT-KNOWLEDGE files in the repo are partially stale — app.py is the ground truth for what's actually built.*
