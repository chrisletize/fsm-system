# Session Notes - February 21, 2026

## Session Overview
Bug fixes and feature additions across statement generator, tax report, and recency report.

---

## Bug Fix: Company Dropdown "Loading Companies" — Statement Generator & Recency Report

### Problem
Company dropdowns on index.html and recency_report.html showed "Loading companies..." permanently and never populated. upload.html had already been fixed previously.

### Root Cause
The `/api/companies` endpoint returns `{ "companies": [...] }` — a wrapper object. The frontend JavaScript was doing:
```javascript
const companies = await response.json();
companies.forEach(...)  // or companies.map(...)
```
This treated the whole object as the array. When `.map()` or `.forEach()` was called on an object instead of an array, it threw `TypeError: companies.map is not a function`, which the catch block swallowed silently, leaving the dropdown stuck on "Loading companies...".

### Fix
**index.html line ~542:**
```javascript
// Before
const companies = await response.json();

// After
const data = await response.json();
const companies = data.companies;
```
Same fix applied to upload.html previously. recency_report.html already used `data.companies.forEach()` correctly so did not need changes.

---

## Feature: Transit Tax on Tax Report

### Background
NC counties Mecklenburg, Wake, Durham, and Orange have a 0.5% transit tax on top of state + county tax. Previously the tax report only showed state and county splits, lumping transit into county.

### Changes — tax_processor.py
- Removed manual proportion math (NC_STATE_RATE = 4.75 approach)
- Added import: `from nc_tax_rates import get_tax_breakdown`
- Now calls `get_tax_breakdown(county_name, total_tax_collected)` which uses the NC_COUNTY_TAX_RATES lookup table for precise state/county/transit splits
- Added `transit_tax` field to each county in counties_list
- Added `total_transit_tax` accumulator to totals
- Returns `transit_tax` in both per-county data and overall totals

### Changes — tax-report.html
- County banner breakdown line now shows transit conditionally:
  `State: $X | County: $X | Transit: $X` (transit only shown when > 0)
- County banner right side now shows taxable sales above total tax:
  `Taxable Sales: $X` / `Tax: $X`
- Summary cards: added Transit Tax card that appears only when transit_tax > 0
- `updateSummary()` function updated to show/hide transit card dynamically

### Changes — generate_pdf_tax_report.py (scripts/)
- Executive Summary table: transit tax row added conditionally (only when > 0)
- County header breakdown line: transit shown conditionally, taxable sales added
- Both the backend/api copy and scripts/ copy updated identically

### Bug: Missing Import
After first restart, got `Error: name 'get_tax_breakdown' is not defined` popup. Fix was adding the import line to tax_processor.py — it was calling the function without importing it.

---

## Feature: Recency Report Days-Since Cache Fix

### Problem
Days since last service was potentially showing stale numbers if a report was generated, cached, and viewed later — the cached HTML had baked-in day counts from when it was first generated.

### Fix
Added `reportCache = {};` as the first line inside the Generate Report button click handler. This clears all cached reports before generating, ensuring the API is always called fresh and PostgreSQL's `CURRENT_DATE` reflects the actual current date.

### Confirmed Working
The backend query already used `CURRENT_DATE - MAX(jd.job_date) as days_since` which is evaluated dynamically by PostgreSQL at query time. The cache was the only obstacle.

---

## Feature: Recency Report Upload Validation

### Problem
No protection against uploading the wrong company's report. Uploading a Get a Grip report into Kleanit would silently create wrong customers with wrong job dates, no warning given.

### Solution: Pre-Upload Validation Endpoint
New route: `POST /api/recency/validate`

Logic:
- Reads file without saving to database
- Scans `Service Location State` column against allowed states per company:
  - Company 1 (Kleanit Charlotte): NC, SC, FL allowed (FL auto-routes correctly)
  - Company 2 (Get a Grip): NC, SC allowed
  - Company 3 (CTS of Raleigh): NC only — strict, CTS is exclusively Raleigh area
  - Company 4 (Kleanit South Florida): FL only
- Checks customer name match rate against existing customers in selected company
- If < 20% of file's customers match existing customers, flags as likely wrong company
- Returns warnings array + summary stats (total rows, unique customers, match rate)

### Frontend Flow
Upload button now calls `validateThenUpload(files)` instead of directly uploading:
1. Sends file to `/api/recency/validate`
2. If no warnings → proceeds directly to upload
3. If warnings → shows modal with warning details and match rate summary
4. Modal has Cancel and Upload Anyway buttons
5. `doUpload()` extracted as separate function, called by both paths

### ServiceFusion Report Columns Available
Examined actual SF Customer Revenue Report — contains 37 columns including:
`Customer, Parent Customer, Service Location Address 1, Service Location City, Service Location State, Service Location Zip, Job#, Date, Status, Total, Tech(s) Assigned` and more. The `Service Location State` column was key for validation (values can be full name "Florida" or abbreviation "FL" — both handled).

---

## Feature: Recency Report Batch Data Manager

### Problem
No way to undo an accidental upload or remove a specific batch of bad data without wiping everything.

### Solution: Three New Backend Routes

**GET `/api/recency/batches/<company_id>`**
Groups `customer_job_dates` records by `DATE_TRUNC('minute', created_at)` and returns batches with record count, earliest job date, and latest job date.

**POST `/api/recency/clear-batch`**
Accepts company_id + batch_time, deletes all job date records matching that company and that minute-truncated timestamp.

**These join through customers table** to filter by company_id since customer_job_dates only has customer_id, not company_id directly.

### Frontend
- Added "🗂️ Manage Data" button next to Upload and Generate buttons
- Button hidden until company is selected (shown in loadStats() success and else blocks)
- Opens modal listing all upload batches with:
  - Upload timestamp (human readable)
  - Record count
  - Job date range (earliest – latest job dates in that batch)
  - Delete button per batch
- Delete prompts confirmation, then calls clear-batch endpoint, refreshes batch list and stats banner

---

## Working Pattern Established This Session
See DEVELOPMENT_WORKFLOW.md for the documented approach to use going forward.

---

## Files Modified
- `~/fsm-system/backend/api/app.py` — validate, batches, clear-batch routes; get_tax_breakdown import in tax_processor.py
- `~/fsm-system/backend/api/tax_processor.py` — transit tax calculation overhaul
- `~/fsm-system/backend/api/templates/index.html` — companies dropdown fix
- `~/fsm-system/backend/api/templates/tax-report.html` — transit tax display, taxable sales, transit summary card
- `~/fsm-system/backend/api/templates/recency_report.html` — cache clear fix, validation flow, manage data modal
- `~/fsm-system/scripts/generate_pdf_tax_report.py` — transit tax and taxable sales in PDF

## Service Restart Command
```bash
sudo systemctl restart fsm-statements
```
