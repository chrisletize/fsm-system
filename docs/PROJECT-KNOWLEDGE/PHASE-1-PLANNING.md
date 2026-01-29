# Phase 1: FSM Development Planning
**Created**: 2026-01-28
**Status**: Planning Phase

---

## 🎯 Project Vision

Build a complete Field Service Management (FSM) system to replace ServiceFusion, saving ~$25k/year while gaining full control over features and eliminating QuickBooks sync issues.

### Success Criteria
- System handles 250 jobs/day at peak (Kleanit)
- Calendar feels "like a video game" (smooth, fast, responsive)
- Mobile photo uploads in 2-5 seconds (vs 30 seconds in ServiceFusion)
- Zero downtime tolerance - business-critical system
- Works better than ServiceFusion for OUR specific workflows

---

## 📋 Complete Feature Requirements

### ✅ MUST HAVE - Day 1

#### Customer Management
- Full customer database with 2-year searchable history
- Up to 3 contacts per customer
- Service location separate from billing address
- Customer notes (visible to customer)
- Internal notes (staff only - SEPARATE from customer notes)
- **Tag system for unit numbers** (apartment workflow)
- **Duplicate job detection** - Alert if same unit # within ±2 weeks

#### Job/Work Order Management
- Create jobs from phone/text/email
- Customer notes vs Internal comments (SEPARATE)
- Job status tracking (scheduled → in progress → completed)
- Before/after photos attached to invoices
- Extensive job history (2 years fast access)
- **Products vs Services separation** (tax compliance per company)

#### Scheduling/Dispatch
- **Drag-and-drop calendar** - Must be FAST and SMOOTH
- Multiple staff + managers editing simultaneously
- Daily view optimized for high volume (200+ jobs/day)
- Real-time updates across all devices
- Manager calendar showing all techs
- Manager ability to reassign jobs from mobile
- **GPS tracking** - See tech locations during workday
- Visual feedback on drag operations
- 60fps animations (no jank)

