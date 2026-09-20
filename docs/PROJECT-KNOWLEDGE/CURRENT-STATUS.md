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
| Users: list/new/edit/reset-password/toggle-active/email reset via Resend | Built |
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
| Cutover import from Phase 0 | Not built — deferred by Chris (2026-09-19) until the site is ready for day-to-day testing. Investigation-only finding logged: the statements DB (`fsm_prod`) currently has zero invoice/tax rows for all four companies (D-038); needs resolving before this increment actually runs. |
| Water extraction queue | Built (2.2, migration 018, `/extraction`): one-WO-lifecycle model (no cloning), daily log, Retrieved flow with per-day billing recompute, pickup-list PDF, follow-up-WO offer. **Not available for Get a Grip** (bathtub/surface resurfacing — never does this work; gated post-build 2026-09-19, D-071). Fully intact for the other three companies. |
| Day sheet / hours / job activity reports | Built (2.3, `/reports`, `/reports/daysheet`, `/reports/hours`, `/reports/jobs`): printable per-tech schedule, honest "scheduled not actual" hours, job list + CSV export. No migration needed — all columns already existed. |
| Retired-tag replacements | Built (2.4 + 2.5, migrations 019/020): `is_internal_task` (customer-less WOs), derived "New Customer" badge, and (once `customer_flags` existed) the Delinquent Account badge on customer detail/WO form/dispatch board. Callback still deferred to §4.4. |
| Scheduled jobs | Built (2.5, migration 020, `phase1/fieldkit_backend/jobs.py`): nightly customer_flags/extraction upkeep, uninvoiced alert, EOD digest, weekly sales report placeholder. Per-company master on/off switch (`company_settings.scheduled_alerts_enabled`, `/settings/company`) — **off for all four companies**; cron installed and live (computing/logging) but sends no real email until switched on. See `docs/DEPLOYMENT/cron-jobs.md`. |
| Estimates | Built (3.1, migration 021, `/estimates`): Draft/Sent/Approved/Declined/Converted lifecycle, PDF + email send, convert-to-WO, public request form at `/request/<company>` (no login, honeypot + rate limit), requests queue. Permissions: admin/manager/salesperson. |
| Customer ratings | Built (3.2, migration 022): nightly A–F grade (payment timeliness + cancellation rate + job volume), manager override, badges on customer detail/WO form/estimate form/dispatch popover. Currently all grade A across all four companies — no real invoice/WO history exists yet. |
| Recency report | Built (3.3, migration 023, `/reports/recency`): last-service date = GREATEST of WO history and imported `customer_job_dates`, bucketed 1-2/3-6/6-12/12+ months (boundaries matched to the Phase 0 site), grouped by management company, PDF export. History-import script (`import_job_dates.py`) written and dry-run for real against production statements data — 258 customers/2,859 job dates would import for Get a Grip (the only company with statements job history); `--commit` on hold pending Chris's review. |
| Callbacks | Built (3.4, migration 024): WO form's "This is a callback for…" combo pre-fills location/site/lines from the prior job, defaults Responsible Tech to its lead tech; badges on dispatch/WO list/customer detail/WO detail; `/reports/callbacks` grouped by responsible tech with paid-vs-unpaid detection (no payroll engine — just exposes the data); customer rating gets a new signed `callback_score` (-3 per callback, trailing 12mo). |
| Sales CRM | Built (3.5, migration 025): prospects/contacts/visits/approval-queue CRUD under `/sales`, mobile quick-tap visit logging, follow-ups, unified customer+prospect search, dormant-customer detection reusing the recency-report formula, convert-to-customer via manager approval (creates customer + contacts in one transaction), Monday weekly report email. See below. |
| Dashboard | Built (5.1, no migration, `/<company>/dashboard`): today's jobs, uninvoiced completed WOs (loud), open extraction units, outstanding A/R + 90+ + unapplied credits (from the `customer_flags` nightly cache), follow-ups due, pending approvals, last-15 recent activity across WO/invoice/payment status history, role-gated Quick Actions. Role-gated sections, not a role-gated route — technicians/salespeople still land here until §5.4 builds `/myday`. |
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
(`tests/smoke_customer_merge.py`), full 22-file regression suite green. Next:
5.3 (audit trail).

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
