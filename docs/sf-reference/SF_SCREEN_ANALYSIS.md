# ServiceFusion Screen Analysis — FieldKit Reference
*Documented: June 9, 2026 | Source: Screenshots reviewed in Claude session*
*Purpose: Functional reference for FieldKit build. Not a pixel-for-pixel copy — adapted and improved.*

---

## How to Use This Document

Each section covers a SF screen we reviewed. For each one:
- **What SF shows** — the data, actions, and layout we observed
- **FieldKit equivalent** — the URL and phase where this gets built
- **FieldKit improvements** — where we do it better
- **Notes** — anything worth remembering at build time

This document is the permanent record so screenshots don't need to be re-shared in future sessions.

---

## SETTINGS SCREENS

---

### Company Information
**SF URL:** `/companyInfo`
**FieldKit equivalent:** `/<company>/settings/company` — Phase 2

**What SF shows:**
- Company Name, Alias, Company ID
- Street Address 1 & 2, City, State, Zip, Country
- Primary/Secondary Phone, Primary/Secondary Email
- Primary/Secondary Contact (name fields)
- EIN/Business Number/License
- Company Logo upload (max 500×300px)
- Company Slogan
- Social Media URLs (Facebook, Twitter, Yelp, Angie's List)
- Modules & Connections (API Key, VoIP settings)
- 10 DLC (existing number, 800 number)

**FieldKit build notes:**
- Core fields: Name, address, phone, email, logo — required for Phase 2
- Social media and VoIP fields: low priority, add later
- API key field not needed (FieldKit is the system, not an integration)
- Logo upload feeds into branded PDF invoices/statements

---

### Company Preferences
**SF URL:** `/companyPreferences`
**FieldKit equivalent:** `/<company>/settings/preferences` — Future (LKit/franchise phase)

**What SF shows:**
- Dozens of toggles: timezone, currency, date/time formats, default payment method,
  default payment terms, tax defaults, invoice numbering, job numbering
- Display options: calendar view, dispatch timeframe, font styles, list sizes
- Copy settings (what gets copied when creating sub-accounts)
- Notification defaults, SMS templates, signature block content
- Rate table column visibility (show/hide rate, qty, total per table type)

**FieldKit build notes:**
- NOT needed for internal 4-company use — values are hardcoded to match current workflow
- Required when offering FieldKit to external franchise customers (LKit phase)
- Each external customer needs their own preferences instance
- Document this now so nothing is forgotten when that phase begins
- Key toggles to eventually support: default payment terms, invoice/job number sequences,
  tax defaults, "mark all customers taxable by default"

---

### Email Settings
**SF URL:** `/companyEmail`
**FieldKit equivalent:** `/<company>/settings/email` — Phase 2

**What SF shows:**
- Default sender address, From/Reply-to address, BCC toggle
- Automated trigger toggles: email customer when job created/modified,
  estimate created/modified, invoice created/modified, payment receipt
- Include PDF copies of all documents toggle
- Always include associated work orders with invoices toggle
- Tech notification toggles (job created/modified confirmations)
- Clock-out reminders, labor time reminders
- Worker app: send to Primary Contact or All Contacts
- SendGrid integration (advanced)

**FieldKit build notes:**
- FieldKit uses Resend API (already configured at noreply@cletize.com)
- Phase 2: build settings page for the trigger toggles (which events send emails)
- Default to: invoice created → yes, payment received → yes, job created → no
  (matches current workflow preference)
- SendGrid not needed — Resend handles this

---

### Manage Workforce (User Management)
**SF URL:** `/companyWorkForce`
**FieldKit equivalent:** `/<company>/settings/users` — Phase 1 remaining task

**What SF shows:**
- Table: Full Name, Title, Department, Phone, Location, Status
- Filter: Active / Inactive / All tabs
- Export: CSV, PDF, Print
- Actions per row: View (magnifier), Edit (pencil)
- "Add New" button top right
- "User Permissions Templates" button

**FieldKit build notes:**
- This is the user management page already planned — build it now (Phase 1 task)
- Columns: Full Name, Role, Company Access, Status, Actions
- Filter: Active/Inactive/All
- Actions: Edit, Reset Password, Deactivate
- Admin only — not visible to manager/salesperson/tech roles
- One page covers all companies (users span companies via company_access jsonb)
- No "User Permissions Templates" needed — roles handle this (admin/manager/salesperson/tech)

---

### Products & Inventory
**SF URL:** `/companyInventory`
**FieldKit equivalent:** `/<company>/settings/catalog` (products sub-section) — Phase 2

**What SF shows:**
- Table: Product Name, Product Category, Model, Type, Quantity On Hand,
  Unit Price, Unit Cost, Member Price
- Left filter panel: Catalog, Category, Name, Description, Price ranges,
  Is Inventory Item toggle, Status
- Batch Edit Selected Products button
- Export, Stock Levels, Reallocate Inventory, Inventory Orders, Inventory Order buttons

**FieldKit build notes:**
- Products used only by CTS and Kleanit for water extraction equipment
- Items visible: Set Armover, Set Compact Dehu, Set Driaz Dehu, Set Large Dehu,
  Set Phoenix Armover, Set Vortex — all Carpet category, $25–$110
- Inventory tracking (Qty On Hand) is a nice-to-have; not blocking Phase 2
- Build products as part of the unified catalog page, filtered by item_type='product'
- Member Price column: not needed for our use case

---

### Services Catalog
**SF URL:** `/companyServices`
**FieldKit equivalent:** `/<company>/settings/catalog` — Phase 2

**What SF shows:**
- Table: Service Name, Service Category, Description, Status, Regular Rate, Internal Cost
- Left filter: Catalog, Category, Name, Description, Task Code, Status,
  Regular Rate range, Internal Cost range, Pays Commission, Pays Bonus,
  Available in Portal/App, Number of Rates
- "New Service" button, Export button
- Batch "Edit Selected Services" button

**Actual services visible (partial list):**
Categories observed: Carpet, Resurfacing, Service, Discount, Fuel Surcharge
- Carpet: 1-4 BR Clean ($60–$75), Additional Stretch ($15), After Hours Water Extraction ($195),
  Apt Stair Cleaning ($10), Clean 1-2 Areas ($89), Clean 10 Areas ($401), etc.
- Resurfacing: Acid Wash ($175), Bathtub Resurface ($275), Bathtub Stripping ($150),
  Bath Countertop Resurface ($95), Surround Resurface ($285), Kitchen Countertop Resurface ($260), etc.
- $0.00 services: callbacks, warranties, admin items (CALLBACK, Cabinet Warranty, etc.)
- Discount category exists for line item discounts

**FieldKit build notes:**
- This is the primary catalog data for Phase 2
- No freeform line items — everything comes from this catalog
- "Custom Service" catch-all replaces freeform (requires description to be filled)
- "Unit Number" is a special catalog item (slots into job description)
- Categories map to our catalog item category field
- $0.00 services confirm we need items with zero price (callbacks, no-charge items)
- "Available in Portal/App" maps to our future public estimate request form
- Internal Cost field supports margin calculation (future feature)

---

### Taxes, Fees & Discounts
**SF URL:** `/companyTaxes`
**FieldKit equivalent:** `/<company>/settings/tax` — Phase 2

**What SF shows:**
- Two tabs: Global Settings, Tax/Discount Items
- Tax items list: Chatham, Discount, Durham, Edgecombe, Franklin, Granville,
  Guilford, Harnett, Johnston, NON TAXABLE, Orange, Vance, Wake
- Each item: Name, Actions (view/edit/delete)

**FieldKit build notes:**
- CTS serves more NC counties than just the 4 transit-tax counties
  (Mecklenburg is Get a Grip; CTS covers Wake, Durham, Orange, Johnston, Harnett, etc.)
- NON TAXABLE as an explicit tax item confirms we need it as a selectable option
  on line items and customers
- Discount as a tax item = SF uses the tax system for discounts too; FieldKit
  should handle discounts as a catalog item type instead (cleaner)
- Transit tax counties (Mecklenburg, Wake, Durham, Orange): NC cash-basis requirement
  already handled in our tax processor
- Build this page with: county list (editable), state base rate (4.75% hardcoded for NC),
  transit tax county toggles

---

### Job Categories
**SF URL:** `/jobCategories`
**FieldKit equivalent:** Replaced by Work Order Tags — Phase 2

**What SF shows:**
- Table: Category Name, Parent Category, Status
- 3 active categories: Kitchen Cabinets, Tile Backsplash, Tile Baseboard

**FieldKit build notes:**
- Confirmed unused in current workflow
- FieldKit replaces single-category with multi-tag system (more flexible)
- Work Order Tags page (`/<company>/settings/tags`) covers this entirely
- No migration needed — these categories have no jobs assigned

---

### Custom Fields
**SF URL:** `/customfields`
**FieldKit equivalent:** `/<company>/settings/fields` — ALREADY BUILT ✅ (customer fields)

**What SF shows:**
- Three sections: Estimate/Job Custom Fields, Customer Custom Fields,
  Equipment Custom Fields
- Each: Type dropdown (Text Input, etc.), Field Label, Default Value, Required checkbox
- Add Another Field link per section

**FieldKit build notes:**
- Customer custom fields already built and working
- Phase 4: extend to job/estimate custom fields
- Equipment custom fields: low priority, add with equipment tracking if needed

---

### Payment Methods
**SF URL:** `/officeSettings/paymentMethods`
**FieldKit equivalent:** `/<company>/settings/payment-methods` — Phase 2

**What SF shows:**
- Table: Payment Method Name, Type, Status
- Active: Cash (CASH), Check (CHECK), Credit Card (CARD), Credit Card Offline (OTHER),
  Direct Bill (BILL), eCheck/ACH (ACH), Other (OTHER)
- Inactive: Donation, Financing, Trade

**FieldKit build notes:**
- Active methods to seed: Cash, Check, Credit Card, ACH/eCheck, Direct Bill, Paymode-X
- Type field maps to our payment_methods table
- "Requires Reference Number" toggle needed for Check (check#) and Paymode (ref#)
- Direct Bill = invoice sent, paid later (most common for commercial customers)

---

### Payment Terms
**SF URL:** `/officeSettings/paymentTerms`
**FieldKit equivalent:** Reference table for invoice due date calculation — Phase 5

**What SF shows:**
- Table: Term Name, Due In Days, Status
- Active: Cash On Delivery (0), Due Upon Receipt (0), NET 15 (15), NET 30 (30), NET 60 (60)
- Inactive: NET 1, NET 7, NET 10, NET 21, NET 45, NET 90, NET 120, NET 180

**FieldKit build notes:**
- Currently payment_terms is a text field on customers defaulting to 'Net 30'
- Phase 5: convert to a proper reference table
- Active terms to seed: COD, Due Upon Receipt, Net 15, Net 30, Net 60
- Due date = invoice_date + due_in_days (used for aging buckets and overdue detection)

---

### Tag Management — Estimate & Job Tags
**SF URL:** `/officeSettings/estimateAndJobTags`
**FieldKit equivalent:** `/<company>/settings/tags` — Phase 2

**What SF shows:**
- Two tabs: Customer Tags, Estimate & Job Tags
- Job tags list: hundreds of unit number tags (01-102, 1-1201, 07-1708, etc.)
  used as a workaround for the lack of a unit number field
- Columns: Tag Name, Used In Estimates, Used In Jobs, Used In Templates

**FieldKit build notes:**
- The unit number tag workaround confirms FieldKit's Unit Number catalog item
  approach is a genuine improvement — no need for unit number tags
- Our work_order_tags table handles this properly
- Starter tag set: Callback, New Customer, Residential, Estimate/No-Charge,
  Misc Task, Water Extraction, Requires Follow-Up
- System auto-tag: Delinquent Account (nightly job)
- Tags show as colored pills on dispatch board job blocks

---

### Estimate & Job Statuses
**SF URL:** `/statuses/index`
**FieldKit equivalent:** `/<company>/settings/statuses` — Phase 2 (configurable in UI)

**What SF shows:**

Job Statuses (with color codes):
- Open Jobs: Unscheduled (yellow-green), Scheduled (blue), Dispatched (dark blue, inactive),
  Delayed (pink, inactive)
- Open Jobs In Progress: On The Way (orange), On Site (yellow-orange), Started (teal),
  Paused (cyan, inactive), Resumed (light blue, inactive), Partially Completed (olive, inactive),
  Completed (purple)
- Open Jobs: Cancelled (dark red)
- Closed Jobs: Job Closed (black), To be invoiced (light green, inactive),
  Invoiced (yellow-green), Paid in Full (dark olive)

Estimate Statuses:
- Estimate Requested (blue), Estimate Provided (green), Estimate Accepted (dark green),
  Lost (gray), Estimate Won (bright green)

**FieldKit build notes:**
- Our planned statuses already match SF's active statuses closely
- Color coding per status is important for dispatch board visibility
- "Allow Manual Job Status Override" checkbox — FieldKit will allow this by default
- Active statuses FieldKit will use:
  Work Orders: Scheduled, On The Way, In Progress, Completed, Invoiced, Cancelled,
  Extraction Active (FieldKit addition), No Charge (FieldKit addition)
- Estimates: Requested, Provided, Accepted, Won, Lost, Converted (FieldKit addition)
- Phase 2: build the settings UI so statuses/colors are configurable
  (important for LKit franchise customers who may want different status names)

---

## OPERATIONAL SCREENS

---

### Customer List
**SF URL:** `/serviceSpot/customersList`
**FieldKit equivalent:** `/<company>/customers` — ALREADY BUILT (needs enhancements)

**What SF shows:**
- Sub-navigation: Customer List, Add New Customer, Service Agreement Management,
  Customer Email Broadcasts
- Left filter panel: Quick Search / Advanced Search, search by name/phone/city/email,
  Show only parent accounts, Show only inactive customers
- Table columns: Customer Name (link, blue), Primary Contact, Phone, Email,
  Service Location, City/State/Prov, Zip/Post Code, Tags (inline badges), Est (count badge),
  Jobs (count badge), Last Service (date)
- Batch actions: Edit Selected, Delete Selected (when rows checked)
- Customer name prefixes visible in data: **OPS**, **VENDOR CAFE**, **VENDOR**,
  **need billing info** — confirms the SF prefix convention used as a tagging workaround

**FieldKit enhancements over SF:**
- Tags shown as proper colored pills (not text badges)
- Last Service date pulled from job history (already planned via recency report data)
- Est and Jobs count badges link to filtered lists
- Billing flag warning for customers with no accepts_billing contact
- Delinquent Account indicator visible on list

**FieldKit gaps to address:**
- Add Last Service date column to customer list
- Add Jobs count badge (clickable → filtered job list)
- Add Estimates count badge
- Add Tags column with colored pills

---

### Customer Edit Page
**SF URL:** `/customer/customerAdd?id=...`
**FieldKit equivalent:** `/<company>/customers/<id>/edit` — ALREADY BUILT (review gaps)

**What SF shows:**

Tabs: Account Info, Financial Data, Service Locations, Equipment, Documents, History, Logs

Account Info tab fields:
- Customer Name, Parent Account (management company), Account Number
- VIP Account toggle, Service Agreement toggle, Active toggle
- Contacts section: search contacts, contact limit selector, Add Another Contact button
- Primary Contact: Prefix, First/Last Name, Suffix, Phone Number (type dropdown),
  Department, Job Title, Email Address (type dropdown)
- Billing Contact checkbox, Booking Contact checkbox
- Birthday, Anniversary date fields
- Web/App Account section (customer portal login)
- Default Document Templates: Estimate Template, Job/Work Order Template, Invoice Template
- Additional Information: Internal/Private Notes, Customer Tags, Referral Source, Industry,
  Assigned Contract, Taxable toggle, Tax Item dropdown, Default Currency,
  Business Number/Tax ID, Assigned Agent/Rep + Commission fields
- Public/Work Order Notes (separate from internal notes)
- Bottom buttons: Delete, **Merge**, Save Customer Account

Right sidebar — Activity Feed:
- Chronological log of all customer activity
- Events shown: Invoice Payment received (with invoice#), Invoice email sent
  (from/to addresses), Invoice detail with email content preview (expandable),
  Job invoiced, Email sent, New Job created
- Each event: timestamp, event type icon, brief description, expandable content

**FieldKit gaps to address:**
- Activity Feed on customer detail — currently we have notes but not a true
  event log pulling in job/invoice/payment events. Add to Phase 5 plan.
- Public/Work Order Notes field (separate from Internal Notes) — add to customer schema
- Referral Source field — add to customer schema
- Assigned Agent/Rep field — links to salesperson (Chris O workflow, Phase 3)
- History and Logs tabs — Phase 5 (requires job/invoice data to exist)
- Equipment tab — future (not current need)
- Documents tab — future (file attachments per customer)
- Merge button on edit page — confirmed SF has this; FieldKit data quality backlog

---

### Jobs Dashboard
**SF URL:** `/jobs`
**FieldKit equivalent:** `/<company>/jobs` — Phase 4

**What SF shows:**
- Left sidebar with status-grouped folders and counts:
  - My Jobs / My Additional Visits
  - All Open Jobs: All Jobs (252), On The Way (7), Scheduled (119)
  - Additional Site Visits
  - Completed & Ready To Close: Cancelled (488), Completed (73)
  - To Be Invoiced: Job Closed (115)
  - Invoiced: Invoiced (282), Paid in Full (1,391)
  - Closed: Paid in Full (31)
  - "Adjust Status Folder Visibility" link
- Main area: job list filtered by selected status folder
- Table: Job (number/link), City, Customer (link), Priority, Category, Tech(s), Status badge
- Sort by: Date, Job#, City, Created On, Customer, Priority, Category
- Sub-navigation: Jobs Dashboard, Create A Job, Job Templates, Repeating Jobs,
  Batch Edit Jobs, Deleted Jobs

**FieldKit build notes:**
- Status-grouped left sidebar with counts is the right pattern for this page
- Counts give instant business state overview (73 completed not yet invoiced = action needed)
- "My Jobs" section for tech-role users (only see their own)
- Job Templates and Repeating Jobs: Phase 4+ features
- Batch Edit Jobs: useful for mass status updates (data quality backlog item)

---

### Estimates Dashboard
**SF URL:** `/estimate/estimateDashboard`
**FieldKit equivalent:** `/<company>/estimates` — Phase 3

**What SF shows:**
- Left sidebar status folders: My Estimates, All Estimates grouped by status
  (Accepted 1, Provided 65, Requested 23, Won 86, Lost 15)
- Table: Requested On (date + estimate#), Customer (link), Description,
  Value ($), Status badge, In QuickBooks (sync button), Rating
- Sub-navigation: Estimates Dashboard, Create An Estimate, Estimate Templates,
  Deleted Estimates

**FieldKit build notes:**
- Same left-sidebar pattern as jobs
- Rating column: SF lets you rate estimate quality — low priority for FieldKit
- In QuickBooks column: not needed (no QB integration planned)
- Estimate Templates: Phase 3 feature (create reusable estimate structures)

---

### Dispatch Board
**SF URL:** `/dispatch`
**FieldKit equivalent:** `/<company>/dispatch` — Phase 4

**What SF shows:**
- Horizontal grid: tech names + avatar down left, time across top (1am–11pm)
- Job blocks as colored bars spanning their time slot
- Top controls: Today button, date nav arrows, Daily/Weekly toggle,
  12 Hour Grid / 24 Hour Grid toggle, Set Filters button
- Sub-navigation tabs: Dispatch Grid, Dispatch Map (beta), Fleet Tracking,
  Fleet Dashboard 2.0 (beta), Fleet Map
- Bottom tray: status buckets with counts —
  Unscheduled, Unassigned, With Open POs, Partially Completed, Paused, Marked for Follow-Up
- Below tray: filter dropdowns (4 rows of "Nothing select" dropdowns) + Reset button
- Unscheduled job blocks sit in the bottom tray area outside the grid

**Hover popup (on job block):**
- Job number + status badge
- Customer name (link)
- Contact name + phone number
- Service address
- Job description snippet (the auto-generated text from line items)
- "View more details" link

**Detail modal (clicking "View more details"):**

Left panel — action buttons:
- Dispatch, View Details, Make Changes, Deposits, Close & Invoice,
  Cancel This Job, Email, Print, Exit

Center panel — job data:
- Customer (link), Primary Contact (name + phone + email link),
  Service Location (address), Job Description (full auto-generated text),
  PO#, Paid By, Check/Ref#, Terms, Status (with red balance warning if unpaid)

Right panel:
- Google Maps embed of service location
- Current Status badge
- Start & End Dates (editable inline)
- Estimated Duration (editable)
- Arrival Time Window (editable)
- Assigned Techs (editable)
- Notes for Techs (editable)
- Additional Site Visits count

**FieldKit build notes:**
- React/DnD Kit prototype already exists as starting point
- "Close & Invoice" button in modal is a critical workflow shortcut for Michele
- Hover popup should show auto-generated job description — confirms value of that feature
- Bottom tray for unscheduled/unassigned jobs is important for dispatcher workflow
- Fleet Tracking / Map views: future Phase 6 (GPS/mobile)
- Inline editing of dates, duration, arrival window, techs in the modal saves
  full page navigations for quick scheduling changes

---

### Job Edit Form — Line Items Section
**SF URL:** `/jobs/jobsEdit?id=...`
**FieldKit equivalent:** `/<company>/jobs/<id>/edit` (bottom section) — Phase 4

**What SF shows:**
- Billing type tabs: Single Invoice, Progress Billing, No Charge
- Three sub-tabs: Products & Services, Drive & Labor Times, Expenses
- Line items table columns: (drag handle), (checkbox), (S marker), Description field,
  (More button), Warehouse, Qty/Hrs (spinner), × , Rate, = , Total, Cost, Margin %, Tax (county dropdown), Action (⋮)
- Each line item: service name pre-filled in left description, editable description
  in right field, county tax dropdown per line
- Special first line: UNIT# item with "UNIT# 1121 vac" as value
- Tax row at bottom of items: county name + rate + tax amount
- Totals panel (bottom right):
  - Products, Services, Taxes & Fees: $1,683.83
  - Total Drive & Labor Time: $0.00
  - Total Billable Expenses: $0.00
  - Job Total: $1,683.83
  - Payments/Deposits: $0.00
  - Total Due: $1,683.83
  - Job Cost: $0.00
  - Gross Profit (100.00%): $1,570.00
- Note To Customer text box
- Bottom buttons: Exit Without Saving, Save Job (with dropdown arrow)
- Also: Task List, Notes, Reminders sections above line items
- Completion Notes section (top right of visible area) with Requires Follow-up checkbox

**FieldKit build notes:**
- Per-line tax county dropdown is important — different line items could theoretically
  have different counties (edge case, but SF supports it; inherit from service location)
- Progress Billing tab: for large multi-phase jobs (not current need, Phase 5+)
- No Charge billing type maps to our "No Charge" work order status
- Drive & Labor Times tab: time tracking (Phase 4/6 with mobile clock-in)
- Expenses tab: reimbursable expenses (future)
- Gross Profit display: requires cost field populated on catalog items (Phase 2 catalog)
- Task List on work order: minor feature, add in Phase 4
- Reminders on work order: links to our GPS reminder system (Phase 6)
- Requires Follow-up checkbox maps to our "Requires Follow-Up" work order tag

---

### Unpaid Invoices Dashboard
**SF URL:** `/unpaidInvoices`
**FieldKit equivalent:** `/<company>/billing` — PARTIALLY BUILT, Phase 5 full version

**What SF shows:**

Right sidebar aging summary (large colored dollar amounts):
- Grand Total Due of All Unpaid Invoices: $141,978
- Grand Total Due of All Past Due: $141,302
- 91+ Days Past Due: $24,896
- 61-90 Days Past Due: $17,374
- 31-60 Days Past Due: $27,027
- 1-30 Days Past Due: $72,005
- Grand Total Due of All Current Invoices: $676

Tabs: Unpaid Invoices, Paid Invoices, All Invoices, Recurring Invoices
Top actions: Email (batch), Print, PDF

Table columns: Date, Customer (link), Invoice#, PO#, Terms, Status (Current/Past Due badge),
Sent (email indicator icon), Total, Total Due, In QuickBooks (sync), View, Edit

**FieldKit build notes:**
- Right sidebar aging summary with large colored numbers is the most valuable UI pattern
  from this screen — replicate it exactly in our billing page
- Four aging buckets: Current, 1-30, 31-60, 61-90, 91+ (matches our planned buckets)
- "Sent" indicator icon shows whether invoice has been emailed — important for Michele
  to know what's been communicated
- Batch email action from this page — Michele's primary statement-sending workflow
- Recurring Invoices tab: future feature (service agreements, recurring customers)
- "In QuickBooks" column: not needed

---

### Create Invoices
**SF URL:** `/customerJobs`
**FieldKit equivalent:** `/<company>/invoices/create` — Phase 5

**What SF shows:**
- Page title: "Create Invoices — Create invoices for unfilled jobs"
- Customer-grouped expandable list
- Each row: Customer name (link), job count, Total Outstanding ($0.00 shown —
  these are uninvoiced completed jobs, not yet billed)
- Chevron expands to show individual jobs under that customer
- Pagination (52 entries across 5 pages)
- "Set Filters" button top right

**FieldKit build notes:**
- This is the batch invoicing starting point — different from the unpaid invoices view
- Workflow: Michele opens this, sees all customers with completed-but-uninvoiced jobs,
  expands each, selects jobs, creates invoice
- Our planned "uninvoiced job alerts" (1hr grace + 5PM escalation) make this list
  shorter over time by catching them early
- Link from uninvoiced jobs alert notification → this page

---

### Receive Payments
**SF URL:** `/receivePayments`
**FieldKit equivalent:** Part of `/<company>/billing` and invoice detail — Phase 5

**What SF shows:**
- Customer-grouped expandable list
- Each row: Customer name (link), invoice count, Total Outstanding ($)
- Expands to show individual invoices per customer
- "Set Filters" button, Search by invoice/job/etc.
- 60 entries across 5 pages

**FieldKit build notes:**
- Customer-grouped view is better than flat invoice list for Michele's payment workflow
- Clicking a customer expands their open invoices; she selects one and records payment
- FieldKit improvement: inline payment modal (never navigates away from this page)
- SF apparently navigates to a separate payment page — we stay on the invoice
- This view can live as a tab on the billing page alongside the unpaid invoices view

---

### Invoice Payments (View All)
**SF URL:** `/payments`
**FieldKit equivalent:** `/<company>/invoices/payments` or report — Phase 5

**What SF shows:**
- Two tabs: Invoice Payments, Job Deposits
- Table: Payment Date, Customer Name, Invoice Number(s), Payment Total,
  Payment Type, Transaction Type, In QuickBooks
- One payment can cover multiple invoices (e.g., "4469, 4486, 4521, 4522, 4544")
- Transaction Types: Payment, Authorize & Capture (credit card)

**Critical FieldKit note:**
- **One payment → multiple invoices must be supported**
- A customer paying a stack of invoices with one check is a common workflow
- Payment model needs: payment → payment_invoice_applications (junction table)
  mapping one payment to multiple invoices with amounts per invoice
- This is a schema change needed before Phase 5 invoicing is built

---

### Job Deposits
**SF URL:** `/deposits`
**FieldKit equivalent:** `/<company>/invoices/deposits` — Phase 5

**What SF shows:**
- Tab on Invoice Payments page
- Table: Deposit Date, Customer Name, Job Number, Payment Total, Payment Type,
  Transaction Type, In QuickBooks
- Deposit tied to job number (not invoice number — taken before invoice exists)

**FieldKit build notes:**
- Deposits = prepayments taken at time of booking or estimate acceptance
- Applied against the invoice when it's created
- Low current usage — add to Phase 5 alongside invoicing
- Schema: job_deposits table separate from payments table

---

### Reports Dashboard
**SF URL:** `/reports`
**FieldKit equivalent:** `/<company>/reports` — Built progressively by phase

**What SF shows (full catalog):**

Sales Revenue:
- All Sales Ungrouped, Sales By Customer, Sales By Service Tech,
  Sales By Referral Source, Estimates
  (all with presets: Last 12 Months, This Year, Last Month, This Month, This Week, Custom)

Accounting:
- Invoice (Custom only)

Tax:
- Sales Tax Report (Last Quarter, Last Month, This Month, This Week, Custom)

Fees:
- Discount/Misc Fees Report (same presets)

Payment & Refund Transactions:
- Transactions by Customer, Transactions by Service Tech, Transactions by Job
  (all with 12-month presets + Custom)

Inventory Stock Levels:
- Inventory Stock Levels By Warehouse (As Of Today, Custom)

List Reports:
- Customer List, Equipment List, Customer Service Locations (all Custom)

Activity Reports:
- Job Activity Report (Last Month, Last Week, This month, This Week, Custom)

Payroll:
- Hours Worked by Employee, Job Drive & Labor Times (Last Two Weeks, Last Week, This Week, Custom)

Sales Commission:
- Sales Commission By Agent, Sales Commission By Service Tech (same presets)

Sales by Product/Service:
- Sales of Product/Service Details, Sales of Product/Service By Service Tech (same presets)

Estimated Sales of Product/Service Details:
- Same structure as above but for estimates

Expense Reports:
- Reimbursable Expenses by Employee (same presets)

Day Sheet:
- Day Sheet By Service Tech, Expanded Day Sheet By Service Tech, Individual Work Orders
  (Today, Tomorrow, Next Two Weeks, Custom)

Service Agreements:
- Service Agreement List (Expired, Expiring This Month, Expiring Next Month, Open Ended, Custom)

**FieldKit build plan by phase:**
- Phase 2: Tax Report (migrated from Phase 0), Recency Report (migrated from Phase 0)
- Phase 4: Day Sheet by Tech, Individual Work Orders, Job Activity Report
- Phase 5: Sales Revenue (by customer, by tech), Payment & Refund Transactions,
  Unpaid Invoices report, Hours Worked by Employee
- Future: Sales Commission (when salesperson commission tracking is built),
  Sales by Product/Service, Expense Reports, Service Agreement reports
- Not needed: Inventory Stock Levels, Equipment List (low priority)

---

## KEY INSIGHTS & FIELDKIT IMPROVEMENTS SUMMARY

### Things SF does that we'll replicate:
1. Status-grouped left sidebar with counts on jobs/estimates list pages
2. Right sidebar aging summary with large colored dollar amounts on billing page
3. Hover popup on dispatch board showing job summary
4. Detail modal on dispatch board with inline editing + Close & Invoice shortcut
5. Customer-grouped expandable lists for Create Invoices and Receive Payments
6. Activity Feed on customer detail (right sidebar showing all events chronologically)
7. Status color coding on dispatch board job blocks

### Things SF does that we'll improve:
1. **Payment navigation** — SF backs out to list after recording payment;
   FieldKit stays on invoice with "Next Unpaid Invoice" link
2. **Unit numbers** — SF uses tags as a workaround; FieldKit has a proper
   Unit Number catalog item that slots into auto-generated job description
3. **Multi-contact billing** — SF has one billing checkbox; FieldKit has
   accepts_billing, accepts_statements, accepts_general per contact
4. **Job description** — SF is manual text entry; FieldKit auto-generates
   from checkboxes + line items with live preview
5. **Water extraction** — SF requires manual daily job-moving;
   FieldKit has auto-roll queue
6. **Tax reporting** — SF is invoice-basis (wrong for NC); FieldKit is native cash-basis
7. **Multi-company** — SF requires separate logins; FieldKit has single login
   with tab-per-company URL architecture
8. **Compliance portals** — SF has no batch export; FieldKit will batch by portal type
9. **Delinquent accounts** — SF has no dispatch visibility; FieldKit auto-tags
   and surfaces everywhere in the workflow

### Schema changes identified from this review:
1. **One payment → multiple invoices**: Need `payment_invoice_applications` junction table
   before Phase 5. Current model assumes one payment per invoice.
2. **Customer fields to add**: `public_notes` (separate from internal notes),
   `referral_source`, `assigned_rep_id` (links to users table, salesperson)
3. **Job deposits table**: separate from payments, tied to job not invoice
4. **Work order**: `task_list` (simple checklist per job), `requires_followup` boolean,
   `completion_notes` text field

---

*Document version: 1.0*
*Reviewed: 19 screenshots from ServiceFusion across Settings and Operational areas*
*Next update: when customer detail page or job form screens are reviewed in more detail*
