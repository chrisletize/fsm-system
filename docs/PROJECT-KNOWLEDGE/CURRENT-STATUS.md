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
| Work orders: list/search/new/edit/detail/delete, two-row-type line items, per-day equipment accrual, `work_site_label`, auto-description, double-booking banner, status history, tech assignment (username-keyed) | Built |
| Billing page | Minimal v1 only — customer list + billing-contact readiness + CSV export. No balances/aging/statements. |
| `tax_rates` | Built, effective-dated (migration 009), `/settings/tax` UI live. 101 rows (NC) in GAG/KC/CTS, 0 in Kleanit SF. |
| `company_settings` | Built (migration 009), `/settings/company` UI live. One seeded row per DB (`company_name` only; everything else NULL pending Chris/Michele). |
| Invoice engine | Backend-only tables (`invoices`/`invoice_line_items`/`invoice_status_history`), zero rows in production, no routes/UI. |
| `customer_compliance_portals` | Table exists, 0 rows, no UI. |
| Dispatch, extraction queue, reports, estimates, sales CRM, company settings, payment methods, tax settings UI, tags, dashboard stats | Not built |

This table matches `FIELDKIT_BUILD_DIRECTIVE_2026-09.md` §0.2 — confirmed by grepping
the full route list out of `app.py` (3,248 lines) and querying row counts in all four
production databases directly, not taken on faith from either doc.

## Current build
Following `docs/FIELDKIT_BUILD_DIRECTIVE_2026-09.md` stage by stage. Stage 0 complete.
**Stage 1 — Finish invoicing & billing**: Increment 1.1 (effective-dated tax rates +
`/settings/tax` + `company_settings` + `/settings/company`) complete. Next: Increment 1.2
(receivable/version refactor — the largest structural change in Stage 1).

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

*Last commit at time of writing: `e75366a` (2026-09-18).*
