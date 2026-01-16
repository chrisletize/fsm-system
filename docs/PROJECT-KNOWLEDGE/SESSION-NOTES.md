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
---

## Session 2 - Excel Upload Feature (2026-01-15)

### What We Built
1. **Upload Page** (`/upload`)
   - Drag-and-drop interface for Excel files
   - Company selector dropdown
   - File validation (xlsx/xls only)
   - Upload progress feedback
   - Instructions for exporting from ServiceFusion

2. **Backend Upload Handler**
   - `/api/upload` endpoint
   - Parses ServiceFusion Excel format correctly
   - Handles ServiceFusion's quirky format (row 6 = headers, data starts row 7)
   - Smart duplicate detection by invoice number
   - Creates new customers automatically
   - Updates existing invoices when re-importing

3. **Import Logic**
   - Reads Excel column mapping dynamically
   - Skips paid invoices (amount_due = 0)
   - Returns stats: inserted, updated, skipped, errors
   - Transaction-based (all or nothing on errors)

### Technical Decisions
- Used openpyxl for Excel parsing (already installed)
- Upload to /tmp/uploads then delete after processing
- 16MB file size limit (plenty for invoice exports)
- Column mapping by header name (flexible if SF changes format)

### Challenges Solved
1. **Flask 404 on /upload route**
   - Problem: Route defined AFTER `if __name__ == '__main__'` block
   - Solution: Moved routes before the main block

2. **ServiceFusion Excel Format**
   - Rows 1-5 are metadata/headers
   - Row 6 contains actual column names
   - Data starts at row 7
   - 42 columns total

3. **Database Schema Mismatch**
   - Original code used wrong column names (customer_id vs id)
   - Fixed to match actual database schema
   - Used correct column names for all queries

### Files Modified
- `backend/api/app.py` - Added upload routes and import function
- `backend/api/templates/upload.html` - New file
- `backend/api/templates/index.html` - Added upload button

### Testing Results
- ✅ Successfully imported 180 invoices
- ✅ Duplicate detection working
- ✅ Customer auto-creation working
- ✅ UI feedback clear and helpful
- ✅ Error handling robust

### Time Spent
~4 hours (including debugging route issues)

### Next Steps
1. Test with other 3 companies' data
2. Show Michele the system
3. Deploy to production
4. Begin Phase 1 planning
