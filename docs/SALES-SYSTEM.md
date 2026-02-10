# FieldKit Sales System Specification

*Last Updated: 2026-02-10*

## Overview

The Sales System is a mobile-first contact relationship manager (CRM) for field salespeople to track property visits, build relationships, and manage prospects without risking customer database integrity.

**Primary Users**: Chris O (all companies), Mikey C (Kleanit South Florida only)

**Core Purpose**: Bridge the gap between cold prospects and active customers through relationship tracking and structured follow-up.

---

## Business Problem

### Current Pain Points
1. **Lost relationships**: Properties stop scheduling, no system to track why or follow up
2. **Contact churn**: Property Managers and Maintenance Supervisors change jobs frequently
3. **Disorganized prospecting**: No central place to track visits, notes, or follow-ups
4. **Data risk**: Sales team could accidentally corrupt customer database
5. **No feedback loop**: Management doesn't know why customers go dormant

### Success Criteria
- Chris O can log a visit in < 60 seconds from his tablet in the field
- Weekly reports show management why customers went dormant
- Zero accidental corruption of customer database
- Prospects convert to customers through approval workflow
- Sales activity is measurable and reportable

---

## System Architecture

### Separate Databases Per Company

Each of the four company databases contains its own sales system:

```
fieldkit_getagrip:
  ├── sales_prospects
  ├── sales_contacts
  ├── sales_visits
  └── approval_queue

fieldkit_kleanit_charlotte:
  ├── sales_prospects
  ├── sales_contacts  
  ├── sales_visits
  └── approval_queue

(same for CTS and Kleanit SF)
```

**Rationale**: 
- Sales prospects are company-specific until they become customers
- Chris O switches between companies via company selector
- No prospect data shared between databases

---

## Data Model

### Core Entities

**1. Properties**
- Can be: Active Customer, Dormant Customer, or Prospect
- Customers live in main `customers` table (read-only for sales)
- Prospects live in `sales_prospects` table (full access for sales)

**2. Contacts (People)**
- Property Managers, Maintenance Supervisors, Regional Managers
- Work at specific properties
- Can move between properties over time
- Personal relationships Chris O builds

**3. Visits (Interactions)**
- Every time Chris O visits a property
- Tagged with visit type (Hot Lead, Brief Chat, etc.)
- Notes about conversation
- Follow-up dates calculated automatically

**4. Management Companies**
- Who owns the property
- Shared across properties
- Helps track contact movements between properties

---

## Database Schema

### `management_companies`

*Master list ensuring consistent naming*

```sql
CREATE TABLE management_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    website VARCHAR(255),
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);
```

**Benefits**:
- Prevents "ABC Management" vs "ABC Prop Mgmt" vs "A.B.C. Management"
- Enables management-company-level reporting
- Tracks when contacts move between management companies

---

### `sales_prospects`

*Properties not yet in customer database*

```sql
CREATE TABLE sales_prospects (
    id SERIAL PRIMARY KEY,
    property_name VARCHAR(255) NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(2),
    zip VARCHAR(10),
    management_company_id INTEGER REFERENCES management_companies(id),
    customer_type VARCHAR(50), -- 'Multi Family', 'Contractors', 'Residential'
    
    -- Contractor-specific fields
    contractor_company_name VARCHAR(255), -- NULL for non-contractors
    active_projects INTEGER DEFAULT 0,
    
    -- Tracking
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Former customer tracking
    is_former_customer BOOLEAN DEFAULT FALSE,
    customer_id INTEGER, -- Reference to main customers table if was customer before
    former_customer_last_job DATE,
    
    -- Conversion tracking
    converted_to_customer BOOLEAN DEFAULT FALSE,
    converted_date DATE,
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_prospects_location ON sales_prospects(latitude, longitude);
CREATE INDEX idx_prospects_type ON sales_prospects(customer_type);
CREATE INDEX idx_prospects_converted ON sales_prospects(converted_to_customer);
```

**Key Features**:
- `is_former_customer` flag - shows Chris O this property already knows us
- `customer_type` distinguishes Multi Family, Contractors, Residential
- Location tracking for proximity-based filtering
- Conversion tracking preserves sales history

---

### `sales_contacts`

*People Chris O meets*

