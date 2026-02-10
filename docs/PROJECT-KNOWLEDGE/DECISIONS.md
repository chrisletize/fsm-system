# FieldKit Technical Decisions Log

## 2026-02-10: CRITICAL - Four Separate Databases Architecture
**Decision**: Four separate PostgreSQL databases (one per company)
**Databases**: 
- `fieldkit_getagrip`
- `fieldkit_kleanit_charlotte`
- `fieldkit_cts`
- `fieldkit_kleanit_sf`

**Reasoning**: 
- **Performance isolation**: Kleanit Charlotte's 250 jobs/day won't impact other companies
- **True data separation**: Zero risk of cross-company contamination
- **Operational independence**: Can maintain, backup, or migrate companies separately
- **Future scalability**: Can move companies to different servers if needed

**Alternatives Considered**: 
- Multi-tenant single database with company_id filtering
- Schema-based multi-tenancy (separate schemas in one database)

**Consequences**: 
- ✅ Complete data isolation and security
- ✅ Independent performance optimization per company
- ✅ Can scale companies independently
- ❌ Schema changes must be applied 4 times
- ❌ Cross-company reporting more complex
- ❌ Slightly more complex deployment

**Status**: FINAL - This is the foundation of FieldKit

---

## 2026-02-10: Product Naming
**Decision**: "FieldKit" as official product name
**Reasoning**: Professional, memorable, describes purpose (field service toolkit)
**Alternatives Considered**: FSM System (too generic), ServiceForce, WorkFlow Pro
**Consequences**: All documentation, code, and UI uses FieldKit branding

---

## 2026-02-10: Comprehensive Audit Trails
**Decision**: Every table includes full audit trail columns
**Implementation**:
```sql
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
created_by VARCHAR(100),
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_by VARCHAR(100),
deleted_at TIMESTAMP NULL,
deleted_by VARCHAR(100)
```

**Reasoning**: 
- Complete accountability for all data changes
- Soft deletes preserve historical data
- Debugging easier with full change history
- Compliance/audit requirements met

**Alternatives Considered**: Partial audit trails, no soft deletes
**Consequences**: Slight storage overhead, but worth it for data integrity

---

## 2026-02-10: Authentication Method
**Decision**: Bcrypt password hashing
**Reasoning**: 
- Industry standard, proven secure
- Built-in salting prevents rainbow tables
- Configurable cost factor for future-proofing
- Not reversible even if database compromised

**Alternatives Considered**: Argon2 (newer but less widely adopted), SHA256 (insecure)
**Consequences**: Passwords safe, no plain text storage ever

**Additional Security**:
- Rate limiting: 5 login attempts per minute
- Session expiration: 24 hours
- HTTPS enforced in production

---

## 2026-02-10: User Role System
**Decision**: Three primary roles with company-based access control
**Roles**:
1. **Admin**: Full access to all assigned companies (Chris Letize, Michele, Mike)
2. **Manager**: Full access to their company only (Patrick, Walter, Mikey C)
3. **Salesperson**: All companies for sales work, read-only customers (Chris O, Mikey C)

**Reasoning**: Matches actual organizational structure and security needs
**Implementation**: JSON array in users table for company_access
**Consequences**: Fine-grained control, prevents accidental cross-company access

---

## 2026-02-10: JSONB Hybrid Approach
**Decision**: Use direct columns for searchable fields, JSONB for flexible supplementary data
**Example**:
```sql
-- Direct columns for search/indexes
target_name VARCHAR(255),
contact_email VARCHAR(255),

-- Flexible data in JSONB
request_details JSONB
```

**Reasoning**: 
- Fast global search on key fields
- Flexibility for edge cases without migrations
- Best of both rigid structure and flexibility

**Alternatives Considered**: 
- All JSONB (slower searches)
- All rigid columns (inflexible)

**Consequences**: Slightly more complex queries, but optimal performance + flexibility

---

## 2026-02-10: Multi-Contact Customer Support
**Decision**: Separate `customer_contacts` table instead of single contact per customer
**Reasoning**: 
- Properties have multiple decision-makers (PM, Assistant PM, MS)
- Contacts change frequently
- Need to track contact history

**Implementation**: One-to-many relationship with `is_primary` flag
**Consequences**: More flexible, matches real-world scenarios

---

## 2026-02-10: Sales System Approval Queue
**Decision**: Salespeople cannot directly modify customer database
**Reasoning**: 
- Prevents accidental data corruption
- Sales team builds relationships without data risk
- Management approval ensures quality control

**Implementation**: Approval queue table with daily digest reports
**Consequences**: Extra approval step, but protects customer data integrity

---

## 2026-02-10: Management Companies Table
**Decision**: Centralized management_companies table referenced by customers
**Reasoning**: 
- Ensures consistent naming
- Enables management-company-level reporting
- Tracks contact movements between companies

