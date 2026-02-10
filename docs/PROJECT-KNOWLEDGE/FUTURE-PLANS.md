# FieldKit Future Plans & Roadmap

*Last Updated: 2026-02-10*

## Phase Overview

### Phase 0: Proof of Concept ✅ COMPLETE
**Timeline**: January 2026 (6 weeks)
**Goal**: Prove we can build production software

**Delivered**:
- ✅ Statement generator (PDF generation, multi-company branding)
- ✅ Tax reporting (NC compliance, cash-basis)
- ✅ Outlook email integration (batch statements)
- ✅ Excel import workflow
- ✅ Production deployment on ubuntu1

**Success**: Michele uses it monthly, prefers it over manual methods ✅

---

### Phase 1: Core Foundation (IN PROGRESS)
**Timeline**: February-March 2026 (4-6 weeks)
**Goal**: Establish multi-company architecture, authentication, customer database

**Deliverables**:
- [ ] Four separate PostgreSQL databases setup
- [ ] User authentication system (bcrypt, sessions)
- [ ] Company switcher with color-coded branding
- [ ] Management companies table
- [ ] Customer table with multi-contact support
- [ ] Basic customer CRUD operations
- [ ] Customer search functionality

**Success Criteria**:
- Users can log in and switch between companies
- Customer data entry works with audit trails
- Color branding prevents mistakes
- Zero cross-company data contamination

---

### Phase 2: Customer Management
**Timeline**: April-May 2026 (6-8 weeks)
**Goal**: Complete customer database for operations

**Deliverables**:
- [ ] Full customer CRUD
- [ ] Customer contacts management (multiple per property)
- [ ] Advanced customer search with filters
- [ ] Customer detail views with complete history
- [ ] Customer notes and tags
- [ ] Invoice import from ServiceFusion (transition)

**Success Criteria**:
- Customer database replaces ServiceFusion customer list
- Multi-contact support working smoothly
- Search performance <100ms
- Office staff prefer FieldKit to ServiceFusion

---

### Phase 3: Sales System
**Timeline**: June-July 2026 (6-8 weeks)
**Goal**: Chris O's field contact management

**Deliverables**:
- [ ] Sales prospects database per company
- [ ] Contact management with property history
- [ ] Mobile-friendly visit logging
- [ ] Visit tagging system with auto follow-ups
- [ ] Approval queue for customer updates
- [ ] Dormancy detection and alerts
- [ ] Weekly sales reports
- [ ] Manager approval workflows
- [ ] Location-based prospect filtering

**Success Criteria**:
- Chris O logs visits in <60 seconds from tablet
- Management receives dormancy feedback weekly
- Zero customer database corruption
- Sales activity measurable and reportable

---

### Phase 4: Job Management & Scheduling
**Timeline**: August-October 2026 (10-12 weeks)
**Goal**: Replace ServiceFusion for daily operations

**Deliverables**:
- [ ] Job/work order creation and tracking
- [ ] Technician assignment
- [ ] Calendar/schedule view (improve on existing prototype)
- [ ] Job status workflows (scheduled → in progress → complete)
- [ ] Basic time tracking
- [ ] Equipment tracking (Kleanit dehumidifiers/fans)
- [ ] Job photos/documentation
- [ ] Dispatch dashboard

**Success Criteria**:
- Get a Grip Charlotte runs entirely on FieldKit for 1 month
- Techs can view and update jobs from field
- Office can dispatch efficiently
- No "oops, we needed ServiceFusion" moments

---

### Phase 5: Invoicing & Payments
**Timeline**: November-December 2026 (8-10 weeks)
**Goal**: Complete financial operations in FieldKit

**Deliverables**:
- [ ] Invoice generation from completed jobs
- [ ] Payment tracking and recording
- [ ] Automated aging reports
- [ ] Collections workflow
- [ ] QuickBooks export (eliminate sync issues)
- [ ] Financial dashboard

