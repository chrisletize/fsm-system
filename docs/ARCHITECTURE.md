# FieldKit Architecture

*Last Updated: 2026-02-10*

## System Overview

FieldKit is a custom Field Service Management (FSM) platform built to replace ServiceFusion for four service companies. The system prioritizes data separation, performance isolation, and complete feature control while eliminating $25,000+ annual SaaS costs.

---

## Core Architectural Decision: Separate Databases

### Four Independent PostgreSQL Databases

**Critical Design Choice**: Each company operates on a completely separate database instance.

```
fieldkit_getagrip          (Get a Grip Charlotte)
fieldkit_kleanit_charlotte (Kleanit Charlotte)
fieldkit_cts               (CTS of Raleigh)
fieldkit_kleanit_sf        (Kleanit South Florida)
```

### Why Separate Databases?

**1. Performance Isolation**
- Kleanit Charlotte processes 250 jobs/day at peak
- High-volume operations won't impact other companies' performance
- No query contention between companies
- Independent query optimization per database

**2. True Data Separation**
- Zero risk of cross-company data contamination
- No "WHERE company_id = X" filter mistakes
- Regulatory compliance easier to demonstrate
- Can backup/restore companies independently

**3. Operational Independence**
- Companies can be taken offline independently for maintenance
- Database migrations can be tested on one company first
- Disaster recovery isolated per company
- Different retention policies possible per company

**4. Future Scalability**
- Can move companies to different servers if needed
- Load balancing straightforward
- Replication/failover per company
- No shared resource bottlenecks

### Trade-offs Accepted

**Cons of Separate Databases:**
- Code duplication (same schema in 4 places)
- Cross-company reporting requires querying multiple databases
- Schema changes must be applied 4 times
- More complex backup strategy

**Why We Accept These:**
- Schema stability expected after initial build
- Cross-company reporting rare (quarterly/annual only)
- Backup automation handles multiple databases easily
- Performance and data safety trump convenience

---

## Database Schema Design Principles

### 1. Comprehensive Audit Trails

