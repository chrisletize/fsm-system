# ServiceFusion Mobile App — FieldKit Reference
*Documented: October 20, 2026 | Source: iPhone screenshots of the ServiceFusion app shared by Chris*
*Purpose: Functional reference for the FieldKit mobile app (Phase 6). Same approach as
`SF_SCREEN_ANALYSIS.md`: adapt and improve, don't copy pixel for pixel.*

Screenshots are saved in `mobile-app/screenshots/`, numbered in the order Chris
shared them, so they never need re-sharing. **More batches are coming** (16 photos
per message limit); add them here as `17-…`, `18-…` and keep the numbering going.

For each screen:
- **What SF shows**: data, actions and layout observed
- **FieldKit today**: what already exists on the web, with route or table
- **For the mobile app**: what to build, improvements, open questions

Index of everything waiting on the mobile app: `docs/MOBILE-APP-BACKLOG.md`.

---

## Batch 1 (2026-10-20, screenshots 01–16)

### Home screen
**Screenshot:** `01-home-menu-open.png` (also visible behind `15`)

**What SF shows:**
- Header bar: **Refresh**, connection state (**Online**), hamburger menu.
- Menu: **Logout**, **My Profile**, **Time Log**.
- Tile grid: **My Work**, **Customers**, **Map View**, **My Team**, **Catalogs**,
  **Create New**, **Inventory**, **FusionDrive**.
- Small red corner triangles on the Catalogs and Create New tiles (meaning not
  known from the screenshot).
- Bottom: "last Clocked Out at 05/22/2024 02:03 pm" and a big green **Clock In**
  button.

**FieldKit today:** My Work ≈ `/<company>/myday`. Customers: techs have read-only
access scoped to their own jobs' customers (`_technician_customer_ids()`, D-091). No
clock in/out or time log.

**For the mobile app:**
- An explicit **Online/Offline** indicator plus Refresh fits the offline-first plan
  (PHASE-1-PLANNING). Show it the same way.
- Keep the home screen to what techs actually use. Of these 8 tiles, check with
  the techs which ones they touch; this account's last clock-out was May 2024,
  which suggests clock-in may not be used at all at Get a Grip.
- Add FieldKit-specific tiles SF doesn't have: **📣 Sales tip** (D-115) and
  **Extraction follow-ups** (non-GAG companies).
- **Open question:** is time clock (clock in/out, time log) wanted? It's listed in
  `FIELDKIT_TASKS.md` Phase 6, but nothing is built and it touches payroll.

### Create New: Job / Estimate / Calendar Task
**Screenshots:** `15-create-new-menu.png`, `14-create-job-top.png`,
`13-create-job-lower.png`, `12-create-estimate-top.png`,
`11-create-estimate-lower.png`, `10-create-calendar-task.png`

**What SF shows:**
- A modal with three choices: **Job**, **Estimate**, **Calendar Task**.
- **Create Job** and **Create Estimate** are the same form: Customer → Service
  Location → Date & Arrival Time Window (date, start, end) → Job Duration (hr/min
  pickers) → Job Description → (Job) Category → Referral Source → **Dispatch &
  Settings**.
- **Create Task:** type toggle **Call / Email / Misc**, Start and End
  date/time, **Assigned To** (defaults to the current user), Description,
  **Everyone can see this task**, **Complete**.

**FieldKit today:** the WO form (`/<company>/workorders/new`) has customer, service
location, start date, arrival window (`arrival_window_start/_end`, migration 005),
duration (with the catalog-duration estimate) and auto-description. `job_source`
(Phone/Email/Website/Referral/Salesperson) is the equivalent of Referral Source.
Estimates: `/<company>/estimates/new` (migration 021). Calendar tasks ≈
**internal tasks** (`is_internal_task`, migration 019): customer-less WOs with a
Task Details field, shown on the dispatch board.

**For the mobile app:**
- Field techs creating jobs and estimates on the phone: **decide who may**. Today
  the web WO form is office-side, and techs are read-only on customers (D-091).
- **Job Category** has no FieldKit equivalent on work orders. FieldKit's catalog
  has a category, and the auto-description already says what the job is. Probably
  not needed; confirm.
- The task type (Call/Email/Misc) and "Everyone can see" have no equivalent on
  internal tasks. Overlaps with sales tips (D-115), which already cover "remind the
  salesman". Decide whether tasks need types at all.
- Improvement: the phone form should reuse the WO form's live catalog-duration
  estimate and the double-booking warning rather than plain hr/min pickers.

### Catalogs
**Screenshots:** `08-catalogs-root.png`, `06-catalogs-products.png`,
`07-catalogs-services.png`

