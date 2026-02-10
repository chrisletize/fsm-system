# FieldKit - Current Status
*Last Updated: 2026-02-10*

## Project Overview
Building **FieldKit**, a custom Field Service Management system to replace ServiceFusion for four service companies.

- **Product Name**: FieldKit
- **Companies**: Get a Grip Charlotte, Kleanit Charlotte, CTS of Raleigh, Kleanit South Florida
- **Users**: ~30 employees (field technicians, office staff, salespeople)
- **Scale**: 250 jobs/day at peak season (Kleanit Charlotte)
- **Current Phase**: Phase 0 Complete ✅ | Phase 1 Starting (Core Foundation)

## Business Problem
ServiceFusion costs ~$25,000/year across 4 companies and lacks critical features:
- Poor statement generation
- Problematic QuickBooks integration (Michele spends 5-10 hours weekly fixing sync errors)
- No sales contact management system
- Limited customization options

**Mission**: Build complete FSM replacement to eliminate SaaS costs, gain full feature control, and provide tools that actually match workflows.

---

## Phase 0: COMPLETE ✅

### Statement Generator (Production-Ready)
- ✅ Import invoices from ServiceFusion Excel exports
- ✅ Auto-split Kleanit customers (*FL* → South Florida, others → Charlotte)
- ✅ Generate professional PDF statements with company branding
- ✅ Clean web interface at statements.cletize.com
- ✅ Multi-company support with color-coded branding
- ✅ Clear data feature per company

**Success**: Michele generates statements in <2 minutes ✅ ACHIEVED

### Tax Reporting (Production-Ready)
- ✅ NC tax compliance reporting with county-by-county breakdown
- ✅ Cash-basis reporting matching ServiceFusion data
- ✅ Transaction-level detail by job number
- ✅ State vs county tax calculations across all 100 NC counties

**Success**: Michele files monthly tax returns accurately ✅ ACHIEVED

### Outlook Email Integration (Production-Ready)
- ✅ Individual customer email drafts
- ✅ Batch email generation
- ✅ PowerShell scripts create Outlook drafts
- ✅ Smart validation (blocks company emails, reports missing)

**Success**: Michele can email statements efficiently ✅ ACHIEVED

---

## Phase 1: Core Foundation (IN PROGRESS - Starting 2/10/26)

**Goal**: Establish multi-company architecture, authentication, and customer database foundation.

### Architecture Decisions Made
- ✅ **Four Separate PostgreSQL Databases** (not multi-tenant)
  - `fieldkit_getagrip`
  - `fieldkit_kleanit_charlotte`
  - `fieldkit_cts`
  - `fieldkit_kleanit_sf`
- ✅ **Rationale**: Performance isolation, true data separation, operational independence
- ✅ **User authentication**: Bcrypt password hashing
- ✅ **Audit trails**: created_by, updated_by, deleted_at, deleted_by on ALL tables
- ✅ **Hybrid JSONB**: Direct columns for searchable fields, JSONB for flexibility

### Phase 1 Deliverables (4-6 weeks)
- [ ] Database initialization scripts for all 4 companies
- [ ] User authentication system (login, sessions, permissions)
- [ ] Company switcher with color-coded branding
- [ ] Management companies table
- [ ] Customer table with multi-contact support
- [ ] Basic customer CRUD operations
- [ ] Customer search functionality

**Success Criteria**: 
- Users can log in and switch between companies
- Customer data entry works with proper audit trails
- Color branding prevents company confusion
- Zero cross-company data contamination

---

## Phase 2: Customer Management (PLANNED - After Phase 1)

**Goal**: Complete customer database that both FieldKit and sales system reference.

### Deliverables (6-8 weeks)
- [ ] Full customer CRUD
- [ ] Customer contacts management (multiple contacts per property)
- [ ] Customer search with autocomplete
- [ ] Customer detail views
- [ ] Invoice import from ServiceFusion (transition period)

**Success Criteria**:
- Customer database replaces ServiceFusion customer list
- Multi-contact support working
- Search performance <100ms

---

## Phase 3: Sales System (PLANNED - After Phase 2)

**Goal**: Chris O's field contact management and prospecting tool.

### Deliverables (6-8 weeks)
- [ ] Sales prospects database per company
- [ ] Contact management with property history tracking
- [ ] Visit logging (mobile-friendly)
- [ ] Visit tagging system with auto follow-ups
- [ ] Approval queue for customer updates
- [ ] Dormancy detection and alerts
- [ ] Weekly sales reports
- [ ] Manager approval workflows

