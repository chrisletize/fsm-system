# Session Notes

## 2026-01-14: Session 1 - Initial Setup

### What We Did
- Created GitHub repository: fsm-system
- Set up GitHub Projects board with 6 sprint cards
- Created directory structure for backend, frontend, database, docs
- Wrote initial PROJECT-KNOWLEDGE documentation files

### Decisions Made
- Using GitHub for version control (cloud-hosted)
- Private repository to keep code secure
- Living documentation approach for context management
- Starting with Statement Generator as Phase 0

### Technical Setup
- Repository structure created
- Documentation framework established
- Ready for development environment setup

### Action Items for Chris
- [ ] Export unpaid invoices from ServiceFusion (all 4 companies)
  - Navigate to: Reports → Custom Reports → Invoice Report
  - Filter: Payment Status = "Unpaid"
  - Select all columns
  - Export to Excel
  - Save files with clear names (e.g., company-a-unpaid-invoices.xlsx)
- [ ] Schedule Session 2 when data is ready

### Next Session Goals
1. Review exported ServiceFusion data
2. Set up PostgreSQL database
3. Design initial schema
4. Start building import script

### Time Spent
~1 hour

### Mood Check
✅ Good start! Foundation is laid, ready to build.

## Company Structure Reference

### Company 1: Kleanit Charlotte
- Type: Carpet Cleaning
- Location: Charlotte, NC
- Notes: Original company, not franchised

### Company 2: Get a Grip Resurfacing of Charlotte
- Type: Surface Resurfacing
- Location: Charlotte, NC
- Notes: Chris runs this company

### Company 3: CTS of Raleigh
- Type: Umbrella Company
- Location: Raleigh, NC
- Services: Get a Grip franchise + Kleanit carpet cleaning

### Company 4: Kleanit South Florida
- Type: Carpet Cleaning
- Location: South Florida
- Notes: Second Kleanit location (not franchised)

**Total**: 4 companies sharing ServiceFusion infrastructure
**Billing**: Each company on Plus tier (~$382/month each)