**What SF shows:**
- Root: **Products** and **Services**.
- Each has a search box with a **barcode scanner** button, category tiles
  (Products: Discount, Non-inventory Part, QBO Product, Service; Services: Discount,
  QBO Service, Service), then the items with photo, name, description and price.
  Every price shown is **$0.00**.
- "Create" on Products: techs can add catalog items from the phone.

**FieldKit today:** catalog CRUD on the web (`catalog_items`, migration 004); 45
real GAG items imported from ServiceFusion (D-093). No item photos, no barcodes.

**For the mobile app:**
- A **read-only catalog browser** is enough for techs. Creating catalog items
  stays office-side; SF letting techs create them is likely how junk items like
  "products used" at $0.00 got in.
- The $0.00 prices suggest SF's catalog was never priced, and the QBO categories
  are QuickBooks sync leftovers. Don't copy those categories.
- Barcode scanning: only worth it if real inventory tracking is wanted (below).

### Inventory
**Screenshot:** `09-inventory-levels.png`

**What SF shows:** "Inventory Levels" with a Search dropdown — **No results found**.

**FieldKit today:** no stock inventory; the equipment registry (`equipment_units`)
tracks extraction equipment units, which is a different thing.

**For the mobile app:** empty in SF, so evidently unused. **Skip** unless Chris
wants stock tracking (materials, colour kits) later.

### FusionDrive (files)
**Screenshots:** `05-fusiondrive-root.png`, `03-fusiondrive-company-files.png`,
`04-fusiondrive-my-files.png`, `02-fusiondrive-shared-with-me.png`

**What SF shows:**
- Three folders: **My Files**, **Company Files**, **Shared With Me**.
- Company Files has four PDFs, all uploaded 02/06/2025: **Basic Color Chart.pdf**,
  **GAG Mixing Instructions.pdf**, **Metallics Color Chart.pdf**, **Premium Color
  Chart.pdf**, each with a download button.
- My Files and Shared With Me are empty.

**FieldKit today:** none. File upload infrastructure does exist (`./uploads/`,
`work_order_attachments`, migration 030).

**For the mobile app:**
- The real use is a **company reference library**: colour charts and mixing
  instructions a Get a Grip tech needs on site. Build that: office uploads per-company
  documents, techs view them offline. Drop "My Files" and "Shared With Me", which
  are unused.
- Offline access matters most here: a tech in a basement unit needs the colour
  chart without signal.
- Small enough to build on the web first (an office upload page plus a tech
  "Reference docs" link on My Day) if Chris wants it before the app.

### My Team / Team Locations map
**Screenshot:** `16-team-locations-map.png`

**What SF shows:** "Team Locations", a map (HERE Maps) with a pin per team member
showing their live location, e.g. "CL" near Cornelius.

**FieldKit today:** none.

**For the mobile app:**
- ⚠️ **This goes further than the location design already written down.**
  FieldKit's mobile designs rule out a continuous GPS stream and geofencing, and use
  iOS visit monitoring (arrival/departure events) for work features
  (`FIELDKIT_DESIGN_ADDENDUM_mobile-afterhours-extraction.md`). A *live* team map
  needs continuous background location.
- A middle ground that fits the design: show each tech's **last known position
  from their own actions and visit events**, such as where they tapped On The Way /
  Started / Completed (visit status, migration 029) or an arrival the phone
  detected, with a timestamp ("at Brookside Apts, 11:40"). That answers "where is
  everyone" without a live stream.
- **Decision for Chris:** a live map, or last-known-from-activity?

### Map View
*Tile visible on the home screen; screen not yet shared.* Presumably today's jobs on a
map. Add it when the screenshot arrives.

---

## Batch 2 (2026-10-20, screenshots 17–19)

### Home screen (menu closed)
**Screenshot:** `17-home-screen.png`. The same tile grid as `01`, with the
**Customers** tile visible (it was hidden behind the open menu there).

### My Work: agenda
**Screenshot:** `18-my-work-agenda-current.png`

**What SF shows:**
- Header: search icon. Toolbar: list/menu icon and a calendar icon (agenda vs.
  calendar view), with the title **Agenda**.
- Tabs: **PAST / CURRENT / FUTURE**.
- One card per job: a status icon on the left (**STARTED**, a blue play icon;
  **SCHEDULED**, a green calendar check), then customer name (bold, red), the
  job's first description line (e.g. "Unit # 21-102 tub-master", "Unit #
  10-1126-N OCC ******occ release form in gag office …"), Start window
  ("8:00am – 8:30am"), Duration, Assigned to, Location (full address) and Job #.
