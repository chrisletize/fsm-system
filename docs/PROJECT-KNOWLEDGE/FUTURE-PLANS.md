# Future Plans & Roadmap

## Phase 1: Real-Time ServiceFusion Integration
- Replace monthly Excel uploads with live API integration
- Requires ServiceFusion Pro API access ($450/month for 4 companies)
- OAuth 2.0 authentication
- Webhook support for instant invoice updates
- Decision: Postponed until statement generator proves value
# Future Plans & Roadmap

## Phase 0: Statement Generator (CURRENT)
**Timeline**: 2-3 weeks
**Goal**: Proof of concept - prove we can build production software
**Deliverable**: Michele can generate PDF statements in <2 minutes

**Features**:
- Import invoices via Excel upload
- Generate branded PDF statements
- Customer search and filtering
- Aging bucket analysis (30/60/90/120+ days)

**Success Criteria**: Michele uses it monthly, prefers it over manual methods

---

## Phase 1: Core FSM Features
**Timeline**: 3-6 months after Phase 0
**Goal**: Replace ServiceFusion for daily operations

**Must-Have Features**:
- Customer management (CRUD)
- Job/work order creation and tracking
- Technician assignment and scheduling
- Invoice generation and management
- Payment tracking
- Mobile-friendly interface for field techs

**Nice-to-Have**:
- Calendar/schedule view
- Basic reporting (jobs completed, revenue)
- Email notifications

**Success Criteria**: Get a Grip Charlotte runs entirely on our system for 1 month

---

## Phase 2: Multi-Company & Advanced Features
**Timeline**: 6-12 months after Phase 1
**Goal**: Roll out to all 4 companies, add power features

**Features**:
- Multi-company support (proper tenant isolation)
- Inventory/parts tracking
- Route optimization for technicians
- Customer portal (view invoices, request service)
- Advanced reporting and analytics
- Mobile app (React Native or Progressive Web App)

**Success Criteria**: All 4 companies migrated off ServiceFusion

---

## Phase 3: Polish & Optimization
**Timeline**: Ongoing after Phase 2
**Goal**: Refinement based on real-world use

**Areas**:
- Performance optimization
- UI/UX improvements based on feedback
- Integrations (accounting software, payment processors)
- Automated backups and monitoring
- Documentation for future maintainers

---

## ServiceFusion API - NOT NEEDED
**Decision**: We are NOT integrating with ServiceFusion API
**Reasoning**: 
- Costs $450/month for API access (4 companies × $150)
- We're replacing ServiceFusion entirely, not extending it
- Manual Excel uploads work fine for Phase 0 statement generator
- Once we build full FSM (Phase 1+), data lives in our database natively

**When real-time data happens**: Phase 1+ when statement generator reads from our own FSM database, not from ServiceFusion exports

---

## Hardware Investment
**Timeline**: Before Phase 1 production deployment
**Goal**: Dedicated production server with redundancy

**Planned Setup**:
- AMD Ryzen 9 7900 (12-core)
- 32GB ECC RAM
- Mirrored NVMe storage
- Redundant power supplies
- Estimated cost: ~$4,300
- Power consumption: 123W average (saves $742/year vs current Dell servers)

**Details**: See `docs/DEPLOYMENT/hardware-plan.md`

---

## Long-Term Vision
**Timeline**: 12-24 months
**Goal**: Fully independent, maintainable system

**Success Looks Like**:
- Zero monthly SaaS costs (saving $25k+/year)
- Complete control over features and data
- System runs reliably with minimal maintenance
- Documentation exists for future developers
- Chris has learned system administration and software development skills
- Potential to sell/license to other service companies (optional)

---

## Known Future Challenges
- **Bus factor**: Currently only Chris knows the system
  - Mitigation: Comprehensive documentation, standard frameworks, clean code
- **Ongoing maintenance**: Software needs updates and bug fixes
  - Mitigation: Keep dependencies minimal, test thoroughly, monitor actively
- **Feature requests**: Staff will want new features
  - Mitigation: Prioritize ruthlessly, stick to core needs first

