# FieldKit — Build Directive: Complete the Web Platform
*Issued: September 18, 2026 · Owner: Chris Letize · Repo: chrisletize/fsm-system*
*Audience: the Claude Code instance running on ubuntu-business in tmux session `fieldkit`.*

---

## 0. Read this first

You are finishing FieldKit — the Flask/PostgreSQL field-service platform that replaces
ServiceFusion for four companies (Get a Grip Charlotte, Kleanit Charlotte, CTS of Raleigh,
Kleanit South Florida). This directive is the single authoritative work plan. It was written
against the repo at commit `d3e1bcd` (2026-09-14) and every design document in `docs/`.
Where this directive and an older design doc disagree, **this directive wins**, and the
disagreement is recorded in `FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md` (the companion file).

**Scope:** everything in the web platform. **Out of scope:** the Phase 6 native/PWA mobile
app, GPS/visit monitoring, after-hours capture, photo upload, business-card OCR, QuickBooks,
card processing, LKit multi-tenant configurability, AI/LLM features. Where a web feature
depends on a mobile feature, the web feature is built with an office-side manual path and
the mobile hook is left as a clearly-commented stub.

**Goal state:** Michele can run the entire customer → work order → dispatch → invoice →
payment → statement/tax-report cycle in FieldKit and retire the Phase 0 statements site.
Chris O can run his prospect pipeline. Dispatchers schedule everything in FieldKit.

### 0.1 Documents you must read before writing any code
In this order (all in the repo):
1. `CLAUDE.md` — architecture invariants (DB-per-company, decorator stack, soft delete, restart vs rebuild).
2. `docs/FIELDKIT_STACK_REFERENCE.md` §3–§5 — drift check and debugging tree.
3. `docs/FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` — the master blueprint (superseded in places; see §0.3).
4. All five `docs/FIELDKIT_DESIGN_ADDENDUM_*.md` — catalog/equipment, worksite/double-booking, duration/rating, reconciliation framework, mobile after-hours (last one for context only).
5. `docs/FIELDKIT_SONNET_TASK_invoice-hardening-and-revision.md` (if present) and migrations `006`–`008`.
6. `docs/SALES-SYSTEM.md` — Phase 3 sales CRM spec.
7. `docs/FIELDKIT_PLANNING_MAY2026.md` §1 — compliance portals.
8. `docs/FIELDKIT_REUSABLE_BRICKS.md` — the UI bricks you must reuse (autocomplete, restricted combobox, Enter policy, line-item editor pattern).
9. `phase1/fieldkit_backend/app.py` in full. It is ~3,250 lines. Read all of it once; it is the ground truth for what exists.

### 0.2 What actually exists today (verified against the repo, not the docs)
| Area | State |
|---|---|
| Auth, RBAC, company-in-URL multi-tab, branding | Built |
| Customers: list/search/detail/new/edit, contacts (with billing flags), service locations, custom fields, notes | Built |
| Users: list/new/edit/reset-password/toggle-active/email reset via Resend | Built |
| Catalog CRUD (`billing_behavior`, `estimated_minutes`, `invoice_label`, min-qty/increment), equipment registry CRUD | Built |
| Work orders: list/search/new/edit/detail/delete, two-row-type line items, per-day equipment accrual (manual deployed/retrieved bridge), `work_site_label`, auto-description, double-booking banner, status history, tech assignment (username-keyed) | Built |
| Billing page | **Minimal v1 only** — customer list with billing-contact readiness + CSV export. No balances, no aging, no statements. |
| `tax_rates` table (NC 100 counties; FL empty) | Built (migration 006/006b). **No `/settings/tax` UI.** Not effective-dated. |
| Invoice engine | **Backend only, single-table.** `invoices`/`invoice_line_items`/`invoice_status_history` (007), credit stamp columns (008), `_next_invoice_number`, `_compute_invoice_tax`, `_resolve_equipment_labels`, `transition_invoice()` with Live↔Hardened↔Sent→Paid, Sent/Paid→Void, Void→Live reissue. **No routes, no templates, no create-from-work-order, no revision, no payments.** Zero invoice rows exist in production. |
| `customer_compliance_portals` table | Built (003). **No UI.** |
| Dispatch board, extraction queue, reports, estimates, sales CRM, company settings, payment methods, tax settings, tags, dashboard stats | **Not built** |
| Statements site (Phase 0, `~/docker/statements`, port 3100) | Separate stack. **Do not modify it under this directive.** Michele relies on it daily until cutover. |

### 0.3 Superseded design points (do not build these as originally written)
- **Work order tags** (design v2 §2) → not built, concept replaced. See §3.4 for what replaces each starter tag.
- **"Unit Number" catalog item** → replaced by `work_orders.work_site_label` (already built).
- **`item_type` service/product** → replaced by `billing_behavior` (already built).
- **Extraction auto-roll by duplicating work orders nightly** (design v2 §8) → replaced by the single-work-order accrual model in §3.2. Do not clone work orders.
- **Single-table invoices with `amount_paid`/`state='Paid'`** (migration 007) → replaced by the receivable/version split in §2.2. `Paid` is derived, never stored.
- **Stored `balance_due`** (design v2 §11) → never stored; always derived.
- **Dispatch board as React/DnD Kit** → vanilla JS, no build step (§3.1).
- **Outlook/PowerShell email drafts** → Resend API from the app (§2.7), with PDF download as the manual fallback.

---

## 1. Standing rules for this build

### 1.1 Environment
- Live stack: `~/docker/fieldkit-prod/` on ubuntu-business (10.83.70.10). Containers `fieldkit-prod-app-1` (port 3000) and `fieldkit-prod-db-1` (postgres:16). Code is bind-mounted from `~/docker/fieldkit-prod/fsm-system/phase1/fieldkit_backend` → `/app`.
- `docker compose restart app` after `.py`/`.html` edits. `docker compose up -d --build app` only after `requirements.txt`/Dockerfile changes (you will need this in Stage 1 when adding ReportLab and openpyxl).
- Migrations live in `phase1/fieldkit_phase1/database/migrations/`. Next number is **009**. Every migration header states which databases it applies to; every migration is idempotent (`IF NOT EXISTS`). Apply to all four DBs unless the header says otherwise. Verify with a row/column check on each DB before moving on.
- DB names: `fieldkit_getagrip`, `fieldkit_kleanit_charlotte`, `fieldkit_cts`, `fieldkit_kleanit_sf`. Company keys in code: `getagrip`, `kleanit_charlotte`, `cts`, `kleanit_sf`. Prefixes: GAG / KC / CTS / KSF.
- **Before every migration:** `pg_dump` all four DBs to `~/db-backups/<date>/`. Never run `docker compose down -v`. Never `DROP` a table that has rows without an explicit go-ahead from Chris.
- VLAN70 cannot initiate connections to RFC1918 addresses. You cannot reach the NAS or ubuntu-services from this VM. GitHub, PyPI are reachable.
- The `users` table is replicated across all four DBs via `write_to_all_dbs()`; user references everywhere are by `username`, not `id`. Verify this at Stage 0 (CLAUDE.md contains a contradictory note; resolve it and fix CLAUDE.md).

