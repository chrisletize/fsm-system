# FieldKit — Task List & Phase Roadmap
*Last updated: June 9, 2026*

---

## Guiding Principle: Hardcoded First, Configurable Later

All features are being built hardcoded for the four internal companies first.
Configurability (company preferences, custom statuses, role management pages, etc.)
gets built as a separate layer before onboarding external LKit/franchise customers.
This speeds up internal deployment without sacrificing the long-term vision.

Items marked **[CONFIGURABLE LATER]** are noted throughout this document.

---

## ✅ Phase 1 — Customer Foundation (COMPLETE as of June 9, 2026)

- [x] Docker stack deployed on ubuntu-business:3100
- [x] Auth system (bcrypt, sessions, RBAC)
- [x] Company-in-URL architecture for Michele's multi-tab workflow
- [x] Home page launch pad for multi-company users
- [x] Customer list with live AJAX search (ILIKE partial match, 300ms debounce)
- [x] Customer detail page with contacts, locations, notes, custom fields
- [x] Customer add/edit form
- [x] Service locations add/edit
- [x] Contact add/edit/delete with billing flags (accepts_billing, accepts_statements, accepts_general)
- [x] Tax settings on customer (is_taxable toggle + county dropdown)
- [x] Custom field system — `/<company>/settings/fields`
- [x] Billing page foundation — `/<company>/billing`
- [x] User management page — `/<company>/settings/users` (admin only)
- [x] Navigation bar in base.html (Dashboard, Customers, Billing, Settings dropdown)
- [x] Password reset email flow via Resend API
- [x] Roles: admin, manager, office, salesperson, technician
- [x] Customer data imported: Get a Grip (1,330), CTS (903), Kleanit Charlotte (3,013), Kleanit SF (61)
- [x] Duplicate customer cleanup on Get a Grip (soft-deleted 1,147 dupes)
- [x] import_sf_customers.py updated: Docker DB connection, FL auto-split, duplicate detection
- [x] Migration 003: contact billing flags + customer_compliance_portals table
- [x] SSL cert, DNS, NPM proxy configured for app.fieldkit.cletize.com
- [x] Nightly backups to NAS via ubuntu-services
- [x] GitHub SSH key auth on ubuntu-business

**Phase 1 milestone:** Michele can look up any customer across all four companies,
see all contacts and billing flags, and manage users without CLI access.

---

## 🔴 Phase 2 — Catalog + Reports + Admin
*Milestone: Michele can run tax/recency reports in FieldKit. Catalog ready for work orders.*

### Services & Products Catalog
- [ ] `/<company>/settings/catalog` — admin/manager/office
- [ ] Per-company catalog of every service/product
- [ ] No freeform line items — everything from catalog
- [ ] Special items: "Custom Service" (catch-all, requires description),
      "Unit Number" (slots into job description auto-generation)
- [ ] Item fields: name, category, description, unit price, cost, is_taxable,
      unit_of_measure, is_active, sort_order
- [ ] Categories: Carpet, Resurfacing, Service, Discount, Fuel Surcharge (per company)
- [ ] $0.00 items supported (callbacks, warranties, no-charge items)
- [ ] **[CONFIGURABLE LATER]** Admin UI to add/edit/deactivate catalog items
      (seed from SF services export for now)

### Work Order Tags
- [ ] `/<company>/settings/tags` — admin/manager
- [ ] Starter set: Callback, New Customer, Residential, Estimate/No-Charge,
      Misc Task, Water Extraction, Requires Follow-Up
- [ ] System auto-tag: Delinquent Account (nightly job, invoices > 60 days overdue)
- [ ] Color per tag for dispatch board display
- [ ] **[CONFIGURABLE LATER]** User-expandable tag management page

