# FieldKit — Complete System Design (v2)
*Updated: May 27, 2026 | Incorporates session feedback*

---

## How to Read This Document

This is the master blueprint for FieldKit. It covers three layers for every part of the system:

1. **What it is** — the feature and its data
2. **How it connects** — what feeds into it and what flows out of it
3. **UX flow logic** — where the system takes the user after each action, and why

The goal: before writing a single line of code for any new feature, open this document and understand exactly what we're building, why it exists, and how it fits.

---

# PART ONE: SUPPORTING DATA STRUCTURES
*The catalog and reference data that makes the operational features work*

---

## 1. Services & Products Catalog

### What it is
A company-level library of every service or product the business offers. Line items on work orders are always pulled from this catalog — no freeform entry is allowed. This ensures consistency, makes reporting reliable, and automates tax handling per item.

### Services vs Products
For most companies in this system, everything is a **service**. The distinction matters for reporting and tax handling:
- **Get a Grip Charlotte** — services only (resurfacing, repairs)
- **Kleanit Charlotte** — services only (carpet cleaning)
- **Kleanit South Florida** — services only (carpet cleaning) + water extraction equipment (products)
- **CTS of Raleigh** — services + water extraction equipment (products)

Products (physical equipment placed and retrieved — extraction fans, dehumidifiers) are a minor sub-feature used only by CTS and Kleanit for water extraction jobs.

### No Freeform Line Items
Every line item on every work order must come from the catalog. There is no "type whatever you want" text field for line items. If something doesn't fit the catalog, the correct item to use is **"Custom Service"** — a catch-all entry where the description field explains the specific details. This enforces consistency without being rigid.

### Every Item Has a Description Box
Regardless of item type, every catalog item on a work order has an editable description field. The catalog provides the default description text; the office staff can modify it per job when needed.

### Special Line Item: Unit Number
A special catalog entry called **"Unit Number"** exists for apartment/property work. When added to a work order, its value (e.g., "Unit #3430-308") slots into the correct position in the auto-generated job description. This keeps the field tech's job description consistently formatted without office staff having to type anything in the right place.

### Data Structure
```
catalog_items
├── id
├── company_id               -- catalog is per-company (Get a Grip's services differ from Kleanit's)
├── item_type                -- 'service' or 'product'
├── name                     -- "Bathtub Resurface", "Surround Resurface", "Custom Service"
├── default_description      -- pre-fills the description box when item is added to a work order
├── category                 -- grouping for catalog display: "Resurfacing", "Cleaning", "Equipment", "Admin"
├── unit_price               -- default price (overridable per work order)
├── unit_of_measure          -- "each", "sq ft", "hour", "flat rate"
├── is_taxable               -- does this item carry sales tax?
├── cost                     -- internal cost for margin calculation
├── is_unit_number_field     -- special flag: this item's value slots into job description as unit number
├── is_catch_all             -- true for "Custom Service" — requires description to be filled
├── sort_order
├── is_active
├── created_by / updated_by
└── deleted_at
```

### Tax Exemption Logic (Three-Layer Hierarchy)
Tax on a line item is determined in this order:
1. **Item level:** if `is_taxable = FALSE` on the catalog item, that line item is always exempt. Example: a "Service Call Fee" that is never taxed.
2. **Customer level:** if the customer has `is_taxable = FALSE`, all line items are exempt regardless of item settings. Example: government or nonprofit accounts.
3. **Location level:** if the work order's service location has a county set, that county's rate applies to all taxable items.

First matching exemption wins. If none apply, the location's county rate is used.

### UX Flow
- Accessed at `/<company>/settings/catalog`
- Admin and manager roles
- New items can be added on the fly from the catalog settings page
- Adding a line item to a work order: type in search box → autocomplete pulls from catalog → selecting populates name, default description, price, tax flag → description box is editable inline → price is editable inline
- "Custom Service" always requires the description box to be filled before the work order can be saved

---

## 2. Work Order Tags

### What it is
A flexible tagging system for work orders. A work order can have multiple tags simultaneously. Tags are user-expandable — any admin or manager can add new tags on the fly from settings. Tags appear on the dispatch board (as colored pills on job blocks), the work order list, and on customer detail.