### 1.2 Code conventions (non-negotiable)
- `app.py` stays a single monolith. Add new sections with the same banner-comment style already used. No modularization pass now.
- Raw SQL via `psycopg2`, `RealDictCursor`, `get_db_connection(company_key)`. No ORM. Every UI `SELECT` filters `deleted_at IS NULL`.
- Route decorator order: `@app.route` → `@login_required` → `@company_access_required` → `@with_branding` (skip `with_branding` on JSON endpoints). Inline role checks per the permissions matrix (design v2 Part Six; §5 below).
- Soft delete only (`deleted_at`/`deleted_by`). Status/lifecycle changes are never deletes.
- Every new lifecycle table gets an append-only `*_status_history` table, same shape as `work_order_status_history`.
- Numbering: `PREFIX-YYYY-####` derived from `MAX()` within year, UNIQUE constraint as the real guarantee. Reuse the existing helper pattern.
- Reuse the bricks: Brick #1 (suggest autocomplete), Brick #2 (restricted combobox), Brick #3 (Enter policy), the two-row-type line-item editor, the auto-generated-editable description pattern, normalized-duplicate detection. Do not write a second autocomplete.
- Templates extend `base.html`. Company branding via the existing CSS variables. Tables for lists, two-column detail pages (main 70% / sidebar 30%), modals for small actions, toasts for confirmations, breadcrumbs on every detail page. Keep the existing visual language — the final aesthetic pass is a separate future session with Chris.
- **After every action, return to the context record, never to a list page** (design v2 Part Four). This is a hard UX rule.
- No new JS frameworks, no bundler, no npm. Vanilla JS in `base.html`/per-template `<script>` blocks. CDN-free (the app is used on-site; assume it may be reached without internet at times).
- Money: `NUMERIC(12,2)`. Rates: `NUMERIC(5,3)`. Dates: `DATE` for business dates, `TIMESTAMP` for record times. Store both effective time and record time wherever the reconciliation framework's Pattern 4 applies.
- Never put a `company_id` column on anything.

### 1.3 Working protocol
- **Work in the order of §2 → §3 → §4 → §5 → §6.** Within a stage, build in the numbered increments. Each increment ends with: migration applied to all 4 DBs (if any) → code written → `docker compose restart app` → `curl` the new routes (302 to login proves the import is clean) → a rollback-safe Python smoke test run inside the app container against `fieldkit_getagrip` → Jinja render test for new templates → git commit with a descriptive message → push.
- Smoke-test convention: a script under `phase1/fieldkit_backend/tests/smoke_<feature>.py` that opens a connection, runs the increment's operations inside a transaction, asserts, then `ROLLBACK`s. Keep these; they are the regression suite. Run all of them before each stage commit.
- **Maintain three files continuously:**
  - `docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md` — rewrite at Stage 0; update at the end of every stage. Short, factual, dated.
  - `docs/BUILD-LOG-2026-09.md` — one dated entry per increment: what was built, migration number, commit hash, smoke result, anything deferred.
  - `docs/DECISIONS-MADE-DURING-BUILD.md` — every choice you made that Chris did not explicitly specify (see §1.4). Number them `D-###`. Chris reviews this after the build.
- **Asking Chris.** He is reachable through the Remote Control session from his phone. Ask only when an answer changes what you build *and* you cannot make a reasonable, reversible default. Batch questions; don't block on non-essential ones — pick a default, tag it `[DEFAULTED]` in the decisions file, and keep going. Use `[ESCALATE]` in the chat for anything that risks data or money. Questions marked **ASK** in this directive are the ones worth asking up front, in one batch, at the start of the relevant stage.
- Do not touch `~/docker/statements/` or `backend/api/` (Phase 0) except for the read-only data import in §2.9.
- Commit at least once per increment. Never leave the working tree dirty overnight.

### 1.4 What counts as a decision you must log
Any of: a column or table not in a design doc; a default value; a label/wording choice on a user-facing screen; a validation rule; an ordering/sort rule; a permission not in the matrix; a behavior where two docs disagreed; anything marked `[DEFAULTED]`. One line each: `D-041 — Invoice PDF footer shows company phone + email; no remit-to address because company_settings.remit_to_address is empty for all four companies.`

---

## 2. STAGE 1 — Finish invoicing & billing (Phase 5). Highest priority.

Everything in this stage hangs off the receivable/version model. Build the model first; do not build routes against the old single-table shape.

### 2.1 Increment 1.1 — Effective-dated tax rates + `/settings/tax`
**Migration 009** (all 4 DBs):
- `tax_rates`: add `effective_from DATE NOT NULL DEFAULT '2000-01-01'`, `effective_to DATE NULL`. Drop `UNIQUE(county)`; add `UNIQUE(county, effective_from)`. Existing rows keep `effective_from = '2000-01-01'`. Insert a second Mecklenburg row: 7.25% (4.75/2.00/0.50) `effective_from '2000-01-01'`, `effective_to '2026-06-30'`, and set the existing 8.25% row to `effective_from '2026-07-01'`. Version the whole row — NC changes county and transit components independently.
- `_compute_invoice_tax()` takes an `as_of` date and selects the row where `effective_from <= as_of AND (effective_to IS NULL OR effective_to >= as_of)`. Anchor on `invoice_date`.
- `company_settings` table (single row per DB; create it here because tax needs it): `id`, `company_name`, `legal_name`, `address`, `address_2`, `city`, `state`, `zip`, `phone`, `email_from_name`, `email_reply_to`, `alert_email`, `default_tax_county`, `tax_exempt_by_default BOOLEAN DEFAULT FALSE`, `state_base_rate NUMERIC(5,3)`, `business_hours_start TIME DEFAULT '08:00'`, `business_hours_end TIME DEFAULT '17:00'`, `remit_to_text TEXT`, `invoice_footer_text TEXT`, `logo_filename`, audit columns. Seed one row per DB from `branding.py`/existing knowledge; leave unknowns NULL and note them.

**Routes:** `/<company>/settings/tax` (list rates with effective ranges, filter active-as-of-today), `/settings/tax/new`, `/settings/tax/<id>/edit`, `/settings/tax/<id>/end` (sets `effective_to`; the UI enforces "to change a rate, end the old row and add a new one" — never edit the pct on a row that any hardened invoice has used). Admin only. Show the NC cash-basis rule as a help note on the page.
**Routes:** `/<company>/settings/company` (edit the `company_settings` row; admin only). Add both to the settings nav.

**ASK Chris (batch, start of Stage 1):** Florida sales tax treatment for Kleanit SF (nonresidential cleaning services are taxable in FL; residential are not) — what rate table does he want seeded, if any? Default: leave FL table empty, `tax_exempt_by_default = TRUE` for `kleanit_sf`, and let the settings page fill it later.

### 2.2 Increment 1.2 — Receivable/version refactor (the July 22 decision)
This is the largest structural change. Zero invoice rows exist, so it is a schema rebuild, not a data migration.