**Alternatives Considered**: Free-text field per customer (inconsistent)
**Consequences**: Cleaner data, better reporting capabilities

---

## OLDER DECISIONS (Phase 0)

## 2026-01-14: Version Control Platform
**Decision**: GitHub (cloud-hosted)
**Reasoning**: Free private repos, built-in Projects feature, industry standard, automatic backups
**Alternatives Considered**: Self-hosted GitLab
**Consequences**: Code lives on GitHub's servers, one less thing to maintain
**Note**: Made repo public so Claude can read docs directly via GitHub URLs

---

## 2026-01-14: Project Organization
**Decision**: Use living documentation in PROJECT-KNOWLEDGE directory
**Reasoning**: Maintain context across multiple conversations, avoid token limits
**Alternatives Considered**: Keep everything in chat history
**Consequences**: 15 min overhead per sprint to update docs, but saves hours of re-explaining

---

## 2026-01-14: Development Approach
**Decision**: Start with Statement Generator proof of concept (Phase 0)
**Reasoning**: Low risk, immediate value to Michele, proves we can build business software
**Alternatives Considered**: Jump straight to full FSM system
**Consequences**: Phase 0 complete in ~40 hours, validated entire approach ✅

---

## 2026-01-15: Backend Framework
**Decision**: Flask (not FastAPI)
**Reasoning**: Simpler for Phase 0, less boilerplate, faster to prototype
**Alternatives Considered**: FastAPI (may reconsider for Phase 1+)
**Consequences**: Rapid development in Phase 0, working production system
**Status**: Confirmed - continuing with Flask for full FieldKit

---

## 2026-01-15: Database Technology
**Decision**: PostgreSQL 16
**Reasoning**: Mature, excellent JSON support, handles complex queries well, proven reliability
**Alternatives Considered**: MySQL, MongoDB
**Consequences**: Solid foundation for all FieldKit features
**Status**: Confirmed - excellent choice

---

## 2026-01-15: PDF Generation
**Decision**: ReportLab
**Reasoning**: Programmatic control over layout, professional output, Python native
**Alternatives Considered**: WeasyPrint (HTML to PDF)
**Consequences**: More code to write layouts, but pixel-perfect control
**Status**: Working excellently in production

---

## 2026-01-15: Data Import Strategy (Phase 0)
**Decision**: Manual Excel upload monthly (no ServiceFusion API integration)
**Reasoning**: 
- ServiceFusion API costs $450/month for 4 companies
- We're replacing ServiceFusion entirely, not extending it
- Manual uploads adequate for monthly statements

**Final FieldKit**: Native data (no uploads needed once SF replaced)
**Consequences**: Extra step for Michele in Phase 0, but $450/month saved
**Status**: Working well, zero ongoing SF API costs

---

## 2026-01-15: Multi-Company Branding
**Decision**: Dynamic color-coded branding per company
**Colors**:
- Get a Grip: Burgundy (#8B1538) + Cream (#F5F5DC)
- Kleanit Charlotte: Blue (#0052CC)
- Kleanit SF: Green (#00D66C)
- CTS: Dark Gray (#2C2C2C) + Cream (#F5F5DC)
- LKit (unselected): Muted lavender (#8b7a9e)

**Reasoning**: Prevents mistakes when switching between companies
**Consequences**: Users always know which company they're viewing
**Status**: Critical safety feature, working perfectly

---

## 2026-01-15: Deployment (Phase 0)
**Decision**: Systemd service on ubuntu1 behind Nginx
**Reasoning**: Already have infrastructure, simple to maintain
**Alternatives Considered**: Docker, dedicated production server
**Consequences**: Fast deployment, adequate for Phase 0
**Future**: Dedicated production server for full FieldKit (Phase 1+)

---

## REJECTED DECISIONS ❌

### ServiceFusion API Integration
**Rejected**: 2026-01-15
**Reason**: Costs $450/month, we're replacing SF not extending it
**Alternative**: Manual Excel uploads for transition period

### Multi-Tenant Single Database  
**Rejected**: 2026-02-10
**Reason**: Performance isolation needed for Kleanit's high volume
**Alternative**: Four separate databases (see first decision)

### FastAPI Framework
**Rejected**: 2026-01-15 (decided on Flask)
**Reason**: Flask simpler and faster for our needs
**May Reconsider**: If performance becomes critical in Phase 2+

---

## Decision-Making Principles

1. **Real user testing beats theory** - Michele tested Phase 0 before moving forward
2. **Data safety first** - Separate databases, audit trails, approval queues
3. **Build methodically** - Foundation before features
4. **Document everything** - Future maintainability matters
5. **Pragmatic over perfect** - Flask good enough, no need for FastAPI complexity
6. **Cost-conscious** - No ServiceFusion API, self-hosted infrastructure
7. **User experience matters** - Color-coding prevents mistakes

---

*All major architectural decisions finalized 2026-02-10. Phase 1 development can proceed with confidence.*
