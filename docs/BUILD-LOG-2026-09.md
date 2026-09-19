# Build Log — September 2026

One dated entry per increment: what was built, migration number, commit hash, smoke
result, anything deferred. Companion to `FIELDKIT_BUILD_DIRECTIVE_2026-09.md`.

---

## 2026-09-18 — Stage 0

**What:** Read the directive and the decisions-for-review doc in full. Verified the
§0.2 "what actually exists today" table against the live repo and the four production
databases rather than taking it on faith:
- Full route inventory (`grep '^@app.route'` on `app.py`, 3,248 lines) confirms no
  invoice/dispatch/extraction/reports/estimates/sales-CRM/company-settings/tax-settings
  routes exist; billing is exactly the v1 page the table describes (customer list +
  billing-contact readiness + CSV export, no balances/aging/statements).
- Live row counts across all four DBs: `invoices` = 0 everywhere; `tax_rates` = 100 rows
  (GAG/KC/CTS) and 0 (Kleanit SF); `customer_compliance_portals` = 0 everywhere.
- Confirmed and resolved the CLAUDE.md users-table conflict (directive §1.1/§5.3,
  decision #63) — see `DECISIONS-MADE-DURING-BUILD.md` D-003 for the full finding.
  Corrected `CLAUDE.md`.
- Searched the server and git history for the missing
  `FIELDKIT_DECISION_payment-anchoring.md` (decision #64) — confirmed absent, no action
  needed since its content is already in the directive. See D-004.
- Rewrote `docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md` (was dated 2026-02-10, badly
  stale). See D-005.
- Set up a project-level Claude Code permission file so the §1.3 working protocol
  (migrate → restart → curl → smoke test → commit → push) doesn't need a manual
  approval on every single command. See D-002.
- Asked and got answers on the Stage-1 ASK items (FL tax, delinquent-age threshold,
  SF-import tax exclusion) — see D-001.

**Migration:** none.
**Commit:** (pending — CLAUDE.md, CURRENT-STATUS.md, DECISIONS-MADE-DURING-BUILD.md,
BUILD-LOG-2026-09.md, .gitignore).
**Smoke test:** n/a (no code changed yet).
**Deferred:** nothing from Stage 0. Proceeding to Stage 1, Increment 1.1.

---

## 2026-09-18 — Stage 1, Increment 1.1 — Effective-dated tax rates + `/settings/tax`

**What:**
- `tax_rates` versioned by whole row: added `effective_from`/`effective_to`, dropped
  `UNIQUE(county)` in favor of `UNIQUE(county, effective_from)`, added a covering index.
  Mecklenburg split into a closed 7.25% row (2000-01-01–2026-06-30, now inactive) and
  the open 8.25% row (2026-07-01–, active) — verified contiguous, no gap/overlap.
- New `company_settings` table (one row per DB, enforced by a partial unique index),
  seeded with `company_name` from the existing `COMPANY_BRANDING` dict and
  `tax_exempt_by_default = TRUE` for `kleanit_sf` only (per D-001). Every other field
  left NULL for Chris/Michele to fill in.
- `_compute_invoice_tax()` reworked to anchor on `invoice_date` via a new
  `_tax_rate_as_of()` helper, instead of "whatever's `is_active = TRUE` right now."
- New routes (admin only): `/settings/tax` (list, "active as of" + "show all"
  filters), `/settings/tax/new`, `/settings/tax/<id>/edit`, `/settings/tax/<id>/end`,
  `/settings/company`. Added to the Settings nav dropdown in `base.html`.
- Reused Brick #1 (suggest-don't-restrict autocomplete) for the county field —
  see D-007 for why not Brick #2.

**Migration:** 009 (`009_tax_effective_dates_and_company_settings.sql`), applied to all
four DBs. First attempt failed on all three NC DBs with a unique-constraint violation
(the historical INSERT ran before the existing row's `effective_from` was moved off
`2000-01-01`, so both rows briefly collided on `(county, effective_from)`); fixed by
reordering to UPDATE-then-INSERT and re-applied cleanly (idempotent — safe re-run
confirmed via `IF NOT EXISTS`/`NOTICE...skipping` on the already-migrated DBs).
Pre-migration `pg_dump` backups of all four DBs are in `~/db-backups/2026-09-18/`.

**Commit:** (pending — this entry, migration file, `app.py`, three new templates,
`base.html` nav, `tests/smoke_tax_settings.py`, decisions log).

**Smoke test:** `tests/smoke_tax_settings.py` — 14/14 checks pass (schema, Mecklenburg
row split, effective-date resolution on both sides of 2026-07-01, duplicate-constraint
rejection, company_settings singleton + seed values). Also manually exercised every
route (list/new/edit/end/company) via Flask's test client with a forged admin session:
caught and fixed one real bug this way (`r.effective_from > today` compared a `date`
against a `str` in the `show_all=1` branch of `tax_rates_list.html`, 500'd — fixed with
a `|string` filter). POST paths (create/edit/end a test rate, save company settings)
exercised against the live `fieldkit_getagrip` DB and cleaned up/reverted afterward.

**Deferred:** the "never edit a rate a hardened invoice used" guard is UX-only for now
(see D-006) — there's no invoice-to-rate linkage yet to enforce it against.

---

## 2026-09-19 — Stage 1, Increment 1.2 — Receivable/version invoice refactor

**What:** the July 22 decision, fully implemented.
- `invoices` is now the RECEIVABLE: `receivable_state` (open/void), `current_version_id`,
  `source` (fieldkit/sf_import), portal fields, `reissue_of_invoice_id`/
  `reissued_as_invoice_id` (renamed from the old supersede columns — see D-011). Every
  single-table column that belongs to a presentation, not the receivable, is gone
  (`revision_number`, `state`, `subtotal`, `tax_*`, `total`, `amount_paid`,
  `hardened_*`, `sent_*`, `credit_*`). `UNIQUE(invoice_number)` — one number per
  receivable, forever.
- New `invoice_versions` (immutable presentations: Live/Hardened/Sent/Superseded) and
  `invoice_version_line_items` (replaces `invoice_line_items`, dropped — confirmed
  empty in production).
- `invoice_status_history` gained `version_id`/`from_state`/`to_state`/
  `subtotal_delta`/`tax_delta`/`effective_date` for version-level and dated-delta
  events (D-010).
- `transition_invoice()` rewritten end to end: `Hardened`/`Live`(reopen)/`Sent`/`Revise`
  are version-level (act on `current_version_id`); `Void`/`Reissue` are
  receivable-level. All six edges from the directive's table are implemented, with the
  exact guards specified (equipment-not-retrieved blocks harden; payment-applied
  blocks reopen/void; Sent required to revise; void-and-not-already-reissued required
  to reissue).
- New `invoice_balance()` and `invoice_display_status()` helpers (Draft/Hardened/
  Sent/Partially Paid/Paid/Void — nothing stored). `_compute_invoice_tax()` and
  `_resolve_equipment_labels()` re-scoped from invoice_id to version_id.
  `_reissue_invoice()` rewritten to mint a new receivable + Live rev-0 version instead
  of a new single-table row.
- Forward-compatibility for Increment 1.4's payment tables: see D-009.

**Migration:** 010 (`010_invoice_receivable_version_split.sql`), applied to all four
DBs (tested on `getagrip` first, then rolled out; re-ran once more afterward to confirm
full idempotency — every statement correctly no-ops via `NOTICE ... skipping`). All
four DBs still show 0 rows in `invoices`/`invoice_versions`/`invoice_version_line_items`
post-migration, as expected (pure schema change, no data existed to migrate).
Pre-migration `pg_dump` backups in `~/db-backups/2026-09-19/`.

**Commit:** (pending — migration file, `app.py`, `tests/smoke_invoice_versions.py`,
this entry, decisions log, `CURRENT-STATUS.md`).

**Smoke test:** `tests/smoke_invoice_versions.py` — 31/31 checks pass. Covers every
item the directive calls out for this increment: harden rejected while an equipment
line is still accruing; harden succeeds once retrieved, with correct subtotal/tax/
total and ordinal labels (1 unit -> bare label, 3 units -> "Test Dehu 1..3"); the
hardened snapshot is provably unchanged after the source catalog item's label and the
tax rate are edited post-harden; reopen rejected once a payment application exists
(exercised against a real temporary `payment_applications` table matching migration
011's future shape, created and dropped inside the test's own transaction) and
succeeds once it's removed; revise clones lines onto a new Live version, marks the old
one Superseded, moves `current_version_id`, and writes `subtotal_delta`/`tax_delta` on
the re-harden's history row; void requires a reason and rejects a second void; reissue
mints a new number, clones the void's lines, links both directions, and rejects a
second reissue of the same invoice. Also re-ran `smoke_tax_settings.py` as a
regression check — still 14/14. Confirmed via direct query that the smoke test's
transaction (including its temp tables) left zero trace after rollback.

**Deferred:** `v_invoice_balances` SQL view and the real `payment_applications`/
`invoice_adjustments` tables — Increment 1.4 (migration 011), per D-009.

---

## 2026-09-19 — Stage 1, Increment 1.3 — Create invoice from work order + invoice UI

**What:**
- `POST /<company>/workorders/<id>/invoice/new`: guards (Completed required, No Charge
  refused, one invoice per WO — a second attempt follows any reissue chain and
  redirects to the current invoice instead of creating a duplicate), snapshots
  `work_order_line_items` onto a new Live rev-0 version (equipment lines keep whatever
  billable-days quantity `_save_work_order` already computed — copied, not
  recomputed), resolves `tax_county` via the service-location → customer →
  `company_settings.default_tax_county` fallback chain, applies the three-layer
  taxability exemption (catalog item → customer → location), flips the WO to
  `Invoiced` with a status-history row, redirects to the new invoice.
- `GET /<company>/invoices` (search/status/date-range/with-balance filters),
  `GET /<company>/invoices/<id>` (two-column detail: line items with live-or-frozen
  ordinals, totals, full revision history, status timeline, state-gated sidebar
  actions), `GET/POST /<company>/invoices/<id>/edit` (Live only — description/qty/
  price/taxable per line, remove a line, add a new standard-catalog line via the
  restricted combobox, `notes_to_customer`/`invoice_date`/`tax_county`),
  `POST .../regenerate` (re-snapshot from the WO), and the six thin transition routes
  (`harden`/`reopen`/`send`/`void`/`reissue`/`revise`) that all just call
  `transition_invoice()` — see D-014 on why the line editor isn't a literal copy of the
  work-order form's brick.
- Work order detail: "Generate invoice now?" banner when Completed and uninvoiced,
  yellow "not invoiced yet" banner otherwise, "View Invoice" link once one exists
  (follows the reissue chain). Work order edit redirects to detail (not the list) when
  status becomes Completed, so the prompt is right there.
- Customer detail: new Jobs and Invoices sections (D-015).
- Added minimal flash-message infrastructure (D-013) since this increment's own spec
  needed it and nothing existed yet.

**Migration:** none (pure application-layer increment on top of migration 010's schema).

**Commit:** (pending — `app.py`, five templates, two smoke tests, this entry, decisions log).

**Smoke test:** `tests/smoke_invoice_routes.py` — drives the real Flask routes (test
client, forged admin session) against live `fieldkit_getagrip`, not just the DB layer:
creates a real Completed work order with a standard + a retrieved equipment line,
posts to `/invoice/new`, verifies the WO flips to Invoiced, the snapshot subtotal
matches, a second `/invoice/new` redirects to the same invoice rather than
duplicating; renders every new page (list with each filter, detail, edit); drives
edit → harden → send → revise through the actual HTTP routes and checks
`current_version_id` moves; drives void → reissue on a second work order and checks
the redirect lands on a genuinely new invoice id. Everything created is hard-deleted
in a `finally` block — confirmed zero residue afterward. Also confirmed a No-Charge
work order is correctly refused. Re-ran `smoke_tax_settings.py` and
`smoke_invoice_versions.py` as regression checks — both still green.

**Deferred:** Record Payment, PDF download, and the Portal panel — later increments
(1.4/1.5/1.8) — the invoice detail sidebar says so rather than showing dead buttons.

Proceeding to Increment 1.4 (payments, applications, adjustments, credits).

---

## 2026-09-19 — Out-of-sequence bug fix: work order auto-description

**What:** Chris reported that typing a per-line description on a standard work order
line (e.g. "guest bathtub") was *replacing* that line's contribution to the
auto-generated job description instead of adding to it — so the catalog item's own
name disappeared from the description the moment someone typed a note on the line.
Root cause: `lineContribution()` in `workorder_form.html` returned the typed
description alone whenever it was non-empty, ignoring the catalog item name
entirely. Fixed to combine both (`"<Catalog Name> - <typed note>"` when both are
present, matching the existing token style of the generated description). One shared
template serves all four companies — no per-company work needed. See D-017.

**Migration:** none (frontend JS only).

**Commit:** (pending — `workorder_form.html`, this entry, decisions log).

**Verification:** restarted the app, confirmed via the Flask test client that
`/workorders/new` now serves the combining logic and the old replace-only logic is
gone; curl-checked the route renders cleanly (302 to login) for all four companies
(same shared template, so this is a formality, not a real per-company risk).

Proceeding back to Increment 1.4.

---

## 2026-09-19 — Stage 1, Increment 1.4 — Payments, applications, adjustments, credits

**What:**
- New `payment_methods` (seeded: Check/Credit Card/Paymode-X/ACH/Cash/Other),
  `payments`, `payment_applications` (append-only — un-apply inserts a reversal row,
  never mutates), `invoice_adjustments`, `payment_status_history`, and
  `v_invoice_balances` (finally buildable now that the tables it needs exist — see
  D-009 from Increment 1.2).
- `invoice_balance()`/`transition_invoice()`'s reopen/void payment guards, written two
  increments ago against this exact schema and gated behind `to_regclass()`, are now
  live and enforcing for real.
- Payment model layer: record (against a customer, optionally applying to one
  invoice), apply (rejects over-application against both the invoice balance and the
  payment's unapplied amount), un-apply (reversal row), void (reason required,
  reverses every active application), refund (only disposition for money owed back to
  a customer — write-offs go through `invoice_adjustments` instead, on amounts owed
  *to* the company).
- Routes + templates: invoice detail's Record Payment / Apply Existing Credit / Add
  Adjustment modals (first real use of a new small modal brick in `base.html`),
  payments list (`/payments`, with date/method/customer/unapplied filters), payment
  detail (`/payments/<id>`, apply/unapply/void/refund actions), customer detail's new
  Payments card. Paying an invoice in full shows a celebration banner + "Next Unpaid
  Invoice →" link right on the (reloaded) invoice detail page.
- The red "Unapplied credit $X — resolve" badge on customer detail, invoice detail,
  and the work order form (via the existing customer-context AJAX endpoint) — not on
  the v1 billing page, which Increment 1.8 replaces wholesale (D-021).

**Migration:** 011 (`011_payments.sql`), applied to all four DBs (tested on `getagrip`
first, then rolled out; idempotency re-verified). Pre-migration backups in
`~/db-backups/2026-09-19b/`.

**Commit:** (pending — migration file, `app.py`, six new/changed templates, smoke
test, this entry, decisions log).

**Smoke test:** `tests/smoke_invoice_versions.py` and `tests/smoke_invoice_routes.py`
re-run clean as regressions throughout. `tests/smoke_payments.py` — 30/30 checks —
drives the real routes: record + apply a partial payment, reject an over-application,
pay off in full and confirm the Paid celebration + Next-Unpaid-Invoice link, un-apply
and confirm the balance is genuinely restored (not just accepted), refund + void,
same-day adjustment soft-delete vs. later-day reversal row, and every list/detail page
render. **Caught two real bugs this way, not just exercised the happy path** — both
fixed and re-verified before calling the increment done (D-018, D-019): a
`reverses_application_id IS NULL` filter that was backwards for every SUM-based
balance/guard calculation (an un-applied payment never actually freed up the invoice —
found because the test re-checks the balance after unapplying instead of trusting the
200 response), and a `Decimal`/`float` arithmetic `TypeError` in the over-application
guard (found because the test records a *real* payment instead of only checking
routes return the right status code).

**Deferred:** `v_invoice_balances` exists now but nothing queries it yet — list pages
still compute balance/status in Python per row (D-016); switching them over is a
cheap follow-up, not urgent. Multi-invoice-per-payment recording in one step isn't
built — the primary flow (record against one invoice) and the secondary "apply
elsewhere" flow (from payment detail or an invoice's Apply Existing Credit modal)
together cover the directive's dispositions without that extra UI.

Proceeding to Increment 1.5 (invoice PDF).

---

## 2026-09-19 — Stage 1, Increment 1.5 — Invoice PDF

**What:**
- `reportlab==5.0.1` / `openpyxl==3.1.5` added to `requirements.txt`, pinned to the
  versions actually installed in the statements stack's container (its own
  `requirements.txt` has them unpinned — checked the real installed version rather
  than trusting an unpinned requirements file). Required a `docker compose up -d
  --build` (image rebuild), not a plain restart.
- `generate_invoice_pdf(company_key, version_id)`: company block (from
  `company_settings`, no logo — none exist yet, see D-026), INVOICE + number (+ Rev N),
  invoice date, due date (parsed from the customer's `payment_terms`), customer +
  service location + work-site label + PO/WTN, line table, subtotal/tax/total/
  payments-applied/balance-due, water-extraction explainer paragraph when any
  per-day-equipment line is present, notes-to-customer, remit-to, footer text.
- New `invoices.work_site_label` (migration 012, alongside
  `company_settings.extraction_explainer_text`) — snapshotted at invoice creation so
  the byte-for-byte guarantee doesn't require reading `work_orders` (D-022).
  `extraction_explainer_text` also exposed on `/settings/company`.
- `GET /invoices/<id>/pdf` (current version) and
  `GET /invoices/<id>/versions/<vid>/pdf` (any specific version — wired into the
  revision history list for superseded versions). "Download PDF" on invoice detail.
- `doc.invariant = 1` + `pageCompression=0` so a hardened version's PDF is genuinely
  byte-identical across repeated renders, not just visually similar (D-025).

**Migration:** 012 (`012_extraction_explainer_text.sql`, extended mid-increment before
commit to also add `invoices.work_site_label` — see the file's own header for why),
applied to all four DBs. Pre-migration backups in `~/db-backups/2026-09-19c/`.

**Commit:** (pending — migration file, `requirements.txt`, `app.py`, two templates,
smoke test, this entry, decisions log).

**Smoke test:** `tests/smoke_invoice_pdf.py` — 22/22 checks. Due-date parsing for
Net 30/15/Due-on-Receipt/unknown/blank; a Live version's PDF renders and is served
correctly over HTTP; **the byte-for-byte claim is actually tested, not assumed** —
hardens a version, renders it twice and diffs the bytes, then mutates the SOURCE
catalog item's name AND the source work order's site label and re-renders, confirming
the hardened PDF is unchanged and never shows the post-harden edit; confirms the
extraction explainer appears and equipment lines show deployed/retrieved day math
(never the internal registry unit name — created a throwaway equipment unit for this,
since GAG's real equipment registry is genuinely empty in production); the
version-scoped PDF route matches direct generation. All four prior smoke tests
re-run clean as regressions.

**Deferred:** no logo images (D-026, waiting on real files from Chris); PDF is
generated on every request, never cached/stored (matches the directive's "store
nothing on disk permanently").

Proceeding to Increment 1.6 (statements, replacing the Phase 0 generator).

---

## 2026-09-19 — Stage 1, Increment 1.6 — Statements (replaces the Phase 0 generator)

**What:**
- `generate_statement_pdf(company_key, customer_id, as_of_date)`: every open receivable
  with a current balance > 0, aged from `invoice_date` into Current/31-60/61-90/90+,
  plus any unapplied credit as a negative line with a note. Deliberately echoes the
  Phase 0 statement's visual language (read `scripts/generate_pdf_statement.py` in the
  statements stack first) — same title treatment, same customer-info-box style, same
  per-invoice table shape and TOTAL row, same "PAYMENT REQUIRED" notice — since
  Michele's customers already recognize that layout.
- `GET /customers/<id>/statement` (single PDF, sets `last_statement_at`) and
  `POST /billing/statements` (ZIP of PDFs for selected customers, sanitized filenames
  — no `*` from Kleanit's FL-marker naming convention). Wired the batch route into the
  EXISTING v1 billing page's customer-checkbox form via `formaction`/`formtarget`
  rather than redesigning the page — Increment 1.8 replaces it wholesale regardless
  (D-028). "Download Statement" added to customer detail.
- New `customers.last_statement_at` (migration 013), updated by both the single and
  batch paths (D-027).

**Migration:** 013 (`013_last_statement_at.sql`), applied to all four DBs. Pre-migration
backups in `~/db-backups/2026-09-19d/`.

**Commit:** (pending — migration file, `app.py`, `billing.html`, `customer_detail.html`,
smoke test, this entry, decisions log).

**Smoke test:** `tests/smoke_statements.py` — 23/23 checks, after fixing a bug **in the
test itself** first: the first draft asserted the PDF contained the *work order*
number (`ZZZ-STMT-0001`) instead of the *invoice* number, which is auto-generated
independently (`GAG-2026-NNNN`) — so several checks were passing/failing for the wrong
reason (one `not in` assertion was trivially true regardless of correctness). Caught
by actually printing the real generated invoice numbers while debugging a failure
rather than assuming the first plausible explanation; fixed the test to capture and
assert against the real invoice number, not the WO number. Once fixed: mixed-aging
statement (Current + 90+ buckets, PAYMENT REQUIRED notice), a fully-paid invoice is
correctly excluded, unapplied credit shows as a negative line, `last_statement_at`
is unset until a statement is actually served, the batch ZIP route produces a
correctly-named single-entry zip and handles an empty selection without a 500, and
the billing page renders with the new button. All five prior smoke tests re-run clean.

**Deferred:** "Send Statements" (email delivery) is Increment 1.7. The full billing
page redesign (aging summary cards, filters, "Open credits" panel) is Increment 1.8 —
today's addition to `billing.html` is intentionally minimal (D-028).

Proceeding to Increment 1.7 (email delivery).

---

## 2026-09-19 — Stage 1, Increment 1.7 — Email delivery (invoices & statements)

**Safety note first:** `RESEND_API_KEY` is a real, live key in this environment, and
real customer contact emails exist in the database (checked before writing any code).
Built `_send_email_via_resend()` as the ONE function that ever calls the Resend API,
specifically so it's a single, easy point to monkey-patch in tests — see D-032 and the
smoke test's own safety-first docstring. No real email was sent at any point while
building or testing this increment (verified — the mock counts every call it
intercepts).

**What:**
- Reuses the existing Resend integration (`send_reset_email`'s pattern) rather than a
  parallel one. `_send_email_via_resend()`: from name / reply-to / BCC from
  `company_settings`, PDF attached as base64, never raises (returns `(message_id,
  error)` — a failed send must never 500 a request).
- `_resolve_email_recipients()` (accepts_billing for invoices, accepts_statements for
  statements), `_render_email_template()` ({customer}/{number}/{total}/{balance}),
  `_send_invoice_email()` / `_send_statement_email()` (resolve → render → send → log
  → only on success, transition/update), all writing to the new `email_log` table
  regardless of outcome.
- Send-dialog modals on invoice detail (recipient checkboxes, extra addresses,
  editable subject/body) and customer detail (statement equivalent). A customer with
  no billing/statement contact shows a blocked message with a link to add one, instead
  of an empty dialog. Kept the old no-email "Mark Sent" action alongside the new real
  send — see D-030.
- `POST /billing/send-statements`: batch send with a sent/failed/skipped-no-contact
  summary page, wired into the same billing-page checkbox form as the other batch
  actions.
- `invoice_email_template` / `statement_email_template` exposed on `/settings/company`.
- If `RESEND_API_KEY` is unset, `_send_email_via_resend` returns a clean error instead
  of raising, and the UI hides the Send button behind a "not configured" note rather
  than showing a dead action.

**Migration:** 014 (`014_email_log.sql`: `email_log` table +
`company_settings.invoice_email_template`/`statement_email_template`), applied to all
four DBs. Pre-migration backups in `~/db-backups/2026-09-19e/`.

**Commit:** (pending — migration file, `app.py`, four templates, smoke test, this
entry, decisions log).

**Smoke test:** `tests/smoke_email_delivery.py` — 31/31 checks, all against a
monkey-patched Resend + throwaway `.invalid`-address fixtures (0 real sends, confirmed
by counting intercepted calls). Covers: missing-API-key returns a clean error without
ever reaching the mock; a successful send calls Resend exactly once with the right
recipient/attachment/reply-to/BCC, writes `email_log` status='sent', and transitions
the invoice to Sent; no-recipient blocks with zero Resend calls and zero state change;
**a failed send (simulated Resend exception) logs status='failed' with the error text
and leaves the invoice Hardened** — this caught a real bug first (D-031: the failure
path's `email_log` row was being rolled back along with the rest of the failed
transaction, silently defeating the whole point of logging failures); single and
batch statement sends, including the batch summary correctly separating sent vs.
skipped-no-contact. All six prior smoke tests re-run clean.

**Deferred:** nothing significant — this closes out the directive's explicit email
requirements for Stage 1's core cycle.

Proceeding to Increment 1.8 (billing page full rebuild, A/R aging report, compliance).

---

## 2026-09-19 — Stage 1, Increment 1.8 — Billing page rebuild, A/R aging report, compliance

**What:**
- **Billing page rewritten from scratch** (`/billing`): summary cards (total open,
  90+ delinquent, open credit), aging strip, filter bar
  (`?filter=delinquent|no_contact|portal|all`), per-customer rows with a real
  per-customer open-invoice list embedded as JSON on the Pay button so the shared
  Record Payment modal (the generic modal brick from base.html) opens pre-filtered to
  that customer's actual open receivables — no AJAX round trip needed (D-037).
  `_customer_aging_summary()` is the shared helper both this page and the aging
  report call, using the same `_aging_bucket_label()` boundaries built for statements
  in Increment 1.6 (0–30 / 31–60 / 61–90 / 90+) rather than reinventing bucket math.
  Delinquent flag uses `DELINQUENT_DAYS_PAST_INVOICE = 90` per Chris's explicit
  override of the directive's 60-day default.
- **A/R Aging report** (`/reports/aging`, `?sort=total|90plus`), ported from the
  Phase 0 spec doc: same 4-bucket layout, sortable, pre-rendered hidden per-customer
  drill-down rows (no AJAX) toggled by JS, `_customer_receivables_detail()` for the
  richer per-invoice drill-down data, print CSS (`print-hide`/`print-focus` +
  `afterprint` listener) for a clean printed report.
- **Compliance portal module** (new): `customer_compliance_portals` table (migration
  015), enrollment/edit/toggle routes on customer detail, `PORTAL_TYPES` fixed to
  `OPS`/`VendorCafe`/`Paymode-X` (D-033). `transition_invoice()`'s Hardened branch
  extended to auto-assign a portal + `portal_status='pending'` only when the customer
  has exactly one active enrollment (D-034) — verified this does NOT retroactively
  touch invoices hardened before the enrollment existed. `/compliance` page lists
  pending/submitted/accepted/rejected invoices per portal type, with accept/reject
  actions and `.xlsx` export via one shared `_build_portal_xlsx()` helper feeding
  three per-portal-type wrapper functions (`_export_ops`/`_export_vendorcafe`/
  `_export_paymode`) — all currently emitting the same `GENERIC_PORTAL_COLUMNS` set
  since the real portal templates haven't been supplied yet (explicitly flagged on
  the compliance page itself, not silently guessed at).
- `invoice_edit`/`invoice_form.html` extended with `wtn_po_number` and a Compliance
  Portal dropdown; `customer_detail.html` gained a Compliance Portals section +
  enrollment modal; `invoice_detail.html` gained a portal sidebar panel.
- Gated `/reports/aging` and `/compliance` to admin/manager/office, consistent with
  every other billing-adjacent route this build has touched, even though Appendix A's
  matrix doesn't list an office column for Reports (D-036) — Michele (office) is the
  primary user of this collections workflow.

**Migration:** 015 (`015_portal_primary_billing.sql`: `customer_compliance_portals`
table, `invoices.portal_id`/`portal_status`, `wtn_po_number`), applied to all four DBs.
Pre-migration backups in `~/db-backups/2026-09-19f/`.

**Performance note (D-035):** both new pages compute aging via a per-customer,
per-invoice loop (N+1), same tradeoff made throughout this build. Measured against
the real 1,330 active Get a Grip customers (zero real invoices yet): billing page
0.82s, aging report 0.27s. Flagged to revisit via `v_invoice_balances` (built in
Increment 1.4, still unused) once real invoice volume grows — not worth pre-optimizing
against volume that doesn't exist yet.

**Commit:** (pending — migration file, `app.py`, five templates, smoke test, this
entry, decisions log, status doc).

**Smoke test:** `tests/smoke_billing_aging_compliance.py` — 26/26 checks. Covers:
aging bucket boundary math; billing page renders with correct customer total;
delinquent filter (90+ days) includes/excludes correctly; no_contact filter; aging
report renders with correct bucket placement and both sort orders; portal enrollment
creation; auto-assign-on-harden fires for a NEW invoice but does NOT retroactively
touch an already-hardened one; compliance page lists the pending invoice; export
produces a real 11-column generic `.xlsx` and flips the invoice to submitted; accept
flips it to accepted; portal-primary-billing toggle correctly includes/excludes the
customer from `?filter=portal`. Cleanup verified zero residue. All 7 prior smoke tests
(`smoke_tax_settings`, `smoke_invoice_versions`, `smoke_invoice_routes`,
`smoke_payments`, `smoke_invoice_pdf`, `smoke_statements`, `smoke_email_delivery`)
re-run clean as regressions. Final curl sweep: all 4 companies × 3 new/rebuilt routes
(`billing`, `reports/aging`, `compliance`) → clean `302` redirect-to-login, confirming
no import errors anywhere.

**Deferred:** real per-portal export column templates (waiting on Chris/Michele —
review-doc item #33, not blocking per directive's own fallback).

This closes out Stage 1's billing/collections surface. Proceeding to Increment 1.9
(cutover data import from Phase 0) pending Chris's go-ahead — the directive flags this
one as requiring explicit sign-off before the real (non-dry-run) import runs.

---

## 2026-09-19 — Stage 1, Increment 1.9 — Cutover import: investigation only (real import deferred)

Chris confirmed real cutover imports are on hold until the whole site is ready for his
and Michele's day-to-day testing — so `import_open_invoices.py` was not built this
session, and no real or dry-run import ran. Before parking the increment, checked the
source the directive assumes it will read from (`statements-db-1`/`fsm_prod`, the live
container behind statements.cletize.com) and found a discrepancy worth recording now:
`invoices` and `tax_transactions` are both empty for all four companies, and
`customers` only has rows for Get a Grip (296; the other three companies have 0). See
D-038. Not a blocker today (real imports are deferred anyway) but needs resolving
before 1.9 actually runs for real — either a fresh ServiceFusion Excel import into that
container, or pointing at wherever the real current numbers actually live.

---

## 2026-09-19 — Stage 1, Increment 1.10 — NC cash-basis tax report from live data

**What:**
- `/<company>/reports/tax?date_from=&date_to=` (default: last calendar month).
  Cash-basis: rows are selected by `payment_applications.applied_date` (receipts) and
  `payments.refunded_at` (refunds), never by `invoice_date` — a revised invoice never
  retroactively changes what was already reported for cash received in an earlier
  period.
- **Migration 016**: adds `state_pct`/`county_pct`/`transit_pct`/`taxable_subtotal` to
  `invoice_versions`, frozen at harden by extending `_compute_invoice_tax()` (which
  already looked up the `tax_rates` row — this just captures more of what it already
  resolves) rather than adding a second lookup path. `taxable_subtotal` is one column
  beyond what the directive named — see D-039.
- `_tax_report_data()`: for each non-reversed `payment_application` in range, allocates
  proportionally against the invoice's CURRENT version (taxable base = applied ×
  taxable_subtotal/total, tax = applied × tax_total/total), splits tax into
  state/county/transit using the version's frozen percentages, excludes
  `source='sf_import'` (D-001 — SF-era balances already reported through Phase 0).
  Mecklenburg's NCDOR-required 1% "additional county" reporting line is split back out
  of the pooled `county_pct` at render time (D-040), since this build's `tax_rates`
  schema pools it rather than storing it separately.
- Refunds appear as negative rows in the period refunded, allocated against the last
  invoice that payment's money was ever associated with (even a since-reversed
  application) — see D-041 for the full reasoning and its limits. Money refunded from
  credit that was never applied to any invoice can't be netted against any county;
  those surface separately as "Unallocated refunds" for visibility.
- County totals box first, then per-county invoice detail, matching the August 2026
  statements tax report rework's layout. Excel export (2-3 sheets: Summary, Detail,
  Unallocated Refunds if any) and PDF export (ReportLab, `pageCompression=0` +
  `doc.invariant = 1`, same discipline as invoice/statement PDFs).
- `applied_date` defaulting to `payment_date` (directive's explicit `[DEFAULTED]`
  requirement) turned out to already be true by construction since Increment 1.4 — the
  Record Payment modal has never had a separate applied_date field. Logged as D-042
  rather than silently assumed satisfied.

**Migration:** 016 (`016_tax_report_components.sql`), applied to all four DBs with a
backfill DO block for any pre-existing Hardened+ versions (a no-op today — production
has zero real invoices). Pre-migration backups in `~/db-backups/2026-09-19g/`.

**Commit:** (pending — migration file, `app.py`, `tax_report.html`, `billing.html` nav
link, smoke test, this entry, decisions log, status doc).

**Smoke test:** `tests/smoke_tax_report.py` — 30/30 checks. Covers: harden correctly
freezes all four new columns (8.25% Mecklenburg rate → 4.75 state / 3.00 county / 0.50
transit / $1000 taxable); a $541.25 partial payment against a $1082.50 invoice
allocates to exact-cent-clean values (state $23.75, county $10.00, additional-county
$5.00, transit $2.50, summing back to $41.25 tax); an `sf_import` invoice's payment in
the same window is fully excluded (county row count stays 1, not 2); a refund from
never-applied credit lands in "unallocated"; a refund of money that WAS applied then
un-applied produces a correctly-signed negative row against the right county; the HTML
page, xlsx export, and PDF export (byte-searched for "Mecklenburg") all render without
error across all four companies. Cleanup verified zero residue. All 8 prior smoke
tests re-run clean as regressions.

**Deferred:** nothing — this closes out Stage 1's directive-listed report work.
Real-data validation ("Tax report for August 2026 test data reconciles by hand for one
county" per the Stage 1 exit criteria) still needs real invoice data, which doesn't
exist yet (D-038/imports deferred).

This closes out Stage 1's exit-criteria feature list except the parts that need real
data (imports) or Michele's hands-on walkthrough. Proceeding per Chris's direction —
awaiting his call on what's next.

---

## 2026-09-19 — Stage 2, Increment 2.1 — Tech profiles + dispatch board

**What:**
- **Migration 017**: `users` gains `color_hex`, `is_field_tech`, `can_be_dispatched`,
  `phone_mobile`, `default_start_time`, `is_active_tech`, `dispatch_sort_order`.
  `work_orders` gains `scheduled_start` (maintained on save = `start_date` +
  `arrival_window_start`, NULL when there's no arrival time — see D-049),
  `catalog_estimated_duration_hours`, `duration_overridden`.
  `work_order_line_items` gains `estimated_minutes` (snapshotted from
  `catalog_items.estimated_minutes` at line-add time, per design addendum §13).
- User form: Tech/Dispatch Profile section (field-tech/dispatchable/active-tech
  checkboxes, mobile phone, default start time, sort order); `color_hex` auto-assigned
  from a fixed 12-color palette by `id % 12` on create, shown read-only on edit.
- WO form: live "Catalog estimate" readout computed client-side from line items
  (`estimated_minutes × quantity`, one formula for every line kind per the addendum),
  auto-syncing the Scheduled Duration field until a manual edit sets
  `duration_overridden` (a hidden flag flipped by JS); server-side recomputation in
  `_save_work_order` matches the client formula exactly, with a non-blocking flash
  warning when scheduled and catalog estimates diverge by more than 15 minutes
  (D-048 — simplified from the addendum's two-button banner sketch).
- **Dispatch board** `/<company>/dispatch?date=&view=day|week`: horizontal timeline
  (tech rows ordered by `dispatch_sort_order`, plus Unassigned), 30-min-resolution
  blocks colored by tech, native HTML5 drag-to-move (`POST /dispatch/move`) and
  edge-drag-to-resize (`POST /dispatch/resize`, same warning logic as WO save),
  click-to-popover (View / Edit / Mark Completed / Mark No Charge — the last two via a
  new lightweight `POST /workorders/<id>/quick-status` route), click-empty-slot →
  pre-filled WO create (`/workorders/new?tech=&date=&time=`), server-computed
  same-tech-row collision detection (red outline + "Overlaps with GAG-2026-0042"
  banner, non-blocking, no auto-bump), a read-only week view (7-day grid per tech),
  and an "unscheduled" strip for WOs with a date but no arrival time.
  `GET /dispatch/data?date=` is the JSON data endpoint the page renders from
  client-side, so drag/resize never triggers a full reload.
- Work order list: `tech`/`date` filters. WO detail: each assigned tech's chip now
  links to `/dispatch?date=&tech=`.
- Nav: Dispatch link for admin/manager only (salesperson and below: no access).

**Bugs found and fixed (pre-existing, not introduced this increment):** D-043
(`user_new`'s INSERT referenced a `created_by` column that has never existed on
`users` — silently failed on every DB, every time, with the route redirecting as if it
succeeded) and D-044 (the WO form's tech checklist read the per-company DB's `users`
table, which is empty for 3 of 4 companies per the known D-003 quirk — always rendered
zero techs there). Both fixed; see the decisions log for detail. Neither was
introduced by this increment, but both were found by its smoke test and are load-
bearing for the dispatch board actually showing techs.

**Migration:** 017 (`017_tech_profiles_and_scheduling.sql`), applied to all four DBs.
Pre-migration backups in `~/db-backups/2026-09-19h/`.

**Commit:** (pending — migration file, `app.py`, `dispatch.html` (new), `base.html`
(nav link), `user_form.html`, `workorder_form.html`, `workorder_detail.html`,
`workorder_list.html`, smoke test, this entry, decisions log, status doc).

**Smoke test:** `tests/smoke_dispatch.py` — 30/30 checks. Covers: creating a real
technician through the user form with color auto-assignment and tech-field round-trip;
creating a WO through the real form and verifying the live catalog-duration total
(120min × 2 qty = 4.0h), `scheduled_start` composition, and the line item's snapshotted
`estimated_minutes`; a second overlapping WO on the same tech correctly flagged by
collision detection both directions; the dispatch data/page/week routes; `/dispatch/
move` re-homing a WO's tech and time (and clearing tech assignment when dropped on
Unassigned); `/dispatch/resize` setting `duration_overridden` and returning the
±15-minute warning; the quick-status route; WO list tech+date filters; and the
click-empty-slot prefill flow. Cleanup verified zero residue across all four DBs
(user creation replicates everywhere via `write_to_all_dbs`). All 9 prior smoke tests
re-run clean as regressions.

**Deferred:** delinquent/rating/callback badges (D-046 — depend on features not yet
built); the richer two-button duration-warning banner (D-048); per-line
`estimated_minutes` override UI (addendum mentions it as possible, not required).

Proceeding to Increment 2.2 (water extraction queue + accrual engine).

---

## 2026-09-19 — Stage 2, Increment 2.2 — Water extraction queue + accrual engine

**What:** One work order per extraction job, from set-up through retrieval — the WO
stays one row the whole time, nothing is cloned (directive §3.2, supersedes design v2
§8's clone-forward model).

- **Migration 018**: `work_orders` gains `is_extraction`, `extraction_started_at`,
  `extraction_closed_at`, `followup_tech_username`, `equipment_incomplete`. New
  `extraction_daily_log` table (`UNIQUE(work_order_id, log_date)`). Most of the
  schema this increment needed (`extraction_status`, `extraction_day_count`,
  `parent_work_order_id`, `description_followup`, the `'Extraction Active'` status
  value) already existed from an earlier increment — confirmed via `\d work_orders`
  before writing the migration, so only the genuinely-missing columns were added.
- WO form: a Water Extraction card (extraction checkbox, equipment-not-confirmed
  checkbox, follow-up tech picker). `is_extraction` auto-sets TRUE the moment an
  equipment line is present in a save; `equipment_incomplete` auto-clears the moment a
  save includes >=1 equipment line, regardless of the checkbox (D-051/D-052).
  Completing a WO that's `is_extraction` triggers an in-page "Set equipment as active?"
  banner (two real buttons, not a native confirm — D-053) that either starts extraction
  (`status='Extraction Active'`, `extraction_status='Drying'`,
  `extraction_started_at` = earliest deployed_at if backdated, else today) or closes
  normally.
- **Queue page** `/<company>/extraction`: summary cards (active/ready/missed-today/
  day-5+-escalated), table with day count (computed live — D-054, since §3.5's nightly
  job doesn't exist yet), row actions (Mark Ready / Needs More Time / Missed Today,
  each upserting `extraction_daily_log`), "Log Today's Status for All" batch action,
  "Generate Pickup List for Tomorrow" PDF grouped by property then follow-up tech.
- **Retrieved**: a modal (reusing the base.html modal brick) lists open per-day lines
  with a per-line retrieved-date input (defaults to today, blank = still open —
  partial retrieval keeps the job active); when none remain open,
  `extraction_status='Equipment Retrieved'`, `extraction_closed_at`,
  `status='Completed'` — the existing "Generate invoice now?" banner on WO detail
  picks this up automatically, no new invoice-prompt code needed.
- **Follow-up cleaning WO**: offered on WO detail once retrieved. Pre-fills the
  customer/location/site label on a genuinely NEW work order by reusing WO-edit's own
  customer-context JS load (D-055) — not a copy of the extraction job, since a cleaning
  follow-up needs its own line items and schedule.
- Dispatch board's droplet badge now reads the real `is_extraction` column (was a live
  equipment-line-existence heuristic in 2.1, before this column existed) and adds an
  ⚠️ equipment-not-confirmed badge to the popover.
- Nav: Extraction link for admin/manager/office.

**Migration:** 018 (`018_extraction_queue.sql`), applied to all four DBs. Pre-migration
backups in `~/db-backups/2026-09-19i/`.

**Commit:** (pending — migration file, `app.py`, `extraction_queue.html` (new),
`base.html`, `workorder_form.html`, `workorder_detail.html`, smoke test, this entry,
decisions log, status doc).

**Smoke test:** `tests/smoke_extraction.py` — 33/33 checks. Covers: is_extraction
auto-set on a fresh equipment-line WO; the full start-extraction transition including
a backdated `extraction_started_at`; the dispatch board's droplet badge now sourced
from the real column; the queue page and its live day count; all three row log
actions and the daily-log upsert; the batch log-all action; the pickup-list PDF
(byte-searched for the customer name); the full Retrieved flow (per-line date,
recomputed quantity/total matching the existing per-day billing formula, close to
Completed, status history row); the follow-up-WO offer and its full prefill chain
(redirect params, customer combo, parent hidden field, Follow-Up Visit checkbox); and
equipment_incomplete auto-clearing even when the checkbox stays checked in the same
submission that adds the line. Cleanup verified zero residue. All 10 prior smoke
tests re-run clean as regressions.

**Deferred:** day-5+ escalation email notification (needs §3.5's nightly job/alert
email, not built yet — the queue page's own escalation count/highlight IS built and
live). `extraction_day_count`'s stored column still isn't written by anything (kept
for when §3.5 lands).

Proceeding to Increment 2.3 (day sheet, hours report, job activity report).

---

## 2026-09-19 — Stage 2, Increment 2.3 — Day sheet, hours report, job activity report

**What:**
- `/<company>/reports` landing page linking tax, aging, day sheet, hours, jobs (and a
  disabled Recency card — that report doesn't exist until §4.3, D-058).
- `/<company>/reports/daysheet?date=&tech=`: printable, grouped by tech (ordered by
  `scheduled_start`), one section per tech with `page-break-after` for print, a
  multi-tech WO appearing under every assigned tech's section, an Unassigned group,
  time/customer/address (with an on-screen-only Google Maps link)/work site/job
  description/tech notes/status/contact phone. "All techs" (no filter) prints all
  sections.
- `/<company>/reports/hours?from=&to=`: per tech per day — scheduled hours
  (Σ `estimated_duration_hours`), jobs count, completed count, and extraction checks
  (computed live from each active job's start/close window, D-059 — nothing clones the
  WO per day so there's no stored per-day row to count). An `actual_duration_hours`
  column renders as an honest blank em dash until the mobile tech app exists.
- `/<company>/reports/jobs?from=&to=&status=&tech=&customer=`: job activity list +
  totals (count, invoiced total via `invoices`/`invoice_versions`), CSV export.
  Status filter includes `Extraction Active`/`Invoiced` alongside the office-settable
  statuses (D-060).

**Bug found and fixed (introduced in 2.1, not this increment):** D-057 —
`_save_work_order`'s duration-warning comparison crashed with a 500 on
`duration_overridden=true` + a real duration value, because `_opt_num()` returns a
string and nothing cast it to float before subtracting. Shipped in `4a33861`, stayed
live through `1ad67d8` (neither 2.1 nor 2.2's own smoke tests happened to exercise
that exact combination), caught when 2.3's report fixtures needed distinct explicit
hours per WO. Fixed; confirmed via the full regression suite.

**Commit:** (pending — `app.py`, four new templates, `base.html` nav link, smoke test,
this entry, decisions log, status doc). No migration this increment — every column
used already existed.

**Smoke test:** `tests/smoke_reports.py` — 23/23 checks. Covers: day sheet grouping
(a multi-tech WO appears under both techs' sections; the tech filter narrows to one);
the hours report rendering with the honest "Scheduled Hours" / blank "Actual Hours"
labels; the job activity report's tech filter, invoiced-total column (a live invoice
created mid-test), and CSV export; the reports landing page linking to all five live
reports. Cleanup verified zero residue across all four DBs (tech fixtures replicate
everywhere). All 11 prior smoke tests re-run clean as regressions.

**Deferred:** nothing from this increment's own scope; Recency (§4.3) intentionally
not built yet.

Proceeding to Increment 2.4 (replacements for the retired tag concept).

---

## 2026-09-19 — Stage 2, Increment 2.4 — Replacements for the retired tag concept

**What:** Directive §3.4 maps 8 ServiceFusion tags to first-class fields/derived
badges. Six of the eight were either already satisfied by prior work or explicitly
assigned to a later increment in the directive's own table (D-061) — only two needed
real code this pass:

- **Misc Task** (`is_internal_task`): `work_orders.customer_id` is now nullable,
  gated by a DB CHECK constraint (`customer_id IS NOT NULL OR is_internal_task`) so
  the rule holds regardless of code path, not just in `_save_work_order`. Every
  `JOIN customers` on `work_orders` across the codebase (11 sites) became a LEFT
  JOIN — see D-062 for why this is safe. WO form gets an "Internal task" checkbox
  that relaxes the customer combo's required-ness via JS
  (`data-required` toggle, since the combo bypasses native HTML5 validation).
  Internal tasks: show as "Internal Task" everywhere a customer name would normally
  render, can't be invoiced (guarded with a clear error, banner hidden entirely), and
  show a header badge on WO detail.
- **New Customer badge**: derived (`NOT EXISTS` a prior Completed/Invoiced WO for the
  same customer with an earlier `start_date`), shown on the dispatch board (block +
  popover) and WO detail header, per the directive.

**Migration:** 019 (`019_internal_tasks.sql`: `customer_id` nullable +
`is_internal_task` + CHECK constraint), applied to all four DBs. Pre-migration
backups in `~/db-backups/2026-09-19j/`.

**Commit:** (pending — migration file, `app.py`, `workorder_form.html`,
`workorder_detail.html`, `workorder_list.html`, `dispatch.html`, `daysheet.html`,
`jobs_report.html`, `extraction_queue.html`, smoke test, this entry, decisions log,
status doc).

**Smoke test:** `tests/smoke_tag_replacements.py` — 21/21 checks. Covers: creating an
internal task through the real form with no customer; it appearing correctly (as
"Internal Task") in the WO list and on the dispatch board with a null
`customer_name` in the JSON; the WO detail badge and the invoice banner correctly
hidden; an invoice attempt correctly blocked with zero invoices created; the New
Customer badge appearing on a customer's first-ever job and correctly NOT appearing
on their second job once the first is Completed, verified both on WO detail and via
the dispatch data endpoint. Cleanup verified zero residue. All 12 prior smoke tests
re-run clean as regressions — confirming the 11-site LEFT JOIN conversion didn't
change behavior for any existing (always-has-a-customer) WO.

**Deferred:** Callback (§4.4) and Delinquent Account (`customer_flags`, §3.5) — both
explicitly later increments per the directive's own table, not scope creep out of
2.4.

This closes out Stage 2's increments that don't require host-level changes. Increment
2.5 (nightly/periodic jobs) needs a host crontab installed under sudo — flagging for
Chris before proceeding, per the directive's own installation instructions.

---

## 2026-09-19 — Stage 2, Increment 2.5 — Scheduled jobs (nightly + periodic)

Chris's condition for proceeding: build it with a master on/off switch defaulting to
off, prove the email path actually works via a mocked test, and only then install the
real cron schedule. All three done, in that order — see D-065.

**What:**
- **Migration 020**: `customer_flags` (customer_id PK, is_delinquent,
  oldest_open_invoice_date, open_balance, unapplied_credit, computed_at), `job_runs`
  (job_name, company_key, started_at/finished_at, status, summary),
  `work_orders.alert_sent_at` (per-WO dedupe for the uninvoiced alert),
  `company_settings.scheduled_alerts_enabled` (the master switch, default FALSE).
- `phase1/fieldkit_backend/jobs.py`: thin CLI wrapper (`python jobs.py <subcommand>`,
  loops all four companies) around job functions living in `app.py` so they're
  directly importable/testable — matches how every other piece of this codebase is
  structured. Subcommands: `nightly`, `uninvoiced`, `eod_escalation`,
  `weekly_sales_report`.
  - `nightly`: recomputes `customer_flags` for every customer (reusing the exact
    `_customer_aging_summary`/`customer_unapplied_credit`/`DELINQUENT_DAYS_PAST_INVOICE`
    the billing page already uses — same answer everywhere, always); refreshes
    `extraction_day_count` for active extractions; writes "Missed Today"
    `extraction_daily_log` rows for active jobs with no log entry for yesterday;
    sends a day-5+ escalation email (gated by the switch). Customer ratings (§4.2)
    and dormancy alerts (§4.1) explicitly skipped with a note — neither exists yet
    (D-066).
  - `uninvoiced`: Completed, billable (non-internal-task), uninvoiced WOs whose most
    recent Completed status-history entry is over an hour old; one email per WO
    (gated by switch), deduped via `alert_sent_at` so it never re-fires for the same
    WO.
  - `eod_escalation`: one digest email of every still-uninvoiced Completed WO — not
    deduped, since it's a standing summary, not a per-item alert (D-067).
  - `weekly_sales_report`: no sales CRM exists yet (Stage 3) — records a `skipped`
    job_runs row with an explanatory summary rather than erroring.
  - Every job writes a `job_runs` row via a shared start/finish wrapper regardless of
    the switch, so the status panel always shows a real last-run timestamp.
- **Master switch UI**: `/settings/company` gets a "Scheduled Jobs" panel (admin
  only) — the switch as its own explicit POST action (not bundled into the general
  settings save, so flipping it is a deliberate, separately-logged action) plus a
  table of last-run-per-job. Lives on `/settings/company` rather than a new settings
  landing page, since this codebase has never had one (D-069).
- **Delinquent badge**, deferred from 2.4 (D-046) pending `customer_flags`, now
  wired to customer detail, the WO form's customer picker, and the dispatch board
  (D-068) — completing that part of the retired-tag replacement work. Billing page
  keeps its own pre-existing live computation (already correct, already tested).
- **Cron installed**: the directive's exact 4-line schedule, under the `letize`
  user's own crontab (no passwordless `sudo` available — the directive's own
  documented fallback), documented in `docs/DEPLOYMENT/cron-jobs.md` (D-070). All
  four subcommands were run for real against production data before and after
  installing — safe, since the switch is off, confirmed zero emails sent (all four
  ran clean: 1,330/3,013/903/61 real customers' flags recomputed across the four
  companies, 0 delinquent — no real invoice data exists yet).

**Migration:** 020 (`020_scheduled_jobs.sql`), applied to all four DBs. Pre-migration
backups in `~/db-backups/2026-09-19k/`.

**Commit:** (pending — migration file, `app.py`, `jobs.py` (new), 
`company_settings_form.html`, `customer_detail.html`, `workorder_form.html`,
`dispatch.html`, `docs/DEPLOYMENT/cron-jobs.md` (new), smoke test, this entry,
decisions log, status doc).

**Smoke test:** `tests/smoke_scheduled_jobs.py` — 34/34 checks. Same safety
discipline as the 1.7 email test (Resend monkey-patched for the whole run, restored
in `finally`), plus a new layer specific to this increment: the real
`scheduled_alerts_enabled` value is captured before the test touches anything and
force-restored in `finally` regardless of outcome, so the production switch can
never be left on by a test run. Covers: `customer_flags` delinquency math against a
real hardened/sent invoice backdated 120 days; the delinquent badge rendering on
customer detail, the WO form's embedded customer JSON, and (implicitly, same query
path) the dispatch board; extraction day-count/Missed-Today upkeep; escalation with
the switch off (computes, sends nothing) and then on (computes AND sends, verified
via the mock call count and recipient); the uninvoiced alert's dedupe (second run
finds nothing new) versus the eod digest's non-dedupe (same fixture still appears);
switching back off and confirming fresh qualifying data still computes but sends
nothing; the `job_runs` wrapper functions; and the settings page panel + toggle
route. Cleanup verified zero residue and the real switch restored to off. All 13
prior smoke tests re-run clean as regressions.

**Deferred:** customer ratings (§4.2) and dormancy alerts (§4.1) — both later-stage
features the directive's nightly-job description references as if built; explicitly
skipped with a logged reason, not silently dropped.

This closes out Stage 2 in full. Awaiting Chris's direction on what's next — Stage 3
(estimates, ratings, sales CRM, callbacks) or a pause for real-world testing.

---

## 2026-09-19 — Post-Stage-2 correction: remove water extraction from Get a Grip

Chris caught this after reviewing the build: extraction was built for all four
companies through 2.2, but Get a Grip (bathtub/surface resurfacing) never does this
work. Not a new increment — a scoped correction.

**What:**
- `COMPANIES_WITHOUT_EXTRACTION = {'getagrip'}` (`app.py`) + a `has_extraction`
  Jinja global. `/extraction` and its 4 sub-routes now 404 for getagrip; the nav link,
  the WO form's "Deploy Equipment" button, and the whole Water Extraction card are
  hidden. Nothing deleted — the feature is untouched for the other three companies.
- Found and fixed a real bug while doing this: the WO form's submit handler assumed
  `#chkExtraction` always exists in the DOM to check whether to show the
  start-extraction prompt. Hiding the card for getagrip would have made that
  `getElementById(...).checked` throw and silently break WO form submission
  entirely for this company. Null-guarded before shipping.
- Per Chris's choice (asked directly rather than guessed): GAG's two unused
  `per_day_equipment` catalog items ("Ozone", "Ozone Treatment" — 0 equipment units,
  0 extraction jobs, ever) were deactivated, not deleted or converted.

**Migration:** none — this is UI/routing gating + one `UPDATE catalog_items SET
is_active = FALSE` on getagrip only, not a schema change.

**Commit:** (pending — `app.py`, `base.html`, `workorder_form.html`, new smoke test,
`smoke_extraction.py` switched to kleanit_charlotte, this entry, decisions log,
status doc).

**Smoke test:** `tests/smoke_extraction_company_gate.py` — 21/21 checks: the 404s,
nav/UI absence for getagrip, the other three companies fully unaffected, and the
Ozone catalog items confirmed deactivated. `smoke_extraction.py` (2.2's original
test) was switched from getagrip to kleanit_charlotte — the feature it exercises no
longer exists for the company it was written against — and re-verified 33/33. Full
15-file regression suite re-run clean.

Decisions: D-071 in `docs/DECISIONS-MADE-DURING-BUILD.md`.
