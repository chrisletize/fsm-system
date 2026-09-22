# FieldKit — Current Status
*Rewritten 2026-09-18 at the start of the September 2026 build
(`docs/FIELDKIT_BUILD_DIRECTIVE_2026-09.md`). Supersedes the 2026-02-10 version, which
described an early Phase 1 state long since overtaken by the actual repo. Update this
file at the end of every stage per the directive's §1.3.*

## What FieldKit is
A custom Flask/PostgreSQL field-service platform (DB-per-company, no shared `company_id`
column) replacing ServiceFusion for four companies: Get a Grip Charlotte, Kleanit
Charlotte, CTS of Raleigh, Kleanit South Florida. Live at
`~/docker/fieldkit-prod/` on ubuntu-business, containers `fieldkit-prod-app-1` (port
3000) / `fieldkit-prod-db-1` (postgres:16). The sibling Phase 0 statements site
(`~/docker/statements/`, port 3100) is what Michele still uses daily for statements/tax
reporting until FieldKit's billing is complete.

## What's built today (verified against the repo and live DBs, 2026-09-18)
| Area | State |
|---|---|
| Auth, RBAC, company-in-URL multi-tab, branding | Built |
| Customers: list/search/detail/new/edit, contacts (billing flags), service locations, custom fields, notes | Built |
| Users: list (per-company scoped)/new/edit (incl. username rename)/reset-password/toggle-active/email reset via Resend | Built. Dispatchable/active-tech are per-company (migration 028, `user_company_dispatch`), not global. See D-094. |
| Catalog CRUD, equipment registry CRUD | Built |
| Work orders: list/search/new/edit/detail/delete, two-row-type line items, per-day equipment accrual, `work_site_label`, auto-description, double-booking banner, status history, tech assignment (username-keyed), tech/date list filters, live catalog-duration estimate | Built |
| Dispatch board | Built (2.1, migration 017, `/dispatch`): drag-to-move, resize, click-to-popover, day/week views, collision detection, tech profiles (color/dispatchable/sort order) on the user form. |
| Billing page | Full rebuild (1.8): summary cards, aging strip, filter bar (delinquent/no_contact/portal/all), per-customer Record Payment pre-filtered to real open invoices. |
| A/R Aging report | Built (1.8, `/reports/aging`), 4-bucket (0-30/31-60/61-90/90+), sortable, print-friendly drill-down. |
| `tax_rates` | Built, effective-dated (migration 009), `/settings/tax` UI live. 101 rows (NC) in GAG/KC/CTS, 0 in Kleanit SF. |
| `company_settings` | Built (migration 009), `/settings/company` UI live. One seeded row per DB (`company_name` only; everything else NULL pending Chris/Michele). |
| Invoice engine | Receivable/version schema + full UI (1.2–1.6) + email delivery (1.7, migration 014) + WTN/PO + compliance portal fields (1.8, migration 015). Zero real invoice/payment/email rows in production yet (only test fixtures, created and cleaned up by each smoke test — email tests use a monkey-patched Resend + `.invalid`-address fixtures, confirmed zero real sends). |
| Compliance portals | Built (1.8, migration 015): `customer_compliance_portals` table, enrollment/edit/toggle UI, auto-assign-on-harden, `/compliance` review page with accept/reject + generic `.xlsx` export (real per-portal templates still pending from Chris/Michele). |
| NC cash-basis tax report | Built (1.10, migration 016, `/reports/tax`): cash-basis by county, state/county/transit split incl. Mecklenburg's 1% additional-county line, refund handling, Excel + PDF export. Untested against real data (none exists yet). |
| Cutover import from ServiceFusion | Built and run for real for Get a Grip (2026-09-22): `import_catalog.py`, `import_open_invoices.py`, `import_job_history_direct.py` (all `phase1/fieldkit_phase1/`, dry-run default). Sources directly from ServiceFusion exports, not the statements DB — that premise turned out wrong (D-038: zero invoice/tax rows there for all four companies). See D-093. Kleanit Charlotte/CTS/Kleanit SF not yet run — waiting on their exports. |
| Water extraction queue | Built (2.2, migration 018, `/extraction`): one-WO-lifecycle model (no cloning), daily log, Retrieved flow with per-day billing recompute, pickup-list PDF, follow-up-WO offer. **Not available for Get a Grip** (bathtub/surface resurfacing — never does this work; gated post-build 2026-09-19, D-071). Fully intact for the other three companies. |
| Day sheet / hours / job activity reports | Built (2.3, `/reports`, `/reports/daysheet`, `/reports/hours`, `/reports/jobs`): printable per-tech schedule, honest "scheduled not actual" hours, job list + CSV export. No migration needed — all columns already existed. |
| Retired-tag replacements | Built (2.4 + 2.5, migrations 019/020): `is_internal_task` (customer-less WOs), derived "New Customer" badge, and (once `customer_flags` existed) the Delinquent Account badge on customer detail/WO form/dispatch board. Callback still deferred to §4.4. |
| Scheduled jobs | Built (2.5, migration 020, `phase1/fieldkit_backend/jobs.py`): nightly customer_flags/extraction upkeep, uninvoiced alert, EOD digest, weekly sales report placeholder. Per-company master on/off switch (`company_settings.scheduled_alerts_enabled`, `/settings/company`) — **off for all four companies**; cron installed and live (computing/logging) but sends no real email until switched on. See `docs/DEPLOYMENT/cron-jobs.md`. |
| Estimates | Built (3.1, migration 021, `/estimates`): Draft/Sent/Approved/Declined/Converted lifecycle, PDF + email send, convert-to-WO, public request form at `/request/<company>` (no login, honeypot + rate limit), requests queue. Permissions: admin/manager/salesperson. |
| Customer ratings | Built (3.2, migration 022): nightly A–F grade (payment timeliness + cancellation rate + job volume), manager override, badges on customer detail/WO form/estimate form/dispatch popover. Currently all grade A across all four companies — no real invoice/WO history exists yet. |
| Recency report | Built (3.3, migration 023, `/reports/recency`): last-service date = GREATEST of WO history and imported `customer_job_dates`, bucketed 1-2/3-6/6-12/12+ months (boundaries matched to the Phase 0 site), grouped by management company, PDF export. History-import script (`import_job_dates.py`) written and dry-run for real against production statements data — 258 customers/2,859 job dates would import for Get a Grip (the only company with statements job history); `--commit` on hold pending Chris's review. |
| Callbacks | Built (3.4, migration 024): WO form's "This is a callback for…" combo pre-fills location/site/lines from the prior job, defaults Responsible Tech to its lead tech; badges on dispatch/WO list/customer detail/WO detail; `/reports/callbacks` grouped by responsible tech with paid-vs-unpaid detection (no payroll engine — just exposes the data); customer rating gets a new signed `callback_score` (-3 per callback, trailing 12mo). |
| Sales CRM | Built (3.5, migration 025): prospects/contacts/visits/approval-queue CRUD under `/sales`, mobile quick-tap visit logging, follow-ups, unified customer+prospect search, dormant-customer detection reusing the recency-report formula, convert-to-customer via manager approval (creates customer + contacts in one transaction), Monday weekly report email. See below. |
| Dashboard | Built (5.1, no migration, `/<company>/dashboard`): today's jobs, uninvoiced completed WOs (loud), open extraction units, outstanding A/R + 90+ + unapplied credits (from the `customer_flags` nightly cache), follow-ups due, pending approvals, last-15 recent activity across WO/invoice/payment status history, role-gated Quick Actions. Role-gated sections, not a role-gated route — technicians land on the reduced view; salespeople land on the full sales-aware view. |
| Customer merge + duplicate detection | Built (5.2, migration 026): non-blocking duplicate-customer banner on the customer form; admin-only `/customers/<id>/merge` with AJAX side-by-side preview and a one-transaction merge across every referencing table; merged customer URLs redirect to the target. |
| Audit trail | Built (5.3, migration 027): `record_audit` written from customers/contacts/service locations/work orders/invoices/payments/estimates/catalog/tax rates/users via one shared `_record_audit()` helper; read-only History panel on customer/WO/invoice/payment detail; admin-only global view at `/settings/audit`. |
| Permissions sweep + My Day | Built (5.4, no migration): full route audit against the Appendix A matrix, gaps closed (see D-091); technician customer access read-only and scoped to own-job customers (`_technician_customer_ids()`); `/<company>/myday` — date-scoped list of a technician's own assigned WOs with On The Way / Start / Complete status buttons. |
| Settings landing + in-app help | Built (5.5, no migration): `/<company>/settings` (admin/manager) with a card per reachable settings page plus the Scheduled Jobs panel inline; collapsible `help_panel()` macro on invoice detail (Revise vs. Reissue), billing, estimate detail, the WO form, extraction queue, and My Day. See D-092. |
| Payment methods | Not built |

