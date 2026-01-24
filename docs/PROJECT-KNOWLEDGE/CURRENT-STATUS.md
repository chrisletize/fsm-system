# FSM System - Current Status
*Last Updated: 2026-01-19*

## Project Overview
Building custom Field Service Management system to replace ServiceFusion.
- **Companies**: 4 service companies (Get a Grip Charlotte, Kleanit Charlotte, CTS of Raleigh, Kleanit South Florida)
- **Users**: ~25 field technicians, 5 office staff
- **Scale**: 250 jobs/day at peak season
- **Current Phase**: Phase 0 - Statement Generator (Proof of Concept) + Tax Reporting

## Business Problem
ServiceFusion costs ~$1,500/month for 4 companies and lacks statement generation capability.
QuickBooks integration is problematic - requires Michele to spend 5-10 hours weekly fixing sync errors.
Michele (AR person) needs to generate professional customer statements monthly AND tax reports for compliance.

**Goal**: Build complete FSM replacement to eliminate ServiceFusion costs ($25k+/year savings) and gain full control over features.

## Phase 0 Status: STATEMENT GENERATOR COMPLETE ✅

Statement generator is production-ready:
- ✅ Import invoices from ServiceFusion Excel exports (all companies)
- ✅ Auto-split Kleanit customers (*FL* → South Florida, others → Charlotte)
- ✅ Generate professional PDF statements with company branding
- ✅ Clean web interface at statements.cletize.com
- ✅ Excel upload with drag-and-drop
- ✅ Dynamic branding (4 companies + LKit default state)
- ✅ Clear data feature per company

**Success Criteria**: Michele can generate statements in <2 minutes ✅ ACHIEVED

## Phase 0.5: Tax Reporting - COMPLETE ✅

Tax report system is production-ready:
- ✅ Import ServiceFusion Tax Report + Transaction Report
- ✅ Match invoices by Job# to payment dates
- ✅ Display breakdown by county and tax rate (NC state vs county)
- ✅ Company-specific data persistence
- ✅ Helpful button feedback for missing requirements
- ✅ Professional help modal with instructions

**Known Issue**: Kleanit FL batch statement ZIP files empty (fix next session)

**Success Criteria**: Michele can file monthly tax returns in <30 minutes ✅ ACHIEVED

## What's Working ✅
- PostgreSQL 16 database on ubuntu1
- Multi-tenant schema (companies, customers, invoices)
- Real data: 1,169 invoices across 4 companies
- Flask web application with systemd service
- PDF statement generator with dynamic branding
- Reverse proxy (statements.cletize.com)
- Excel upload with duplicate detection
- **Auto-split: Kleanit Charlotte (1,138 customers) + Kleanit FL (202 customers)**
- **LKit branding for "no selection" state**
- **Import paid + unpaid invoices (statements use unpaid, tax uses paid)**
- **Tax data fields in database (awaiting tax report import)**
- ✅ Batch statement generation (ZIP download)

## What's In Progress 🔄
- Email delivery functionality (NEXT PRIORITY)
- Batch email functionality

## Known Issues
None - system stable

## Next Steps
1. Build tax report page with ServiceFusion Tax Report import
2. Implement batch PDF generation
3. Add email functionality
4. Get Michele's feedback after 1 month of use
5. Begin planning Phase 1 (full FSM features)

## Technical Stack
- **Backend**: Python + Flask
- **Database**: PostgreSQL 16
- **PDF Generation**: ReportLab
- **Frontend**: HTML + CSS + JavaScript
- **File Upload**: openpyxl for Excel parsing
- **Deployment**: Systemd service on ubuntu1, Nginx reverse proxy

## Key Metrics
- Development time: ~16 hours total
- Database: 3 tables, 1,340+ customer records
- Outstanding AR: $230,053.28 (across all companies)
- Features completed: 100% of Phase 0 scope
- Tax data ready: 108 paid invoices with tax fields

## Company Breakdown
- **Kleanit Charlotte** (ID 1): 1,138 customers, $194,994.28 outstanding
- **Get a Grip Charlotte** (ID 2): Data ready for import
- **CTS of Raleigh** (ID 3): Data ready for import  
- **Kleanit South Florida** (ID 4): 202 customers, $35,059.00 outstanding

## Tax Report PDF Generation - COMPLETE ✅

Tax reports can now be downloaded as professional PDFs:
- Executive summary with tax breakdown
- County-by-county details
- Customer tax totals
- Company branding
- B&W print-optimized

**Critical Bug Fixed**: State vs county tax calculation now uses proportions instead of flat percentages, eliminating negative county tax values.