**Every table includes:**
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
created_by VARCHAR(100),
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_by VARCHAR(100),
deleted_at TIMESTAMP NULL,
deleted_by VARCHAR(100)
```

**Automatic Update Trigger:**
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Applied to every table
CREATE TRIGGER update_[table_name]_updated_at 
    BEFORE UPDATE ON [table_name]
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Rationale:**
- Complete accountability for all data changes
- Soft deletes preserve historical data
- Debugging easier with full change history
- Compliance/audit requirements met

### 2. Hybrid Column + JSONB Approach

**Direct columns for:**
- Frequently searched fields (names, dates, IDs)
- Fields needed in indexes
- Required for foreign key relationships
- Core business logic fields

**JSONB for:**
- Flexible supplementary data
- Fields that change structure over time
- Low-priority metadata
- Request details in approval queues

**Example (approval_queue table):**
```sql
CREATE TABLE approval_queue (
    id SERIAL PRIMARY KEY,
    
    -- Searchable direct columns
    request_type VARCHAR(50) NOT NULL,
    target_name VARCHAR(255),
    contact_name VARCHAR(200),
    contact_email VARCHAR(255),
    
    -- Flexible details in JSONB
    request_details JSONB,
    
    -- Standard audit fields
    status VARCHAR(20) DEFAULT 'pending',
    submitted_by VARCHAR(100),
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Benefits:**
- Fast global search on key fields
- Flexibility for edge cases
- Schema evolution without migrations
- Best of both worlds

### 3. Multi-Contact Customer Support

**Problem**: Properties have multiple decision-makers (Property Manager, Assistant PM, Maintenance Supervisor).

**Solution**: Separate customer_contacts table:
```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    property_name VARCHAR(255),
    address VARCHAR(500),
    management_company_id INTEGER REFERENCES management_companies(id)
    -- No direct contact fields here
);

CREATE TABLE customer_contacts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    title VARCHAR(150),
    office_phone VARCHAR(20),
    office_email VARCHAR(255),
    is_primary BOOLEAN DEFAULT FALSE
);
```

**Advantages:**
- Unlimited contacts per property
- Track contact changes over time
- Sales system can reference same contacts
- Prevents data duplication

---

## User Authentication & Permissions

### Authentication Method: Bcrypt

**Password Storage:**
```python
import bcrypt

# Registration
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
# Store password_hash in database

# Login
if bcrypt.checkpw(entered_password.encode('utf-8'), stored_hash):
    # Success
```

**Why Bcrypt:**
- Industry standard, proven secure
- Built-in salting prevents rainbow tables
- Configurable cost factor for future-proofing
- Not reversible even if database compromised

**Additional Security:**
- Rate limiting: 5 login attempts per minute
- Session expiration: 24 hours
- HTTPS enforced in production
- No sensitive data stored (no credit cards, SSNs)

### User Roles & Permissions

**Three Role Types:**

**1. Admin**
- Full access to all companies they're assigned
- Can approve sales updates
- Manage users and settings
- Run reports across companies

**Users**: Chris Letize, Michele, Mike

**2. Manager**
- Full access to their assigned company only
- Approve sales updates for their company
- Run company-specific reports
- Cannot manage users

**Users**: Patrick (CTS), Walter (Kleanit Charlotte), Mikey C (Kleanit SF)

**3. Salesperson**
- Access to all companies (for sales work)
- Cannot modify customer database directly
- Submit updates for approval
- Manage own prospects and contacts

**Users**: Chris O, Mikey C (dual role)

### User Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    
    role VARCHAR(50) NOT NULL, -- 'admin', 'manager', 'salesperson'
    
    -- Company access as JSON array
    company_access JSONB NOT NULL,
    -- Examples:
    -- ['getagrip', 'kleanit_charlotte', 'cts', 'kleanit_sf'] for admins
    -- ['cts'] for Patrick
    -- ['kleanit_charlotte'] for Walter
    
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Multi-Company User Experience

### Company Switcher Interface

**Color-Coded Branding:**

```javascript
// Each company has distinct color palette
Get a Grip:         Burgundy (#8B1538) + Cream (#F5F5DC)
Kleanit Charlotte:  Blue (#0052CC) 
Kleanit SF:         Green (#00D66C)
CTS:                Dark Gray (#2C2C2C) + Cream (#F5F5DC)
```

**Visual Indicators:**
- Top navigation bar changes color
- Company logo displayed
- "Currently viewing: [Company Name]" header
- All buttons/accents match company colors

**Prevents Mistakes:**
- Impossible to miss which company you're working in
- Color difference immediately visible
- Critical for shared properties between Get a Grip & Kleanit Charlotte

### Database Connection Switching

**Backend Implementation:**
```python
# User selects company from dropdown
selected_company = request.form['company']

# Map to database name
db_map = {
    'getagrip': 'fieldkit_getagrip',
    'kleanit_charlotte': 'fieldkit_kleanit_charlotte',
    'cts': 'fieldkit_cts',
    'kleanit_sf': 'fieldkit_kleanit_sf'
}

# Connect to appropriate database
db = get_connection(db_map[selected_company])
```

**Session State:**
- Currently selected company stored in session
- Persists across page navigation
- Cleared on logout
- Validated against user's company_access permissions

---

## Sales System Architecture

### Separate Prospect Databases Per Company

**Each company database contains:**
- `sales_prospects` - Properties not yet customers (or dormant customers)
- `sales_contacts` - People Chris O/Mikey C meet
- `sales_visits` - Every interaction logged
- `visit_tags_config` - Customizable visit types
- `approval_queue` - Pending customer updates

**Data Flow:**

```
Chris O visits property → Logs in sales_prospects
                       ↓
         Builds relationship via sales_contacts
                       ↓
         Logs visits with tags (Hot Lead, etc.)
                       ↓
     Ready to convert → Submits approval request
                       ↓
          Manager approves → Added to customers table
```

### Approval Queue System

**Purpose**: Sales team cannot directly modify customer database, preventing accidental data corruption.

**Workflow:**
1. Chris O finds new contact at existing customer
2. Adds to his sales_contacts
3. Clicks "Submit to Customer Record"
4. Creates approval_queue entry
5. Daily 12pm report to Michele + company manager
6. Manager reviews and approves
7. System updates customer_contacts table

**Daily Approval Digest Format:**
```
FIELDKIT APPROVALS NEEDED (2/10/26)

KLEANIT CHARLOTTE (for Walter + Michele):
- Add contact "Tom Davis" to Oakwood Apartments customer record
- Update Riverside phone number

GET A GRIP (for Chris Letize + Michele):
- Convert prospect "Sunset Village" to customer
```

### Dormancy Detection

**Problem**: Customers stop scheduling, relationships go cold.

**Solution**: Automated dormancy alerts per company.

**Configuration:**
```sql
CREATE TABLE dormancy_alerts_config (
    company_name VARCHAR(100),
    alert_after_weeks INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);

-- Settings per company
Get a Grip:           8 weeks (projects less frequent)
Kleanit Charlotte:    3 weeks (high-volume, regular cleaning)
CTS:                  4 weeks
Kleanit SF:           3 weeks
```

**Chris O's App Shows:**
- "Oakwood Apartments - No jobs scheduled in 4 weeks"
- He investigates, logs notes
- Notes automatically sent to management in weekly report
- Fast feedback loop on why customers leave

---

## Cross-Database Capabilities (Phase 2)

### Contact Sync Across Companies

**Scenario**: Oakwood Apartments is customer in both Kleanit Charlotte and Get a Grip databases.

**Problem**: Contact changes in one database should propagate to other.

**Solution**: Lightweight cross-reference service

```sql
-- Separate coordination database
CREATE TABLE cross_db_property_matches (
    property_name VARCHAR(255),
    address VARCHAR(500),
    
    getagrip_customer_id INTEGER,
    kleanit_charlotte_customer_id INTEGER,
    cts_customer_id INTEGER,
    kleanit_sf_customer_id INTEGER,
    
    verified BOOLEAN DEFAULT FALSE
);
```

**Workflow:**
1. Contact updated in Kleanit Charlotte
2. System checks cross_db_property_matches
3. If Oakwood also exists in Get a Grip, creates approval request
4. Manager approves sync to both databases
5. Prevents inconsistent contact info

**Implementation**: Phase 2 feature, not MVP.

---

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: Flask (simple, proven, fast to build)
- **Database**: PostgreSQL 16
- **ORM**: psycopg2 (direct SQL, no heavy ORM)
- **PDF Generation**: ReportLab (existing, works well)

### Frontend
- **HTML/CSS/JavaScript** (no framework for simplicity)
- **Tailwind CSS** (utility-first styling)
- **Mobile-first responsive design**
- **Minimal JavaScript** (progressive enhancement)

### Infrastructure
- **Server**: Ubuntu 24 LTS on AMD Ryzen 9 hardware
- **Web Server**: Nginx reverse proxy
- **SSL**: Let's Encrypt certificates
- **Process Manager**: systemd
- **Backups**: Automated pg_dump on schedule

### Development Tools
- **Version Control**: Git + GitHub
- **IDE**: Any (VS Code, PyCharm, vim)
- **Database Tool**: psql CLI, pgAdmin (optional)

---

## Deployment Architecture

### Current Setup (Phase 0)
- Development and production on ubuntu1 server
- Single Flask instance behind Nginx
- statements.cletize.com domain
- Adequate for statement generator

### Future Production Setup (Phase 1+)

**Dedicated Production Server:**
- AMD Ryzen 9 7900 (12-core)
- 32GB ECC RAM
- Mirrored NVMe storage (RAID 1)
- Redundant power supplies
- Budget: ~$4,300

**Network:**
- OPNsense firewall/router
- Dual internet (fiber primary, 5G cellular backup)
- VPN for remote management
- IPMI for hardware management

**High Availability:**
- PostgreSQL replication (streaming)
- Automated failover (Patroni or similar)
- Daily backups to separate storage
- Offsite backup to cloud (encrypted)

---

## Data Migration Strategy

### Phase 0 (Current): Manual Excel Uploads
- Michele exports from ServiceFusion monthly
- Uploads via web interface
- Good enough for statement generator
- Zero ongoing SF costs

### Phase 1+: Native Data
- Jobs created directly in FieldKit
- No ServiceFusion dependency
- Statement generator reads FieldKit database
- Real-time data, no uploads needed

**No ServiceFusion API Integration:**
- API costs $150/month per company ($600 total)
- We're replacing SF, not extending it
- Manual uploads bridge the gap during transition

---

## Security Considerations

### Data Protection
- ✅ Bcrypt password hashing
- ✅ HTTPS enforced
- ✅ SQL injection prevention (parameterized queries)
- ✅ CSRF tokens on forms
- ✅ Rate limiting on authentication
- ✅ Session expiration
- ✅ Input validation and sanitization

### What We Don't Store
- ❌ Credit card numbers (use payment processor)
- ❌ Social Security numbers
- ❌ Sensitive personal health info
- ❌ Passwords in plaintext

### Backup Security
- Encrypted backups
- Access logs for restore operations
- Offsite storage encrypted at rest
- Regular restore testing

---

## Performance Targets

### Response Times
- Page loads: < 500ms
- Database queries: < 100ms
- PDF generation: < 2 seconds per statement
- Bulk operations: < 30 seconds for 100 items

### Scalability
- Support 300+ concurrent users
- Handle 500 jobs/day per company
- 100,000+ customer records total
- 5 years of historical data

### Availability
- 99.5% uptime target (43 hours downtime/year)
- Planned maintenance windows announced
- Automated monitoring and alerts
- Recovery time objective: < 1 hour

---

## Monitoring & Observability

### System Monitoring
- PostgreSQL slow query log
- Nginx access/error logs
- Python application logs (structured JSON)
- System resources (CPU, RAM, disk, network)

### Business Metrics
- Statements generated per month
- Active customers per company
- Job completion rates
- Revenue trends

### Alerting
- Database connection failures
- Disk space < 20%
- Application errors (500s)
- Backup failures
- SSL certificate expiration

---

## Development Principles

### Code Quality
- Clear variable/function names
- Comments for complex logic
- Type hints where helpful
- Consistent formatting (Black for Python)

### Testing Strategy
- Test with real data from day one
- Michele as primary tester for office features
- Chris O as tester for sales features
- Iterate based on actual usage feedback

### Documentation
- Living docs in GitHub (PROJECT-KNOWLEDGE/)
- Session notes after each work session
- Inline code comments for tricky parts
- README for each major component

### Version Control
- Main branch always deployable
- Feature branches for new work
- Descriptive commit messages
- GitHub for collaboration and backup

---

## Key Architectural Principles

1. **Separation of Concerns**: Four databases = four independent systems
2. **Security by Design**: Authentication, authorization, audit trails built-in
3. **Performance First**: Database design optimized for real-world queries
4. **User Experience**: Color-coding and clear feedback prevent mistakes
5. **Maintainability**: Standard tools, clear code, comprehensive docs
6. **Data Integrity**: Soft deletes, audit trails, approval workflows
7. **Scalability**: Can grow to handle more companies or higher volume
8. **Flexibility**: JSONB for evolving requirements without migrations

---

## Future Architecture Considerations

### Mobile Apps (Phase 4+)
- React Native for iOS/Android
- Or Progressive Web App (PWA)
- Offline-first for field techs
- Photo upload optimization
- GPS integration

### Advanced Features
- Real-time notifications (WebSockets)
- Advanced reporting (data warehouse)
- Machine learning (job duration prediction)
- API for third-party integrations

### Potential Multi-Tenant SaaS
- If successful, could license to other service companies
- Would require true multi-tenant architecture
- Different security model
- More complex but proven possible

---

*This architecture supports FieldKit's mission: eliminate SaaS costs, gain feature control, ensure data separation, and provide reliable tools for 30+ employees across four companies.*
