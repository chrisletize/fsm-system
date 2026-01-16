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
---

## Session 3 - Dynamic Branding & Multi-Company Support (2026-01-16)

### What We Built

1. **Company Branding System**
   - Created `backend/api/branding.py` with color schemes for all 4 companies
   - Get a Grip: Burgundy (#8B1538) + Cream (#F5F5DC)
   - Kleanit (Charlotte & South Florida): Blue (#0052CC) + Green (#00D66C)
   - CTS of Raleigh: Dark Gray (#2C2C2C) + Cream (#F5F5DC)
   - Added `/api/branding/<company_id>` endpoint

2. **Dynamic Web Interface**
   - Main page changes colors/logo when company selected
   - Upload page changes colors/logo when company selected
   - Uses CSS variables for dynamic color switching
   - Smooth transitions between color schemes
   - Company display names distinguish between Kleanit Charlotte and South Florida

3. **Logo Management**
   - Added all company logos to `assets/` and `backend/api/static/`
   - get-a-grip-logo.jpg
   - kleanit-logo.png
   - cts-logo.jpg

4. **PDF Dynamic Branding** (In Progress)
   - Updated `generate_pdf_statement.py` to use dynamic branding
   - Imports branding config
   - Sets colors and logo based on company_id
   - Fixed logo path to use absolute paths

### Technical Challenges

1. **JavaScript fetch() syntax issue**
   - Problem: Backticks appearing outside parentheses: `fetch`/api/...`)`
   - Solution: Used sed to fix: `sed -i "s/fetch\`/fetch(\`/g"`
   - Occurred in both index.html and upload.html

2. **Company dropdown not refreshing summary**
   - Problem: API calls had syntax errors, summary boxes showed stale data
   - Solution: Fixed fetch syntax, added proper company_id parameter

3. **Upload functionality breaking**
   - Problem: Database column mismatch `service_location_address` vs `service_location_address_1`
   - Status: IN PROGRESS - debugging import errors

### Files Modified

- `backend/api/branding.py` - NEW
- `backend/api/app.py` - Added branding endpoint, fixed summary handling
- `backend/api/templates/index.html` - Dynamic CSS variables, branding loader
- `backend/api/templates/upload.html` - Dynamic CSS variables, branding loader
- `scripts/generate_pdf_statement.py` - Dynamic branding support
- `assets/` - Added kleanit-logo.png, cts-logo.jpg

### Current Status

**Working:**
- ✅ Dynamic branding on main page
- ✅ Dynamic branding on upload page  
- ✅ All 4 company color schemes configured
- ✅ Logo switching works
- ✅ Company dropdown updates properly

**In Progress:**
- 🔄 Excel upload debugging for Kleanit/CTS data
- 🔄 PDF generation with dynamic branding (code written, needs testing)

**Blocked:**
- Upload import failing with cryptic "0" errors on every row
- Need better error logging to diagnose

### Next Session Tasks

1. Fix upload import errors (add detailed error logging)
2. Test PDF generation with all 4 companies
3. Import real data from Kleanit Charlotte, CTS, Kleanit South Florida
4. Build bulk statement generation feature
5. Add date range filter for statements

### Time Spent
~3 hours (branding system, dynamic UI, logo management, debugging)
---

## Session 4 - Excel Upload Debugging & Clear Data Feature (2026-01-16)

### What We Fixed

1. **Excel Upload KeyError Issues**
   - Fixed database query result handling (dictionary vs tuple access)
   - Changed `customer[0]` and `existing[0]` to `customer['id']` and `existing['id']`
   - Added `invoice_status` column to INSERT and UPDATE statements (defaulting to 'Unpaid')
   - All 4 companies can now successfully import invoice data

2. **Setup as System Service**
   - Created `/etc/systemd/system/fsm-statements.service`
   - Flask now runs automatically in background
   - Service starts on boot, restarts on failure
   - Can manage with `sudo systemctl start/stop/restart fsm-statements`

3. **Clear Data Feature**
   - Added "Clear All Data for This Company" button (red trash icon)
   - Double confirmation before deletion
   - Deletes all invoices and customers for selected company
   - Button only appears when company is selected
   - Backend API endpoint: DELETE `/api/clear-company-data/<company_id>`

4. **UX Improvements**
   - Fixed company dropdown behavior - no auto-load on page load
   - Users must explicitly select company before data appears
   - Prevents confusion when dropdown shows different company than loaded data

### Technical Challenges

1. **JavaScript variable naming vs HTML IDs**
   - HTML element ID: `company-select` (with hyphen)
   - JavaScript variable: `companySelect` (camelCase, no hyphen)
   - Find-replace accidentally changed variable names, breaking syntax
   - Learned: only element IDs in quotes should have hyphens

2. **Event listener null reference errors**
   - Added safety checks: `if (element)` before adding listeners
   - Prevents crashes when elements don't exist on page

3. **Browser caching**
   - Hard refresh (Ctrl+Shift+F5) needed after HTML/JS changes
   - Systemd service restart only updates Python backend

### Files Modified

- `backend/api/app.py` - Fixed database queries, added clear-data endpoint
- `backend/api/templates/index.html` - Added clear button HTML and JavaScript
- `/etc/systemd/system/fsm-statements.service` - NEW systemd service file

### Testing Results

- ✅ Get a Grip Charlotte: 180 invoices imported successfully
- ✅ Kleanit Charlotte: Upload working
- ✅ CTS of Raleigh: Upload working
- ✅ Get a Grip Charlotte (re-upload): 22 invoices updated correctly
- ✅ Clear data feature working with double confirmation
- ✅ PDF generation with dynamic branding confirmed working
- ✅ Company dropdown behavior fixed

### Current Status

**Working Features:**
- Multi-company invoice import via Excel
- Dynamic branding (colors/logos) per company
- PDF statement generation
- Clear data functionality
- Systemd background service
- Professional web interface

**Ready for Next Session:**
- Bulk statement generation (generate for all customers at once)
- Date range filter for statements
- Email statements directly to customers
- Additional testing with larger datasets

### Time Spent
~3 hours (debugging, systemd setup, clear data feature, UX fixes)

### Next Session Goals

1. Build bulk statement generation feature
2. Add date range filter
3. Test with Michele's feedback
4. Begin email functionality planning