**Success Criteria**:
- Michele can invoice from FieldKit
- Statement generator uses native FieldKit data
- QuickBooks sync problems eliminated
- Financial reporting accurate

---

### Phase 6: Mobile Apps
**Timeline**: Q1 2027 (12-16 weeks)
**Goal**: Native mobile experience for field techs

**Deliverables**:
- [ ] Mobile app (React Native or PWA)
- [ ] Offline-first for field use
- [ ] Photo upload optimization
- [ ] GPS integration
- [ ] Push notifications
- [ ] Voice notes
- [ ] Barcode scanning (equipment tracking)

**Success Criteria**:
- Techs prefer mobile app to ServiceFusion mobile
- Works reliably with poor cell coverage
- Photo uploads don't eat mobile data
- App is fast and responsive

---

## Long-Term Enhancements (2027+)

### Advanced Features
- **Route optimization** for techs (AI-powered)
- **Predictive scheduling** (job duration estimates)
- **Customer portal** (view invoices, request service)
- **Advanced analytics** (revenue forecasting, trends)
- **Duplicate job detection** (apartment units)
- **Help system** (context-aware, uses real data in examples)

### Integration Possibilities
- QuickBooks Online API (two-way sync)
- Payment processors (Stripe, Square)
- Marketing automation (Mailchimp, etc.)
- Text/SMS notifications (Twilio)
- Google Calendar sync
- Accounting software alternatives (Xero, FreshBooks)

### Cross-Database Features (Phase 2 Enhancement)
- **Contact sync across companies**: When contact info changes in one company's database, can sync to others where same property exists
- **Implementation**: Lightweight coordination database tracks property matches
- **Approval workflow**: Both company managers approve before sync
- **Benefit**: Consistent contact info across Get a Grip + Kleanit shared customers

### AI-Powered Features (Exploration)
- Natural language reporting: "Show me hot leads in Charlotte from last month"
- Smart duplicate detection: "This prospect might already be a customer"
- Route optimization: "Best order to visit these 8 properties"
- Email cleanup: Auto-fix formatting in imported contact data
- Follow-up suggestions: Based on historical conversion rates
- **Philosophy**: Invisible assistance, not Clippy-style popups

---

## ServiceFusion Migration Strategy

### Parallel Operation Period (Phases 1-5)
- FieldKit and ServiceFusion run simultaneously
- Import data from SF as needed
- One company at a time migration
- Extensive testing before full cutover