**Success Criteria**:
- Chris O can log visits in <60 seconds from tablet
- Management receives dormancy feedback
- Zero accidental customer database corruption
- Sales activity is measurable

---

## What's Working ✅
- PostgreSQL 16 database on ubuntu1
- Statement generator with real customer data
- Tax reporting with NC compliance
- Outlook email integration
- Flask web application with systemd service
- Reverse proxy (statements.cletize.com)
- Multi-company branding (4 companies + LKit default)

## What's In Progress 🔄
- Phase 1 foundation work starting 2/10/26
- Architecture documentation complete
- Database schema design complete
- Sales system specification complete

## Known Issues
None - Phase 0 features stable in production

---

## Technical Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: Flask
- **Database**: PostgreSQL 16 (4 separate databases)
- **PDF Generation**: ReportLab
- **Authentication**: Bcrypt

### Frontend
- **HTML/CSS/JavaScript** (no framework initially)
- **Tailwind CSS** for styling
- **Mobile-first responsive design**

### Infrastructure
- **Server**: Ubuntu 24 LTS on ubuntu1
- **Web Server**: Nginx reverse proxy
- **Process Manager**: systemd
- **Domain**: statements.cletize.com (Phase 0)
- **Future**: Dedicated production server for full FieldKit

---

## Key Metrics

### Phase 0 Success
- Statement generation: <2 minutes (target met)
- Tax reports: Accurate NC compliance (target met)
- Email integration: Working smoothly (target met)
- Michele satisfaction: High ✅

### Development Stats
- Phase 0 development time: ~40 hours total
- Database: Currently 1,340+ customer records across companies
- Outstanding AR tracked: $230,053.28
- Features completed: 100% of Phase 0 scope

### Future Targets
- Phase 1-3: 16-24 weeks development
- Full ServiceFusion replacement: Q3 2026
- Cost savings: $25,000+/year once complete
- ROI timeframe: 6-8 months

---

## Company Breakdown

### Get a Grip Charlotte (ID 2)
- Type: Surface Resurfacing
- Services: Parking lots, pool decks, commercial surfaces
- Cycle: Longer project intervals (4-8 weeks normal)
- Dormancy threshold: 8 weeks

### Kleanit Charlotte (ID 1)
- Type: Carpet Cleaning
- Volume: Highest (250 jobs/day at peak)
- Cycle: Frequent recurring (2-4 week intervals)
- Dormancy threshold: 3 weeks
- Customers: 1,138 properties

### CTS of Raleigh (ID 3)
- Type: Umbrella company
- Services: Get a Grip franchise + Kleanit operations
- Location: Raleigh, NC
- Dormancy threshold: 4 weeks

### Kleanit South Florida (ID 4)
- Type: Carpet Cleaning
- Volume: Moderate
- Cycle: Similar to Kleanit Charlotte
- Dormancy threshold: 3 weeks
- Customers: 202 properties

---

## Team Structure

### Key Users

**Administrators** (Full access to all companies):
- Chris Letize (you) - Owner, system architect
- Michele - Accounts receivable, primary office user
- Mike - Original business partner

**Managers** (Company-specific):
- Patrick - CTS of Raleigh
- Walter - Kleanit Charlotte
- Mikey C - Kleanit South Florida (also does sales)

**Salespeople** (All companies):
- Chris O - Primary salesperson (travels to all locations)
- Mikey C - Dual role (sales + management for Kleanit SF)

---

## Next Steps (Immediate)

1. **Start Phase 1 Development** (Today - 2/10/26)
   - Set up database initialization scripts
   - Begin user authentication system
   - Design company switcher interface

2. **Documentation Maintenance**
   - Keep SESSION-NOTES.md updated after each work session
   - Update ACTIVE-SPRINT.md with current tasks
   - Document decisions in DECISIONS.md

3. **GitHub Sync**
   - Commit new architecture docs
   - Push updated status files
   - Maintain version control discipline

---

## Long-Term Vision

**Success Metrics (12-24 months)**:
- ✅ Zero monthly SaaS costs ($25k+/year saved)
- ✅ Complete feature control
- ✅ Reliable tools for 30+ employees
- ✅ Chris has learned system admin & development skills
- ✅ Comprehensive documentation for maintainability
- 🎯 Optional: License to other service companies

**Guiding Principles**:
- Data separation first (four databases)
- User experience matters (color-coding, clear feedback)
- Build methodically (foundation before features)
- Real user testing (Michele, Chris O, field techs)
- Document everything (future-proof the system)

---

*FieldKit Phase 0 proved the concept. Phase 1 builds the foundation. Phases 2-3 deliver the complete ServiceFusion replacement.*
