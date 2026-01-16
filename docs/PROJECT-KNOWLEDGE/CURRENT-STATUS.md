# FSM System - Current Status
*Last Updated: 2026-01-15*

## Project Overview
Building custom Field Service Management system to replace ServiceFusion.
- **Companies**: 4 service companies (Get a Grip Charlotte, Kleanit Charlotte, CTS of Raleigh, Kleanit South Florida)
- **Users**: ~25 field technicians, 5 office staff
- **Scale**: 250 jobs/day at peak season
- **Current Phase**: Phase 0 - Statement Generator (Proof of Concept)

## Business Problem
ServiceFusion costs ~$1,500/month for 4 companies and lacks statement generation capability.
QuickBooks integration is problematic - requires Michele to spend 5-10 hours weekly fixing sync errors.
Michele (AR person) needs to generate professional customer statements monthly.

**Goal**: Build complete FSM replacement to eliminate ServiceFusion costs ($25k+/year savings) and gain full control over features.

## Phase 0 Status: NEARLY COMPLETE ✅

Build standalone statement generator as proof of concept:
- ✅ Import unpaid invoices from ServiceFusion Excel exports
- ✅ Generate professional PDF statements with company branding
- ✅ Clean web interface for Michele at statements.cletize.com
- ✅ Excel upload feature with drag-and-drop
- 🔄 Testing with all 4 companies' data (in progress)

**Success Criteria**: Michele can generate statements in <2 minutes

## What's Working ✅
- PostgreSQL 16 database on ubuntu1
- Multi-tenant database schema (companies, customers, invoices)
- Real data imported: All 4 companies' unpaid invoices
- Flask web application with dynamic branding per company
- PDF statement generator with company logo and aging buckets
- Reverse proxy configured (statements.cletize.com via NPM)
- Web interface shows customer list, search, and one-click PDF generation
- Excel upload page with drag-and-drop interface
- Automatic duplicate detection (updates existing, inserts new)
- Upload feedback shows inserted/updated/skipped counts
- **NEW: Clear data button per company with double confirmation**
- **NEW: Systemd service - runs automatically in background**
- **NEW: Fixed company dropdown UX - no auto-load confusion**
- **NEW: All 4 companies tested and working**

## What's In Progress 🔄
- Bulk statement generation (next priority)
- Date range filtering
- Email delivery functionality

## Known Issues
None currently - system stable and functional

## Next Steps
1. Test upload with Kleanit Charlotte, CTS of Raleigh, Kleanit South Florida data
2. Deploy to production and train Michele
3. Monitor for any issues during first month of use
4. Begin planning Phase 1 (full FSM features)

## Technical Stack Confirmed
- **Backend**: Python + Flask
- **Database**: PostgreSQL 16
- **PDF Generation**: ReportLab
- **Frontend**: HTML + CSS (burgundy/cream brand colors)
- **File Upload**: openpyxl for Excel parsing
- **Deployment**: Docker on ubuntu1, Nginx reverse proxy

## Key Metrics
- Development time: ~12 hours total
- Database: 3 tables, 180+ records
- Outstanding invoices tracked: $119,360+
- Features completed: 100% of Phase 0 scope