**Migration 010** (all 4 DBs):
```
invoices  (the RECEIVABLE)
  keep: id, invoice_number, work_order_id, customer_id, service_location_id,
        invoice_date, notes, audit columns
  add:  receivable_state VARCHAR(10) NOT NULL DEFAULT 'open'  CHECK IN ('open','void')
        current_version_id INTEGER  (FK to invoice_versions, added after that table exists)
        source VARCHAR(20) NOT NULL DEFAULT 'fieldkit'  CHECK IN ('fieldkit','sf_import')
        voided_at, voided_by, void_reason   (keep)
        reissued_as_invoice_id INTEGER REFERENCES invoices(id)   (rename of superseded_by for void→reissue)
        reissue_of_invoice_id INTEGER REFERENCES invoices(id)
        portal_id INTEGER REFERENCES customer_compliance_portals(id)
        portal_status VARCHAR(20) CHECK IN ('pending','submitted','accepted','rejected')
        portal_submitted_at TIMESTAMP, portal_submission_notes TEXT, wtn_po_number VARCHAR(100)
  drop: revision_number, state, subtotal, tax_county, tax_rate_pct, tax_total, total,
        amount_paid, hardened_*, sent_*, supersedes_invoice_id, superseded_by_invoice_id,
        credit_amount, credit_status, credit_opened_at
  UNIQUE (invoice_number)   -- numbers are per-receivable now

invoice_versions  (immutable PRESENTATIONS)
  id, invoice_id NOT NULL FK, revision_number INTEGER NOT NULL DEFAULT 0,
  state VARCHAR(12) NOT NULL DEFAULT 'Live' CHECK IN ('Live','Hardened','Sent','Superseded'),
  subtotal, tax_county, tax_rate_pct, tax_total, total  (NULL until harden except subtotal),
  hardened_at/by, sent_at/by, sent_to_emails TEXT,
  superseded_at, superseded_by_version_id FK,
  revision_reason TEXT, notes_to_customer TEXT, internal_notes TEXT,
  pdf_filename VARCHAR(255),
  audit columns
  UNIQUE (invoice_id, revision_number)

invoice_version_line_items
  as 007's invoice_line_items but version_id NOT NULL FK (drop invoice_id)

invoice_status_history
  add version_id INTEGER NULL, from_state VARCHAR(12), to_state VARCHAR(12),
      subtotal_delta NUMERIC(12,2), tax_delta NUMERIC(12,2), effective_date DATE
  (receivable-level events: version_id NULL; revision events carry the dated deltas)
```
Drop `invoice_line_items` (empty). Migration 008's credit columns go away here; see §2.4 for where credits live now.

**`transition_invoice()` — one function, two levels.** Signature stays `(cur, company_key, invoice_id, to_state, username, notes=None) -> (ok, reason, extra)`. The receivable id is always the handle; the function operates on `current_version_id`. Legal `to_state` values and what they do:

| to_state | Level | Guard | Effect |
|---|---|---|---|
| `Hardened` | version | current version is Live; every per-day equipment line has `retrieved_at` | freeze subtotal, tax (as-of `invoice_date`), totals; bake ordinals into `resolved_label`; set `hardened_at/by` |
| `Live` (reopen) | version | current version is Hardened or Sent; **no non-reversed payment application exists on this receivable** | clear frozen fields (write prior totals into history notes first, as today); clear `resolved_label` |
| `Sent` | version | current version is Hardened | set `sent_at/by`, `sent_to_emails` |
| `Void` | receivable | receivable open; **no non-reversed applications** (UI must unapply first, §2.4) | `receivable_state='void'`, `voided_*`; current version state unchanged (it stays as evidence) |
| `Reissue` | receivable | receivable is void and not already reissued | mint a NEW receivable with a new number + a Live rev 0 whose lines are **cloned** from the void receivable's current version; link both directions; return `{'new_invoice_id'}` |
| `Revise` | version | current version is Sent | mark current `Superseded`; insert new version `revision_number+1`, state Live, lines cloned, `revision_reason` required; set `current_version_id`; history row carries `effective_date = today` and (once re-hardened) `subtotal_delta`/`tax_delta` vs the superseded version — write the deltas at the *harden* of the new version, on that version's history row |

Remove `'Paid'` and `'Revision'` from the state enums. **Display status** is a derived helper `invoice_display_status(receivable, version, balance)` → `Draft` (Live), `Hardened`, `Sent`, `Partially Paid`, `Paid`, `Void`. Store nothing.

**Balance helper:** `invoice_balance(cur, invoice_id)` = current version `total` (or `subtotal` if not yet hardened) − Σ non-reversed `payment_applications.amount` − Σ `invoice_adjustments.amount`. One function, used everywhere. Add a SQL view `v_invoice_balances` with the same math for list pages and the billing page.

Update `_resolve_equipment_labels`, `_reissue_invoice` (now a clone-to-new-receivable), `_next_invoice_number` (revision no longer shares numbers; only receivables consume numbers) accordingly. `INVOICE_TRANSITIONS_IMPLEMENTED` gate flag: keep the pattern; all edges above are implemented by the end of this increment.

**Smoke test must cover:** harden with an accruing equipment line is rejected; reopen after an application is rejected; revise → new Live version cloned, old marked Superseded, `current_version_id` moved; reissue mints a new number; hardened snapshot unchanged after editing the source work order; ordinals: 1 unit → bare label, 3 units → 1..3.

### 2.3 Increment 1.3 — Create invoice from work order + invoice UI
**Routes:**
- `POST /<company>/workorders/<id>/invoice/new` → creates receivable + rev 0 Live version, snapshots WO line items (standard: qty × price; per-day equipment: `deployed_at`, `retrieved_at`, quantity = billable days if retrieved else NULL), copies `tax_county` from the WO's service location (fallback customer `tax_county`, fallback `company_settings.default_tax_county`), applies the three-layer exemption (item → customer `is_taxable` → location), sets WO `status='Invoiced'` + status history, redirects to invoice detail. Guard: WO must be `Completed`, `No Charge` is refused ("no-charge work orders are not invoiced"), one invoice per WO (a second request redirects to the existing one with a flash). Single-WO invoices only; multi-WO batching is deferred (`[DEFAULTED]`).
- `GET /<company>/invoices` — list: number, customer, date, display status, total, balance, portal status; filters: status, customer, date range, "with balance only"; live search like work orders.
- `GET /<company>/invoices/<id>` — detail (two-column). Main: line items of the current version (live ordinals rendered via the resolver), totals, revision history (all versions, superseded ones view-only), payments applied, adjustments, status timeline. Sidebar: customer/WO/location links, actions gated by state: Edit (Live only), Harden, Reopen, Send, Record Payment, Revise, Void, Reissue, Download PDF, Portal panel.
- `GET/POST /<company>/invoices/<id>/edit` — Live version only: edit description/qty/price/taxable per line, `notes_to_customer`, `invoice_date`, `tax_county`. Reuse the line-item editor. No adding lines that aren't from the catalog. A "Regenerate from work order" button re-snapshots lines (confirm dialog).
- `POST .../harden`, `.../reopen`, `.../send`, `.../void` (reason required), `.../reissue`, `.../revise` (reason required) — all call `transition_invoice()`. Routes stay dumb.
- Work order detail: when status is `Completed` and no invoice exists, show the prompt banner "Generate invoice now? [Create Invoice] [Do Later]"; when "Do Later", the yellow "not invoiced yet" banner. When invoiced, "View Invoice" link. Work order edit form: when status changes to `Completed` on save, redirect to detail with the prompt.
- Customer detail: add an **Invoices** tab (all receivables, balance, status) and **Jobs** tab (work orders), if not already present in that shape.