### Why tags instead of a single category
A work order might be simultaneously a "Callback" AND belong to a "Delinquent Account" customer. A single-category field can't represent that. Tags are more flexible and composable.

### Starter Tag Set
| Tag | Who applies it | How |
|-----|---------------|-----|
| Callback | Office staff | Manual, on work order create/edit |
| New Customer | Office staff | Manual |
| Residential | Office staff | Manual (most work is commercial) |
| Estimate/No-Charge | Office staff | Manual — job with no billable amount |
| Misc Task | Office staff | Manual — internal tasks, errands |
| Water Extraction | Office staff | Manual — triggers extraction queue visibility |
| Requires Follow-Up | Office staff / system | Manual or auto (see water extraction workflow) |
| Delinquent Account | System (automated) | Auto-applied nightly when customer's oldest invoice > 60 days overdue |

### Delinquent Account Auto-Tagging
A nightly background job runs and checks every customer's outstanding invoices. Any customer with an invoice more than 60 days past due gets the `Delinquent Account` tag automatically applied to all their future work orders at creation time. The tag is also visible on the customer detail page. This makes it impossible for a dispatcher to unknowingly schedule new work for someone who hasn't paid in two months without seeing the flag.

### Data Structure
```
work_order_tags (catalog of available tags)
├── id
├── company_id
├── name
├── color_hex          -- displayed on dispatch board
├── is_system_tag      -- true for auto-applied tags like Delinquent Account
├── sort_order
└── is_active

work_order_tag_assignments (many-to-many: work orders ↔ tags)
├── work_order_id
├── tag_id
├── applied_by         -- 'system' or username
└── applied_at
```

---

## 3. Job Description Auto-Generation

### What it is
The job description is how anyone previews a work order without opening the line items — it's the quick-read summary that field techs rely on. Rather than office staff typing it out, FieldKit generates a standardized description automatically from the work order's contents.

### Why this matters
Consistent formatting means techs always know where to look for the key details. It reduces data entry errors and removes the mental load of "how should I phrase this?"

### How it works
When a work order is built, the job description is auto-generated from:
1. **Checkboxes the office staff selects:** Occupied (OCC) or Vacant (VAC), AM or PM job, Gated Property, Follow-Up Visit
2. **The Unit Number line item** (if present): slots into the description in the unit field position
3. **The service line items:** listed in order they appear on the work order

The output is always the same structure:
```
Unit #[unit number] [OCC/VAC] [AM/PM]
[Service 1 description]
[Service 2 description]
[Special notes if any]
```

Example auto-generated description:
```
Unit #3430-308 OCC AM
Bathtub Resurface
Surround Resurface
*use VENDOR key — tub surround
```

### Office staff experience
- On the work order form, there is a small "Job Details" panel with:
  - [ ] Occupied  [ ] Vacant
  - [ ] AM  [ ] PM
  - [ ] Gated Property
  - [ ] Follow-Up Visit
  - [Special notes text box — optional, short]
