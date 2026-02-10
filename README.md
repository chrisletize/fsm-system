# FieldKit

Custom Field Service Management system built to replace ServiceFusion for four service companies.

**Companies**: Get a Grip Charlotte, Kleanit Charlotte, CTS of Raleigh, Kleanit South Florida  
**Mission**: Eliminate $25,000+/year in SaaS costs while gaining complete feature control

---

## Current Status

**Phase 0**: ✅ Complete (Statement Generator + Tax Reporting + Email Integration)  
**Phase 1**: 🔄 In Progress (Core Foundation - Database Architecture & Authentication)

See [`docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md`](docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md) for detailed status.

---

## Key Features (Phase 0 - Production)

### Statement Generator
- Professional PDF statements with company branding
- Multi-company support with color-coded interface
- Excel import from ServiceFusion
- Auto-split Kleanit customers (Charlotte vs South Florida)
- Aging bucket analysis (30/60/90/120+ days)

### Tax Reporting
- North Carolina sales tax compliance
- Cash-basis reporting by county
- Transaction-level detail matching ServiceFusion data
- State vs county tax calculations

### Outlook Email Integration  
- Individual and batch customer emails
- PowerShell scripts create Outlook drafts for review
- Smart validation (blocks company emails, reports missing)
- PDF attachments included automatically

**Live at**: statements.cletize.com

---

## Architecture

### Four Separate Databases
FieldKit uses **four independent PostgreSQL databases** (one per company) for:
- Performance isolation (Kleanit's high volume won't affect others)
- True data separation (zero cross-contamination risk)
- Operational independence (backup/migrate companies separately)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for complete technical details.

### Technology Stack
- **Backend**: Python 3.11+ with Flask
- **Database**: PostgreSQL 16 (4 separate databases)
- **Frontend**: HTML/CSS/JavaScript with Tailwind CSS
- **PDF**: ReportLab
- **Auth**: Bcrypt password hashing
- **Deployment**: Systemd on Ubuntu 24 LTS behind Nginx

---

## Documentation

Comprehensive documentation in [`docs/`](docs/) directory:

### Core Documentation
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture, four-database design, technology stack
- **[DATABASE-SCHEMA.md](docs/DATABASE-SCHEMA.md)** - Complete schema with audit trails, indexes, triggers
- **[SALES-SYSTEM.md](docs/SALES-SYSTEM.md)** - Sales CRM specification for field prospecting

### Project Knowledge
- **[CURRENT-STATUS.md](docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md)** - Current phase, what's working, what's next
- **[DECISIONS.md](docs/PROJECT-KNOWLEDGE/DECISIONS.md)** - All major technical decisions with rationale
- **[FUTURE-PLANS.md](docs/PROJECT-KNOWLEDGE/FUTURE-PLANS.md)** - Roadmap, phases 1-6, long-term vision
- **[SESSION-NOTES.md](docs/PROJECT-KNOWLEDGE/SESSION-NOTES.md)** - Development session history

---

## Development Phases

| Phase | Timeline | Status | Goal |
|-------|----------|--------|------|
| **Phase 0** | Jan 2026 | ✅ Complete | Proof of concept (statements, tax, email) |
| **Phase 1** | Feb-Mar 2026 | 🔄 In Progress | Core foundation (auth, databases, customers) |
| **Phase 2** | Apr-May 2026 | 📋 Planned | Customer management (full CRUD) |
| **Phase 3** | Jun-Jul 2026 | 📋 Planned | Sales system (Chris O's field CRM) |
| **Phase 4** | Aug-Oct 2026 | 📋 Planned | Job management & scheduling |
| **Phase 5** | Nov-Dec 2026 | 📋 Planned | Invoicing & payments |
| **Phase 6** | Q1 2027 | 📋 Planned | Mobile apps |

**Target**: Complete ServiceFusion replacement by Q3 2026

---

## Quick Start (Development)

```bash
# Clone repository
git clone https://github.com/chrisletize/fsm-system.git
cd fsm-system

# Install Python dependencies
pip install -r requirements.txt --break-system-packages

# Set up PostgreSQL databases (four separate databases)
# See database/migrations/ for schema scripts

# Run Flask application
cd backend/api
python app.py

# Access at http://localhost:5000
```

---

## Project Structure

```
fsm-system/
├── backend/
│   └── api/
│       ├── app.py              # Flask application
│       ├── branding.py         # Multi-company color schemes
│       ├── tax_processor.py    # NC tax compliance logic
│       └── templates/          # HTML templates
├── database/
│   ├── migrations/             # Schema initialization scripts
│   └── seed/                   # Default data
├── docs/
│   ├── ARCHITECTURE.md         # System design
│   ├── DATABASE-SCHEMA.md      # Complete schema reference
│   ├── SALES-SYSTEM.md         # Sales CRM specification
│   └── PROJECT-KNOWLEDGE/      # Living documentation
├── scripts/
│   ├── generate_pdf_statement.py  # PDF generation
│   └── import_sf_data.py          # ServiceFusion data import
└── README.md
```

---

## Key Principles

1. **Data Safety First**: Four separate databases, audit trails, approval workflows
2. **User Experience Matters**: Color-coded branding prevents mistakes
3. **Build Methodically**: Foundation before features
4. **Real User Testing**: Michele, Chris O, and field techs guide priorities
5. **Document Everything**: Future maintainability through comprehensive docs

---

## Success Metrics

### Financial
- ✅ Zero monthly SaaS costs ($25k+/year saved once complete)
- ✅ Hardware ROI in 6-8 months
- ✅ Elimination of QuickBooks sync issues

### Operational
- ✅ System reliability (<1 hour downtime/month target)
- ✅ Fast response times (<500ms for common operations)
- ✅ 30+ employees using FieldKit daily

### Strategic
- ✅ Complete control over features and data
- ✅ Custom workflows for each company
- ✅ Comprehensive documentation
- 🎯 Optional: License to other service companies

---

## License

Proprietary - Built for Get a Grip, Kleanit, and CTS companies.

---

## Contact

**Chris Letize**  
Owner & System Architect  
chrisletize/fsm-system on GitHub

---

*FieldKit: Built by field service professionals, for field service professionals.*