Permissions: admin/manager create/edit/transition; salesperson and technician cannot see invoices.

### 2.4 Increment 1.4 — Payments, applications, adjustments, credits
**Migration 011** (all 4 DBs):
```
payment_methods: id, name, requires_reference BOOLEAN, sort_order, is_active, audit
  seed: Check(ref req), Credit Card, Paymode-X(ref req), ACH(ref req), Cash, Other
payments: id, customer_id NOT NULL, payment_date DATE NOT NULL (effective; the cash-basis date),
  amount NUMERIC(12,2) NOT NULL CHECK > 0, payment_method_id, reference_number, notes,
  status VARCHAR(12) NOT NULL DEFAULT 'received' CHECK IN ('received','voided'),
  voided_at, voided_by, void_reason, refunded_amount NUMERIC(12,2) DEFAULT 0,
  refunded_at, refund_reference, refund_notes, audit
payment_applications: id, payment_id NOT NULL, invoice_id NOT NULL, amount NUMERIC(12,2) NOT NULL,
  applied_date DATE NOT NULL, reverses_application_id INTEGER NULL REFERENCES payment_applications(id),
  reason TEXT, created_at, created_by      -- APPEND ONLY. No updated_at, no deleted_at.
invoice_adjustments: id, invoice_id NOT NULL, effective_date DATE NOT NULL,
  amount NUMERIC(12,2) NOT NULL (positive reduces balance),
  adjustment_type VARCHAR(20) CHECK IN ('write_off','discount','late_fee','other'),
  reason TEXT NOT NULL, audit (soft-delete allowed only while created today by same user — otherwise reversal row)
payment_status_history: id, payment_id, event, changed_by, changed_at, notes
```
Rules:
- A payment is recorded **against a customer**, then applied to one or more open receivables. Recording from an invoice page pre-selects that invoice and pre-fills the balance. Over-application is rejected (application amount ≤ remaining balance and ≤ unapplied payment amount).
- Un-apply = insert a reversal row (`reverses_application_id`, negative amount). Never update or delete an application.
- Void a payment (bounced check) = status `voided` + reversal rows for all its active applications. Reason required. Loud.
- **Unapplied amount on a payment = credit.** There is no separate credits table. Unapplied money is the structured representation of every credit in the system, including the "Paid invoice was voided" case (void requires un-applying first, which leaves the payment unapplied). Dispositions: **Apply** to another open receivable; **Refund** (`refunded_amount`, reference, date); **Write off** — not allowed on a payment; a customer who is owed money is refunded, not written off. Balances owed to the company are written off via `invoice_adjustments`.
- Every page that shows a customer (customer detail, billing page, invoice detail, work order form) shows a red "Unapplied credit $X — resolve" badge when the customer has any. The billing page has an "Open credits" panel at the top. Credits are never quiet.
- `Paid` display status when balance = 0 and at least one application exists. `Partially Paid` when 0 < balance < total.

**UI:** "Record Payment" is an inline modal on invoice detail (never navigates away). After save: toast; if paid in full, the celebration toast + "Next Unpaid Invoice →" link (next open receivable with balance for the same customer, else company-wide by oldest date). Payment detail page `/<company>/payments/<id>` (applications, reversals, void/refund actions). Payments list `/<company>/payments` (date range, method, customer, unapplied-only filter). Customer detail: Payments tab.

### 2.5 Increment 1.5 — Invoice PDF
- Add `reportlab` (pin the version the statements stack uses) and `openpyxl` to `requirements.txt`; rebuild with `--build`.
- `generate_invoice_pdf(company_key, version_id) -> bytes`, ReportLab, branded per company using `company_settings` + the existing logo files under `static/`. Layout: company block, "INVOICE" + number (+ "Rev N" when `revision_number > 0`), invoice date, due date (`invoice_date + payment_terms` days; parse "Net 30"/"Net 15"/"Due on Receipt"), customer + service location + work-site label, PO/WTN, line table (customer-facing label = `resolved_label` if hardened else live-resolved, description, qty, unit, price, total), subtotal, tax line with county + rate, total, payments applied, balance due, `notes_to_customer`, `invoice_footer_text`, `remit_to_text`. Per-day equipment lines show the machine-day math in the description ("3 units × 4 days") and never a registry unit name.
- Water-extraction invoices: if any per-day line exists, include a short "Drying & monitoring process" paragraph from `company_settings.extraction_explainer_text` (add the column; seed a sensible default paragraph; `[DEFAULTED]`).
- Store nothing on disk permanently; generate on demand. `GET /<company>/invoices/<id>/pdf` (current version) and `/<company>/invoices/<id>/versions/<vid>/pdf`. A hardened/sent version's PDF must be reproducible byte-for-byte from the snapshot — do not read the work order or catalog when rendering a hardened version.

### 2.6 Increment 1.6 — Statements (replaces Phase 0 statement generator)
- `generate_statement_pdf(company_key, customer_id, as_of_date) -> bytes`: all open receivables with balance > 0 (and unapplied credits, shown as negatives with a note), aged from **invoice date** (Net 30 assumption, per the AR aging spec) into Current (0–30) / 31–60 / 61–90 / 90+, totals row, company branding, remit-to text. Match the visual of the Phase 0 statement (`scripts/generate_pdf_statement.py`) closely — Michele's customers know it.
- Batch: `POST /<company>/billing/statements` with selected customer ids → ZIP of PDFs (filenames sanitized — no `*` from Kleanit names). Record `last_statement_at` per customer (add column to `customers`, migration 012).

### 2.7 Increment 1.7 — Email delivery (invoices & statements)
- Use the existing Resend integration (`resend` package, `noreply@cletize.com` verified). From name = `company_settings.email_from_name`, reply-to = `email_reply_to`. Recipients = customer contacts with `accepts_billing` (invoices) / `accepts_statements` (statements), plus any addresses added in the send dialog. Attach the PDF. BCC `company_settings.email_reply_to` so the office has a copy (`[DEFAULTED]`).
- Send dialog (modal): shows resolved recipients with checkboxes, editable subject (default `Invoice GAG-2026-0042 from Get a Grip Charlotte`), short editable body template stored in `company_settings.invoice_email_template` / `statement_email_template` with `{customer}`, `{number}`, `{total}`, `{balance}` placeholders. On success: `transition_invoice(..., 'Sent')` with `sent_to_emails`, toast "Invoice sent to …". A customer with no billing contact: the dialog blocks with "Add a billing contact" link to the contact form (returns here after).
- Log every send in `email_log` (migration 012): company-local table `id, kind ('invoice'|'statement'|'estimate'|'alert'), related_id, to_emails, subject, resend_message_id, status, error, sent_at, sent_by`.
- Batch send from the billing page: `POST /<company>/billing/send-statements` — sends to each selected customer's statement contacts; summary page of sent/failed/skipped-no-contact.
- If `RESEND_API_KEY` is missing in the container env, the send actions render disabled with an explanatory note rather than 500.