- This account sees **other techs' jobs** too (Christian Cole, Danyal Sherer): an
  admin view, not "my" work.

**FieldKit today:** `/<company>/myday` is a date picker plus today's assigned jobs:
time, customer, visit-status pill, address with a Map link, contact phone,
auto-description, notes for techs, line items, and visit-status buttons. Job
number and duration aren't shown on the regular job cards. It shows only the
logged-in tech's own jobs.

**For the mobile app:**
- Keep the card layout. It's the right density: customer first, unit/work line,
  arrival window, address. Add **job number** and **duration**, which My Day lacks.
- Past/Current/Future tabs are a nicer frame than a date picker for a tech.
  "Current" = today plus anything still open (e.g. a Started job from yesterday).
- The status icon should be the **visit status** (migration 029), with the job's
  own status secondary, the same split the dispatch board uses.
- An admin/manager "everyone's jobs" view is useful (Chris sees all techs here),
  but keep the default **my jobs only**.
- Note the description text "OCC ******occ release form in gag office". That's the
  paper workflow FieldKit already replaced: the OCC token plus the signed form
  attached to the job (migration 030, D-102). The app should show "Release on
  file ✓" instead of free-text asterisks.

### Customers list
**Screenshot:** `19-customers-list.png`

**What SF shows:** a searchable list of customer name plus address. Several names
carry **flags typed into the name itself**: `**NEED NEW BILLING**Junction 1504`,
`**OPS**The Weathersby at Station Circle`, `**see notes for billing**Stonesthrow
Apartments (Greensboro)`, `*FL* Woodsdale Oaks`.

**FieldKit today:** structured equivalents already exist for each of those
prefixes:
- `**OPS**` / `**VENDOR**` / `**VENDOR CAFE**` → compliance portals
  (`customer_compliance_portals`, migration 015)