This table matches `FIELDKIT_BUILD_DIRECTIVE_2026-09.md` §0.2 — confirmed by grepping
the full route list out of `app.py` (3,248 lines) and querying row counts in all four
production databases directly, not taken on faith from either doc.

## Current build
Following `docs/FIELDKIT_BUILD_DIRECTIVE_2026-09.md` stage by stage. Stage 0 complete.
**Stage 1 — Finish invoicing & billing**: Increments 1.1 through 1.8 and 1.10 complete
(tax rates/company settings, receivable/version invoice refactor, invoice UI, payments,
invoice PDF, statements, email delivery, billing page rebuild + A/R aging + compliance
portals, NC cash-basis tax report). Increment 1.9 (cutover data import) is deferred at
Chris's direction (2026-09-19) until the site is ready for his and Michele's
day-to-day testing — see D-038 for what was found investigating the source data.
Stage 1's remaining exit criteria (tax report reconciling by hand, Michele's
walkthrough) need real data/Michele's time, not more code.

**Stage 2 — Finish scheduling: COMPLETE.** Increments 2.1 (tech profiles + dispatch
board, migration 017), 2.2 (water extraction queue + accrual engine, migration 018),
2.3 (day sheet/hours/jobs reports, no migration), 2.4 (retired-tag replacements,
migration 019), and 2.5 (scheduled jobs, migration 020, cron installed under the
`letize` user per the directive's sudo-unavailable fallback) all done. Found and
fixed three bugs along the way, none of them introduced by the increment that caught
them: D-043/D-044 (2.1, pre-existing — user creation silently failed on every DB; the
tech checklist always rendered empty for 3 of 4 companies) and D-057 (a 2.1
regression caught by 2.3's smoke test — saving a WO with a manually-overridden
duration 500'd). Scheduled email alerts are installed and computing for real but
switched OFF for all four companies pending Chris's review — see
`docs/DEPLOYMENT/cron-jobs.md`.

Stage 2 exit criteria from the directive: dispatcher scheduling/moving/overlap-seeing/
day-sheet-printing — done and smoke-tested; extraction Day 1 → Day 4 → Retrieved →
invoice — done and smoke-tested; cron jobs showing last-run timestamps — done (the
Scheduled Jobs panel); "a customer 61+ days overdue is red everywhere" — done using
Chris's 90-day threshold instead of the directive's 60-day default (D-001), on
customer detail, WO form, dispatch board, and billing page.

**Post-Stage-2 correction (2026-09-19):** water extraction was built for all four
companies, but Get a Grip never actually does this work — Chris caught it after
review. Gated off for getagrip specifically (`COMPANIES_WITHOUT_EXTRACTION` in
`app.py`): `/extraction` 404s, nav link/WO-form UI hidden, two unused catalog items
deactivated. Nothing removed for the other three companies. See D-071.

**Stage 3 — Estimates, ratings, sales CRM, callbacks: COMPLETE.** Increment 3.1 (estimates + public estimate request form, migration 021)
complete — full Draft→Sent→Approved→Converted lifecycle, PDF/email send, decline
with reason, convert-to-WO (a WO save flips the source estimate, not the navigation
click), public no-login request form with honeypot + 5/hr per-IP rate limit, requests
queue with "Create customer + estimate." Increment 3.2 (customer rating system,
migration 022) complete — nightly A–F grade, manager override, badges on all four
display points. Caught and fixed a test-only bug along the way (D-083 — a prior
increment's smoke test didn't know about the new table its own job_nightly() call
now writes to; a stray production `alert_email` value from that got caught and
cleaned by hand). Increment 3.3 (recency report + history import, migration 023)
complete — report + PDF export built and smoke-tested; `import_job_dates.py`'s real
dry run confirms 258 customers/2,859 job dates for Get a Grip only (consistent with
D-038 — the other three companies have zero statements job history), 38 unmatched
names logged for Chris/Michele; the actual `--commit` import stays on hold per his
2026-09-19 instruction. Increment 3.4 (Callbacks, migration 024) complete — self-
referencing WO link with a required reason, prefill from the prior job, badges
everywhere the directive lists, `/reports/callbacks` (paid vs. unpaid, no payroll
engine), and a new signed `callback_score` folded into the customer rating.
Increment 3.5 (Sales CRM, migration 025) complete — the largest piece of Stage 3:
prospects/contacts/visits/approval-queue schema built against
`docs/SALES-SYSTEM.md`; dashboard/prospect/contact/visit-log/follow-ups/approvals
routes under `/<company>/sales/…`; mobile quick-tap visit logging with tag-driven
follow-up dates; unified customer+prospect search (live AJAX, not a preloaded
combobox — getagrip alone has 5,307 customers); dormant-customer detection
reusing the exact recency-report last-service-date formula against each
company's own `dormancy_alerts_config` threshold; prospect-to-customer conversion
gated through a manager `approval_queue` review (never a direct sales-side write
to `customers`); the Increment 2.5 `job_weekly_sales_report` placeholder now does
the real Monday report. Stage 3 is now complete — all five increments (3.1–3.5)
done, smoke-tested, and the full 20-file regression suite green.

Stage 3 exit criteria from the directive: Chris O logs a visit in under a minute on
a tablet (built, not yet exercised by Chris O himself — smoke-tested only); a
prospect converts through approval into a real customer (done, smoke-tested); an
estimate is sent and converted to a WO (done since 3.1); the Monday report arrives
(built and smoke-tested with alerts forced on — real delivery still waits on a
company having `scheduled_alerts_enabled` switched on, which all four don't yet,
per Increment 2.5); ratings show on the board (done since 2.1/3.2). Next up:
**Stage 4 — Dashboard, data quality, permissions sweep, help** (directive §5).

**Stage 4 — Dashboard, data quality, permissions sweep, help**: in progress.
Increment 5.1 (Dashboard) complete — replaced the Phase 1 placeholder with the
real thing: today's jobs, uninvoiced completed WOs (loud), open extraction
units, outstanding A/R + 90+ + unapplied credits (read from the `customer_flags`
nightly cache rather than a live per-customer walk — see D-088), follow-ups due,
pending approvals, last-15 recent activity, role-gated Quick Actions. No
migration — every table read already existed. 21/21 smoke checks
(`tests/smoke_dashboard.py`), full 21-file regression suite green.
Increment 5.2 (customer merge + duplicate detection, migration 026) complete —
non-blocking duplicate-customer banner on the customer form (reuses the
double-booking brick's normalized-match SQL); admin-only merge tool with a
search-and-pick target picker, AJAX side-by-side preview, and a one-transaction
merge that re-points every referencing table (with explicit collision handling
for the three UNIQUE-constrained ones), soft-deletes the source with
`merged_into_customer_id` set, notes both customers, and logs to
`customer_merge_log`; visiting a merged customer's old URL now redirects to the
target instead of 404ing. See D-089. 24/24 smoke checks
(`tests/smoke_customer_merge.py`), full 22-file regression suite green.
Increment 5.3 (audit trail, migration 027) complete — `record_audit` written
from all ten entity types the directive lists (customers, contacts, service
locations, work orders, invoices/versions, payments, estimates, catalog, tax
rates, users) via one shared `_record_audit()` helper; update diffs show only
what changed (a no-op save writes nothing); `password_hash` is redacted
centrally inside the helper, not per call site — see D-090 for the bug this
design caught on the first smoke-test run (briefly present in a test fixture,
never a real user). Read-only History panel on customer/WO/invoice/payment
detail; admin-only global view at `/settings/audit`. 46/46 smoke checks
(`tests/smoke_audit_trail.py`), full 23-file regression suite green.
Increment 5.4 (permissions sweep) complete — full route-by-route audit (142
routes) against the directive's Appendix A matrix found and fixed 13
completely ungated Customers-area routes + `billing_export`, 3 routes too
permissive for manager, 5 too restrictive for salesperson; technician
customer access is now read-only and scoped to customers they've been
assigned a work order for (`_technician_customer_ids()`), not a flat
exclude. **New**: `/<company>/myday`, the technician mobile-stand-in page —
date-scoped list of the tech's own assigned WOs with On The Way / Start /
Complete buttons writing the two status values (`'On The Way'`,
`'In Progress'`) the schema had already reserved for this surface but
nothing could reach until now. See D-091. 42/42 smoke checks
(`tests/smoke_permissions.py`), full 24-file regression suite green.
Increment 5.5 (settings landing + in-app help) complete — `/<company>/settings`
(admin/manager) with a card per reachable settings page plus the Scheduled
Jobs panel rendered inline; a collapsible `help_panel()` macro added to six
pages with a genuine reconciliation rule to explain (invoice Revise-vs-Reissue
is the directive's own worked example; also billing, estimates, the WO form,
extraction, and My Day). See D-092. 27/27 smoke checks
(`tests/smoke_settings_landing.py`), full 25-file regression suite green.

**Stage 4 is functionally complete** (Increments 5.1–5.5 all done, smoke-tested,
full regression suite green throughout).

**Increment 5.6 / Stage 5 cutover — in progress, Get a Grip done (2026-09-22).**
Chris supplied real ServiceFusion exports for Get a Grip; three new scripts
built and run for real (`phase1/fieldkit_phase1/import_catalog.py`,
`import_open_invoices.py`, `import_job_history_direct.py` — dry-run default,
`--commit` to write). Committed: 45 catalog items, 268 open invoices
totaling **$179,521.14**, 1,285 job-history rows across 141 customers. 24
invoice + 39 job-history ServiceFusion customer names didn't match any
FieldKit customer (heavy overlap between the two lists — logged to CSV under
`~/servicefusion-imports/get-a-grip/_review/` for Chris). Three mismatched
pre-existing GAG catalog items soft-deleted. See D-093 for every scope
decision, the regression the catalog cleanup caused and how it was fixed,
and the `smoke_dashboard.py` test fix real production data exposed.
**Deferred**: the same import for Kleanit Charlotte, CTS, and Kleanit South
Florida once Chris supplies their exports; company settings fields (legal
names, remit-to text, reply-to/alert emails) and non-admin user password
resets still need Chris's input before they can be entered.

**Post-Stage-4 fix (2026-09-22)** — User Management usability, flagged by
Chris after using the built site, not a directive increment: `/settings/users`
is now scoped per company (a user only appears on a company's page if they
actually have access to it); `can_be_dispatched`/`is_active_tech` moved off
`users` onto a new per-(user, company) table, `user_company_dispatch`
(migration 028) — a tech with multi-company access is no longer forced onto
every one of their companies' dispatch boards; and usernames are now editable
(was a disabled field, never a real DB constraint) with a rename cascade that
keeps a tech's current work-order assignments intact while leaving historical/
audit records showing whoever it was at the time, plus a self-rename block.
See D-094. 20/20 smoke checks (`tests/smoke_user_management.py`), full
26-file regression suite green.

**Post-Stage-4 fixes (2026-09-22, same day)** — three more usability/bug
reports: (1) `_company_techs()` hard-required `role='technician'`, so the
"Field tech" checkbox silently did nothing for any other role — Chris
himself (admin, is_field_tech=TRUE) was invisible on the dispatch board;
fixed to `(role='technician' OR is_field_tech=TRUE)`. (2) Dispatch board
left-click on an empty slot no longer jumps straight into a new WO form —
right-click opens a small menu with the same action instead. (3) An
internal task could never actually be saved (line items stayed required
even though the customer field correctly became optional) — fixed, and per
Chris's own framing, internal tasks now use a "Task Details" notes field
instead of line items entirely (reuses the existing `notes_for_techs`
column). No migration. See D-095. 8/8 new smoke checks
(`tests/smoke_field_tech_dispatch.py`) plus 6 more in an updated
`smoke_tag_replacements.py`, full 27-file regression suite green. The
right-click menu was verified via rendered HTML only, not a live browser
walkthrough — disclosed gap.

Next: the same cutover import for the other three companies, then Stage 5's
remaining items (drift check, `DEPLOYMENT/RUNBOOK.md`, final doc pass) once
all four companies are done, or continue at Chris's direction.

Decisions Chris has already made for this build (delinquent threshold = 90 days past
invoice date, FL tax left empty/exempt for Kleanit SF, SF-import receivables excluded
from the tax report) are in `docs/DECISIONS-MADE-DURING-BUILD.md` D-001. Every other
undocumented choice is logged there as it's made, numbered `D-###`. Increment-by-increment
progress (migration numbers, commit hashes, smoke results) is in
`docs/BUILD-LOG-2026-09.md`.

## Known data quirk (not a bug, just worth knowing)
`fieldkit_getagrip.users` has 7 rows; the `users` tables in the other three DBs have 0.
Login only ever reads `getagrip`'s copy, and nothing else has a foreign key into a
per-company `users` table, so this doesn't break anything today. Full detail in
`CLAUDE.md` and `docs/DECISIONS-MADE-DURING-BUILD.md` D-003.

## Where things live
See `CLAUDE.md`'s pointer table for the doc map. `docs/FIELDKIT_BUILD_DIRECTIVE_2026-09.md`
is the authoritative work plan for this build; where it disagrees with an older design
doc, the directive wins (disagreements are catalogued in
`docs/FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md`).

*Last commit at time of writing: `48e2085` (2026-09-20).*