```sql
CREATE TABLE sales_contacts (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    title VARCHAR(150), -- 'Property Manager', 'Maintenance Supervisor', etc.
    
    -- Contact info
    personal_phone VARCHAR(20),
    personal_email VARCHAR(255),
    office_phone VARCHAR(20),
    office_email VARCHAR(255),
    
    -- Current employment
    current_property_id INTEGER,
    current_property_type VARCHAR(20), -- 'prospect' or 'customer'
    
    notes TEXT,
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX idx_contacts_name ON sales_contacts(last_name, first_name);
CREATE INDEX idx_contacts_property ON sales_contacts(current_property_id, current_property_type);
```

**Design Notes**:
- Separate personal vs office contact info (personal = Chris O's relationship)
- Can reference either prospect or existing customer
- Notes field for relationship details

---

### `contact_property_history`

*Tracks when contacts move between properties*

```sql
CREATE TABLE contact_property_history (
    id SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES sales_contacts(id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL,
    property_type VARCHAR(20) NOT NULL, -- 'prospect' or 'customer'
    property_name VARCHAR(255), -- Denormalized for history
    
    started_date DATE,
    ended_date DATE,
    
    notes TEXT, -- Why they left, where they went
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);

CREATE INDEX idx_contact_history ON contact_property_history(contact_id, ended_date);
```

**Use Cases**:
- "Sarah Johnson worked at Oakwood from 2023-2025, now at Pinecrest"
- Helps Chris O track relationships across properties
- Valuable for management company connections

---

### `sales_visits`

*Every interaction logged*

```sql
CREATE TABLE sales_visits (
    id SERIAL PRIMARY KEY,
    property_id INTEGER NOT NULL,
    property_type VARCHAR(20) NOT NULL, -- 'prospect' or 'customer'
    
    visit_date DATE NOT NULL,
    visit_time TIME,
    
    -- Visit classification
    visit_tag VARCHAR(50), -- 'Leasing Agent Only', 'Hot lead', etc.
    contact_id INTEGER REFERENCES sales_contacts(id), -- Who they met
    
    notes TEXT,
    
    -- Follow-up tracking
    follow_up_needed BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    follow_up_completed BOOLEAN DEFAULT FALSE,
    
    -- Dormant customer investigation
    is_dormant_investigation BOOLEAN DEFAULT FALSE,
    dormancy_reason TEXT, -- Why customer went quiet
    dormancy_reported_to_management BOOLEAN DEFAULT FALSE,
    
    -- Location
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    
    -- Audit
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
);

CREATE INDEX idx_visits_property ON sales_visits(property_id, property_type);
CREATE INDEX idx_visits_date ON sales_visits(visit_date DESC);
CREATE INDEX idx_visits_followup ON sales_visits(follow_up_date) WHERE follow_up_needed = TRUE;
CREATE INDEX idx_visits_dormant ON sales_visits(is_dormant_investigation) WHERE is_dormant_investigation = TRUE;
```

**Critical Features**:
- `is_dormant_investigation` triggers automatic management report
- `visit_tag` drives follow-up scheduling
- Location captured for routing optimization later
- Notes searchable for finding specific conversations

---

### `visit_tags_config`

*Customizable visit types*

```sql
CREATE TABLE visit_tags_config (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(50) NOT NULL UNIQUE,
    tag_description TEXT,
    default_followup_days INTEGER, -- NULL = no automatic follow-up
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default tags
INSERT INTO visit_tags_config (tag_name, tag_description, default_followup_days, display_order) VALUES
('Leasing Agent Only', 'Could not reach decision-maker, left card', 14, 1),
('Brief chat', 'Short conversation under 5 minutes', 30, 2),
('Full meeting', 'Substantial discussion 15+ minutes', 21, 3),
('Hot lead', 'Expressed immediate interest', 5, 4),
('Warm lead', 'Interested but timing unclear', 21, 5),
('Cold/No interest', 'Not interested currently', 90, 6),
('Existing customer check-in', 'Relationship maintenance', 60, 7),
('Pricing requested', 'Needs quote or proposal', 3, 8),
('Follow-up scheduled', 'They asked for specific return date', NULL, 9);
```

**Customization**:
- Chris O can adjust follow-up timeframes
- Can add new tags as workflow evolves
- `is_active` allows retiring old tags without deleting history

---

### `approval_queue`

*Sales-to-customer data flow control*

```sql
CREATE TABLE approval_queue (
    id SERIAL PRIMARY KEY,
    request_type VARCHAR(50) NOT NULL, -- 'add_contact', 'update_contact', 'convert_prospect'
    
    -- Target of change
    target_type VARCHAR(20), -- 'customer', 'prospect'
    target_id INTEGER,
    target_name VARCHAR(255), -- Denormalized for display
    
    -- Contact info for global search
    contact_name VARCHAR(200),
    contact_phone VARCHAR(20),
    contact_email VARCHAR(255),
    
    -- Additional flexible data
    request_details JSONB,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected', 'edited'
    submitted_by VARCHAR(100) NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    
    -- Cross-database sync (Phase 2)
    requires_cross_db_sync BOOLEAN DEFAULT FALSE,
    target_databases TEXT[],
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approval_status ON approval_queue(status, submitted_at DESC);
CREATE INDEX idx_approval_submitter ON approval_queue(submitted_by);
```

**Example `request_details` JSON**:

*Add contact to customer:*
```json
{
  "action": "add_contact",
  "customer_id": 45,
  "customer_name": "Oakwood Apartments",
  "contact": {
    "first_name": "Sarah",
    "last_name": "Johnson",
    "title": "Property Manager",
    "office_phone": "555-1234",
    "office_email": "sjohnson@oakwood.com"
  },
  "submitted_reason": "New PM replaced Tom Davis"
}
```

*Convert prospect to customer:*
```json
{
  "action": "convert_prospect",
  "prospect_id": 47,
  "prospect_name": "Riverside Apartments",
  "customer_type": "Multi Family",
  "contacts_to_include": [23, 24]
}
```

---

### `dormancy_alerts_config`

*Per-company dormancy detection settings*

```sql
CREATE TABLE dormancy_alerts_config (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    alert_after_weeks INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default per company (inserted during setup)
-- Get a Grip: 8 weeks
-- Kleanit Charlotte: 3 weeks
-- CTS: 4 weeks
-- Kleanit SF: 3 weeks
```

**Rationale**:
- Get a Grip projects less frequent (resurfacing multi-year cycle)
- Kleanit high-volume, regular cleaning (2-week gap is red flag)

---

## User Workflows

### Chris O's Daily Workflow

**Morning: Review Today's Schedule**
1. Login to sales system
2. Switch to appropriate company (color-coded interface)
3. View "Follow-ups Due Today" dashboard
4. See list of properties to visit with context from last visit

**In the Field: Log Visits**
1. Arrive at Oakwood Apartments
2. Open mobile interface
3. Search "Oakwood" (finds existing customer or prospect)
4. Click "Log Visit"
5. Select visit tag: "Full meeting"
6. Select contact: "Sarah Johnson - Property Manager"
7. Add notes: "Discussed upcoming project, wants quote by Friday"
8. Submit (takes < 60 seconds)
9. System auto-calculates follow-up date (21 days for Full meeting)

**End of Day: Quick Review**
- View "Today's Activity" summary
- Add any forgotten notes
- Review tomorrow's scheduled follow-ups

---

### Chris O Investigates Dormant Customer

**Scenario**: App shows "Oakwood Apartments - No jobs in 4 weeks (Kleanit Charlotte)"

**Workflow**:
1. Click on alert
2. Reviews last job date, previous notes
3. Visits property next day
4. Logs visit with special flag: "Dormant investigation"
5. Tags as "Brief chat"
6. Notes: "Spoke with Sarah - they switched to EcoClean because we missed two appointments last month. She said if we can prove reliability they'd consider coming back."
7. Checks box: "Send to management"
8. System automatically adds to Monday morning weekly report

**Management Sees** (Monday 8am email):
```
DORMANT CUSTOMER INTELLIGENCE

Oakwood Apartments (Kleanit Charlotte)
Investigated by: Chris O on 2/8/26
Last job: 1/10/26
Reason: Missed appointments, switched to EcoClean
Reactivation potential: Possible if we improve reliability
Notes: [full text]
```

---

### Converting Prospect to Customer

**Scenario**: Chris O has been building relationship with Riverside Apartments, they're ready to sign.

**Workflow**:
1. Chris O opens Riverside in prospects
2. Clicks "Convert to Customer"
3. Reviews prospect info (property name, address, management company)
4. Selects primary contact: "John Smith - Maintenance Supervisor"
5. Adds note: "Hot lead, wants immediate service"
6. Clicks "Submit for Approval"
7. Approval request created

**Manager Sees** (Daily 12pm digest):
```
KLEANIT CHARLOTTE APPROVALS (for Walter + Michele)

Convert prospect "Riverside Apartments" to customer
- Address: 123 Main St, Charlotte NC
- Management: ABC Property Management
- Primary contact: John Smith, MS (555-1234)
- Customer type: Multi Family
- Submitted by: Chris O on 2/10/26
- Notes: Hot lead, wants immediate service

[Approve] [Reject] [Edit]
```

**Manager clicks Approve**:
- Prospect converted wizard launches
- Reviews all details
- Confirms customer type
- Clicks "Create Customer"
- System adds to `customers` table
- Marks prospect as `converted_to_customer = TRUE`
- Chris O notified of approval

---

## User Interface Design

### Mobile-First Principles

**Target Device**: iPad or Android tablet in field

**Design Priorities**:
1. **Large touch targets** (minimum 44x44px)
2. **Minimal typing** (dropdowns, checkboxes, pre-filled data)
3. **Works offline** (cache recent data, sync when online)
4. **Fast load times** (< 2 seconds on 4G)
5. **Clear visual hierarchy** (most important actions prominent)

### Company Selector

**Visual Design**:
```
[🎨 Get a Grip ▼]  ← Burgundy background, cream text
[🎨 Kleanit Charlotte ▼]  ← Blue background, white text
[🎨 CTS ▼]  ← Dark gray background, cream text
[🎨 Kleanit SF ▼]  ← Green background, white text
```

**Behavior**:
- Selected company shown in top navigation
- Entire app theme changes color
- Confirms which database user is viewing
- Impossible to miss what company you're working in

### Property Search

**Smart Search Features**:
- Autocomplete as user types
- Shows: Property name, address, last visit date
- Sorts by proximity if GPS enabled
- Differentiates customers (✓) from prospects (○)

**Example Results**:
```
📍 Nearby Properties

✓ Oakwood Apartments
  123 Main St • Last visit: 2 days ago
  
○ Riverside Commons  
  456 Oak Rd • Prospect • Never visited
  
✓ Pinecrest Village
  789 Pine Ave • Last visit: 3 weeks ago
```

### Visit Logging Screen

**Quick-Tap Interface**:
```
Log Visit - Oakwood Apartments

Who did you meet?
[Search contacts...] or [+ New Contact]

Visit Type (tap one):
[Leasing Agent Only] [Brief chat] [Full meeting]
[Hot lead] [Warm lead] [Cold/No interest]
[Customer check-in] [Pricing requested]

Notes:
[Text area - voice-to-text enabled]

Follow-up needed?
☑ Yes (auto-calculated: 21 days)
☐ No

[Log Visit] [Cancel]
```

**Speed Optimizations**:
- Last contacted person pre-selected
- Visit tags have keyboard shortcuts (1-9)
- Voice notes supported
- Auto-saves draft if interrupted

---

## Reporting & Analytics

### Weekly Sales Report (Management)

**Delivered**: Monday 8am to Michele + company managers

**Sections**:

**1. Activity Summary**
```
Chris O - Week of 2/3-2/9

Total visits: 47
- Get a Grip: 12 visits
- Kleanit Charlotte: 25 visits
- CTS: 5 visits
- Kleanit SF: 5 visits

New prospects added: 8
Contacts created/updated: 14
Dormant investigations: 6
```

**2. Dormant Customer Intelligence**
```
KLEANIT CHARLOTTE
- Oakwood Apartments: Switched to competitor (service quality issue)
- Riverside Commons: Budget cuts, may return Q3
- Pinecrest Village: Property manager changed, new PM not interested

GET A GRIP
- Downtown Plaza: Completed renovation, no immediate needs
- Sunset Center: Sold to new ownership, researching vendors
```

**3. Hot Leads Requiring Follow-Up**
```
PRICING REQUESTED (urgent):
- Bayview Apartments (Kleanit Charlotte) - Quote due by 2/12
- Tech Park Office (CTS) - Wants proposal this week

HOT LEADS (high interest):
- Marina Village (Kleanit SF) - Ready to sign, waiting on contract
- Lakeside Townhomes (Get a Grip) - Wants to schedule estimate
```

**4. Pipeline Health**
```
KLEANIT CHARLOTTE
- Prospects: 45 total
- Hot leads: 8
- Warm leads: 22
- Cold: 15

Trend: +3 prospects from last week, +2 hot leads
```

---

### Chris O's Personal Report

**Same Structure, Different Focus**:
- Shows his own activity (not critique from management)
- Highlights upcoming follow-ups
- Completion rate for scheduled tasks
- Personal goals tracking (optional)

**No Management Commentary**:
- No quota pressure
- No "expected results" vs actual
- Just facts and follow-ups

---

### Manager Dashboard

**Real-Time View**:
- Pending approvals count
- This week's visit summary
- Hot leads by salesperson
- Dormant customer trends

**Monthly Rollup**:
- New customers acquired (from prospects)
- Retention rate (customers staying active)
- Sales activity by region/territory
- Most common dormancy reasons

---

## Integration with Core FieldKit

### Read-Only Customer Access

**Sales system can:**
- Search customers by name
- View customer contact info
- See last job date (for dormancy detection)
- View job history summary

**Sales system cannot:**
- Modify customer records directly
- Delete customers
- Change invoices
- Alter job history

### Approval-Mediated Updates

**Sales system can submit:**
- Add new contact to customer
- Update existing contact info
- Flag customer as "needs attention"
- Add notes to customer record

**All changes go through approval queue first.**

### Prospect-to-Customer Conversion

**When approved, system:**
1. Creates new customer record in `customers` table
2. Copies contacts to `customer_contacts` table
3. Sets management_company_id reference
4. Marks prospect as `converted_to_customer = TRUE`
5. Preserves prospect record for sales history

**Customer ID linking**:
- Prospect record gets `customer_id` field populated
- Enables tracking: "This customer came from Chris O's prospecting"

---

## Dormancy Detection Logic

### Algorithm

**For each company, every night at 2am:**

```python
# Get company's dormancy threshold
threshold_weeks = get_dormancy_config(company_id).alert_after_weeks

# Find customers with no recent jobs
dormant_customers = db.query("""
    SELECT c.id, c.property_name, MAX(j.job_date) as last_job
    FROM customers c
    LEFT JOIN jobs j ON c.id = j.customer_id
    GROUP BY c.id
    HAVING MAX(j.job_date) < NOW() - INTERVAL '{} weeks'
    OR MAX(j.job_date) IS NULL
""".format(threshold_weeks))

# Create alerts for sales system
for customer in dormant_customers:
    if not already_has_alert(customer.id):
        create_dormancy_alert(customer.id, customer.last_job)
```

**Chris O sees in app**:
```
⚠️ DORMANT CUSTOMERS (6)

Oakwood Apartments
Last job: 4 weeks ago
[Investigate] [Dismiss]

Riverside Commons
Last job: 5 weeks ago
[Investigate] [Dismiss]
```

**Clicking "Investigate"**:
- Opens visit logging screen
- Pre-fills: property, date, "Dormant investigation" checkbox
- Chris O adds notes about why they went quiet
- Submits → automatically goes to weekly management report

---

## Location-Based Features

### Proximity Search

**Use Case**: Chris O is in area, wants to see nearby properties to visit.

**Implementation**:
```sql
-- Find properties within 5 miles
SELECT p.*, 
    (3959 * acos(cos(radians(:user_lat)) 
    * cos(radians(p.latitude)) 
    * cos(radians(p.longitude) - radians(:user_lng)) 
    + sin(radians(:user_lat)) 
    * sin(radians(p.latitude)))) AS distance
FROM sales_prospects p
WHERE deleted_at IS NULL
HAVING distance < 5
ORDER BY distance
LIMIT 20;
```

**UI Display**:
```
📍 Properties Near You (within 5 miles)

0.3 mi - Oakwood Apartments ✓
         Last visit: 2 days ago
         
0.8 mi - Riverside Commons ○
         Never visited • Warm lead
         
1.2 mi - Pinecrest Village ✓
         Last visit: 3 weeks ago • Follow-up due
```

### Route Planning (Future)

**Goal**: Optimize drive time between visits.

**Phase 3 Feature**:
- Select multiple properties to visit
- Generate optimal route
- Export to Google Maps
- Track actual vs planned time

---

## Security & Permissions

### Role-Based Access

**Salespeople (Chris O, Mikey C)**:
- ✅ Full access to sales_prospects
- ✅ Full access to sales_contacts
- ✅ Full access to sales_visits
- ✅ Can submit approval requests
- ✅ Read-only access to customers
- ❌ Cannot modify customers directly
- ❌ Cannot approve own requests

**Managers (Walter, Patrick, Mikey C)**:
- ✅ Approve/reject sales requests for their company
- ✅ View sales reports for their company
- ✅ Cannot approve for other companies
- ❌ Cannot modify Chris O's prospect data

**Admins (Chris Letize, Michele, Mike)**:
- ✅ Full access to all sales data
- ✅ Approve requests for any company
- ✅ Cross-company reporting
- ✅ Modify system configuration

### Data Isolation

**By Company**:
- Chris O in "Kleanit Charlotte mode" sees only Kleanit Charlotte prospects
- Company switcher enforces database-level separation
- No accidental cross-company data contamination

**By User**:
- Chris O sees his own notes in full detail
- Managers see summarized reports
- Cannot edit other users' visit logs (audit integrity)

---

## Phase 2 Enhancements (Future)

### Cross-Database Contact Sync

**Problem**: Contact changes in one company should propagate to other companies where same property exists.

**Solution**:
- Separate "coordination database" tracks property matches
- "Oakwood Apartments exists in Kleanit Charlotte AND Get a Grip"
- Contact update triggers cross-database approval request
- Both company managers approve before sync

**Implementation**: Not in MVP, adds complexity.

---

### AI-Powered Features (Future Consideration)

**Potential Use Cases**:
- Natural language reporting: "Show me hot leads in Charlotte from last month"
- Smart duplicate detection: "This prospect might already be a customer"
- Route optimization: "Best order to visit these 8 properties"
- Email cleanup: Auto-fix formatting in imported contact data
- Suggested follow-up dates based on historical conversion rates

**Philosophy**: 
- Invisible assistance, not Clippy-style popups
- AI should make Chris O faster, not annoying
- Always user-controllable (can override AI suggestions)

---

## Success Metrics

### Quantitative Goals

**For Chris O**:
- < 60 seconds to log a visit
- Zero lost notes (everything saved)
- 90%+ follow-up completion rate
- 100% dormant customer investigation coverage

**For Management**:
- Weekly dormancy feedback within 24 hours of investigation
- Zero customer database corruption incidents
- 95%+ approval requests reviewed within 48 hours
- 20%+ increase in prospect-to-customer conversion rate

**System Performance**:
- < 2 seconds page load on 4G
- < 500ms property search response
- 99.5% uptime

### Qualitative Goals

**Chris O Experience**:
- "This makes my job easier"
- "I never lose track of follow-ups"
- "I can prove my activity to management"

**Management Experience**:
- "We know why customers leave now"
- "No more accidental data problems from sales team"
- "Sales activity is measurable"

---

## Implementation Roadmap

### Phase 1: Foundation (4-6 weeks)
- Database schema setup (all 4 companies)
- User authentication
- Company switcher
- Basic prospect CRUD

### Phase 2: Core Sales Features (6-8 weeks)
- Visit logging
- Contact management
- Visit tag system
- Follow-up scheduling

### Phase 3: Reporting & Approval (4-6 weeks)
- Weekly sales reports
- Approval queue
- Dormancy detection
- Manager dashboard

### Phase 4: Mobile Optimization (4 weeks)
- Offline support
- GPS integration
- Voice notes
- Touch-optimized UI

### Phase 5: Advanced Features (ongoing)
- Route planning
- Cross-database sync
- Advanced analytics
- AI enhancements (optional)

---

*The Sales System completes FieldKit's mission by bridging prospecting and operations, protecting data integrity while empowering sales activity, and providing management with visibility into customer retention.*