### 2.8 Increment 1.8 — Billing page (full) + A/R aging report + compliance
**Billing page** `/<company>/billing` (replace the v1 page):
- Summary cards: total outstanding, customers with balances, count 90+.
- Aging summary strip: Current / 31–60 / 61–90 / 90+.
- Filter bar: all/with-balance-only/delinquent-only/no-billing-contact/portal-billed, search.
- Table: checkbox, customer (red flag if delinquent = any receivable 60+ days past invoice date; tooltip shows oldest), billing contact + emails, four aging columns, total due, last statement, unapplied credit, actions (View, Statement PDF, Record Payment modal pre-filtered to that customer's open receivables).
- Batch bar: Generate Statements (ZIP), Send Statements, Export CSV.
- "Open credits" panel at the top when any exist.
- Customers whose active portal enrollment has `portal_is_primary_billing` (add to `customer_compliance_portals`, migration 012) are marked "Portal billing — no direct email" and excluded from email batches by default.

**A/R Aging report** `/<company>/reports/aging`: port the spec in `FIELDKIT_SONNET_TASK_ar-aging-report.md` (root of repo) onto live FieldKit data: columns Customer, Total Due, Not Due (0–30), 30, 60, 90+, Oldest Invoice; totals row; secondary sort by 90+; per-customer drill-down of open invoices; printable per-customer detail; run date in the header. No staleness banner is needed here (data is live).

**Compliance** `/<company>/compliance` and customer-detail "Compliance Portals" section (CRUD on `customer_compliance_portals`, with `portal_is_primary_billing`). Invoice form/detail: portal panel pre-filled from the customer's enrollment(s); WTN/PO field; `portal_status='pending'` on hardened invoices for enrolled customers. Compliance page: pick portal type + date range + customers → table of pending invoices → "Generate Export" → file download + mark `submitted` with timestamp; recent submissions with status; manual accept/reject with notes. **Exporter design:** one function per portal type (`_export_ops`, `_export_vendorcafe`, `_export_paymode`) returning an `.xlsx`; all three initially emit the same generic column set (invoice number, invoice date, due date, property/client id, vendor account number, WTN/PO, work-site label, description, subtotal, tax, total) so the plumbing is real and each formatter can be corrected in one place once the exact portal templates are supplied. **ASK Chris/Michele** for the OPS Excel import template and VendorCafe field list; until then the generic layout ships and is flagged on the page ("Generic layout — portal template not yet confirmed").

### 2.9 Increment 1.9 — Cutover data import from Phase 0 (SF-era open invoices)
Michele cannot retire the statements site until FieldKit's billing page shows the money customers already owe. Build `phase1/fieldkit_phase1/import_open_invoices.py`:
- Source: a `pg_dump`/CSV of `fsm_prod.invoices` + `customers` from the statements stack. The statements DB is on the same VM (`statements-db-1` or equivalent — check `docker ps`); read from it directly with a read-only query. Do not write to it.
- For each source invoice with `invoice_total_due > 0`, matched to a FieldKit customer by normalized `customer_name` ↔ `property_name` (log unmatched to a CSV for Chris/Michele to resolve; do not create customers): create a receivable `source='sf_import'`, `invoice_number` = the SF number as-is (relax any format assumption in `_next_invoice_number` so imported numbers never collide with or advance the FieldKit sequence), one version at `revision_number 0`, `state='Sent'`, `hardened_at = sent_at = invoice_date`, a single line item "Balance carried from ServiceFusion — Job #<n>" (catalog: create an admin-category `Custom Service`-style item `Imported Balance` once per DB, non-taxable), `subtotal = total = invoice_total_due`, `tax_total = 0` (tax was already reported through the Phase 0 path; do not double-count in the FieldKit tax report — the tax report must exclude `source='sf_import'` receivables), and a payment-free balance equal to `invoice_total_due`. Kleanit FL split by `*FL*` as in Phase 0.
- Idempotent (re-run skips already-imported numbers). Dry-run mode prints counts and totals per company; Chris compares the totals against the statements site before the real run. **Do not run the real import until Chris says so.**
- The recency history (`customer_job_dates`) is imported in §4.3.

### 2.10 Increment 1.10 — NC cash-basis tax report from live data
`/<company>/reports/tax`: date range (default: last calendar month). For every non-reversed `payment_application` with `applied_date` in range (use `payments.payment_date` as the cash date; `applied_date` should equal it by default — make the modal default them equal and log a `[DEFAULTED]`), allocate the applied amount proportionally across the invoice's current version: taxable base = applied × (taxable subtotal / total), tax collected = applied × (tax_total / total), then split tax into state/county/transit/additional-county components using the version's frozen `tax_rate_pct` and the `tax_rates` row that was effective on the version's `invoice_date` (store the three component percentages on the version at harden — add `state_pct`, `county_pct`, `transit_pct` to `invoice_versions` in migration 012 so the report never has to re-look-up). Group by county; county totals box first, then per-county invoice detail (same layout as the August 2026 statements tax report rework, including Mecklenburg's 1% additional county component shown separately). Exclude `source='sf_import'`. Excel export (openpyxl) and PDF. Refunds in range appear as negative rows. Revisions: nothing special — cash basis means only money movement matters; note this in the page help text and in the decisions file for the accountant.

### Stage 1 exit criteria
- Chris can: create a WO → complete → create invoice → harden → send (email arrives with PDF) → record a partial payment → record the rest → see Paid → revise a sent invoice → void and reissue a different one → un-apply a payment → refund it. All with history rows.
- Billing page shows correct aging for imported + native receivables (dry run numbers reconciled).
- Tax report for August 2026 test data reconciles by hand for one county.
- Michele has been shown a walkthrough (Chris does this); her notes go to §7 punch list.

---

## 3. STAGE 2 — Finish scheduling (Phase 4 remainder)

### 3.1 Increment 2.1 — Tech profiles + dispatch board
**Migration 013** (all 4 DBs): `users` add `color_hex VARCHAR(7)`, `is_field_tech BOOLEAN DEFAULT FALSE`, `can_be_dispatched BOOLEAN DEFAULT FALSE`, `phone_mobile VARCHAR(20)`, `default_start_time TIME DEFAULT '08:00'`, `is_active_tech BOOLEAN DEFAULT TRUE`, `dispatch_sort_order INTEGER`. Extend the user form. Assign default colors from a fixed palette of 12 by `id % 12`.

`work_orders`: add `scheduled_start TIMESTAMP` (= `start_date` + `arrival_window_start`, maintained by the save path; keep the two source columns), `catalog_estimated_duration_hours NUMERIC(5,2)`, `duration_overridden BOOLEAN DEFAULT FALSE` (duration addendum §13). Implement the live catalog-duration total on the WO form, the override lock, and the ±15-minute non-blocking warning on save.