### Payment Methods
- [ ] `/<company>/settings/payment-methods`
- [ ] Seed: Cash, Check, Credit Card, ACH/eCheck, Direct Bill, Paymode-X
- [ ] requires_reference_number flag per method (Check needs check#, Paymode needs ref#)
- [ ] **[CONFIGURABLE LATER]** Admin UI to add/edit payment methods

### Tax Settings Page
- [ ] `/<company>/settings/tax` — own section, NOT buried in company settings
- [ ] NC county list (editable), state base rate (4.75% hardcoded for NC),
      transit tax county toggles (Mecklenburg, Wake, Durham, Orange)
- [ ] NON TAXABLE as explicit selectable option
- [ ] CTS county list broader than GAG (Johnston, Harnett, Guilford, etc. — see SF screenshot)
- [ ] **[CONFIGURABLE LATER]** Full tax settings UI for non-NC companies

### User Management Enhancements
- [ ] `/<company>/settings/users` already built — add:
- [ ] Phone number field on user profile (needed for dispatch board tech rows)
- [ ] is_field_tech flag (separates office/sales from dispatchable techs)
- [ ] color_hex field (tech row color on dispatch board)
- [ ] **[CONFIGURABLE LATER]** Role management page (add/edit/delete roles)

### Company Settings Page
- [ ] `/<company>/settings/company`
- [ ] Name, address, phone, email, logo upload
- [ ] Logo feeds into branded PDF invoices/statements
- [ ] **[CONFIGURABLE LATER]** Full preferences page (SF-style toggles) for LKit customers

### Reports — Migration from Phase 0
- [ ] `/<company>/reports/tax` — NC cash-basis tax report (migrated from Phase 0)
- [ ] `/<company>/reports/recency` — customer recency report (migrated from Phase 0)
- [ ] `/<company>/reports` — reports landing page with all available reports listed

### Global Search
- [ ] Global search bar in top nav (already in base.html nav area — wire it up)
- [ ] `/<company>/search?q=...` — searches customers (Phase 2), jobs+invoices (Phase 5+)
- [ ] Enter-key submission (no live preview — results organized by entity type)
- [ ] All other search boxes on list pages use live AJAX pattern (established in Phase 1)

---

## 🟢 Phase 3 — Estimates + Sales CRM
*Milestone: Chris O manages sales pipeline in FieldKit. Estimates can be created and sent.*

- [ ] Estimate list — `/<company>/estimates` (left sidebar status folders with counts)
- [ ] Estimate create/edit — line items from catalog, status tracking
- [ ] Estimate → Work Order conversion ("Convert to Job" button)
- [ ] Estimate PDF generation + email to billing/general contacts
- [ ] Prospect/lead tracking — Chris O salesperson workflow, visit logging
- [ ] Salesperson dashboard — pipeline view
- [ ] Public estimate request form — per-company branded, feeds estimate queue
- [ ] Business card scanning — Google Cloud Vision API → contact import (Chris O)

---

## 🟢 Phase 4 — Work Orders + Dispatch
*Milestone: All work scheduled in FieldKit. Techs have work orders. Extraction has a queue.*

### Work Orders
- [ ] Work order list — `/<company>/jobs` (left sidebar status folders with counts)
- [ ] Work order create/edit — full form with catalog line items
- [ ] Job description auto-generation from checkboxes + line items (OCC/VAC, AM/PM, Gated, Follow-Up)
- [ ] Unit Number catalog item slots into auto-generated description
- [ ] Live preview of generated description on the form
- [ ] Work order status workflow with history log
- [ ] Per-line tax county dropdown (inherits from service location)
- [ ] Task list, completion notes, requires follow-up checkbox on work order
- [ ] Notes for techs (shown to tech, not on invoice)
- [ ] Internal notes (office only)

### Dispatch Board
- [ ] `/<company>/dispatch` — horizontal grid, tech rows × time columns
- [ ] React/DnD Kit prototype exists as starting point
- [ ] Job blocks as colored bars (color = tag color or status color)
- [ ] Hover popup: job#, customer name+link, contact phone, address, job description snippet
- [ ] Detail modal: full job info, inline edit of date/time/tech/arrival window,
      "Close & Invoice" shortcut button
- [ ] Bottom tray: Unscheduled, Unassigned, With Open POs, Marked for Follow-Up buckets
- [ ] Delinquent Account tag visible on job blocks (red indicator)

### Water Extraction Queue
- [ ] `/<company>/extraction`
- [ ] Status per unit: Drying, Ready for Pickup, Equipment Retrieved,
      Needs More Time, Missed Today
- [ ] Midnight auto-roll for Drying/Needs More Time/Missed Today jobs
- [ ] Batch actions: Roll All to Tomorrow, Generate Pickup List (PDF)
- [ ] Office notification when tech marks unit Ready

### Reports
- [ ] Day Sheet by Tech — `/<company>/reports/daysheet`
- [ ] Expanded Day Sheet, Individual Work Orders
- [ ] Hours Worked by Employee — `/<company>/reports/hours`
- [ ] Job Activity Report — `/<company>/reports/jobs`

---

## 🟢 Phase 5 — Invoicing + Billing
*Milestone: Michele retires Phase 0 entirely. Full billing cycle in FieldKit.*

### Invoicing
- [ ] Invoice create from work order — pre-fills all line items, locks tax rates at creation
- [ ] Invoice list — `/<company>/invoices` (filter by status, date, customer)
- [ ] Invoice detail — line items, payment history, balance due, send/resend
- [ ] Invoice PDF generation — branded ReportLab (same approach as Phase 0)
- [ ] Send invoice — email to all accepts_billing contacts, stay on invoice after sending
- [ ] Void invoice with confirmation
- [ ] **Schema note:** payment → payment_invoice_applications junction table needed
      (one payment can cover multiple invoices — confirmed from SF screenshot)
- [ ] Job deposits table (prepayments tied to job, not invoice)

### Payment Recording
- [ ] Inline modal on invoice detail (never navigates away)
- [ ] Amount, date, payment method, reference number
- [ ] One payment → multiple invoices (apply payment across open invoices)
- [ ] Balance updates in place, "Invoice Paid!" celebration state
- [ ] "Next Unpaid Invoice →" link after payment recorded

### Billing Page — Full Version
- [ ] Right sidebar aging summary (large colored amounts):
      Grand Total, Past Due, 91+ days, 61-90, 31-60, 1-30, Current
- [ ] Tabs: Unpaid, Paid, All Invoices
- [ ] "Sent" indicator per invoice (was it emailed?)
- [ ] Batch PDF statement generation
- [ ] Batch Outlook/email integration
- [ ] Delinquent Account filter

### Receive Payments Page
- [ ] `/<company>/billing/receive-payments`
- [ ] Customer-grouped expandable list (customer → open invoices)
- [ ] Inline payment modal per invoice

### Create Invoices Page
- [ ] `/<company>/invoices/create`
- [ ] Customer-grouped list of completed-but-uninvoiced jobs
- [ ] Expandable per customer, batch invoice creation

### Compliance Portal Exports
- [ ] `/<company>/compliance` — OPS/VendorCafe/Paymode batch submissions
- [ ] customer_compliance_portals table (already created in migration 003)
- [ ] OPS Excel export (get template from servicerequests@opstechnology.com)
- [ ] VendorCafe export (get format from Yardi VendorCafe vendor support)
- [ ] Paymode export (lower urgency)
- [ ] Portal status tracking per invoice (pending/submitted/accepted/rejected)

### Tax Report — Full Version
- [ ] `/<company>/reports/tax` — NC cash-basis from live FieldKit data
- [ ] Replaces Phase 0 two-Excel-file workflow entirely
- [ ] Payment date (not invoice date) determines reporting period

### Alerts
- [ ] Uninvoiced job alerts: 1-hour grace after completion → office alert
- [ ] 5PM escalation: uninvoiced jobs still open → email + SMS to manager

---

## 🟢 Phase 6 — Mobile App
*Milestone: Techs use FieldKit on phones. GPS reminders. Photo upload.*

- [ ] PWA (Progressive Web App) — accessible on mobile browser alongside Phase 4-5
- [ ] Tech job list (own jobs only for today)
- [ ] Work order detail (mobile-optimized)
- [ ] Status updates: On My Way, Start Job, Complete Job
- [ ] GPS-triggered reminders (10-minute grace periods):
      arrive at property → prompt to start; leave without completing → reminder
- [ ] Completed + uninvoiced alert: 1-hour grace → office; 5PM → manager
- [ ] Soft block: can't open next job without submitting completion notes
      (dismissible with one tap)
- [ ] Before/after photo upload (target 2-5 sec vs SF's ~30 sec)
- [ ] Clock in/out for hours report
- [ ] Water extraction mobile view: quick-tap Wet/Ready/Retrieved
- [ ] React Native app (iOS + Android) after PWA validated
- [ ] Unlisted App Store distribution for field crews

---

## 🔵 Configurability Layer (Pre-LKit / Pre-Franchise Onboarding)
*Build after Phase 5 is in production for internal companies.*
*Required before offering FieldKit to external Get a Grip franchises or LKit customers.*

These are all the **[CONFIGURABLE LATER]** items consolidated:

- [ ] Company Preferences page (SF-style: timezone, currency, date formats,
      default payment terms, invoice/job number sequences, notification toggles,
      SMS templates, signature block content)
- [ ] Role management page (add/edit/delete custom roles beyond the 5 hardcoded ones)
- [ ] Status management page (add/edit/delete job and estimate statuses with colors)
      Currently hardcoded: Scheduled, On The Way, In Progress, Completed, Invoiced,
      Cancelled, Extraction Active, No Charge
- [ ] Catalog management UI (currently seeded from SF export; needs full add/edit/deactivate)
- [ ] Tag management UI (currently hardcoded starter set)
- [ ] Payment method management UI
- [ ] Tax settings full UI (currently NC-hardcoded)
- [ ] Email settings page (trigger toggles, from address, template customization)
- [ ] Service rate tiers (Regular, Member, Add-On, Premium, Value, Afterhours — per SF)
- [ ] Customer communication preferences (confirmations, status updates, receipts)
- [ ] Document templates (estimate, work order, invoice — per-company branding)

---

## 🔵 Data Quality & Remediation
*Build before full staff onboarding.*

- [ ] Customer merge — HIGH PRIORITY. Side-by-side preview, soft-delete source,
      audit note. SF has this on the edit page.
- [ ] Duplicate detection — flag at creation time based on name/address similarity
- [ ] Audit trail — every create/edit/delete logs user + timestamp
- [ ] Bulk status correction
- [ ] Job reassignment (move job to correct customer)
- [ ] Contact deduplication
- [ ] Address validation via API (Google/SmartyStreets)
- [ ] Import conflict resolution (re-import from SF surfaces conflicts vs overwriting)
- [ ] Undo recent actions (30-min window for admins)
- [ ] Data retention: soft-deleted records purged after 1 year (nightly job)

---

## 🔵 Activity Feed (Phase 5+)
*Requires job/invoice data to exist.*

The SF customer detail page has a right-sidebar Activity Feed showing all events
chronologically: invoice payments received, invoices emailed, jobs invoiced,
emails sent with content preview, new jobs created.
FieldKit currently has customer notes. The full activity feed pulling in
job/invoice/payment events should be added to customer detail in Phase 5
once those entities exist.

---

## 🤖 AI Features (Post Local LLM Infrastructure)
*Requires PowerEdge R730/R740 + NVIDIA A40 48GB inference server.*

- [ ] NC tax rate monitor (n8n → LLM reads NC DOR → proposes updates for approval)
- [ ] Natural language report building
- [ ] Email drafting (AI-assisted customer responses)
- [ ] Double-booking detection
- [ ] n8n quality control layer (scheduling, billing completeness, invoice data quality)
- [ ] Outlook email triage via Microsoft Graph API
- [ ] Business card scanning → OCR → contact import (Chris O)

---

## Session Notes — June 9, 2026

### Completed this session:
- Customer data imported for CTS (903) and Kleanit Charlotte/SF (3,013 + 61)
- Duplicate customers cleaned up on Get a Grip (1,147 soft-deleted)
- import_sf_customers.py updated: Docker connection, FL auto-split, duplicate detection
- User management page built (user_list.html + user_form.html)
- Office role added to all 4 databases and app.py
- Navigation bar added to base.html (role-aware, active page highlighting)
- Billing contacts display replaces legacy billing_email field on customer detail
- Customer search upgraded to live AJAX with ILIKE partial matching
- SF screen analysis documented in docs/sf-reference/SF_SCREEN_ANALYSIS.md
- OPNsense firewall alias updated to include port 3100

### Key decisions made:
- **Hardcoded first, configurable later** — build for 4 internal companies now,
  add configurability layer before LKit/franchise onboarding
- **Global search** — Enter-key submission, no live preview, results by entity type
- **All list page searches** — live AJAX pattern (established this session)
- **One payment → multiple invoices** — junction table needed before Phase 5
- **Office role** sits between manager and salesperson: billing/customers/reports access,
  no user management or settings changes

### Infrastructure notes:
- Port 3100 added to OPNsense FIELDKIT_PORTS alias (VLAN20→VLAN70 rule)
- Password reset via CLI: generate hash to file first to avoid shell escaping issues

---

*Master blueprint: FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md*
*SF reference: docs/sf-reference/SF_SCREEN_ANALYSIS.md*
*Stack reference: FIELDKIT_STACK_REFERENCE.md*