#### Invoicing/Billing
- Same-day invoicing after completion
- Products vs Services line items
- Payment tracking (field + office)
- Before/after photos attached to sent invoices
- Tax calculation by county
- **Payment recording workflow optimized** (Michele's pain point - stay on same page after recording payment)

#### Estimates/Quotes
- Create and send estimates
- Convert estimate → job
- Track status (pending/approved/declined)
- Email delivery

#### Equipment Tracking (Kleanit-specific)
- Track fans/dehumidifiers by unique ID
- **Location tracking** (which customer site)
- Check-in/check-out system
- Last used date/location
- Equipment history reports
- Alert for overdue returns
- **Critical equipment**: $4.5k dehumidifiers, $400+ fans, dozens of units

#### Mobile App (Technicians)
- View assigned jobs
- Navigate to job sites (Google/Apple Maps button)
- Modify invoices (add-ons, changes)
- **Upload photos FAST** (2-5 seconds target vs 30 seconds now)
- Collect payments in field
- **Site maps storage** (apartment complex layouts)
- **Document library** (training manuals, color charts, cheat sheets)
- Update job status
- **Offline-first architecture** (works without internet, syncs later)

#### Mobile App (Managers)
- See all techs' jobs
- GPS locations of techs
- **Drag-and-drop reassign jobs**
- Calendar view optimized for management
- Different interface than tech view

#### Reporting
- AR aging reports (already built ✅)
- Tax reports (already built ✅)
- Equipment tracking reports
- Revenue by company/tech/date range
- Job completion metrics
- Custom report builder
- **AI-assisted report generation** (describe in plain English)

#### Search
- Universal search across customers/jobs/invoices
- **Unit number search** (apartment-specific)
- Fast 2-year history access
- Tag-based filtering
- Fuzzy matching for typos

#### Communication
- Email invoices/estimates
- Appointment reminders (SMS/email)
- Basic customer communication

---

### ❌ NOT NEEDED - Cut Entirely

- Customer portal (self-service)
- Marketing automation
- Traditional inventory management
- Payment processing integration (initially)
- QuickBooks integration (pending bookkeeper confirmation)
- Clock in/out (techs paid by job)
- Complex routing optimization

---

## 🤖 AI Feature Integration

**Philosophy**: AI should be **invisible** - just makes things work better. No Clippy-style interruptions.

### High Priority AI Features

**1. Smart Duplicate Detection** 🔥
- Fuzzy matching for unit numbers
- Catches: "304" vs "Unit 304" vs "Apt #304" vs "Camdan" (typo)
- 95% confidence threshold for warnings
- Prevents double-bookings automatically

**2. Natural Language Reporting** 🔥
- "Show me how much each tech made last month excluding estimates"
- Self-hosted Llama 3 (no data leaves server)
- Generates SQL, shows results
- < 2 second response time

**3. Invoice Text Cleanup** 🔥
- Auto-correct: "crpet clening 2 roms" → "Carpet Cleaning - 2 Rooms"
- Suggest prices based on historical data
- Standardize formatting across office staff entries
- **Critical pain point**: Inconsistent job description formatting

**4. Customer Communication Assistant** 🔥
- Input loose information → Professional email
- Scan incoming emails/texts → Suggest scheduling
- Clean grammar, professional tone
- Human reviews before sending

### Medium Priority AI Features

**5. Smart Job Assignment**
- Suggest tech based on:
  - Recent jobs at same property (familiarity)
  - Current GPS location (proximity)
  - Tech specialty (carpet vs tile)
  - Current schedule availability
  - Historical performance
- **Office staff use** (managers review day before)
- Errors okay, will be caught in review

**6. Equipment Return Predictions** (Kleanit-specific)
- Monitor checkout dates
- Day 3: Suggest scheduling pickup
- Day 5: OVERDUE alert with tech name
- Pattern detection: "Mike frequently forgets - auto-remind 24hrs before"

### Lower Priority AI Features

**7. Schedule Optimization**
- Analyze tech locations, drive times, durations, skills
- **Request-based, not suggestion-based**
- Managers use on demand (not automatic)
- "Move John's 2pm to 10am, saves 45min drive time"

**8. Voice-to-Job Creation** (Future)
- Transcribe phone calls → Draft job
- Office staff reviews and confirms
- 3 seconds vs 2 minutes typing

### AI Implementation Notes
- Self-hosted Llama 3 (no cloud dependency)
- No data leaves server
- Fast (< 2 seconds)
- No chatbot interface
- No autonomous decision-making
- AI suggests, humans decide

---

## 🏗️ Technical Architecture

### Backend
- **Python + FastAPI** (upgrade from Flask)
- **PostgreSQL** with proper indexing
- **Redis** for caching (calendar performance)
- **WebSockets** for real-time updates

### Frontend
- **React** (smooth calendar interactions)
- **TanStack Query** (data management)
- **DnD Kit** (drag-and-drop)
- **Tailwind CSS** (consistent branding)

### Mobile
- **React Native** (iOS + Android single codebase)
- **Offline-first architecture**
- **Client-side image compression**
- **Progressive upload with retry**

### Photo Storage
- **Self-hosted MinIO** or **Cloudflare R2**
- Client-side compression (4MB → 200KB)
- Thumbnail generation
- CDN for fast delivery

### Real-time Features
- WebSocket server for calendar updates
- GPS polling (every 5min when job active)
- Live schedule changes across devices

---

## 🚀 Development Phases

### **Phase 0: Calendar Prototype (2-3 weeks) - START HERE**
**Goal**: Visual proof-of-concept for business partner

**Features**:
- Drag-and-drop jobs between time slots
- Drag-and-drop between technicians
- Visual feedback (ghost image, drop zones)
- 60fps smooth animations
- Fake data (no backend yet)
- Day/Week view toggle
- Responsive (tablet/desktop)

**Deliverable**: Slick demo that feels like real product

**Success**: Business partner convinced this is achievable

---

### **Phase 1: Foundation (2-3 months)**
**Goal**: Basic job management + calendar

**Features**:
- Customer database
- Job creation/management
- Calendar with backend (save changes)
- Invoice generation
- Import ServiceFusion data
- Single-user testing (Chris + Michele)

**Deliverable**: Michele can create and schedule jobs

**Testing**: Alpha (Chris + Michele only, parallel with ServiceFusion)

---

### **Phase 2: Mobile MVP (2-3 months)**
**Goal**: Techs can use in field

**Features**:
- Mobile app (iOS + Android)
- Photo upload (OPTIMIZED 2-5 seconds)
- View assigned jobs
- Update job status
- Basic invoice modifications
- Maps integration
- Offline-first architecture

**Deliverable**: One tech tests in production

**Testing**: Alpha expands (Chris + Michele + 1 test tech)

---

### **Phase 3: Real-time + Multi-user (1-2 months)**
**Goal**: Full office + field team simultaneously

**Features**:
- WebSocket real-time updates
- Multiple users editing schedule
- GPS tracking
- Manager mobile features
- Duplicate job detection
- Equipment tracking system
- Smart duplicate detection AI

**Deliverable**: Get a Grip runs entirely on new system

**Testing**: Beta (all Get a Grip staff, parallel with ServiceFusion)

---

### **Phase 4: Communication + Polish (1-2 months)**
**Goal**: Customer-facing features

**Features**:
- Email invoices/estimates
- SMS reminders
- Payment collection in field
- Reporting enhancements
- Document library for techs
- Site maps storage
- Invoice text cleanup AI

**Deliverable**: Get a Grip 100% migrated, ServiceFusion cancelled

**Testing**: Production (Get a Grip only)

---

### **Phase 5: Rollout to All Companies (2-3 months)**
**Goal**: All 4 companies migrated

**Rollout Order**:
1. Get a Grip (complete in Phase 4)
2. Kleanit Charlotte (2 weeks stabilization)
3. CTS of Raleigh (2 weeks stabilization)
4. Kleanit South Florida (2 weeks stabilization)

**Testing**: Staged production rollout

---

### **Phase 6: AI & Advanced Features (Ongoing)**
**Goal**: Competitive advantages

**Features**:
- Natural language reporting AI
- Customer communication assistant AI
- Smart job assignment AI
- Equipment return predictions AI
- Schedule optimization AI
- Predictive maintenance

---

## 🛡️ Reliability Architecture

**Critical Requirement**: 20-30 people's livelihoods depend on this system.

### Offline-First Mobile App
- Tech's phone stores today's jobs + next 2 days
- Works without internet
- Photos queue and upload when online
- All critical features work offline

### Database Replication
- Primary: ubuntu1
- Backup: Second server or cloud VPS
- Real-time replication
- < 30 second failover
- No data loss

### Multiple Redundant Endpoints
```
App tries:
1. Primary server (ubuntu1)
2. Backup server (cloud VPS)
3. Read-only mode (local cache)
```

### Monitoring & Alerts
- Server health checks every 60 seconds
- Text alert if down > 2 minutes
- Database slow > 5 seconds → Alert
- Photo uploads failing → Alert

### Graceful Degradation
**If backend down**:
- ✅ Techs see jobs (cached)
- ✅ Techs take photos (queued)
- ✅ Techs navigate (maps cached)
- ✅ Office sees today's schedule (cached)
- ❌ Can't create NEW jobs
- ❌ No real-time updates

### Backup Strategy
- Full database backup nightly (3am)
- 30 days retention
- Offsite storage (Backblaze B2 - $6/month)
- Real-time replication to backup server
- Zero data loss even if primary explodes
- Test restore monthly

### Staged Rollout Risk Management
```
Week 1: Just Chris (alpha)
Week 2: Chris + Michele
Week 4: Get a Grip managers
Week 6: Get a Grip all techs
Week 10: Kleanit Charlotte
Week 14: CTS
Week 18: Kleanit FL
```

**Escape hatch**: Can switch back to ServiceFusion anytime

**Conservative approach**: 6+ months parallel operation is FINE

---

## 💰 Cost Analysis

### ServiceFusion Current Cost
- $1,500/month × 12 = $18,000/year
- Michele's time fixing QB sync: 10hrs/week × 50 weeks × $50/hr = $25,000/year
- **Total: ~$43,000/year**

### Self-Hosted FSM Cost
- Server (ubuntu1): $0 (already have)
- Development: Chris's time + Claude
- Hosting/storage: ~$50/month = $600/year
- **Total Savings: ~$42,400/year**

### ROI
- Development: 6 months
- Break even: ~4 months of operation
- Year 1 net savings: ~$28,000
- Year 2+ savings: ~$42,000/year

---

## 📊 Key Metrics & Goals

### Performance Targets
- **Calendar**: 60fps drag operations, < 100ms response
- **Photo Upload**: 2-5 seconds (vs 30s in ServiceFusion)
- **Search**: < 1 second for 2-year history
- **Page Load**: < 2 seconds
- **Mobile Sync**: < 10 seconds

### Reliability Targets
- **Uptime**: 99.9% (< 9 hours downtime/year)
- **Data Loss**: Zero tolerance
- **Recovery Time**: < 4 hours from disaster
- **Backup Frequency**: Continuous + nightly full

### User Satisfaction Targets
- Michele: "Faster than ServiceFusion"
- Techs: "Easier than ServiceFusion"
- Managers: "Better visibility than ServiceFusion"
- Partner: "Confident in system stability"

---

## 🎯 Next Immediate Steps

### This Week: Calendar Prototype
1. Set up React development environment
2. Install DnD Kit and dependencies
3. Build basic calendar grid
4. Implement drag-and-drop
5. Add smooth animations
6. Create demo with fake data
7. Show business partner

### Next Week: Hardware Documentation
1. Document hardware plan on GitHub
2. Finalize server specifications
3. Price out components
4. Order long-lead items

### Ongoing: Feature Specification
1. Detailed workflow documentation
2. Screenshot existing ServiceFusion workflows
3. Map out data relationships
4. Define API endpoints
5. Design database schema

---

## 📝 Important Design Principles

### "Sticky Details" Philosophy
- Capture every frustration with current system
- Optimize every click
- "Michele's payment page" problem - stay on same page
- Build for YOUR workflows, not universal workflows

### Calendar Must Feel Like "Video Game"
- 60fps animations
- Optimistic updates
- Collision detection
- Snap-to-grid
- Keyboard shortcuts
- Undo/redo (Ctrl+Z)
- Virtual scrolling (200 jobs render instantly)

### Mobile-First for Field Features
- Photo upload is #1 priority
- Offline-first always
- Large touch targets
- Works in bright sunlight
- Fast with poor cell signal

### No Overproduction Risk
- Small errors okay (managers review)
- Big errors costly
- Conservative approach
- Parallel operation for months
- Test everything thoroughly

---

## 🤝 Team & Roles

### Chris (Developer/Owner)
- 5+ hours/week minimum
- Winter/spring: More time
- Summer: Less time (busier season)
- Hands-on development
- Alpha/beta testing in field

### Michele (AR/Primary Office User)
- Alpha tester
- Payment workflow expert
- UX feedback
- Data quality validation

### Business Partner (Decision Maker)
- Money guy, efficiency focused
- Zero technical background
- Needs visual proof (calendar demo)
- Approval for hardware investment

### Get a Grip Techs (Beta Testers)
- Field testing
- Mobile app feedback
- Real-world usage patterns

---

## 📚 Resources & References

### Documentation Location
- GitHub: github.com/chrisletize/fsm-system
- Hardware Plan: docs/DEPLOYMENT/hardware-plan.md
- Session Notes: docs/PROJECT-KNOWLEDGE/
- Feature Specs: docs/FEATURES/

### Key Technologies
- React: https://react.dev
- React Native: https://reactnative.dev
- FastAPI: https://fastapi.tiangolo.com
- DnD Kit: https://dndkit.com
- PostgreSQL: https://postgresql.org
- Llama 3: https://llama.meta.com

---

**Last Updated**: 2026-01-28
**Status**: Planning Complete, Ready to Start Calendar Prototype
**Next Session**: Begin calendar prototype development