- As they check boxes and add line items, the description preview updates live
- The generated description is editable if needed (it's a textarea pre-filled by the system)
- This description is what appears on the dispatch board hover, the work order detail, and the invoice

---

## 4. Technicians / Staff Profiles

### Additional fields needed for scheduling
```
-- Additional fields on users table for field scheduling:
├── color_hex                -- their row color on the dispatch board
├── is_field_tech            -- false for Michele, Chris O (office/sales roles)
├── can_be_dispatched        -- false for admin-only users
├── phone_mobile             -- for day-of contact by dispatch
├── default_start_time       -- "08:00" — default for new job scheduling
└── is_active_tech           -- can deactivate without deleting user account
```

---

## 5. Payment Methods

```
payment_methods
├── id
├── name                     -- "Check", "Credit Card", "Paymode-X", "ACH", "Cash"
├── requires_reference_number -- true for Check (check #), Paymode (ref #)
├── sort_order
└── is_active
```

---

## 6. Tax Settings

Tax settings are their own section at `/<company>/settings/tax` — not buried inside company settings. This is important enough to warrant its own navigation entry.

### What's configured here
- Default tax rate for the company (if no location county is set)
- County-level rate overrides
- Transit tax counties (Mecklenburg, Wake, Durham, Orange for NC)
- State base rate (NC: 4.75%)
- "Tax-exempt by default" toggle for the whole company (useful if a future company is all-exempt)

### NC Cash-Basis Rule (documented here for reference)
NC requires tax to be reported in the period it was **collected** (payment date), not the period the invoice was issued. FieldKit handles this natively in Phase 5 — the tax report queries payments in a date range and matches them to their invoices to get the tax amounts. No more uploading two separate Excel files.

---

# PART TWO: THE OPERATIONAL CORE
*The main workflow: Estimate → Work Order → Invoice → Payment*

---

## 7. The Work Order Lifecycle

```
INQUIRY / LEAD
    ↓
ESTIMATE (optional)
    ↓
WORK ORDER CREATED (status: Scheduled)
    ↓
DISPATCHED (tech assigned, appears on dispatch board)
    ↓
TECH ON WAY (status: On The Way)
    — Mobile: tech taps "On My Way" on their job
    — 10-minute GPS grace period before system prompts if not updated
    ↓
WORK IN PROGRESS (status: In Progress)
    — Mobile: tech taps "Start Job" on arrival
    — 10-minute GPS grace period after arriving at property geofence
    ↓
WORK COMPLETE (status: Completed)
    — Mobile: tech taps "Complete Job"
    — If tech leaves geofence without completing: 10-minute grace, then reminder
    ↓
INVOICE GENERATED (status: Invoiced)
    — Office creates invoice from completed work order
    — If not invoiced within 1 hour of completion: alert to office
    — If still uninvoiced at end of business (5:00 PM): email + text to manager
    ↓
INVOICE SENT
    — PDF emailed to billing contacts
    ↓
PAYMENT RECEIVED
    — Recorded by Michele
    ↓
INVOICE CLOSED (balance = $0)
```

### Special Statuses
- **No Charge** — Work was done but no invoice will be generated (estimate visit, warranty, goodwill)
- **Cancelled** — Work order cancelled before any work; cannot be invoiced
- **Water Extraction Active** — Sub-status for extraction jobs (see water extraction workflow below)

---

## 8. Water Extraction Workflow

### The Problem
Water extraction jobs are fundamentally different from other work orders. Equipment is set and then checked daily — the job doesn't close until equipment is retrieved, which could be 3–7+ days later. Currently in SF, this requires manually moving 20+ jobs to the next day every single day. It requires constant phone calls between the follow-up tech and the office. It's the most operationally painful workflow in the business.

### The FieldKit Solution: Extraction Queue

#### Concept
Water extraction work orders live in a separate **Extraction Queue** view in addition to appearing on the dispatch board. The queue is the central dashboard for all active extraction jobs. It shows the current status of every active extraction unit at a glance, and provides one-click tools to roll jobs forward or mark them for specific actions.

#### Work Order Flow for Extraction
1. Water extraction work order is created and tagged `Water Extraction`
2. Job appears on dispatch board normally for the day it's being set
3. After equipment is set and tech marks it done, the work order transitions to **Extraction Active** status instead of closing
4. Work order automatically rolls forward to the next day's schedule at midnight — no manual intervention
5. On each subsequent day, the follow-up tech has the rolled jobs in their dispatch queue
6. Tech uses mobile app to mark each unit's status (see below)
7. When equipment is retrieved: work order marked **Equipment Retrieved**, rolls to office queue for invoicing
8. When cleaning is needed: system can auto-create a follow-up cleaning work order

#### Extraction Status Per Unit
Each active extraction work order has a current extraction status:
- **Drying** — equipment is set, still wet
- **Ready for Pickup** — tech assessed, equipment can come out
- **Equipment Retrieved** — all equipment out, job complete
- **Needs More Time** — explicitly marked wet, will auto-roll to tomorrow
- **Missed Today** — tech fell behind, auto-rolls to tomorrow with a note

#### Auto-Roll Logic
At midnight every night, any work order with status **Extraction Active** and extraction sub-status **Drying**, **Needs More Time**, or **Missed Today** is automatically duplicated forward to the next business day's schedule for the assigned tech. The original job is linked to the rolled copy so the full history is preserved.

#### The Extraction Queue Page `/<company>/extraction`
```
ACTIVE WATER EXTRACTIONS — Get a Grip Charlotte

[Summary]
  22 Active Units  |  8 Ready for Pickup  |  3 Missed Today

[Table]
  Unit/Customer         | Days Active | Last Status      | Assigned Tech | Actions
  Abbington #204        | Day 3       | Drying           | Chris L       | [Mark Ready] [Needs More Time] [Retrieved]
  Abbington #108        | Day 5       | Ready for Pickup | Danyal S      | [Confirm Retrieved] [More Time]
  Vista Villa #1104     | Day 1       | Drying           | Braulio O     | [Mark Ready] [Needs More Time] [Retrieved]
  ...

[Batch Actions]
  [Roll All "Needs More Time" to Tomorrow]
  [Roll All "Drying" to Tomorrow]
  [Generate Pickup List for Tomorrow]
```

#### Mobile Experience for Extraction
On the tech's mobile job list, extraction follow-up jobs are visually distinct. For each one, the tech sees:
- Unit address and number
- Days equipment has been in
- Quick-tap status buttons: Wet (rolls to tomorrow), Ready (notifies office), Retrieved (closes unit)
- Photo upload for documentation

#### Office Communication
- When a tech marks a unit "Ready for Pickup" — office gets a notification
- When a unit reaches Day 5+ — escalation flag appears on the queue
- "Generate Pickup List for Tomorrow" — produces a PDF/printout of all units ready for retrieval, grouped by property and tech

---

## 9. Estimates

### Data Structure
```
estimates
├── id
├── customer_id
├── service_location_id
├── contact_id
├── estimate_number          -- EST-2026-0001
├── status                   -- Draft, Sent, Approved, Declined, Converted
├── expiration_date
├── notes_to_customer
├── internal_notes
├── converted_to_job_id
├── created_by / updated_by
└── created_at / updated_at

estimate_line_items
├── id
├── estimate_id
├── catalog_item_id
├── description
├── quantity
├── unit_price
├── total
├── is_taxable
└── sort_order
```

### UX Flow
- From customer detail → "New Estimate" button → estimate form pre-filled with customer
- After saving: go to estimate detail
- "Convert to Job" button → job create form pre-filled from estimate data
- After conversion: estimate status → Converted, links to the new job
- From estimate detail → back breadcrumb → customer detail

---

## 10. Work Orders (Full Detail)

### Data Structure
```
work_orders
├── id
├── work_order_number        -- auto-generated per company: GAG-2026-0001
├── customer_id
├── service_location_id
├── primary_contact_id
├── estimate_id              -- null if not from an estimate
├── status                   -- Scheduled, On The Way, In Progress, Completed,
│                               Invoiced, No Charge, Cancelled, Extraction Active
├── extraction_status        -- null unless Water Extraction tag applied
│                               Drying, Ready for Pickup, Equipment Retrieved, Needs More Time, Missed Today
├── auto_description         -- the generated job description text
├── description_occ_vac      -- 'OCC' or 'VAC' checkbox value
├── description_am_pm        -- 'AM' or 'PM' checkbox value
├── description_gated        -- boolean
├── description_followup     -- boolean
├── description_special_notes -- optional short text
├── internal_notes           -- NOT shown to tech or on invoice
├── notes_for_techs          -- shown to tech, not on invoice
├── completion_notes         -- filled by tech when done
├── po_number                -- from property management companies
├── job_source               -- Phone, Email, Website, Referral, Salesperson
├── priority                 -- Normal, High, Urgent
├── start_date
├── end_date
├── arrival_window_start
├── arrival_window_end
├── estimated_duration_hours
├── actual_duration_hours
├── is_multi_day
├── extraction_day_count     -- increments daily for active extraction jobs
├── parent_work_order_id     -- for extraction roll-forward jobs, links to original
├── created_by / updated_by
└── deleted_at

work_order_techs
├── work_order_id
├── user_id
├── is_lead_tech
└── assigned_at

work_order_line_items
├── id
├── work_order_id
├── catalog_item_id          -- always required; no null/freeform
├── description              -- editable per line item; pre-filled from catalog default
├── quantity
├── unit_price               -- overridable from catalog default
├── total
├── cost
├── is_taxable               -- inherited from catalog item, overridable
├── tax_county               -- inherited from service location
└── sort_order

work_order_status_history
├── id
├── work_order_id
├── status
├── extraction_status        -- if applicable
├── changed_by               -- username or 'system' or 'mobile_app'
├── changed_at
└── notes
```

### UX Flow
**Creating a work order:**
- From customer detail → "New Work Order" → form pre-filled with customer
- From dispatch board → click empty time slot for a tech → form pre-filled with tech + date/time
- From estimate → "Convert to Job" → form pre-filled with all estimate data
- After saving → go to work order detail page

**Working with line items:**
- Type in search → autocomplete from catalog → select item → description box appears (pre-filled, editable) → price appears (editable)
- Adding Unit Number item → a special field appears for the unit number value, which slots into the description
- "Custom Service" selected → description box is required before save
- No freeform items outside the catalog — if something is truly new, add it to the catalog first (admin/manager can do this inline from a "+Add to Catalog" link that appears when a search returns no results)

**Job description preview:**
- Live preview panel on the work order form updates as checkboxes are selected and items are added
- Preview shows exactly what the tech will see
- Office staff can manually edit the generated description if needed

**Completing a work order:**
- Office or tech marks "Completed"
- Prompt appears: "Generate invoice now?" → [Create Invoice] [Do Later]
- If "Create Invoice" → goes to invoice form pre-filled from work order
- If "Do Later" → stays on work order detail, yellow banner: "This work order has not been invoiced yet."

**For extraction work orders:**
- After marking complete: prompt is different: "Set equipment as active?" → [Yes — Start Extraction] [No — Close Normally]
- Selecting "Start Extraction" → status becomes Extraction Active, work order appears in extraction queue
- Auto-roll happens at midnight

---

## 11. Invoices

### Data Structure
```
invoices
├── id
├── invoice_number           -- INV-2026-0001
├── work_order_id
├── customer_id
├── service_location_id
├── status                   -- Draft, Sent, Partially Paid, Paid, Void
├── invoice_date
├── due_date                 -- calculated from invoice_date + customer.payment_terms
├── billing_contact_ids      -- JSON array: contacts who received this
├── subtotal
├── tax_total
├── total
├── amount_paid
├── balance_due
├── notes_to_customer
├── internal_notes
├── sent_at
├── sent_to_emails
├── portal_id                -- for OPS/VendorCafe/Paymode
├── portal_status
├── portal_submitted_at
├── wtn_po_number
└── created_by / updated_by

invoice_line_items
├── id
├── invoice_id
├── work_order_line_item_id  -- source line item
├── catalog_item_id
├── description
├── quantity
├── unit_price
├── total
├── tax_rate                 -- locked at invoice creation (not recalculated)
├── tax_county
├── tax_amount
└── is_taxable
```

### UX Flow
**Recording a payment:**
- From invoice detail → "Record Payment" button → modal opens (inline, no page navigation)
- Modal: Amount, Date, Payment Method, Reference Number
- Save → modal closes, invoice updates in place
- If balance_due reaches $0 → status → Paid, toast: "Invoice paid in full."
- **User stays on the same invoice. Always.**
- If user wants to process the next unpaid invoice: "Next Unpaid Invoice →" link appears at top after payment recorded

**After sending invoice:**
- Status → Sent, user stays on invoice detail
- Toast: "Invoice sent to [emails]."

---

## 12. Payments

```
payments
├── id
├── invoice_id
├── amount
├── payment_date             -- CRITICAL for NC cash-basis tax
├── payment_method_id
├── reference_number         -- check number, Paymode ref, etc.
├── notes
├── recorded_by
└── recorded_at
```

---

# PART THREE: THE BILLING PAGE (FULL VISION — PHASE 5)

## Michele's Billing Page — Complete

```
BILLING — Get a Grip Charlotte

[Summary]
  $47,230 Total Outstanding  |  23 Customers with Balances  |  8 Overdue 90+ days

[Aging summary]
  Current: $12,400  |  31-60 days: $8,900  |  61-90 days: $6,800  |  90+: $19,130

[Filter bar]
  [All Customers ▼]  [All Statuses ▼]  [☐ With Balance Only]  [☐ Delinquent Only]  [Search...]

[Table]
  ☐ | Customer | Billing Contact | Email | Current | 31-60 | 61-90 | 90+ | Total Due | Last Statement | Actions
  ☐ | Abbington | Sarah Lee | ap@co.com | $0 | $0 | $450 | $1,200 | $1,650 | 03/15 | [Invoice] [Send]

[Batch actions — appear when rows selected]
  12 selected  |  [Generate Statements]  [Send via Outlook]  [Export CSV]  [Mark for Follow-Up]
```

### Delinquent Account visibility on billing page
Customers with the `Delinquent Account` auto-tag appear with a red flag icon in the customer name column. Michele can filter to show only delinquent accounts. This feeds directly into her collections workflow.

---

# PART FOUR: UX FLOW LOGIC
*Where the system takes you after every action*

## The Core Principle
**After any action, the user returns to the context they came from — not to a list page.**

## Navigation After Every Action

| Action | Where you go |
|--------|-------------|
| Save new work order | Work order detail page |
| Save edited work order | Work order detail page |
| Complete a work order | Stay on work order, prompt to invoice |
| Create invoice from work order | Invoice create form (pre-filled) |
| Save invoice | Invoice detail page |
| Send invoice | Stay on invoice detail; toast confirmation |
| Record payment | Stay on invoice detail; offer "Next Unpaid Invoice" link |
| Invoice paid in full | Stay on invoice; celebration toast; "Next Unpaid Invoice" link |
| Add contact | Return to customer detail, scroll to contacts section |
| Save new customer | Customer detail page |
| Save edited customer | Customer detail page |
| Add line item to catalog | Stay on catalog settings |
| Convert estimate to work order | Work order create form (pre-filled) |
| Delete any record | Navigate to parent record |
| Roll extraction job forward | Stay on extraction queue |

## Breadcrumb Navigation
Every detail page shows its context:
```
Customers > Mountain Island Lake > Work Order GAG-2026-0042
Customers > Mountain Island Lake > Invoice INV-2026-0018
Dispatch > Wed May 28 > Work Order GAG-2026-0042
Extraction Queue > Mountain Island Lake #3430-308
```
Clicking any breadcrumb goes to exactly that page.

## Context-Aware Pre-fill
Buttons change based on where they're clicked:
- "New Work Order" on customer detail → pre-fills customer
- "New Work Order" on dispatch board (empty slot) → pre-fills tech + date/time
- "New Invoice" on work order detail → pre-fills all work order data
- "Record Payment" on billing page → opens modal showing that customer's open invoices
- "New Contact" on customer detail → pre-fills customer

## Mobile GPS Reminders (Phase 6)
- Tech arrives at scheduled property geofence → **10-minute grace period** → if no "Start Job" tap: gentle reminder notification
- Tech leaves property geofence without completing job → **10-minute grace period** → reminder to update status
- Completed work order not invoiced → **1-hour grace period** after completion → alert to office staff
- Any uninvoiced completed work orders still open at **5:00 PM** → email + SMS to manager
- Soft block: tech cannot open a new work order if they have a completed one they haven't submitted notes for (they can dismiss with one tap, not a hard lock)

---

# PART FIVE: COMPLETE URL MAP

```
/                                → /home or /<company>/dashboard
/login                           → login
/logout                          → clears session → /login
/home                            → multi-company launch pad

/<company>/dashboard             → overview: stats, recent activity, quick actions
/<company>/customers             → customer list
/<company>/customers/new         → create customer
/<company>/customers/<id>        → customer detail (tabs: Info, Jobs, Invoices, Documents)
/<company>/customers/<id>/edit   → edit customer
/<company>/customers/<id>/contacts/new          → add contact
/<company>/customers/<id>/contacts/<id>/edit    → edit contact
/<company>/customers/<id>/contacts/<id>/delete  → soft delete
/<company>/customers/<id>/locations/new         → add service location
/<company>/customers/<id>/locations/<id>/edit   → edit service location
/<company>/customers/<id>/jobs/new              → create work order (pre-filled)
/<company>/customers/<id>/estimates/new         → create estimate (pre-filled)

/<company>/dispatch              → dispatch board (calendar grid, today)
/<company>/dispatch?date=YYYY-MM-DD             → specific date

/<company>/extraction            → water extraction queue (active extraction jobs)

/<company>/jobs                  → work order list (filter by status, tech, tag, date)
/<company>/jobs/new              → create work order
/<company>/jobs/<id>             → work order detail
/<company>/jobs/<id>/edit        → edit work order
/<company>/jobs/<id>/invoice/new → create invoice from this work order

/<company>/estimates             → estimate list
/<company>/estimates/new         → create estimate
/<company>/estimates/<id>        → estimate detail
/<company>/estimates/<id>/edit   → edit estimate
/<company>/estimates/<id>/convert → POST: convert to work order → redirect to /jobs/new pre-filled

/<company>/invoices              → invoice list (filter by status, date, customer)
/<company>/invoices/<id>         → invoice detail
/<company>/invoices/<id>/edit    → edit draft invoice
/<company>/invoices/<id>/void    → void invoice (with confirmation)

/<company>/billing               → Michele's billing page (aging, batch tools)
/<company>/compliance            → OPS/VendorCafe/Paymode batch submissions

/<company>/reports               → reports landing
/<company>/reports/tax           → NC cash-basis tax report
/<company>/reports/recency       → customer recency report
/<company>/reports/daysheet      → day sheet (today or selected date)
/<company>/reports/hours         → technician hours report
/<company>/reports/jobs          → job activity report

/<company>/settings                     → settings landing page
/<company>/settings/catalog             → services & products catalog
/<company>/settings/tags                → work order tags (add/edit/deactivate)
/<company>/settings/users               → user management
/<company>/settings/tax                 → tax rates, counties, NC cash-basis settings
/<company>/settings/portals             → OPS/VendorCafe/Paymode configuration
/<company>/settings/payment-methods    → payment methods (check, ACH, Paymode, etc.)
/<company>/settings/company             → company name, address, phone, logo, branding
/<company>/settings/fields              → custom customer fields (done ✅)
```

---

# PART SIX: ROLES AND PERMISSIONS

| Action | Admin | Manager | Salesperson | Tech (mobile) |
|--------|-------|---------|-------------|---------------|
| View customers | ✅ | ✅ | ✅ | Own jobs only |
| Create/edit customers | ✅ | ✅ | ✅ | ❌ |
| Delete customers | ✅ | ❌ | ❌ | ❌ |
| Create/edit work orders | ✅ | ✅ | ❌ | Status updates only |
| View dispatch board | ✅ | ✅ | ❌ | Own row only |
| Update job status (mobile) | ✅ | ✅ | ❌ | ✅ |
| View/manage extraction queue | ✅ | ✅ | ❌ | Own jobs |
| Create estimates | ✅ | ✅ | ✅ | ❌ |
| View invoices | ✅ | ✅ | ❌ | ❌ |
| Create/edit invoices | ✅ | ✅ | ❌ | ❌ |
| Record payments | ✅ | ✅ | ❌ | ❌ |
| View billing page | ✅ | ✅ | ❌ | ❌ |
| Manage compliance portals | ✅ | ✅ | ❌ | ❌ |
| View reports | ✅ | ✅ | Limited | ❌ |
| Edit settings | ✅ | ❌ | ❌ | ❌ |
| Edit catalog | ✅ | ✅ | ❌ | ❌ |
| Add tags | ✅ | ✅ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ |

---

# PART SEVEN: INTELLIGENT CROSS-LINKS

### From Customer Detail
- Each work order in Jobs tab → work order detail
- Each invoice in Invoices tab → invoice detail
- Balance Due amount → billing page filtered to that customer
- "New Work Order" → work order create pre-filled
- "New Estimate" → estimate create pre-filled
- Delinquent Account tag → tooltip explaining oldest overdue invoice age
- Billing contact email → mailto: link

### From Work Order Detail
- Customer name → customer detail
- Service location → Google Maps
- Primary contact email → mailto:
- "Create Invoice" → invoice create pre-filled
- "View Invoice" (if invoiced) → that invoice
- Tech names → their day sheet for that date
- Tags → tag filter on work order list
- Status history → timeline of every status change

### From Invoice Detail
- Customer name → customer detail
- Work order number → work order detail
- "Record Payment" → inline modal (never leaves page)
- "Next Unpaid Invoice" (after payment) → next invoice in queue
- Portal status → compliance page

### From Dispatch Board
- Click job block → hover popup
- "View Details" in popup → full work order modal
- Customer name in modal → customer detail
- Delinquent Account tag on job block → visible red indicator

### From Billing Page
- Customer name → customer detail
- Balance amount → oldest unpaid invoice
- "Add Contact" for missing-billing customers → contact create form
- Delinquent flag → customer detail

### From Reports
- Tax report → customer name → invoice detail
- Recency report → customer name → customer detail
- Day sheet → job → work order detail
- Hours report → tech name → their job history

### From Extraction Queue
- Unit/customer → customer detail
- Work order → work order detail
- "Generate Pickup List" → printable PDF

---

# PART EIGHT: IMPROVEMENTS OVER SERVICEFUSION

| Area | SF behavior | FieldKit improvement |
|------|-------------|---------------------|
| Payment recording | Backs out to invoice list after each payment | Stays on invoice; "Next Unpaid" option |
| Billing contacts | One checkbox per contact | Three flags: billing, general, statements |
| Freeform line items | Anything goes | Catalog-enforced with "Custom Service" catch-all |
| Job description | Manual text entry | Auto-generated from checkboxes + line items |
| Water extraction | Manual daily job-moving | Auto-roll queue with one-click batch tools |
| Batch billing | No direct batch tool | Aging view, batch PDF + Outlook integration |
| Tax reporting | Invoice-basis (wrong for NC) | Native cash-basis matching |
| Multi-company | Separate logins | Single login, tab-per-company URL architecture |
| Delinquent accounts | No visibility on dispatch | Auto-tag surfaces everywhere in the workflow |
| Navigation | Backs to list after actions | Always returns to context record |
| Mobile status updates | No GPS intelligence | GPS-triggered reminders with grace periods |
| Uninvoiced jobs | No alerts | 1-hour grace + 5PM escalation to manager |
| Compliance portals | Manual per-invoice | Batch export by portal type |

---

# PART NINE: EXPLICIT OUT OF SCOPE (FOR NOW)

- QuickBooks integration — noted; Michele handles manually today
- Credit card processing — Paymode handles most; future Phase 7+
- Customer self-service portal — future
- Payroll / time tracking integration — future
- Inventory / warehouse management — not a current need
- Multi-tenant franchise billing under LKit — after core is stable for internal companies
- AI features — planned; require PowerEdge inference server

---

# PART TEN: BUILD ORDER (CONFIRMED)

### Phase 1 — Customer Foundation (IN PROGRESS)
**Remaining:** Import 3 other company customer data, user management UI, billing email field cleanup, nav links
**Milestone:** Michele can look up any customer, see all contacts and locations in FieldKit

### Phase 2 — Catalog + Reports + Admin
**Build:** Services & products catalog, work order tags, payment methods, tax settings page, user management UI, company settings, tax report migration from Phase 0, recency report migration from Phase 0
**Milestone:** Michele can run tax and recency reports in FieldKit. Admin can manage users via UI. Catalog is ready for work orders.

### Phase 3 — Estimates + Sales CRM
**Build:** Estimate create/edit/view/send, estimate→work order conversion, Chris O salesperson workflow, prospect/lead tracking
**Milestone:** Chris O manages his pipeline in FieldKit. Estimates can be created and sent.

### Phase 4 — Work Orders + Dispatch
**Build:** Work order create/edit with auto-description, work order list, dispatch board (calendar), work order status workflow, water extraction queue, day sheets, hours report, job description auto-generation from line items
**Milestone:** All work is scheduled and dispatched in FieldKit. Techs have work orders. Water extraction has a proper queue.

### Phase 5 — Invoicing + Billing (The Big One)
**Build:** Invoice create from work order, invoice list, PDF generation (branded), send via email/Outlook, payment recording (inline modal), NC cash-basis tax report from live data, billing page full version with aging/balances/batch tools
**Milestone:** Michele retires Phase 0 entirely. Full billing cycle lives in FieldKit.

### Phase 6 — Mobile App
**Build:** PWA for techs, work order list, work order detail, status updates, GPS reminders (10-min grace), before/after photos, clock in/out, extraction queue mobile view
**Milestone:** Techs use FieldKit on phones. Office gets GPS-informed status updates. Uninvoiced job alerts fire automatically.

---

*Document version: 2.0*
*Owner: Chris Letize | chrisletize/fsm-system*
*Next update: when Phase 2 planning begins*
