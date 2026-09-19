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