- `**NEED NEW BILLING**` / `**see notes for billing**` → billing-contact readiness
  (the billing page's `no_contact` filter, billing contact flags)
- `*FL*` → the property belongs to Kleanit South Florida, which has its own database

⚠️ **Data-quality finding: the prefixes came across into FieldKit.** Live count,
2026-10-20, of active customers whose name starts with `*`:

| Company | Count | Prefixes |
|---|---|---|
| Get a Grip | 4 | `*FL*`, `**NEED NEW BILLING**`, `**OPS**`, `**see notes for billing**` |
| Kleanit Charlotte | 5 | `* FL*` (2), assorted "need new billing" spellings |
| CTS | 16 | `**OPS**` (9), `**VENDOR**` (4), `**VENDOR CAFE**`, `**ops**`, `**need billing info**` |
| Kleanit SF | 61 | `*FL*` (58), `**FL**` (3); **every customer** |

They clutter search, sort to the top of lists, and duplicate (or contradict) the
structured fields. A one-off cleanup would strip each prefix, set the matching
structured field (portal enrolment, billing-contact follow-up), and keep the
original name in the audit trail. For the Florida ones in the Charlotte companies'
lists, confirm whether they belong in Kleanit SF instead. **Not done; needs Chris's
go-ahead.** Listed as an open item in CURRENT-STATUS.

**For the mobile app:** a customer list for techs is only their own jobs' customers
(D-091 scoping). Show structured badges ("OPS portal", "Billing info needed") instead
of name prefixes.

---

## Batch 3 (2026-10-20, screenshots 20–30): job detail, status, edit forms

*Chris: "that's all of the screens I can access in the service fusion mobile app."
This completes the reference. The consolidated plan, which merges these notes with
everything FieldKit already intends for the app, is `docs/MOBILE-APP-PLAN.md`.*

### Job detail
**Screenshots:** `21-job-detail-notes-tab.png`, `22-job-detail-docs-tab.png`,
`23-job-detail-eqpt-tab.png`, `20-job-photos-empty.png`

**What SF shows:**
- Header: customer name, **Edit**, and a customer link bar under it.
- Four round action buttons: **info**, **map**, **photo**, **sign**.
- Fields: Location (full address), Description (Job# plus the first line, "Unit #
  21-102 tub-master"), **Custom Fields**, **Additional Visits: 0**, **Completion
  Notes**, Assigned to.
- Tab bar: **Tasks · Notes · Docs · Eqpt · Invoice**.
  - Notes: **Notes For Techs** and **Job Notes**, plus **Add Notes**.
  - Docs: "Stored Documents", **Upload new**.
  - Eqpt: "No equipment assigned", **Add Equipment** (customer-owned equipment,
    e.g. HVAC units; not the same as FieldKit's extraction equipment).
- Photo: "No images yet", **Add new**.

**FieldKit today:** WO detail has notes for techs (`notes_for_techs`), status history,
the record_audit History panel, attachments (release forms, migration 030), and line
items with per-unit deployed/retrieved dates for extraction equipment. No job
photos, no signature capture, no "completion notes" field as such, no custom fields
on WOs (custom fields exist on customers).

### Invoice tab
**Screenshots:** `24-job-invoice-tab-charges.png`, `25-job-invoice-tab-actions.png`

**What SF shows:**
- "Estimated Charges": line items with edit icons ("Unit # 21-102 vacant (1.00)
  $0.00", "Bathtub Resurface XL-master (1.00) $335.00"), Fees & Discounts, Taxes
  (**Mecklenburg $27.64**), and a Summary (Line Items, Drive & Labor, Billable
  Expenses, Fees & Discounts, Taxes, Payments/Deposits, **Total Due $362.64**).
- Buttons: **Add Line Item** (+ barcode), **Add Time**, **Add Expense**, **Email Job**,
  **Print Job**, **Apply Deposit**.
- Notice: "Please complete the job to create an invoice."

**Observations:**
- The tax matches FieldKit: Mecklenburg is 8.25% in `tax_rates` (4.75 state +
  3.00 county incl. the 1% additional + 0.50 transit, effective 2026-07-01), and
  8.25% of $335 is $27.64. A good spot check that the tax engine agrees with SF on
  a real job.
- "Unit # 21-102 vacant" is a **$0.00 line item used as a description**: SF had
  nowhere better to put the unit. FieldKit already has `work_site_label` and the
  auto-description for that, so no $0 lines are needed.
- Techs can edit prices and add line items in the field here. In FieldKit, pricing
  and invoicing are office-side (invoices harden and freeze totals, D-104
  reasoning).

### Status picker
**Screenshot:** `26-job-status-picker.png`

**What SF shows:** one picker with **UNSCHEDULED, SCHEDULED, ON THE WAY, ON SITE,
COMPLETED, CANCELLED**, over a header of date, arrival window and duration.

**FieldKit today:** deliberately **two** state machines (D-100): the job's own status
(office-controlled) and the tech's **visit status** (On The Way / Started / Completed
/ Cancelled, per tech, migration 029). SF mixes them into one list, which is exactly
the problem D-100 solved (a "completed" daily extraction check must not close the
job). SF says **"On Site"** where FieldKit says **"Started"**. Worth deciding which
word the techs prefer.

### Edit job
**Screenshots:** `27-job-edit-top.png`, `28-job-edit-lower.png`

**What SF shows:** Customer, Service Location, Date & Arrival Time Window (dropdowns),
Job Duration (Hr / Min text boxes), Referral Source, Job Description, **Save Job**.
The same fields as Create Job (batch 1).

### Edit customer
**Screenshots:** `29-customer-edit-top.png`, `30-customer-edit-lower.png`

**What SF shows:** Customer Name, PrimaryContact (first/last), Email, Mobile, a second
Email/Mobile, Referral Source, Customer Custom Fields, **Public/Work Order Notes**,
**Save**.

**Observations:**
- The primary contact for "Legacy Cornelius Apartment Homes" is first name
  "Legacy", last name "Cornelius Apartment": the property name split in two, not a
  person. The email `GCIAP@AVIDBILL.COM` is an **AvidBill accounts-payable
  inbox**, i.e. a billing portal address rather than a contact. FieldKit models
  this properly (billing-flagged contacts, compliance portals), so the app should
  show **contacts** and **billing** separately, and techs shouldn't edit billing data.
- Customer editing from the phone: FieldKit techs are read-only on customers (D-091).
  Keep that.

---

## Running list: decisions this reference raises for Chris

1. Time clock (Clock In/Out, Time Log): wanted, or skip?
2. Can techs create jobs/estimates from the phone, or only the office?
3. Calendar task types (Call/Email/Misc): needed, given internal tasks and sales tips?
4. Team map: live tracking, or last known position from visit-status taps?
5. Company reference library (colour charts): build on the web now, or wait for
   the app?
6. Inventory / barcode scanning: skip?
7. Should managers/admins get an "everyone's jobs" view in the app, alongside my jobs?
8. Clean up the `**OPS**` / `**NEED NEW BILLING**` / `*FL*` prefixes in 86 FieldKit
   customer names (batch 2)?
9. Can techs add or price line items in the field, or is that office-only (batch 3)?
10. "Started" or "On Site" as the visit-status word?

*All of these are carried into the discussion agenda in `docs/MOBILE-APP-PLAN.md`.*