**Board** `/<company>/dispatch?date=YYYY-MM-DD` (default today):
- Horizontal timeline: rows = dispatchable techs (ordered by `dispatch_sort_order`, then name) plus an **Unassigned** row; columns = 30-min slots from `business_hours_start − 1h` to `business_hours_end + 2h`; each work order is a block spanning `scheduled_start` → `+ estimated_duration_hours` (min 30 min); block color = tech color; badges: priority, extraction (droplet), delinquent (red), customer rating letter (once §4.2 exists), callback (once §4.4 exists). Multi-tech WOs render on every assigned tech's row with a link icon.
- Vanilla JS drag/drop: drag block to another tech/time → `POST /<company>/dispatch/move` (JSON: wo_id, username, scheduled_start) → server re-validates → returns the re-rendered block data. Drag block edge to resize → `POST /<company>/dispatch/resize` (triggers the duration warning; response carries the warning text; client shows the [Use catalog] [Keep] banner). Click empty slot → WO create form pre-filled with tech + date/time (`/workorders/new?tech=&date=&time=`). Click block → popover (customer, description, status, tags-equivalents, tech list, buttons View / Edit / Mark Completed / Mark No Charge). Day/week toggle: week view is 7 stacked day strips per tech, read-only except click-through.
- Data endpoint `GET /<company>/dispatch/data?date=` returns JSON; the page renders client-side from it so moves don't reload.
- Tech-capacity collision (two blocks overlap on one tech's row): non-blocking red outline + banner "Overlaps with GAG-2026-0042". No auto-bump.
- Work order list gets `tech` and `date` filters; tech name on WO detail links to `/dispatch?date=&tech=`.
- Nav: Dispatch (admin, manager). Salesperson no access.

### 3.2 Increment 2.2 — Water extraction queue + accrual engine
Model (supersedes design v2 §8's clone-forward): one work order per extraction job, from set-up through retrieval.

**Migration 014** (all 4 DBs):
- `work_orders` add `is_extraction BOOLEAN NOT NULL DEFAULT FALSE` (set true automatically when any per-day equipment line is added; editable), `extraction_started_at DATE`, `extraction_closed_at DATE`, `followup_tech_username VARCHAR(100)`, `equipment_incomplete BOOLEAN NOT NULL DEFAULT FALSE`.
- `extraction_daily_log`: `id, work_order_id, log_date DATE, extraction_status (same CHECK set as work_orders.extraction_status), tech_username, notes, created_at, created_by`, `UNIQUE(work_order_id, log_date)`.
- `work_order_line_items`: `deployed_at`/`retrieved_at` already exist and remain the source of truth for billable days.

Behavior:
- Completing a WO that `is_extraction` prompts "Set equipment as active? [Yes — Start Extraction] [No — Close Normally]". Yes → `status='Extraction Active'`, `extraction_status='Drying'`, `extraction_started_at = today` (or earliest `deployed_at` if earlier — supports backdated starts), history row.
- **The WO stays one row.** `extraction_day_count` = `today − extraction_started_at` (+1), computed by the nightly job (§3.5) and on read. The dispatch board shows every `Extraction Active` WO on the follow-up tech's row (`followup_tech_username`, default = lead tech) every day at `default_start_time` as a compact "check" block, until closed. Nothing is cloned.
- Queue page `/<company>/extraction`: summary (active units, ready for pickup, missed today, day-5+ escalations), table per the design (Unit/Customer, Days Active, Last Status, Follow-up Tech, Actions), row actions: Mark Ready, Needs More Time, Missed Today, Retrieved. Batch: "Roll all Drying/Needs More Time to tomorrow" = writes today's daily-log rows with the current status for every selected WO (a no-op on dates, since nothing moves — the button exists so Michele's habit still has a target; label it "Log today's status for all"). "Generate Pickup List for Tomorrow" = PDF of Ready-for-Pickup units grouped by property then tech.
- Retrieved: sets `retrieved_at` on every open per-day line (per-line override possible in the same modal — a partial retrieval keeps the WO active), and when no open lines remain → `extraction_status='Equipment Retrieved'`, `extraction_closed_at`, `status='Completed'`, and the invoice prompt fires. Same-day set-and-pull = 1 day (already built).
- Day 5+ escalation flag on the queue; office notification via the alert email in the nightly job.
- Follow-up cleaning WO: on Retrieved, offer "Create follow-up cleaning work order" → new WO pre-filled with customer/location/site label, `parent_work_order_id` set, tagged as follow-up (`description_followup = TRUE`).
- `equipment_incomplete`: settable on the WO form ("equipment not yet confirmed") and surfaced as a red banner on the WO, the queue, and the dispatch block. Clearing it requires the equipment lines to be confirmed (any edit that saves ≥1 per-day line clears it). This is the office-side stand-in for the mobile flow.
- Retroactive/backdated extraction: the WO form allows `start_date` and per-line `deployed_at` in the past; `extraction_started_at` follows the earliest `deployed_at`. This satisfies the after-hours addendum's backdated-start requirement without any mobile piece.

### 3.3 Increment 2.3 — Day sheet, hours report, job activity report
- `/<company>/reports/daysheet?date=&tech=` — printable: per tech, ordered by `scheduled_start`: time, customer, address (Google Maps link on screen), work-site label, auto-description, notes_for_techs, status, contact phone. One page per tech; "All techs" prints all.
- `/<company>/reports/hours?from=&to=` — per tech per day: scheduled hours (Σ `estimated_duration_hours`), jobs count, completed count, extraction checks count. Add an `actual_duration_hours` column that stays blank until mobile exists; label the report "Scheduled hours" honestly.
- `/<company>/reports/jobs?from=&to=&status=&tech=&customer=` — job activity list with totals (count, invoiced total) and CSV export.
- `/<company>/reports` landing page linking tax, aging, recency, daysheet, hours, jobs.

### 3.4 Increment 2.4 — Replacements for the retired tag concept
Each starter tag becomes a first-class field or a derived badge; no `work_order_tags` tables:

| Original tag | Replacement |
|---|---|
| Callback | §4.4 callback object |
| New Customer | derived: customer has no Completed WO before this one — badge on dispatch and WO detail |
| Residential | derived from `customer_type` |
| Estimate/No-Charge | `status='No Charge'` (exists); estimates are their own object (§4.1) |
| Misc Task | `work_orders.is_internal_task BOOLEAN` (migration 014) — no customer required; the WO form gets an "Internal task" toggle that relaxes the customer requirement (customer_id becomes nullable; adjust the NOT NULL in the same migration) |
| Water Extraction | `is_extraction` (§3.2) |
| Requires Follow-Up | `description_followup` (exists) + the follow-up WO link |
| Delinquent Account | derived nightly into `customer_flags` (§3.5): `is_delinquent`, `oldest_open_invoice_date`; shown on customer detail, WO form (badge next to customer picker), dispatch block, billing page |

### 3.5 Increment 2.5 — Scheduled jobs (nightly + periodic)
No scheduler in the container. Create `phase1/fieldkit_backend/jobs.py` with subcommands, run by **host cron** under `letize` on ubuntu-business:
```
# /etc/cron.d/fieldkit  (install with sudo; document in DEPLOYMENT)
0 1 * * *    letize  cd /home/letize/docker/fieldkit-prod && docker compose exec -T app python jobs.py nightly    >> /home/letize/logs/fieldkit-jobs.log 2>&1
*/15 * * * * letize  cd /home/letize/docker/fieldkit-prod && docker compose exec -T app python jobs.py uninvoiced >> /home/letize/logs/fieldkit-jobs.log 2>&1
0 17 * * 1-5 letize  cd /home/letize/docker/fieldkit-prod && docker compose exec -T app python jobs.py eod_escalation >> ...
0 8 * * 1    letize  cd /home/letize/docker/fieldkit-prod && docker compose exec -T app python jobs.py weekly_sales_report >> ...
```
`nightly` (all 4 DBs): recompute `customer_flags` (migration 014: `customer_id PK, is_delinquent, oldest_open_invoice_date, open_balance, unapplied_credit, computed_at`), customer ratings (§4.2), `extraction_day_count`, write `extraction_daily_log` "Missed Today" rows for active extraction WOs with no log entry for yesterday, day-5+ escalation email, dormancy alerts (§4.1). `uninvoiced`: Completed WOs with no invoice and `completed_at` (add to history lookup) older than 1 h → in-app flag + one email per WO to `company_settings.alert_email` (dedupe via `alert_sent_at` column on `work_orders`). `eod_escalation`: at 5 PM, one digest email listing all still-uninvoiced completed WOs. Each job writes a `job_runs` row (`job_name, company_key, started_at, finished_at, status, summary`) so a "Scheduled jobs" panel on the settings landing page shows last run per job — that panel is how Chris knows cron is wired.

If `sudo` for `/etc/cron.d` is unavailable to you, write the crontab under the `letize` user's own `crontab -e` instead and note it.

### Stage 2 exit criteria
A dispatcher schedules a full day on the board, moves jobs, sees overlaps, prints day sheets; an extraction runs Day 1 → Day 4 → Retrieved → invoice with correct machine-days; cron jobs show last-run timestamps; a customer 61+ days overdue is red everywhere.

---

## 4. STAGE 3 — Estimates, ratings, sales CRM, callbacks (Phase 3 + designed-not-built)

### 4.1 Increment 3.1 — Estimates + public estimate request form
**Migration 015** (all 4 DBs): `estimates` and `estimate_line_items` per design v2 §9 (`estimate_number` = `PREFIX-EST-YYYY-####`; add `work_site_label`, `subtotal`, `tax_total`, `total` computed at send using the same tax path as invoices, `sent_at/by`, `sent_to_emails`, `approved_at`, `declined_reason`), `estimate_status_history`. Add FK `work_orders.estimate_id → estimates(id)` (column already exists).
Routes: list/new/edit/detail (`/<company>/estimates...`), `POST .../send` (PDF + Resend, same dialog as invoices, `status='Sent'`), `POST .../approve|decline`, `POST .../convert` → WO create form pre-filled (lines, site label, contact), sets `status='Converted'` + `converted_to_job_id` on WO save. Customer detail: Estimates tab + "New Estimate". Permissions: admin/manager/salesperson.

**Public request form** `GET/POST /request/<company_key>` (no login; branded; fields: name, email, phone, property/company, address, customer type, service wanted (checkboxes from catalog categories), description, preferred dates; honeypot field + per-IP rate limit 5/hour via an in-memory dict — no external service). Writes `estimate_requests` (migration 015: `id, name, email, phone, property_name, address, city, state, zip, customer_type, services TEXT, description, preferred_dates, source_ip, status ('new','contacted','converted','spam'), assigned_to_username, linked_customer_id, linked_estimate_id, audit`). Queue page `/<company>/estimates/requests` with actions: mark contacted / spam, "Create customer + estimate" (pre-fills both). New requests trigger an email to `alert_email`. NPM/Cloudflare already expose the app, so the URL works as soon as the route exists; Chris decides whether to link it from company websites.

### 4.2 Increment 3.2 — Customer rating system
Migration 015: `customer_ratings` per the duration/rating addendum §14. Nightly compute in `jobs.py`: base 100; payment penalty = Σ over open receivables of (days past 30 / 30, capped 4) × 5 plus 10 per receivable currently 90+; cancellation penalty = cancellation rate (Cancelled ÷ scheduled, trailing 12 mo) × 40; volume bonus = min(completed WOs trailing 12 mo, 20) × 0.5; clamp 0–100; bands A ≥90 / B 75–89 / C 60–74 / D 40–59 / F <40. Constants at the top of `jobs.py` for tuning. Manager override (delta + required note) editable on customer detail; `adjusted_letter_grade` shown as the primary badge with the algorithmic grade beside it. Badge on customer detail, WO form (next to customer picker), dispatch popover, estimates.

### 4.3 Increment 3.3 — Recency report on live data + history import
- `/<company>/reports/recency`: last service date per customer = `MAX(work_orders.start_date WHERE status IN ('Completed','Invoiced','Extraction Active'))` unioned with imported `customer_job_dates`; buckets 1–2 / 3–6 / 6–12 / 12+ months; management-company grouping; PDF + print like Phase 0.
- Migration 015: `customer_job_dates (customer_id, job_date, source, audit, UNIQUE(customer_id, job_date))`.
- `import_job_dates.py`: read the statements DB `customer_job_dates` (1,851 rows) + `customers`, map by normalized name to FieldKit customers, insert with `source='servicefusion_import'`, log unmatched. Dry-run first; Chris confirms counts.

### 4.4 Increment 3.4 — Callbacks
Migration 016: `work_orders` add `callback_of_work_order_id INTEGER REFERENCES work_orders(id)`, `callback_reason TEXT`, `callback_responsible_username VARCHAR(100)` (the tech whose original work is being corrected). WO form: "This is a callback for…" restricted combobox over the customer's prior WOs; selecting it pre-fills location/site label/lines and sets responsible = the original lead tech (editable). Callback badge on dispatch, WO list filter, customer detail. Report `/<company>/reports/callbacks?from=&to=`: by responsible tech: callback count, ratio to their completed jobs, list; per row whether the responsible tech went back themselves (unpaid visit) or another tech went (paid) — computed from `work_order_techs` vs `callback_responsible_username`. **No payroll/commission engine is built** — the report exposes the data the future commission module needs. Callback count also feeds the rating (subtract 3 per callback in trailing 12 mo; add to §4.2 constants).

### 4.5 Increment 3.5 — Sales CRM (Chris O)
Build against `docs/SALES-SYSTEM.md`, trimmed to what the web can do well:
Migration 017 (all 4 DBs): `sales_prospects`, `sales_contacts`, `contact_property_history`, `sales_visits`, `visit_tags_config` (+ seed), `approval_queue`, `dormancy_alerts_config` (+ seed: GAG 8 wk, KC 3, CTS 4, KSF 3). Use the spec's columns; `property_id/property_type` polymorphism stays as specified.
Routes under `/<company>/sales/…`: dashboard (follow-ups due today/overdue, dormant customers list computed from the recency data vs the threshold, recent visits), prospects list/new/edit/detail (with map link, visit history, contacts), contacts list/new/edit (with property history), unified property search (customers ✓ + prospects ○), **log visit** (mobile-friendly single-screen form per the spec's quick-tap layout: tag buttons, contact picker with last-contacted preselected, notes, auto follow-up date from tag, dormant-investigation checkbox + reason + "send to management"), follow-ups list, `POST convert` → `approval_queue` row; manager approval page `/<company>/sales/approvals` (approve → creates customer + contacts in one transaction, marks prospect converted, links; reject/edit with notes). `jobs.py weekly_sales_report`: Monday email to `alert_email` + all managers/admins for the company: activity summary, dormant investigations with reasons, pending approvals. Salesperson role: full access under `/sales/`, read-only customers, can create estimates; no invoices/billing/dispatch. All pages responsive (Chris O uses a tablet) — the base template already is; verify at 768 px.

### Stage 3 exit criteria
Chris O logs a visit in under a minute on a tablet; a prospect converts through approval into a real customer; an estimate is sent and converted to a WO; the Monday report arrives; ratings show on the board.

---

## 5. STAGE 4 — Dashboard, data quality, permissions sweep, help

### 5.1 Dashboard `/<company>/dashboard`
Replace the Phase 1 placeholder: today's jobs (count + link to board), uninvoiced completed WOs (loud), open extraction units, outstanding A/R + 90+, unapplied credits, follow-ups due (salesperson view), pending approvals (manager), recent activity (last 15 status-history events across WOs/invoices/payments), quick actions (New WO, New Customer, New Estimate, Record Payment).

### 5.2 Customer merge + duplicate detection
- Duplicate detection at customer create: normalized-name + normalized-address match (reuse the double-booking brick) → non-blocking banner listing matches with links.
- Merge `/<company>/customers/<id>/merge` (admin): pick target; side-by-side preview; on confirm, in one transaction re-point `customer_contacts`, `service_locations`, `customer_notes`, `customer_field_values`, `customer_compliance_portals`, `work_orders`, `estimates`, `invoices`, `payments`, `customer_job_dates`, `sales_*` references to the target; soft-delete source with `merged_into_customer_id` (migration 018) and a note on both. Log to `customer_merge_log`.

### 5.3 Audit trail
`record_audit` table (migration 018: `table_name, record_id, action, changed_by, changed_at, diff JSONB`) written by the save paths of customers, contacts, locations, work orders, invoices/versions, payments, estimates, catalog, tax rates, users (via a small helper you call after each UPDATE with before/after dicts). Read-only "History" panel on customer, WO, invoice, payment detail. Admin-only global view `/<company>/settings/audit?table=&id=&user=&from=&to=`.

### 5.4 Permissions sweep
Walk every route against design v2 Part Six plus these clarifications: `technician` role exists in the DB CHECK; give it read-only access to the day sheet for their own username and the WO detail of their own assignments (a minimal "My Day" page at `/<company>/myday`, responsive, with buttons Mark On The Way / Start / Complete that write status history — this is the office-web stand-in for mobile status updates). Everything else 403 for technicians. Verify with a smoke test that logs in as each seeded role and hits every route.

### 5.5 Settings landing + in-app help
`/<company>/settings` landing with cards for every settings page plus the scheduled-jobs panel (§3.5). Each major page gets a collapsible "?" help panel (static text in the template) describing the workflow and the reconciliation rules that apply (e.g., on invoices: why you can't edit a sent invoice, how to revise vs reissue).

### 5.6 Seeding tasks that need Chris
- Catalogs for Get a Grip, CTS, Kleanit SF are thin/empty; equipment registries for GAG/CTS/KSF are empty. Write `import_catalog.py` (CSV: name, category, billing_behavior, unit_price, unit_of_measure, estimated_minutes, is_taxable, default_description, invoice_label) and `import_equipment.py` (CSV: name, catalog item name, notes) and **ASK Chris** for ServiceFusion price-list exports; run when supplied.
- Company settings rows: ask for legal names, remit-to text, reply-to and alert emails per company. Default alert email: Chris's login email (`[DEFAULTED]`).
- Non-admin user passwords (patrick, walter, mikeyc, chriso) — reset via the existing "send reset" email when Chris says those users are onboarding.

---

## 6. STAGE 5 — Cutover readiness

1. Real run of `import_open_invoices.py` and `import_job_dates.py` after dry-run sign-off.
2. Full drift check (stack reference §3) and all smoke tests green.
3. `DEPLOYMENT/RUNBOOK.md`: restart/rebuild rules, migration procedure, backup location, cron jobs, env vars (`RESEND_API_KEY`, `APP_BASE_URL`, `SECRET_KEY`, DB creds), how to add a user, how to end a tax rate.
4. Update `CLAUDE.md` pointer table for every new doc; rewrite `CURRENT-STATUS.md`; finalize `DECISIONS-MADE-DURING-BUILD.md` and `BUILD-LOG-2026-09.md`.
5. Hand-off message to Chris: what to test first (the Stage exit criteria), what is `[DEFAULTED]`, and which **ASK** items are still open.
6. Leave the statements stack running. Retirement is Chris's call after Michele signs off.

---

## 7. Punch list (Chris adds here after testing)
*(empty — Chris will append notes; you then work them in priority order)*

---

## Appendix A — Permissions matrix (authoritative for this build)
| Capability | admin | manager | salesperson | technician |
|---|---|---|---|---|
| Customers view / create-edit / delete-merge | ✅/✅/✅ | ✅/✅/❌ | ✅/✅/❌ | own jobs' customers read-only |
| Work orders create/edit | ✅ | ✅ | ❌ | status buttons on own WOs (`/myday`) |
| Dispatch board | ✅ | ✅ | ❌ | ❌ |
| Extraction queue | ✅ | ✅ | ❌ | ❌ |
| Estimates | ✅ | ✅ | ✅ | ❌ |
| Invoices / payments / billing / compliance | ✅ | ✅ | ❌ | ❌ |
| Reports | ✅ | ✅ | recency, jobs (own), sales | day sheet (own) |
| Sales CRM | ✅ | ✅ (+approvals) | ✅ | ❌ |
| Catalog, equipment, tax rates, company settings, users, audit | ✅ | catalog & equipment only | ❌ | ❌ |

## Appendix B — Migration index for this build
009 tax effective dates + company_settings · 010 receivable/version split · 011 payments/applications/adjustments · 012 email_log, last_statement_at, version tax components, portal_is_primary_billing, extraction_explainer_text · 013 tech profile columns + WO duration columns · 014 extraction model, internal tasks, customer_flags, job_runs, alert_sent_at · 015 estimates, estimate_requests, customer_ratings, customer_job_dates · 016 callbacks · 017 sales CRM · 018 merge log, record_audit.
(Fold or split as needed, but keep the header discipline and update this index.)

## Appendix C — Verification commands you will use constantly
```bash
cd ~/docker/fieldkit-prod
docker compose restart app && sleep 3 && docker compose logs app --tail=20
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:3000/getagrip/invoices   # 302 = imports clean
for db in fieldkit_getagrip fieldkit_kleanit_charlotte fieldkit_cts fieldkit_kleanit_sf; do
  docker exec -i fieldkit-prod-db-1 psql -U fieldkit -d $db -v ON_ERROR_STOP=1 \
    < fsm-system/phase1/fieldkit_phase1/database/migrations/0NN_name.sql; done
docker compose exec -T app python tests/smoke_invoices.py
```

*End of directive.*