### Migration Order (Tentative)
1. **CTS** (smallest, test case)
2. **Get a Grip** (Chris's company, will catch issues)
3. **Kleanit Charlotte** (highest volume, most critical)
4. **Kleanit South Florida** (last, benefits from all lessons learned)

### Data Migration Tasks
- [ ] Historical job data (keep for reference)
- [ ] Customer information (complete with contacts)
- [ ] Invoice history (past 2-3 years)
- [ ] Payment records (for AR accuracy)
- [ ] Technician schedules (current/future jobs)
- [ ] Equipment assignments (Kleanit only)

### Cutover Criteria
- All critical features working
- Staff trained on FieldKit
- 2 weeks successful parallel operation
- Backup plan if rollback needed
- Management sign-off

---

## Hardware Investment Plan

### Dedicated Production Server
**Timeline**: Before Phase 4 (Job Management)
**Reason**: Can't run high-volume operations on development server

**Planned Specifications**:
- AMD Ryzen 9 7900 (12-core, excellent single-thread + multi-thread)
- 32GB ECC RAM (error correction for data integrity)
- Mirrored NVMe storage (RAID 1 for redundancy)
- Redundant power supplies
- IPMI for remote management

**Budget**: ~$4,300
**Power**: 123W average (~$10/month vs $72/month current Dell servers)
**ROI**: Hardware pays for itself in power savings + zero SaaS costs

### Network Infrastructure (Already in Place)
- OPNsense firewall/router
- Dual internet (fiber primary, 5G cellular backup)
- VPN for remote management
- Proper segmentation and security

---

## Success Metrics (12-24 Months)

### Financial Goals
- ✅ Zero monthly SaaS costs ($25,000+/year saved)
- ✅ Hardware ROI in 6-8 months
- ✅ No ServiceFusion subscription fees
- ✅ No QuickBooks sync issues costs (Michele's time saved)

### Operational Goals
- ✅ System runs reliably with <1 hour downtime/month
- ✅ 30+ employees use FieldKit daily
- ✅ Response times <500ms for common operations
- ✅ Michele spends <1 hour/week on system issues (vs 5-10 hours fixing SF sync)

### Strategic Goals
- ✅ Complete control over features and data
- ✅ Can customize workflows for each company
- ✅ Chris has learned system administration
- ✅ Comprehensive documentation for future maintainability
- 🎯 Optional: License FieldKit to other service companies

---

## Known Challenges & Mitigation

### Challenge: Bus Factor (Only Chris knows system)
**Mitigation**:
- Comprehensive documentation (PROJECT-KNOWLEDGE, code comments)
- Use standard frameworks (Flask, PostgreSQL, React)
- Clean, readable code
- Session notes after every work session

### Challenge: Ongoing Maintenance
**Mitigation**:
- Minimal dependencies (reduce update burden)
- Automated backups
- Monitoring and alerting
- Test thoroughly before deploying

### Challenge: Feature Creep
**Mitigation**:
- Prioritize ruthlessly
- Stick to core needs first
- "Can we do this in Phase 7?" mentality
- Real user feedback guides priorities

### Challenge: User Adoption
**Mitigation**:
- Involve users early (Michele tested Phase 0)
- Training before rollout
- Parallel operation period
- Listen to feedback and iterate

---

## What We're NOT Building

❌ **ServiceFusion API Integration**: We're replacing them, not extending
❌ **Generic SaaS Platform**: Built for our 4 companies, not marketplace
❌ **Mobile App (Initially)**: Web-first, PWA, then native if needed
❌ **Complex Inventory System**: Just equipment tracking for Kleanit
❌ **HR/Payroll**: Not in scope, use existing systems
❌ **Marketing Automation**: Out of scope for now
❌ **Business Intelligence Suite**: Basic reporting sufficient

---

## Potential Future Revenue (Optional)

If FieldKit proves successful:

### Licensing to Similar Service Companies
- Small carpet cleaning companies (~10-50 employees)
- Surface restoration businesses
- Similar high-volume service industries
- Charge monthly SaaS fee (less than ServiceFusion)
- Provide hosting, support, updates

### Revenue Model (Hypothetical)
- $200/month per company (vs $382 SF charges)
- 10 customers = $24,000/year revenue
- Covers maintenance, support, hosting
- Additional income stream for Chris

**Status**: Not a priority, but possible if FieldKit succeeds

---

## Timeline Summary

| Phase | Timeline | Status | Goal |
|-------|----------|--------|------|
| Phase 0 | Jan 2026 | ✅ Complete | Proof of concept |
| Phase 1 | Feb-Mar 2026 | 🔄 In Progress | Core foundation |
| Phase 2 | Apr-May 2026 | 📋 Planned | Customer management |
| Phase 3 | Jun-Jul 2026 | 📋 Planned | Sales system |
| Phase 4 | Aug-Oct 2026 | 📋 Planned | Job management |
| Phase 5 | Nov-Dec 2026 | 📋 Planned | Invoicing & payments |
| Phase 6 | Q1 2027 | 📋 Planned | Mobile apps |
| Migration | Q3-Q4 2026 | 📋 Planned | Full SF replacement |

**Total Development**: ~12 months from start to complete SF replacement

---

*FieldKit replaces $25k/year in SaaS costs with a system built exactly for our workflows. The investment is time, not money - and we get complete control forever.*
