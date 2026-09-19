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
| Water extraction queue | Built (2.2, migration 018, `/extraction`): one-WO-lifecycle model (no cloning), daily log, Retrieved flow with per-day billing recompute, pickup-list PDF, follow-up-WO offer. |
| Day sheet / hours / job activity reports | Built (2.3, `/reports`, `/reports/daysheet`, `/reports/hours`, `/reports/jobs`): printable per-tech schedule, honest "scheduled not actual" hours, job list + CSV export. No migration needed — all columns already existed. |
| Recency report, tag replacements, nightly jobs, estimates, sales CRM, payment methods, dashboard stats | Not built |

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

**Stage 2 — Finish scheduling**: Increments 2.1 (tech profiles + dispatch board,
migration 017), 2.2 (water extraction queue + accrual engine, migration 018), and 2.3
(day sheet/hours/jobs reports, no migration) complete. Found and fixed three bugs
along the way, none of them introduced by the increment that caught them: D-043/D-044
(2.1, pre-existing — user creation silently failed on every DB; the tech checklist
always rendered empty for 3 of 4 companies) and D-057 (a 2.1 regression caught by
2.3's smoke test — saving a WO with a manually-overridden duration 500'd). Next:
Increment 2.4 (replacements for the retired tag concept).

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

*Last commit at time of writing: `e7a9c27` (2026-09-19).*
