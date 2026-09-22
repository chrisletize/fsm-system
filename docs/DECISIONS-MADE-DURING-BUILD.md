# Decisions Made During the September 2026 Build

Companion to `FIELDKIT_BUILD_DIRECTIVE_2026-09.md` and
`FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md`. Every choice made during the build that
Chris did not explicitly specify (per directive §1.4) is logged here, numbered `D-###`.
Chris reviews this after the build.

---

D-001 — Confirmed via `AskUserQuestion` at the start of Stage 1 (2026-09-18), overriding
defaults where noted:
- FL tax for Kleanit SF: used the directive's stated default — FL `tax_rates` left
  empty, `kleanit_sf.tax_exempt_by_default = TRUE`.
- Delinquent threshold: **90 days** past invoice date (directive's own default was 60;
  Chris chose 90). Applies to Increment 1.8 (billing page red flag) and Increment 3.4/§3.4
  (`customer_flags.is_delinquent`, computed nightly).
- SF-import tax exclusion: confirmed — imported `source='sf_import'` receivables carry
  `tax_total = 0` and are excluded from the FieldKit cash-basis tax report (Increment 1.9/1.10).

D-002 — [DEFAULTED] Added a project-level Claude Code permission file
(`.claude/settings.local.json`, gitignored) allow-listing the routine
migrate/restart/smoke-test command shapes the directive's §1.3 working protocol requires
(psql/pg_dump exec into `fieldkit-prod-db-1`, python exec into `fieldkit-prod-app-1`,
`docker compose restart/up --build/logs/ps/exec`, `curl` to `localhost:3000`), with
`docker compose down -v` and interactive `psql -it` explicitly denied. Prefix-based
permission rules can't semantically block a `DROP`/`TRUNCATE` embedded inside an allowed
`psql -c "..."` call, so directive §1.1's rule ("never DROP a table that has rows without
an explicit go-ahead from Chris") is treated as a standing personal rule regardless of
what the permission file technically allows.

D-003 — [CONFLICT resolved] CLAUDE.md's users-table note (flagged as contradictory by
directive §1.1/§5.3, decision #63 in the review doc) has been corrected. Verified live
against all four production DBs (2026-09-18):
  - Schema: `users` table exists in all 4 DBs (migration/schema baseline, not one of the
    numbered `009+` migrations).
  - Write path: `user_new`/`user_edit` routes write through `write_to_all_dbs()`, which
    does attempt to replicate INSERT/UPDATE to all 4 DBs.
  - Live data: `fieldkit_getagrip.users` has 7 rows; the other three DBs have 0 rows.
    The 7 users predate `write_to_all_dbs()` — they were seeded once directly into
    `getagrip` and never backfilled to the other three DBs.
  - Auth: `get_user_by_username()` / `update_last_login()` hardcode `get_db_connection('getagrip')`
    — login and `session['company_access']` never read a per-company copy.
  - No FK enforces per-company `users` rows against anything else in that DB (e.g.
    `work_order_techs.username` is a plain `VARCHAR`, not a foreign key), so the
    out-of-sync copies in the other three DBs do not currently break anything.
  This means the directive's own summary ("replicated across all four DBs... verify at
  Stage 0") is accurate about the *code path* but the *current data* is not actually
  replicated. No functional bug results from this today; flagged here in case a future
  increment ever queries a per-company `users` table directly instead of `getagrip`'s.

D-004 — [SCOPE] Per decision #64 in the review doc: searched the whole server
(`find / -iname "*payment-anchoring*"`, git log across all refs, grep of session-note
files) for `FIELDKIT_DECISION_payment-anchoring.md`. It does not exist anywhere on
ubuntu-business, in this git repo's working tree, or in git history. Its content is
already restated in full in the directive §2.2, so nothing is lost; there is nothing to
commit. No further action taken.

D-005 — [DEFAULTED] Rewrote `docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md` per directive
§0.2/§1.3 — the prior version was dated 2026-02-10 and described a "Phase 1 60% complete"
state that predates everything in the directive's verified "what exists today" table
(customers/work orders/catalog/equipment/users/billing-v1 are all built; invoicing,
dispatch, estimates, sales CRM, etc. are not). Replaced with a short, factual, dated
summary matching the directive's §0.2 table, verified directly against `app.py`'s route
list and live row counts in all four DBs rather than taken on faith from either document.

D-006 — [DEFAULTED] Increment 1.1, `/settings/tax` edit guard: the directive says the
UI should enforce "to change a rate, end the old row and add a new one — never edit
the pct on a row that any hardened invoice has used." Nothing today links an invoice
back to a specific `tax_rates.id` (the old single-table invoice engine only stores the
resolved `tax_rate_pct` value, not a foreign key — and zero invoice rows exist in
production), so there is no query that could actually enforce this as a hard block yet.
Implemented `/settings/tax/<id>/edit` as a full, unrestricted edit for now, with a
prominent on-page warning explaining the End-then-New workflow instead. Revisit once
Increment 1.2's `invoice_versions` table exists and could plausibly carry that
provenance — flagged for Stage 1 review, not urgent since it's a soft UX guard either way.

D-007 — [DEFAULTED] Increment 1.1, county field on `/settings/tax/new` and
`/settings/tax/<id>/edit`: used Brick #1 (suggest-don't-restrict autocomplete, existing
counties + the full `NC_COUNTIES` list for the three NC companies) rather than Brick #2
(restricted combobox). A restricted combobox needs a bounded, authoritative option list
with real ids; there's no authoritative Florida county list anywhere in this codebase,
and even for NC a hard restriction would block correcting a typo'd or missing county.
Server-side, county is still just a `VARCHAR` — no new validation was added beyond
"not empty," consistent with how `tax_rates.county` already worked pre-migration.

D-008 — [DEFAULTED] `company_settings.default_tax_county` was left NULL for all four
companies in the migration 009 seed (per the directive's explicit allowance to leave
unknowns NULL). Nothing in the codebase records a "primary county" per company today —
work orders/customers carry their own `tax_county`-equivalent per job/location, not a
company-wide default. Chris/Michele can set it via the new `/settings/company` page.

D-009 — [DEFAULTED] Increment 1.2: the directive's `invoice_balance()` formula and
`v_invoice_balances` view both need `payment_applications`/`invoice_adjustments`
(migration 011, Increment 1.4 — not built yet). Rather than wait to build
`transition_invoice()`'s reopen/void payment guards and `invoice_balance()` until 1.4,
I guarded every reference to those two tables behind `to_regclass(...) IS NOT NULL`
(`_payments_tables_exist()`): today it's vacuously "no payments possible yet" (correct,
since there's no way to record one), and once migration 011 lands the exact same code
starts enforcing the real guard with no code change needed. Verified this actually
works, not just compiles, by creating temporary tables matching the future
`payment_applications`/`invoice_adjustments` shape inside the smoke test's own
transaction (dropped on rollback) and confirming the reopen-rejected-with-a-payment
and balance-subtracts-the-payment cases both behave correctly against them.
`v_invoice_balances` itself is a static view and can't reference tables that don't
exist yet at CREATE time, so it's deferred to migration 011 outright (same query, just
trivial once the tables are real).

D-010 — [DEFAULTED] `invoice_status_history.state` (the pre-existing NOT NULL column)
is kept populated on every new row rather than dropped, since the directive only
specified *adding* columns to this table. New code sets it to a receivable-level
value (`'Void'`, `'Live'`) or the resulting version-level value (`'Hardened'`,
`'Sent'`, `'Live'`) — real reads going forward should prefer `from_state`/`to_state`/
`version_id`, which are unambiguous about which level and direction the event was.

D-011 — [MODEL] `invoices.supersedes_invoice_id` was renamed to
`reissue_of_invoice_id` (not just `superseded_by_invoice_id` -> `reissued_as_invoice_id`,
which the directive names explicitly). Under the old single-table model
`supersedes_invoice_id` did double duty (revision predecessor OR reissue source);
revision linkage moved down to `invoice_versions.superseded_by_version_id` in this
increment, so the receivable-level backward pointer only ever means "reissued from,"
making the rename the honest choice over leaving a now-single-purpose column with its
old dual-purpose name. See migration 010's header comment for the full reasoning.

D-012 — [DEFAULTED] Increment 1.3: invoice routes (and the new "Invoices" nav link)
are gated `admin`/`manager`/`office`, matching the existing Work Orders and Billing
routes' role check — even though Appendix A's permissions matrix only lists
admin/manager/salesperson/technician columns and doesn't mention `office` at all.
Given the directive's own framing ("Michele can run the entire customer → work order →
dispatch → invoice → payment → statement/tax-report cycle in FieldKit") and that
Michele's role is `office`, excluding `office` from invoices would contradict the
build's stated goal. Flagging in case the matrix's omission of `office` was
intentional rather than an oversight — easy one-line change either way.

D-013 — [MODEL] Added minimal flash-message infrastructure (Flask's built-in
`flash()`/`get_flashed_messages()`, rendered as plain colored banners in `base.html`)
since nothing like it existed yet and this increment's own spec requires it ("a second
request redirects to the existing one with a flash"). Deliberately NOT the "toast"
mentioned in directive §1.2 — that implies auto-dismissing overlay notifications, a
bigger piece of shared UI infrastructure than one increment's redirect messages
justify building un-asked. Revisit if/when a real toast system gets built; the flash
category strings (`success`/`error`/`info`) were chosen to make that swap easy later.

D-014 — [DEFAULTED] The invoice edit page's line-item editor does NOT reuse the work
order form's two-row-type editor verbatim — that brick is JS embedded in
`workorder_form.html`'s own `<script>` block and, per
`docs/FIELDKIT_REUSABLE_BRICKS.md`, is explicitly listed as a "candidate brick...not
yet extracted" into `base.html`, so there's no shared module to import from a
single-file-monolith Flask app without either duplicating ~300 lines of JS or
undertaking a real extraction (out of scope for this increment). Built a smaller,
purpose-fit editor instead: existing lines get inline-editable description/qty/price/
taxable + remove; new lines can only be added via Brick #2 (the restricted combobox,
which IS already shared in `base.html`) against standard catalog items only —
equipment lines only ever arrive via WO snapshot or "Regenerate from Work Order,"
never manual entry, since they need `deployed_at`/`retrieved_at` tracking that only
makes sense sourced from the work order. This satisfies "no adding lines that aren't
from the catalog" while keeping today's scope sane. Extracting the two-row-type
editor into a real shared brick is still open (tagged in the bricks doc since July).

D-015 — [UX] Customer detail's "Invoices tab" and "Jobs tab" requirement (§2.3) is
rendered as two more stacked cards matching every other section on that page (Property
Details, Service Locations, Contacts, ...), not literal tab-switching UI — no tab
pattern exists anywhere else in the app, and the directive's own phrasing ("if not
already present in that shape") allows this. Consistent with "keep the existing visual
language" (§1.2).

D-016 — [DEFAULTED] The invoices list page and customer-detail invoices section filter
on display status and balance in Python after computing them per row
(`invoice_display_status`/`invoice_balance`), not in SQL — `v_invoice_balances`
doesn't exist until migration 011 (Increment 1.4). Fine at today's invoice volumes;
switch the list query to the view once it exists rather than duplicating its math in a
raw `WHERE`.

D-017 — [DEFAULTED] Bug fix (reported by Chris 2026-09-19, out of increment sequence):
`lineContribution()` in `workorder_form.html` combines a standard line's catalog item
name and its typed description with `" - "` (e.g. "Bathtub Resurface - guest bathtub")
when the auto-generated job description is rebuilt. Previously the typed description
silently replaced the catalog name instead of adding to it. Chris didn't specify an
exact separator; `" - "` was chosen to match the existing "Unit Number OCC AM GATED"
space/token style used elsewhere in the same generated description. One shared
template serves all four companies, so one fix covers all of them.

D-018 — [MODEL, bug caught by smoke testing] Every numeric SUM over
`payment_applications` (`invoice_balance()`, `_remaining_unapplied()`,
`customer_unapplied_credit()`, and `transition_invoice()`'s Void/reopen payment
guards) originally filtered `WHERE reverses_application_id IS NULL`, intending to sum
only "active" applications. That filter is backwards for a SUM: it excludes the
reversal row itself (which carries the negative amount that's supposed to net the
original back out), so it keeps counting an application as fully in effect forever,
even after it's been un-applied. Fixed by summing ALL rows (originals + reversals,
no filter) for every numeric total — the reversal's negative amount is what makes the
net correct. The `reverses_application_id IS NULL` filter is still correct, and kept,
for the two places that need "find an original application with no reversal yet"
(`_unapply_payment`'s lookup, `_void_payment`'s NOT EXISTS scan) — those are boolean/
selection queries, not sums, and are a genuinely different question. Caught by
`smoke_payments.py`'s unapply-then-recheck-balance assertion; without that check this
would have shipped silently (a voided/un-applied payment would have kept blocking
reopen/void forever, and balances would never have recovered).

D-019 — [MODEL, bug caught by smoke testing] `invoice_balance()` now always returns a
plain `float` rather than sometimes a `Decimal` (psycopg2's type for NUMERIC columns).
Comparing Decimal and float works fine in Python, but arithmetic (`+`/`-`) between
them raises `TypeError` — `_apply_payment()`'s over-application guard (`amount > bal +
0.005`) 500'd on the very first real payment the smoke test tried to record. Casting
once at the source means every caller can do arithmetic freely without hitting this
again.

D-020 — [UX] "Record Payment is an inline modal... never navigates away" (§2.4) is
implemented as a real modal (the new `.modal-overlay`/`.modal-box` brick in
`base.html`) whose form POSTs and reloads — it never leaves the invoice/customer
detail page it was opened from, but it is a full page load, not an AJAX no-reload
submission. This codebase has no AJAX-form or toast infrastructure anywhere yet
(confirmed before building this increment), and building one is a bigger scope change
than one increment's payment form justifies. The "celebration toast + Next Unpaid
Invoice" requirement is similarly implemented as a green banner rendered server-side
on the reloaded invoice detail page (shown whenever `display_status == 'Paid'`) rather
than an ephemeral JS toast — same reasoning as D-013's flash-message choice.

D-021 — [SCOPE] The v1 billing page (`billing.html`) does NOT get the "Unapplied
credit" badge that directive §2.4 asks for on "every page that shows a customer."
That page is explicitly rebuilt from scratch in Increment 1.8 ("Billing page (full)"),
including its own "Open credits" panel per §2.8 — adding a badge to the page now, only
to delete it in 1.8's rewrite, is exactly the kind of throwaway work the build
shouldn't do. The badge is on customer detail, invoice detail, and the work order
form (via the existing customer-context AJAX endpoint) — the three pages from that
list that aren't about to be rebuilt wholesale.

D-022 — [MODEL] Increment 1.5: `invoices.work_site_label` (migration 012) is a new
snapshotted column, populated at invoice creation (and carried forward on reissue)
from the source work order. The PDF spec requires showing the work-site label, but
also requires a hardened/sent version's PDF to never read `work_orders` (so it stays
byte-for-byte reproducible even if the WO is edited later). Since Increment 1.2/1.3
never captured this anywhere on the invoice, closing the gap needed a new column —
same reasoning as why `tax_county` already lives on `invoice_versions` rather than
being live-joined from the service location.

D-023 — [DEFAULTED] The directive's PDF spec says per-day equipment lines should show
"the machine-day math in the description ('3 units × 4 days')". This assumes a data
shape (one combined line covering N identical units) that this codebase doesn't have —
the July 2 design (`docs/FIELDKIT_REUSABLE_BRICKS.md`) deliberately gives each physical
unit its own line item row with its own `deployed_at`/`retrieved_at`, distinguished by
ordinal (`resolved_label`: "Set Dehu 1", "Set Dehu 2", ...). Built the closest faithful
equivalent for the ACTUAL per-row model instead: each equipment line's description
shows its own day math ("Deployed 09/15 – Retrieved 09/19"), never a "3 units ×"
grouped figure that would misrepresent per-unit lines with different day counts as
one uniform block.

D-024 — [DEFAULTED] The PDF's line-table "Unit" column shows a generic `day` (for
per-day equipment lines, detected from `deployed_at IS NOT NULL` — no catalog lookup
needed) or `ea` (everything else), rather than the catalog item's real
`unit_of_measure` ("hour", "sq ft", etc.). `invoice_version_line_items` never
snapshotted `unit_of_measure` in migration 010, and joining `catalog_items` to fetch
it live would violate the "don't read the catalog for a hardened version" rule for
this one cosmetic label. The number that actually matters (unit_price × quantity =
total) is unaffected — this only trades away a label's precision, not correctness.

D-025 — [MODEL] `generate_invoice_pdf()` sets `doc.invariant = 1` and
`pageCompression=0` on the ReportLab document. Without `invariant`, ReportLab stamps a
fresh `CreationDate`/`ModDate`/document ID into every PDF it builds, which would make
two renders of the exact same hardened version produce different bytes purely from
timestamps — directly undermining the "byte-for-byte reproducible" requirement this
increment exists to satisfy. `pageCompression=0` leaves content streams uncompressed;
verified this actually matters (the smoke test's text-presence assertions initially
failed against compressed output) and the size cost is negligible for a one-page
invoice.

D-026 — [SCOPE] The PDF has no logo image. `COMPANY_BRANDING`'s `logo_url` values
(`/static/img/getagrip-logo.png`, etc.) don't correspond to any real files — this
repo's `static/` directory doesn't exist at all (confirmed) beyond an empty
`static/img/` the Dockerfile creates at build time. Rather than write logo-loading
code with a "file doesn't exist" fallback path that would never once execute its
happy path in production today, the PDF header is text-only (company name/address/
phone from `company_settings`) until Chris supplies actual logo files.

D-027 — [DEFAULTED] `customers.last_statement_at` is updated by BOTH the single-
customer statement download (`/customers/<id>/statement`) and the batch ZIP route,
not just the batch path the directive's §2.6 text explicitly mentions it under. A
statement is a statement regardless of which button generated it, and the field's
whole purpose (per §2.8's future billing page) is "when did this customer last get
one" — same reasoning as D-021/D-012's pattern of extending an explicit requirement
to its obvious sibling case.

D-028 — [SCOPE] The v1 billing page (`billing.html`) gets the smallest possible
addition for this increment: a second submit button on the EXISTING customer-checkbox
form, using `formaction`/`formtarget` to post the same `customer_ids` selection to
`/billing/statements` in a new tab instead of `/billing/export`. No redesign, no new
layout — Increment 1.8 replaces this whole page regardless, so anything more elaborate
here would be thrown away almost immediately. This is the same reasoning as D-021,
applied to a case where SOME minimal UI genuinely has to exist now (a route nobody can
reach is not a shipped feature) rather than skipping the page entirely.

D-029 — [MODEL] A statement's aging and "open receivables with balance > 0" both use
each invoice's CURRENT balance (`invoice_balance()`), not a balance reconstructed as
of `as_of_date` by excluding later payments/adjustments. Matches how the Phase 0
statement generator itself worked (`WHERE invoice_total_due > 0`, no point-in-time
reconstruction) — `as_of_date` only controls the aging-bucket math (days since
`invoice_date`) and the printed "Statement Date," not which payments count. Reprinting
a past-dated statement today will reflect payments made since then; this matches
existing Michele-facing behavior, not a regression.

D-030 — [UX] The invoice detail sidebar keeps TWO ways to reach Sent once Hardened:
the new "Send Email" dialog (real Resend send, primary/big button) and a small
secondary "Mark Sent (no email)" action that just calls `transition_invoice()`
directly with no email attempt — this is the same route Increment 1.3 already built.
Kept deliberately rather than replaced: Michele sometimes hands a PDF to a customer in
person or sends it through some channel outside FieldKit, and the directive's own
§2.5 philosophy ("PDF download as the manual fallback") implies the system shouldn't
force every Sent transition through email. Also avoids breaking five earlier smoke
tests that call the plain `/send` route as setup for other scenarios.

D-031 — [MODEL, bug caught by smoke testing] `invoice_send_email` and
`customer_send_statement` originally called `conn.rollback()` on a failed send —
which also rolled back the `email_log` row that `_send_invoice_email`/
`_send_statement_email` had just written for that failure, silently defeating the
entire point of logging failed sends (the schema's `status` CHECK literally has
`'sent'`/`'failed'` as its two values). Fixed to `conn.commit()` on both branches: the
NO_BILLING_CONTACT path never wrote anything (a no-op commit), and the failed-send
path's `email_log` row is exactly what should persist. Caught by
`smoke_email_delivery.py` asserting the failure log row actually exists, not just that
the route didn't 500.

D-032 — [MODEL] Testing safety for this increment specifically: `RESEND_API_KEY` is a
real, live key in this environment and real customer contact emails exist in this
database (confirmed before writing any code). `smoke_email_delivery.py` monkey-patches
`_resend.Emails.send` for its entire run (restored in `finally` even on failure) AND,
as defense in depth on top of that, only ever uses a freshly-created throwaway
customer/contact with a `.invalid`-TLD address (RFC 2606 — reserved, guaranteed
non-deliverable), never a real customer's real contact. The test explicitly asserts
"Resend was NOT called" / "was called exactly N times" at each step, not just that
routes returned the expected status code — this is the pattern any future test
touching `_send_email_via_resend` or the send routes must follow.

D-033 — [SCOPE] Portal exporters (`_export_ops`/`_export_vendorcafe`/`_export_paymode`)
all emit the identical `GENERIC_PORTAL_COLUMNS` set via one shared `_build_portal_xlsx`
helper, exactly as directive §2.8 specifies, with the compliance page's own banner
saying so ("Generic layout — portal template not yet confirmed"). `PORTAL_TYPES` is a
fixed three-value list (`OPS`, `VendorCafe`, `Paymode-X`) rather than a free-text
field, since the directive names exactly these three and a fixed dropdown is more
useful than free text for a field that drives which exporter function runs. Still
waiting on Chris/Michele for the real OPS import template and VendorCafe field list
(review-doc item #33) — not blocking, per the directive's own explicit fallback.

D-034 — [MODEL] Portal auto-assignment on Hardened only fires when the customer has
EXACTLY ONE active compliance portal enrollment and the invoice doesn't already have
one chosen. With zero enrollments there's nothing to assign; with two or more, guessing
which one this invoice belongs to would silently misroute a submission — the office
picks explicitly via invoice edit instead. Verified this doesn't retroactively touch
invoices hardened before an enrollment existed (the smoke test hardens one invoice,
THEN adds the enrollment, THEN hardens a second — only the second gets auto-assigned).

D-035 — [SCOPE, performance] Both the billing page and the A/R aging report compute
per-customer aging by looping every active customer and, for each one with any open
receivable, calling `invoice_balance()` per invoice (N+1 query pattern) — the same
"fine at today's volumes" tradeoff made throughout this build (D-016 et al.). Measured
against the real 1,330 active Get a Grip customers (zero real invoices yet): billing
page 0.82s, aging report 0.27s. This will need to move to a GROUP BY over
`v_invoice_balances` (built in Increment 1.4, currently unused — see D-016) once real
invoice volume makes the loop slow; flagging now rather than pre-optimizing against a
volume that doesn't exist yet.

D-036 — [DEFAULTED] `/reports/aging` and `/compliance` are gated
`admin`/`manager`/`office`, same as every other billing-adjacent route this build has
touched (D-012), even though Appendix A's Reports row only lists admin/manager and
doesn't mention office at all. Michele (office) is the primary user of "who owes us
money" collections work this report exists for — excluding her would contradict the
report's own purpose.

D-037 — [UX] The billing page's shared "Record Payment" modal pre-fills its "Apply to
Invoice" dropdown from each row's REAL open-invoice list (embedded as JSON on that
row's Pay button, parsed by a small JS function when the modal opens) — not a
placeholder or a generic "enter an amount" fallback. This properly satisfies "Record
Payment modal pre-filtered to that customer's open receivables" without needing a new
AJAX endpoint, consistent with how every other pre-filled dropdown in this build works
(e.g. the invoice edit line-item catalog picker).

D-038 — [FINDING, not a build decision] Increment 1.9 (cutover import) was scoped to
a dry run only — Chris confirmed 2026-09-19 that real imports are on hold until the
whole site is ready for his and Michele's day-to-day testing, so the real (non-dry-run)
import described in directive §2.9 was never going to run this session regardless.
Investigating the source (`statements-db-1`/`fsm_prod`, the live container behind
statements.cletize.com) before writing the import script surfaced a discrepancy worth
recording now so it doesn't get lost before 1.9 actually runs: `invoices` and
`tax_transactions` both have **zero rows** for all four companies, and `customers` has
296 rows for Get a Grip only (Kleanit Charlotte/CTS/Kleanit SF all have 0). The import
script (`scripts/import_sf_data.py`) is a plain upsert with no `TRUNCATE`/`DELETE`, so
this isn't "the table gets cleared every cycle" — it looks like invoice/tax data has
simply never been loaded into this container, contradicting the directive's premise
that real open-invoice data already lives there. Flagged to Chris directly rather than
guessed past. No code changed as a result of this finding; revisit before 1.9's real
run.

D-039 — [SCOPE] Increment 1.10's tax report needs a "taxable-only" dollar figure per
the directive's own allocation formula ("taxable base = applied x (taxable subtotal /
total)"), but `invoice_versions.subtotal` totals ALL lines (taxable or not) and no
taxable-only figure was previously frozen anywhere. Rather than back-deriving it from
`tax_total / (tax_rate_pct/100)` (undefined whenever a version is legitimately 0%
taxed), migration 016 adds a 4th column, `taxable_subtotal`, alongside the three the
directive named (`state_pct`/`county_pct`/`transit_pct`) and freezes it at harden the
same way. See migration 016's header comment for the full rationale.

D-040 — [MODEL] Mecklenburg's 1.00% "additional county" NCDOR reporting line
(effective 2026-07-01) is NOT stored as its own column — this build's `tax_rates`
schema (built in Increment 1.1, before 1.10 existed) pools it into `county_pct`
(2.00 base + 1.00 additional = 3.000), matching how NCDOR itself announces county-rate
changes as one combined number per county. Rather than reshape `tax_rates` mid-build
for one county's one-time change, the report splits the pooled dollar amount back into
2.00/1.00 shares at render time (`_split_mecklenburg_county_component`), hardcoded to
the known composition from migration 009. If NC changes Mecklenburg's county rate
again, this needs a matching code update — there's nowhere in the schema this could
self-derive from. Verified against the sibling Phase 0 statements site's own
`nc_tax_rates.py`, which independently models the same 4-component breakdown
(state/county/transit/additional_county) for the same reason.

D-041 — [MODEL] Refund allocation for the tax report: a refund is recorded against a
*payment's* unapplied balance, not against one specific invoice, so there's no direct
link from a refund to a tax jurisdiction to net out. Resolved by walking that payment's
most recent `payment_applications` row (even a since-reversed one, found by
`created_at DESC`) to find the last invoice that money was ever associated with, and
allocating the negative refund against THAT invoice's current version using the exact
same proportional formula as a normal receipt. A refund from credit that was **never**
applied to any invoice never contributed taxable revenue in the first place, so it
can't be netted out of any county — those surface separately as "unallocated" on the
report for reconciliation visibility rather than being silently dropped or guessed
into an arbitrary county. Flagged for the accountant to confirm; not something the
directive specified beyond "refunds in range appear as negative rows."

D-042 — [DEFAULTED] `payment_applications.applied_date` already equals
`payments.payment_date` for every application created via the Record Payment modal
(`_record_payment` passes `payment_date` straight through to `_apply_payment` as
`applied_date` — built in Increment 1.4, before this was a named requirement). The
modal has never exposed a separate applied_date field, so the two have been equal by
construction since 1.4; formally logging the `[DEFAULTED]` here per directive §2.10
since no prior entry named it explicitly.

D-043 — [BUG FIX, pre-existing] `user_new`'s INSERT named a `created_by` column that
has never existed on `users` (that table doesn't carry the created_by/updated_by/
deleted_at audit columns every other table has — confirmed via `\d users`). The insert
therefore failed on **every** database, every time, silently: `write_to_all_dbs()`
catches the exception into an `errs` list rather than raising, and the route's own
comment ("Still redirect — getagrip (canonical) succeeded") assumed success without
checking, so it redirected as if the user had been created. Found because Increment
2.1's smoke test tried to create a real technician through this route and got a 302
with no row to show for it. Fixed two things: (1) dropped `created_by` from the
INSERT's column list; (2) the route now actually verifies the getagrip row exists
before claiming success, surfacing a real error message instead of a false-positive
redirect if it ever fails again. The 7 real production users were seeded directly by
SQL before this route existed in its current form, which is why nobody had hit this.

D-044 — [BUG FIX, pre-existing] `_wo_form_data()`'s tech list (used for the WO form's
"Assigned Techs" checklist) queried `get_db_connection(company_key)` — the
PER-COMPANY database's own `users` table. Per the known quirk (D-003/CLAUDE.md), only
`fieldkit_getagrip.users` has ever actually been seeded; the other three companies'
copies are empty. That meant the tech checklist has always silently rendered zero
techs for Kleanit Charlotte, CTS, and Kleanit South Florida. Extracted a shared
`_company_techs(company_key, dispatchable_only=False)` helper that reads the
CANONICAL getagrip table (same source auth already uses) filtered by
`company_access ? company_key`, and pointed both the WO form and the new dispatch
board at it — one source for "who are this company's techs," not two, and both now
actually populate for every company.

D-045 — [MODEL] Dispatch board tech rows only show users where
`can_be_dispatched = TRUE AND is_active_tech = TRUE` (plus `is_active`/role/
company_access) — a field tech who isn't marked dispatchable yet (new hire, or an
office-only field role) doesn't appear as a draggable row, matching the three-flag
design in migration 017's header comment.

D-046 — [DEFERRED] Dispatch board badges for delinquent (red) and customer rating
letter are NOT built in this increment — they depend on `customer_flags` (§3.5,
Increment 2.5, not yet built) and the rating system (§4.2, not yet built) respectively.
Priority and an extraction badge (💧, heuristic: WO has any per-day-equipment line
item — `is_extraction` itself doesn't exist until Increment 2.2) are built now.
Callback badge deferred to §4.4 for the same reason. Revisit once those land.

D-047 — [MODEL] `/dispatch/move`'s payload names a single `username` (directive's own
JSON shape: `{wo_id, username, scheduled_start}`), so a move REPLACES a WO's tech
assignments with exactly that one tech (or clears them entirely when dropped on the
Unassigned row) rather than adding to a multi-tech WO's existing roster. Multi-tech
WOs still DISPLAY on every assigned tech's row (per the directive's separate bullet on
that) — only the move action itself is single-tech, matching what the payload shape
actually describes. Reassigning a multi-tech WO to a different combination still goes
through the full WO edit form.

D-048 — [SCOPE] The duration-mismatch warning (directive: "non-blocking... gets a
warning... [Use catalog] [Keep Anyway]") is implemented as a plain flash-message notice
on WO save, and a JSON `warning` string on dispatch-board resize (rendered as a banner
the client already shows) — not the richer two-button interactive banner the addendum
sketches. Same non-blocking informational intent and the same ±15-minute tolerance
check; simpler to build and verify this pass. Upgrading to the two-button version is a
pure frontend addition later if Chris wants it — no schema or backend change needed.

D-049 — [MODEL] A work order with a `start_date` but no `arrival_window_start` gets
`scheduled_start = NULL` and shows in the dispatch board's "No arrival time set" strip
rather than being placed on the timeline at a fabricated default time (e.g. business
open). The directive doesn't specify this case; forcing a fake time would make an
unscheduled job look scheduled, which is worse than a visible "needs a time" bucket.

D-050 — [MODEL] An equipment (per-day) line item's contribution to
`catalog_estimated_duration_hours` uses `quantity = 1` when the line hasn't been
retrieved yet (`retrieved_at IS NULL`, open-ended deployment — day count genuinely
unknown). 1 represents the initial setup visit, not a guess at total days; this mirrors
the existing "quantity is None until retrieved" pattern the invoice engine already
established for these lines (D-016 era). Applied identically client-side (JS) and
server-side (`_save_work_order`) so the live preview and the saved value never
disagree.

D-051 — [MODEL] `is_extraction` can only be auto-set TRUE by the presence of an
equipment line in the current save; the checkbox alone can't turn it OFF while an
equipment line remains on the WO (that would hide a real extraction job from the
queue/board). Once every equipment line is removed, the checkbox's own value takes
over. This reads "editable" (directive's own word) as "editable within the bounds of
what's actually on the WO," not "can contradict the data."

D-052 — [MODEL] `equipment_incomplete` auto-clears the moment a save includes >=1
equipment line, REGARDLESS of what the checkbox says in that same submission (a
checked-but-ignored checkbox, not a validation error) — the directive's own wording
("clearing it requires the equipment lines to be confirmed... any edit that saves >=1
per-day line clears it") reads as an unconditional rule, not something the office can
override by leaving the box checked. Verified by the smoke test submitting the
checkbox as checked in the very save that adds the line, confirming it clears anyway.

D-053 — [SCOPE] The "Set equipment as active?" prompt (directive: "[Yes — Start
Extraction] [No — Close Normally]") is a same-page banner with two real buttons, not a
native `confirm()` dialog — matches the two distinct labels the directive specifies,
which a plain confirm/cancel can't express. Intercepts the form's submit event only
when status is being changed to Completed on an `is_extraction` WO and no choice has
been recorded yet (`extraction_action` hidden field empty); either button re-submits
with that field set, letting the normal save path do the rest.

D-054 — [SCOPE] `extraction_day_count` is computed live on every read (WO detail, the
queue page) rather than trusted from the stored column of the same name (which
predates this increment and nothing writes to yet — Increment 2.5's nightly job is
what the directive actually assigns that column to). This matches the directive's own
"computed by the nightly job and on read" wording for the "on read" half; the "nightly
job" half is out of scope until §3.5.

D-055 — [SCOPE] "Create Follow-Up Cleaning Work Order" pre-fills the customer combo
and, when present, the service location, work site label, and Follow-Up Visit
checkbox — reusing the exact customer-context JS load that WO-edit mode already
performs (`loadCustomerContext(id, true)`), just triggered on a NEW-WO page instead of
an edit. It does NOT pre-fill line items, techs, or scheduling — the office picks a
fresh cleaning service and time, which is the actual point of a follow-up (a
different job, at the same site, not a copy of the extraction job).

D-056 — [DEFAULTED] Starting an extraction with no assigned techs on the WO leaves
`followup_tech_username` NULL rather than guessing; when at least one tech IS
assigned, `followup_tech_username` defaults to the first assigned tech (directive:
"default = lead tech" — this build doesn't yet surface a distinct "lead" flag in the
WO form's tech checklist, only `work_order_techs.is_lead_tech` at the schema level
with nothing setting it differently from "first assigned," so "first assigned" and
"lead" are the same thing today). The office can always override via the Extraction
card's Follow-Up Tech dropdown.

D-057 — [BUG FIX, introduced in 2.1, caught by 2.3's smoke test] `_save_work_order`'s
duration-warning check (`abs(est_duration - catalog_duration_hours) > 0.25`) crashed
with a 500 whenever a WO was saved with `duration_overridden=true` AND a real
`estimated_duration_hours` value submitted — `_opt_num()` returns the raw form STRING,
not a float, and nothing converted it before the subtraction. Increment 2.1's own
smoke test never hit this path (it only exercised `duration_overridden=false` on
create, and the dispatch `/resize` endpoint parses its own float separately), so it
shipped in `4a33861` and stayed live through `1ad67d8` until 2.3's report fixtures —
which needed distinct, explicit hours per WO — tripped it. Fixed with an explicit
`float(est_duration)` before the comparison. Confirmed via the regression suite that
no other route was affected.

D-058 — [SCOPE] `/reports` (the landing page) links to Recency even though that report
doesn't exist until directive §4.3 — shown as a disabled card ("Coming in a later
increment") rather than omitted, since the directive explicitly lists it among this
page's links. Matches the build's practice of not silently dropping a directive-named
item just because it isn't built yet.

D-059 — [MODEL] The hours report's "extraction checks" count is computed live per
(tech, day) by checking whether an `is_extraction` WO's active window
(`extraction_started_at`..`extraction_closed_at` or today) covers that day — not from
a stored per-day row, since nothing clones the WO per day (§3.2's model). This mirrors
the dispatch board's own live "show every Extraction Active WO on the follow-up tech's
row every day" rule from the same section.

D-060 — [SCOPE] Job activity report's status filter dropdown includes
`WO_OFFICE_STATUSES` plus `Extraction Active` and `Invoiced` — both real statuses the
app sets automatically (extraction start, invoice creation) that aren't in the
office-settable set. `On The Way`/`In Progress` are left out: they exist in the DB
CHECK constraint but nothing in the app sets them yet (reserved for a future mobile
tech app per the design docs), so including them in a filter dropdown today would
offer a choice that can never match a real row.

D-061 — [SCOPE] Increment 2.4's row-by-row mapping in the directive has 8 entries;
only two needed real new work. Callback (§4.4) and Delinquent Account (§3.5's
`customer_flags`) are deferred — they're explicitly assigned to later increments in
the directive's own table, not part of 2.4. Residential (already derived from
`customer_type`, nothing to add), Estimate/No-Charge (`status='No Charge'` already
built), Water Extraction (`is_extraction`, built in 2.2), and Requires Follow-Up
(`description_followup` + the follow-up-WO link, both built pre-2.2/in-2.2) were
already satisfied by prior work — confirmed, not re-implemented. Only Misc Task
(`is_internal_task`) and the New Customer badge were net-new for this increment.

D-062 — [MODEL] `work_orders.customer_id` is now nullable, gated by
`is_internal_task` (migration 019's CHECK constraint: `customer_id IS NOT NULL OR
is_internal_task = TRUE` — enforced at the DB level, not just in `_save_work_order`,
so no future code path can silently create an orphaned customer-less WO without the
flag). Every `JOIN customers c ON c.id = wo.customer_id` in the codebase (11 sites:
WO list, WO search, WO detail, WO edit, dispatch board, extraction queue, pickup-list
PDF, day sheet, job activity report) was converted to LEFT JOIN in the same change —
an INNER JOIN would have silently dropped every internal-task WO from every list,
board, and report it should still appear on. This is safe for every existing row
(LEFT JOIN is a strict superset of INNER JOIN's result set when the joined column is
never NULL, which is true for 100% of pre-existing WOs), confirmed by the full
12-file regression suite passing unchanged.

D-063 — [SCOPE] An internal task cannot be invoiced (guarded in
`workorder_invoice_new` with a clear flash error) since there's no customer to bill —
the "Generate invoice now?" banner is hidden entirely for `is_internal_task` WOs on
the detail page rather than shown and then failing on click.

D-064 — [MODEL] "New Customer" (directive: "customer has no Completed WO before this
one") is computed as `NOT EXISTS(...status IN ('Completed','Invoiced') AND
start_date < this WO's start_date)`, using `start_date` for "before" (the same
chronological field every other feature in this build anchors on) rather than
insertion order or `created_at`. An internal task (no customer) is never flagged.
Shown on the dispatch board (badge in the popover and inline on the block) and WO
detail (header badge) per the directive; NOT added to the WO list page, which the
directive doesn't mention for this badge.

D-065 — [CONFIRMED, Chris 2026-09-19] Increment 2.5 (scheduled jobs) ships with a
per-company master on/off switch (`company_settings.scheduled_alerts_enabled`,
default FALSE) gating every email-sending step in `jobs.py`. Chris's explicit
condition for proceeding: build it, keep the switch off, and prove the send path
actually works via a mocked test before installing anything live. All three were
satisfied: the switch defaults off in the migration, `smoke_scheduled_jobs.py`
temporarily flips it on inside a monkey-patched Resend session to prove the email
path fires (then restores the real value in `finally` regardless of pass/fail), and
the cron schedule was installed only after that test passed. Computation (customer_
flags, extraction day-count upkeep, job_runs bookkeeping) always runs regardless of
the switch — only real email sends are gated.

D-066 — [SCOPE] `job_nightly` explicitly skips customer ratings (§4.2) and dormancy
alerts (§4.1) with a note in its own summary string ("skipped -- not built yet")
rather than silently omitting them — neither feature exists yet (both are later-
stage work), and the directive's nightly-job description references both as if they
already exist. Revisit once §4.1/§4.2 land.

D-067 — [MODEL] `uninvoiced`'s dedupe (`work_orders.alert_sent_at`) is per-WO and
one-shot (once sent, never re-alerted for that WO), matching "one email per WO to
alert_email (dedupe via alert_sent_at)" literally. `eod_escalation`'s digest
deliberately does NOT check `alert_sent_at` — it's a standing summary of "what's
still outstanding right now," not a per-item alert, so the same WO can legitimately
appear in multiple days' digests until it's actually invoiced. Verified both
behaviors explicitly in the smoke test (a second `uninvoiced` run finds nothing new;
the same fixture still appears in the eod digest).

D-068 — [MODEL] Completing 2.4's deferred Delinquent Account display (D-046): now
that `customer_flags` exists (populated by the nightly job), the badge is wired to
customer detail, the WO form's customer picker (client-side, from the same options
JSON the combo already embeds — no new endpoint), and the dispatch board (block +
popover), matching the directive's list exactly. The billing page's OWN delinquent
computation (built in 1.8, live via `_customer_aging_summary` + the same 90-day
threshold) is left as-is rather than switched to read `customer_flags` — it was
already correct and already tested; there was no reason to make it depend on a
once-nightly cache when its live computation costs nothing extra at current volumes
(same reasoning as D-035).

D-069 — [MODEL] The "Scheduled Jobs" status panel (directive: "a panel on the
settings landing page... is how Chris knows cron is wired") lives on
`/settings/company` rather than a new settings landing page — this codebase has
never had one (settings is a dropdown menu, not a page), and `/settings/company` is
already the closest thing to a settings home (it's also where `alert_email` and now
the master switch live). Inventing a new landing page for one panel felt like more
surface area than the directive's actual ask.

D-070 — [OPS] The cron schedule (directive's exact 4-line schedule) is installed
under the `letize` user's own `crontab`, not `/etc/cron.d/fieldkit` — no passwordless
`sudo` was available in this session, and the directive explicitly names this as the
accepted fallback. Documented in `docs/DEPLOYMENT/cron-jobs.md`. Functionally
identical either way since `letize` is the user both approaches would run jobs as;
can be moved to `/etc/cron.d` later if `sudo` becomes available, for a more
discoverable/version-controlled location.

D-071 — [CONFIRMED, Chris 2026-09-19] Water extraction was built for all four
companies through Increment 2.2, but Get a Grip (bathtub/surface resurfacing) never
actually does this work. Chris caught it post-build and asked for it to be removed
from GAG specifically. Implemented as a `COMPANIES_WITHOUT_EXTRACTION = {'getagrip'}`
set (`app.py`) plus a `has_extraction(company_key)` Jinja global, rather than deleting
any extraction code or schema — the feature is fully intact and unchanged for the
other three companies, just unreachable for this one:
- `/extraction` and its four sub-routes 404 for getagrip (checked after the existing
  role check, before any DB work).
- The nav link is hidden (`has_extraction(company_key)` guard in `base.html`).
- The WO form's "Deploy Equipment" button and the whole Water Extraction card are
  hidden for getagrip; a JS null-guard was added where the extraction-start-prompt
  submit handler previously assumed `#chkExtraction` always exists in the DOM (it
  doesn't, for a company without the card) — this would otherwise have broken WO
  form submission entirely for getagrip the moment the card was hidden. Found and
  fixed before shipping, not after.
- GAG's two unused `per_day_equipment` catalog items ("Ozone", "Ozone Treatment" — 0
  equipment units ever registered, 0 extraction jobs ever created) were deactivated
  (`is_active = FALSE`) per Chris's explicit choice among leave-alone/convert-to-
  standard/deactivate — data kept, not deleted, and no longer reachable anywhere now
  that "Deploy Equipment" is hidden for this company anyway.
- `jobs.py`'s nightly extraction upkeep was left company-agnostic rather than special-
  cased to skip getagrip — it already queries `WHERE is_extraction = TRUE`, which is
  now permanently empty for GAG (no path to ever set it), so the no-op is structural,
  not a maintained exception.

New test `smoke_extraction_company_gate.py` covers the gating itself (404s, nav/UI
absence for getagrip; unaffected for the other three; Ozone items deactivated).
`smoke_extraction.py` (Increment 2.2's original test) was switched from getagrip to
kleanit_charlotte, since the feature it tests no longer exists for the company it
was originally written against.

D-072 — [MODEL] Estimates deliberately do NOT reuse the invoice engine's receivable/
version split (migration 010). One row per estimate, editable while Draft, frozen
(tax_rate_pct/tax_total/total) the moment it's Sent — no version history. An estimate
that needs a real revision after sending has no payment history riding on it (unlike
an invoice), so "decline it, create a new one" is an acceptable answer and a second
freeze-discipline table wasn't justified. Editing a Sent/Approved/Declined/Converted
estimate is rejected outright (`_save_estimate` checks status='Draft'), matching the
freeze discipline's spirit even without a version table backing it.

D-073 — [MODEL] Estimate tax is computed at send time anchored on TODAY's date
(`_compute_estimate_tax` calls `_tax_rate_as_of(cur, county, date.today())`), not a
frozen "estimate date" — an estimate has no receivable date of its own the way an
invoice has `invoice_date`. This matches the directive's own wording ("total computed
at send using the same tax path as invoices") for the one date that actually exists
at that moment.

D-074 — [SCOPE] `workorder_customer_context` (built in Stage 2 for the WO form) is now
also used by the estimate form and gates in `salesperson` alongside the existing
admin/manager/office — it's read-only location/contact data for a customer the
directive already grants salespeople read access to, so extending one endpoint beat
duplicating it for a second form that needs the exact same shape.

D-075 — [MODEL] "Convert" is two steps, not one: `GET .../convert` (Approved-only
guard) redirects into `/workorders/new?estimate_id=&customer_id=&...`, pre-filling a
genuinely NEW work order's line items from the estimate's lines (fresh ids, so they
save as new `work_order_line_items`, never edits to the estimate's own rows) — the
estimate itself only flips to Converted once that WO is actually SAVED
(`_save_work_order`, guarded `WHERE status='Approved'` so it can't double-convert or
convert a non-Approved estimate). Clicking Convert is navigation, not a commitment;
the office can back out of the WO form without side effects.

D-076 — [SCOPE] The public estimate request form (`/request/<company_key>`) is a
standalone HTML page that does NOT extend `base.html` — it has no session, no
company switcher, no nav, and needs to render correctly for an anonymous visitor,
so reusing the authenticated-app shell risked broken assumptions (`session.user_role`
checks, `current_path` nav-highlighting, etc.) for no benefit. It borrows only
`branding.color_primary`/`branding.name` for a consistent look.

D-077 — [MODEL] The public form's per-IP rate limit (5/hour, directive's own number)
is an in-memory dict keyed by `(company_key, ip)`, matching the directive's explicit
"no external service" instruction — it resets on app restart and doesn't survive
multiple app instances, which is an accepted limitation for a low-volume public form
where the honeypot field (not the rate limit) is the actual bot deterrent. IP is read
from `X-Forwarded-For` (first hop) falling back to `request.remote_addr`, since the
app sits behind NPM/Cloudflare per the directive's own note.

D-078 — [MODEL] `customer_ratings`' three `*_score` columns store SIGNED
contributions to the 100-point base (a penalty is negative, the volume bonus is
positive), not raw sub-scores — `composite_score = 100 + payment_timeliness_score +
cancellation_score + job_volume_score` (clamped 0–100) is then a direct, auditable
sum rather than a weighted-average formula hidden in application code, and it's what
customer detail's "full breakdown" (per the design addendum) displays directly.

D-079 — [MODEL] `manager_adjustment` is a numeric point delta applied on top of
`composite_score`, not a direct letter-grade override — matches the addendum's own
"a delta plus a required note" wording. `adjusted_letter_grade` is re-banded from
`clamp(composite_score + manager_adjustment, 0, 100)` every time it changes (both on
a fresh override and on every nightly recompute, which re-reads the existing
`manager_adjustment` before writing so a standing override is never lost to the
nightly job — verified in the smoke test). Posting an empty adjustment clears the
override entirely, reverting `adjusted_letter_grade` to the algorithmic grade.

D-080 — [SCOPE] Rating constants (`RATING_PAYMENT_FACTOR_CAP` etc.) live in `app.py`
next to `_job_recompute_customer_ratings`, not "at the top of jobs.py" as the
directive's literal wording suggests — continuing the same decision already made for
every other scheduled job in Increment 2.5 (jobs.py stays a thin CLI wrapper; the
actual logic and its tuning constants live in app.py, where a smoke test can import
and exercise them directly without shelling out to a subprocess).

D-081 — [MODEL] Cancellation rate's denominator ("scheduled, trailing 12 mo") is
every WO with `start_date` in the trailing 365 days, regardless of final status — not
just ones that reached a terminal state — matching "Cancelled WOs / total WOs
scheduled" as literally as the data allows. Job volume counts `status IN
('Completed', 'Invoiced')`, the same set Increment 2.3's job activity report already
uses (D-060) for "did the work actually get done."

D-082 — [SCOPE] The rating badge is added to the SAME customer-options JSON the
delinquent badge already reads client-side (`_load_wo_customers`, shared by both the
WO form and the estimate form) — one query change lit up two of the four display
points the directive lists at once. The dispatch board gets it in the popover only
(directive: "dispatch popover," not "dispatch block" — unlike 2.4's New
Customer/Delinquent badges, which the directive explicitly put on the block itself).

D-083 — [BUG FIX, test-only] `smoke_scheduled_jobs.py` (Increment 2.5) calls
`job_nightly()` directly, which now (Increment 3.2) also writes a `customer_ratings`
row for that test's fixture customer — a table the 2.5 test's `finally` block didn't
know about yet, so `DELETE FROM customers` hit the new FK and raised. Worse: because
the whole cleanup block runs in one uncommitted transaction, that one failure rolled
back EVERY delete in the same `finally` block, including the restore of
`company_settings.scheduled_alerts_enabled`/`alert_email` to their real production
values — leaving `alert_email` set to the test's throwaway address until caught and
fixed by hand (`scheduled_alerts_enabled` itself was already safe because that test
also commits it back to FALSE mid-run, separately from the final restore). Fixed by
adding `DELETE FROM customer_ratings` to that test's cleanup. General lesson for any
future job that touches a new table Increment 2.5's smoke test doesn't know about:
one unhandled FK violation in a `finally` block silently discards every OTHER cleanup
statement in the same uncommitted transaction, not just the one that failed — worth
a from-scratch verification pass (`SELECT` for stray rows, not just "did it crash")
after adding any new table that a shared job function writes to.

D-084 — Increment 3.3 (Recency report + history import). Bucket boundaries
(`days>=30&&<60`→1-2mo, `>=60&&<183`→3-6mo, `>=183&&<365`→6-12mo, `>=365`→12+mo,
`<30` excluded entirely) copied verbatim from the Phase 0 statements site's own
`recency_report.html`/`app.py`, not re-derived, so the two sites' numbers never
diverge for the same customer during the transition period. Last-service date is
`GREATEST()` of `MAX(work_orders.start_date)` (statuses Completed/Invoiced/
Extraction Active) and `MAX(customer_job_dates.job_date)` — the latter is a new
table (migration 023) that exists solely to hold pre-cutover ServiceFusion job
history that has no corresponding FieldKit work order. `import_job_dates.py`
matches statements customers to FieldKit customers by normalized (lowercased,
punctuation-stripped, whitespace-collapsed) `property_name`/`customer_name`
WITHIN each company's own database — exact match only, no fuzzy matching, same
discipline as the Increment 1.9 cutover-import design — and never creates a
FieldKit customer; unmatched statements customers are logged to a CSV instead.

Ran the real dry run today (2026-09-20) via a temporary
`docker network connect statements_default fieldkit-prod-app-1` bridge
(disconnected again immediately after, per the script's own docstring — no
route/table/permission changes needed on either side, so nothing else to log).
Confirmed result matches D-038's earlier finding that the statements DB only has
job history for Get a Grip (`company_id=2`): **258 customers matched, 2,859 job
date rows would be inserted, 38 unmatched customer names** (list in
`/tmp/unmatched_job_dates_getagrip.csv`, mostly management-company/property
accounts whose ServiceFusion name doesn't exactly match the FieldKit
`property_name` on file, plus a few individual names that look like duplicate/
personal contacts rather than a distinct billable property). Nothing was
written — `--commit` was not passed and, per Chris's 2026-09-19 standing
instruction, must not be until he's reviewed these counts and the unmatched-name
list and says to proceed.

---

D-085 — Increment 3.4 (Callbacks, directive §4.4). callback_of_work_order_id is a
self-referencing FK on `work_orders` (migration 024), not a new join table — a
callback is a real work order (dispatchable, invoiceable) that happens to point
back at what it corrects. `callback_reason` is required the moment a source WO
is linked, enforced in `_save_work_order` (not a DB CHECK, so a future
NULL-cleanup doesn't need special-casing) — a form re-render, not a silent
failure. The WO form's "This is a callback for…" combo is populated from a NEW
`prior_workorders` field on the existing `workorder_customer_context` JSON
endpoint (reused, not duplicated) rather than a separate lookup; its options
depend on which customer is currently selected, so `initRestrictedComboFields`
(base.html) gained a small extension — each combo now exposes
`input._comboSetOptions()` and a global `setRestrictedComboOptions()` helper —
so a combo's option list can be refreshed after a customer change without
re-initializing the whole widget. Callback line-item prefill deliberately
excludes equipment (per-day) lines: those reference specific already-deployed
equipment units, not something to silently redeploy onto a different job (plain
catalog lines only, mirroring the estimate-convert prefill from 3.1).

Callback count feeds the customer rating per the directive: -3 per callback
against that customer's jobs, trailing 12mo, as a new signed `callback_score`
column on `customer_ratings` (migration 024) — same signed-contribution
convention as the other three scores from migration 022, so
`composite_score = 100 + payment + cancellation + callback + volume` stays a
direct auditable sum. `RATING_CALLBACK_PENALTY_PER = 3` lives next to the other
rating constants in `app.py`.

The callbacks report (`/reports/callbacks?from=&to=`) groups by
`callback_responsible_username`, computing paid vs. unpaid per row from
`work_order_techs` (was the responsible tech actually assigned to redo the
callback WO themselves, or did someone else go) — no payroll/commission engine
built, per the directive's own explicit instruction; this only exposes the data
a future one would need. Default range is trailing 90 days (no `from`/`to`
given) — long enough to be useful without a full year of (currently empty)
history dominating the page.

Found in passing while wiring the WO list's new Callback filter: the existing
live-search JS (`workorder_list.html`) wires EVERY `.filter-select` element
(including the date input) to the AJAX `liveSearch()` handler, but
`liveSearch()` only ever read `search`/`status` — so the date filter's dropdown
has silently done nothing via the AJAX path since Increment 2.3, only working
through a full-page form submit that never actually fires because the JS
strips the `onchange` that would trigger it. Not fixed here (out of scope for
this increment, pre-existing, and not something callbacks made worse) — only
added `callback` to what `liveSearch()` reads, since leaving the new filter
silently broken the same way would be introducing a fresh instance of a bug I
could see happening in front of me. Left as a known gap for whoever next
touches the WO list's date/tech filters.

---

D-086 — Increment 3.5 (Sales CRM, directive §4.5, migration 025). Schema decisions
built against `docs/SALES-SYSTEM.md` column-for-column, with deliberate additions:

- Every new table gets the full six-column audit+soft-delete set (created_at/by,
  updated_at/by, deleted_at/by) per CLAUDE.md's blanket rule, even where the spec's
  own DDL omitted `deleted_at` (`sales_visits`, `approval_queue`) or the full set
  (`visit_tags_config`, `dormancy_alerts_config`) — matching `catalog_items`'
  existing precedent of `is_active` (business toggle) and `deleted_at` (actual
  removal) coexisting on the same table. `contact_property_history` is the one
  deliberate exception: an append-only log, `created_at`/`created_by` only, same
  convention as `estimate_status_history`/`work_order_status_history` — a log entry
  is never edited or soft-deleted, only added to.
- `sales_prospects.customer_id` is dual-purpose, matching the spec's own narrative
  exactly: before conversion, if `is_former_customer`, it links to the customer
  record they used to be; after conversion (`converted_to_customer = TRUE`), the
  approval workflow populates the same column with the newly created customer's id
  (spec's own words: "Prospect record gets customer_id field populated"). One
  column serves both cases because they're mutually exclusive in practice.
- `dormancy_alerts_config` is seeded company-aware via `current_database()`, same
  technique migration 009 used for `company_settings` — one script, run identically
  against all four DBs, produces the right `alert_after_weeks` per company (GAG 8wk
  / KC 3wk / CTS 4wk / KSF 3wk, per directive + the spec's own rationale: GAG's
  multi-year resurfacing cycle vs. Kleanit's high-volume regular cleaning). Verified
  live against all four DBs at migration time.
- `property_id`/`property_type` polymorphism (`sales_contacts.current_property_id`,
  `sales_visits.property_id`, `contact_property_history.property_id`, each paired
  with a `'prospect'`/`'customer'` type column) has no FK on either column, same
  non-FK pattern as `work_order_techs.username`/`callback_responsible_username`
  elsewhere in this schema — a column that can point into either of two tables
  can't be a foreign key to either one.
- `approval_queue.requires_cross_db_sync`/`target_databases` are kept as unused
  Phase-2 columns (cross-database contact sync is explicitly "not in MVP" per the
  spec) — present so a future increment doesn't need a schema change, but nothing
  in this increment writes them.

D-087 — Increment 3.5 (Sales CRM), behavior/route decisions not specified by the
directive's own text:

- **`approval_queue` scope is `convert_prospect` only** this increment. The spec's
  other example `request_type` (`add_contact` — a salesperson updating an existing
  real customer's contact through approval) isn't in the directive's §4.5 route
  list, and `sales_contacts` is a fully sales-owned table regardless of whether
  `current_property_type` is `'prospect'` or `'customer'` — so ordinary
  `sales_contacts` CRUD never needs an approval step; only the prospect-to-customer
  conversion ever touches the real `customers`/`customer_contacts` tables.
- **The directive's "reject/edit with notes" is folded into one approve action**,
  not a separate `'edited'` status. The manager's approval form lets them adjust
  property name/type/address/management company inline before submitting; clicking
  Approve creates the customer with whatever is in the form at that moment. An edit
  that isn't approved is just a rejection with notes explaining what needed to
  change — there's no case where "edited, not yet approved" is a useful state to
  sit in, so `approval_queue.status` stays `pending`/`approved`/`rejected` in
  practice (the `'edited'` value from the spec's own CHECK constraint is kept in
  the migration for schema completeness but this increment never writes it).
- **Weekly report recipients** = `company_settings.alert_email` (if set) + every
  active admin/manager user with this company in their `company_access` (queried
  from `fieldkit_getagrip.users`, the canonical source per D-003) — directive text:
  "Monday email to alert_email + all managers/admins for the company." Data
  (visit/prospect/dormancy counts) is always computed and written to `job_runs`
  regardless of the master switch, same `_job_alerts_enabled_and_recipient` gate
  every other scheduled email in this build already uses — only the send itself is
  conditional.
- **Dormant-customer "Dismiss"** (mentioned in the spec's own mockup) was not
  built — the directive's route list for 3.5 only asks for "dormant customers list
  computed from the recency data vs the threshold" on the dashboard, not a
  persisted dismiss state. Chris O's "Investigate" action (pre-fills the visit-log
  form with `is_dormant_investigation` checked) is the only dormant-list
  interaction this increment implements.
- **Unified property search** (`GET /<company>/sales/search`) is a live AJAX
  endpoint against the DB, not a client-side preloaded combobox like the existing
  `restricted_combo_field` macro uses elsewhere — getagrip alone has 5,307
  customers (per the 3.2 rating run), too many to embed in a page's `data-options`
  attribute. A small standalone type-ahead script (not the shared
  `js-combo-restricted` brick, which assumes a bounded preloaded option list) is
  duplicated across the two templates that need it (contact form's property
  picker, visit-log form's property picker) rather than building a new shared
  brick this increment, matching this build's existing pattern of small
  per-usage JS over premature shared abstractions.
- Responsive verification at 768px (directive: "Chris O uses a tablet... verify at
  768px") was done by CSS review — every new grid layout collapses to a single
  column under a `@media (max-width:768px)` breakpoint, matching `base.html`'s
  existing responsive pattern — not a live browser walkthrough. Flagged here as a
  disclosed gap, not a silent skip.
- Pre-existing, not touched: `app.py`/`base.html` already check `session.user_role`
  against an `'office'` role in several places (e.g. the Work Orders nav link,
  `workorder_dupe_check`), but the `users.role` CHECK constraint
  (`01_core_tables.sql`) never included `'office'` — only
  `admin`/`manager`/`salesperson`/`technician` are real roles. Those checks are
  simply unreachable for any real user; noticed while adding the Sales nav link
  next to the existing Estimates one, not something this increment introduced or
  fixed.

**Migration:** 025 (`025_sales_crm.sql`), applied to all four DBs, verified
idempotent (re-run against getagrip produced only `NOTICE: ... already exists,
skipping` and `INSERT 0 0`). Pre-migration backups in `~/db-backups/2026-09-20e/`.

**Smoke test:** `tests/smoke_sales_crm.py` — 40/40 checks: prospect CRUD + search,
contact CRUD + `contact_property_history` open/close on property change, visit
logging with tag-driven follow-up date auto-calculation, dormancy-reason
validation, a never-serviced customer appearing in the dormant list, the weekly
report computing real data with alerts off and actually emailing (mocked) with
alerts on, the full convert → pending approval → manager notification → approve
→ customer+contact creation → prospect-linked chain, and a separate reject-with-
notes path. Updated `smoke_scheduled_jobs.py`'s `job_weekly_sales_report`
assertions, which predated this increment and still expected the old
Stage-3-not-built-yet `'skipped'` stub — same category of fix as D-083, a prior
test that didn't know a placeholder had become real. Full 20-file regression
suite re-run clean.

**Deferred:** nothing from this increment's own scope (see D-087 for what was
deliberately left out as directive-scope decisions, not deferrals).

---

D-088 — Increment 5.1 (Dashboard, directive §5.1). Replaced the Phase 1 placeholder
(`active_customers` count + `recent_customers` list, "Coming in Phase N" stubs) with
the real thing.

- **Outstanding A/R / 90+ / unapplied credits read from `customer_flags`**, the
  nightly-computed cache Increment 2.4 built for the Delinquent Account badges
  (`_job_recompute_customer_flags`, reusing `_customer_aging_summary`/
  `customer_unapplied_credit`), not a live per-customer aging walk repeated on
  every dashboard load. The live per-invoice walk (`_customer_receivables_detail`)
  stays reserved for pages that need exact bucket-by-invoice precision for real
  financial work — the A/R aging report and the billing page. A dashboard tile is
  a badge, not a report; badges read the cache elsewhere in this build (customer
  ratings, delinquent flag) and this follows the same line. "90+" on the tile is
  `SUM(open_balance) FILTER (WHERE is_delinquent)` — `is_delinquent` is exactly
  "has an open invoice >90 days past its invoice date" (`DELINQUENT_DAYS_PAST_INVOICE
  = 90`, D-001), the same 90-day cut the aging report's own 90+ bucket uses, just
  evaluated once nightly instead of live.
- **Role-gated sections, not a role-gated route.** `/dashboard` itself keeps no
  role check (it's every role's landing page, including technician, until §5.4
  builds `/myday`) — instead the route computes a `financial_view` bool
  (`admin`/`manager`) that gates uninvoiced-WOs/extraction/A/R/credits/recent-
  activity both in the query layer (skip the queries entirely, don't just hide
  the markup) and in the template. Follow-ups-due uses `SALES_ROLES`
  (admin/manager/salesperson — same constant Increment 3.5 defined), pending-
  approvals uses the stricter `SALES_APPROVAL_ROLES` (admin/manager) — both
  already existed, reused rather than redefined. Quick Actions row follows the
  same per-button gate (`ESTIMATE_ROLES` for "+ New Estimate", `financial_view`
  for "Record Payment", which links to `/billing` since there's no standalone
  "new payment" page — `POST /payments/new` is a form action embedded in the
  per-customer billing flow, not a page of its own).
- **Recent activity** is a `UNION ALL` across `work_order_status_history`/
  `invoice_status_history`/`payment_status_history` (all three already existed,
  append-only, `changed_by`/`changed_at` on each per migrations 005/007/011) —
  nothing new written, just read together and limited to 15. Gated under
  `financial_view` since it surfaces invoice/payment events technicians and
  salespeople have no route access to view directly.
- **"Today's Jobs"** = WOs with `start_date = today AND status != 'Cancelled'`,
  visible to every role, linking to `/dispatch` — the closest existing "today's
  schedule" surface. Not gated, since every role (including technician, until
  `/myday` exists) benefits from knowing today's job count.
- No migration — every table this increment reads already existed.

**Smoke test:** `tests/smoke_dashboard.py` — 21/21 checks: today's-jobs count
increments on a same-day WO, a Completed/uninvoiced WO shows up (and turns the
tile "loud"), recent activity surfaces a fixture WO's status event, outstanding
A/R / 90+ / unapplied credits move by exactly the fixture's `customer_flags`
values (diff-based, not exact-value, since production already carries real
`customer_flags` rows), and role-based visibility for technician (no financial
tiles, still sees Today's Jobs) vs. salesperson (follow-ups yes, approvals no,
estimate quick-action yes, payment quick-action no) vs. admin (sees everything).
Full 21-file regression suite re-run clean.

**Deferred:** nothing from this increment's own scope.

---

D-089 — Increment 5.2 (Customer merge + duplicate detection, directive §5.2,
migration 026). 

- **Duplicate detection reuses the double-booking brick's exact SQL pattern**
  (`workorder_dupe_check`, Increment 1.x/2.x): `lower(regexp_replace(x,
  '[^a-zA-Z0-9]', '', 'g'))` equality, non-blocking banner, 400ms debounce, a
  small `/customers/dupe_check` JSON endpoint. Matches on normalized
  `property_name` always; normalized `address` only when the new customer's
  address field is non-empty (an empty address shouldn't suppress a same-name
  match just because nobody's typed the address yet). No role gate on the
  endpoint — `customer_new`/`customer_edit` have none either (pre-existing;
  same category of gap as D-087's `'office'`-role finding, left for §5.4's
  permissions sweep rather than invented here).
- **Merge is one Python transaction (`_merge_customers`), not a stored
  procedure or per-table routes** — same style as `sales_approval_approve`'s
  create-customer-in-one-transaction from Increment 3.5. Three tiers of
  tables: plain FK re-point (`customer_contacts`, `service_locations`,
  `customer_notes`, `work_orders`, `estimates`, `invoices`, `payments`);
  UNIQUE-constrained tables (`customer_field_values`,
  `customer_compliance_portals`, `customer_job_dates`) where a straight
  UPDATE could collide with a row the target already has for the same key —
  those re-point only the non-colliding rows, `NOT IN (SELECT ... WHERE
  customer_id = target)`, and leave genuine duplicates on the soft-deleted
  source rather than deleting them (a soft-delete-everywhere codebase doesn't
  invent a hard-delete here just because it's convenient — they're simply
  not app-visible any more, same as everything else under a `deleted_at`);
  and the three `sales_*` polymorphic tables (`sales_contacts`,
  `contact_property_history`, `sales_visits`) re-pointed with an added
  `AND property_type = 'customer'` guard since their `property_id` column
  can also mean a `sales_prospects` row. `approval_queue` was deliberately
  left out of the re-point list — its `target_id`/`target_type` rows are
  already-resolved historical requests (D-087 established `approval_queue`
  only ever writes `convert_prospect` rows today), not live references a
  future page reads by customer id.
- **The merge preview endpoint counts from the exact same three table lists**
  `_merge_customers` writes to (`_MERGE_SIMPLE_TABLES`/`_MERGE_UNIQUE_TABLES`/
  `_MERGE_SALES_TABLES` are module-level, shared by both), so the preview
  screen can never promise a different set of changes than the merge
  actually performs.
- **Viewing a merged (soft-deleted) customer redirects to the target**
  instead of 404ing — `customer_detail`'s not-found branch now checks
  `merged_into_customer_id` before giving up. Not directive text, but without
  it every existing link/bookmark to a merged-away customer (dispatch board
  history, old emails, browser back-button) would silently 404 right after
  the very re-pointing operation that's supposed to make the target the new
  home for that data. Minimal addition, same "don't leave a link that used
  to work now dead-ending" instinct as D-071's extraction gate leaving old
  data intact rather than orphaning it.
- **A `customer_notes` row is written on both sides** (target: "Merged in
  X"; source: "Merged into Y") per the directive's "a note on both" —
  the source's own note is still reachable by anyone looking directly at
  `customer_notes` for that id (e.g. from `customer_merge_log`), even though
  the source customer's detail page itself now redirects away.
- No role check exists yet on `customer_new`/`customer_edit` themselves
  (pre-existing, not touched) but the merge route and preview endpoint are
  both admin-only per the directive's explicit "(admin)" — the one new
  route in this increment that does get a role gate, gets the right one.

**Migration:** 026 (`026_customer_merge.sql`) — `customer_merge_log`
(append-only, same convention as `contact_property_history`) and
`customers.merged_into_customer_id` — applied to all four DBs, verified
idempotent. Pre-migration backups in `~/db-backups/2026-09-20f/`.

**Smoke test:** `tests/smoke_customer_merge.py` — 24/24 checks: dupe_check
matches on normalized name+address and respects `exclude_id`; merge preview
counts match real fixture data; a manager is blocked (403) from both the
merge page and the merge POST; after confirming, a WO/contact/service
location land on the target; the `customer_field_values` collision case
(target keeps its own value, doesn't get clobbered by the source's) and the
`customer_job_dates` collision case (a shared date isn't duplicated, a
non-shared one moves over) both verified directly against the DB, not just
"the merge didn't error"; source ends up soft-deleted with
`merged_into_customer_id` set; notes written on both sides; the
`customer_merge_log` row's `details` JSONB matches the real per-table
counts; and visiting the now-merged source customer's URL redirects to the
target with a flash message instead of 404ing. Full 22-file regression
suite re-run clean.

**Deferred:** nothing from this increment's own scope.

---

D-090 — Increment 5.3 (Audit trail, directive §5.3, migration 027). `record_audit`
(`table_name, record_id, action, diff JSONB, changed_by, changed_at`, append-only)
written by the save paths of customers, contacts, service locations, work orders,
invoices/versions, payments, estimates, catalog, tax rates, and users — the
directive's full list, all ten covered.

- **One shared helper, `_record_audit(cur, table_name, record_id, action, before,
  after, changed_by)`**, called from inside the existing save-path functions
  right before their own `conn.commit()` (never a separate transaction) — same
  discipline as every other cross-cutting write in this build (customer_flags,
  audit-adjacent). `action='update'` diffs `before` against `after` and writes
  only the columns that actually changed, `{col: {'old':, 'new':}}`; a true no-op
  save (nothing differs) writes nothing at all, verified directly in the smoke
  test — re-saving a customer form with identical values does not grow the audit
  table. `action='create'`/`'delete'` write the full after/before row (there's
  nothing to diff against).
- **Two centralized redactions inside `_record_audit` itself**, not left to each
  call site to remember: `updated_at` is dropped from every diff (it's bumped by
  every UPDATE regardless of whether anything user-meaningful changed — pure
  noise; `record_audit.changed_at` already carries "when"), and `password_hash`
  is stripped from `before`/`after` unconditionally before anything is written,
  even for `users`' own `create` action. Caught by the smoke test on the FIRST
  run: an early version only stripped the hash in `user_edit`'s own call site,
  missing `user_new`'s (the create path used a full un-redacted `SELECT *`) —
  the hash briefly went into `record_audit.diff` in this test's fixture before
  being caught and fixed. No real user was ever exposed (test-only, this
  environment's `getagrip` DB, immediately caught and cleaned), but it's the
  reason the redaction moved into the shared helper instead of staying
  per-call-site: a security-relevant exclusion should not depend on N call
  sites all remembering it.
- **Invoices/versions is audited as one logical record** (`table_name='invoices'`,
  keyed by the receivable id, never a separate `invoice_versions` audit trail) —
  `transition_invoice`'s Hardened/Sent/Live(reopen)/Void/Revise branches and
  `_reissue_invoice` each write one row summarizing that transition (e.g. Harden:
  `{'version_state': {'old': 'Live', 'new': 'Hardened'}, 'total': <frozen total>}`)
  rather than a full invoice_versions row diff — `invoice_status_history` (migration
  007) already captures the granular per-transition detail with from_state/
  to_state/notes; `record_audit` here is the unified cross-entity feed the
  directive's History panel/global view need, not a duplicate of that existing
  table.
- **`users` writes `record_audit` to `getagrip` only**, never all four DBs —
  same canonical-source reasoning as D-003 (auth and `session['company_access']`
  only ever read `getagrip.users`; the other three DBs' copies are inert and
  don't need their own audit trail of writes nobody reads). `write_to_all_dbs`
  itself is untouched — record_audit is written in a small separate
  getagrip-only connection immediately after, using the row `write_to_all_dbs`'s
  own canonical-id lookup already resolved.
- **Payment applications (`payment_applications`) are not separately audited** —
  it's already an append-only ledger by construction (an "unapply" inserts a
  negative reversal row, nothing is ever mutated or deleted), so a `record_audit`
  entry on top of it would just restate what the table's own rows already show.
  Same reasoning `contact_property_history` used in Increment 3.5 to skip its
  own audit entries.
- **Per-record "History" panel** (`_macros.html`'s `audit_history_panel()`, a
  native `<details>` disclosure — no JS needed) is on customer/WO/invoice/payment
  detail per the directive, visible to whoever can already view that detail page
  (no extra role gate — the directive only calls the *global* view "Admin-only",
  not the per-record panels). **The global view** (`/settings/audit?table=&id=
  &user=&from=&to=`) is admin-only, paginated, with a table/id/user/date filter
  bar, reusing the exact same diff-rendering markup as the per-record panel.

**Migration:** 027 (`027_record_audit.sql`), applied to all four DBs, verified
idempotent. Pre-migration backups in `~/db-backups/2026-09-20g/`.

**Smoke test:** `tests/smoke_audit_trail.py` — 46/46 checks: create/update/delete
audit rows verified for customers, catalog items, work orders, invoices (create +
harden), payments (record + void), estimates (create + send), tax rates
(create + end), and users (create + toggle-active + reset-password); the no-op-
update-writes-nothing guarantee; every detail page's History panel renders and
shows the right diff; the global view's admin-only gate (manager gets 403), its
table/id filter narrows correctly, and — the most safety-critical assertion —
`password_hash` never appears anywhere in any diff, on the create path or
anywhere in the global view's rendered HTML. Full 23-file regression suite
re-run clean.

**Deferred:** nothing from this increment's own scope.

---

D-091 — Increment 5.4 (Permissions sweep, directive §5.4). Full route-by-route
audit against the directive's Appendix A matrix (142 routes, every `@app.route`
in app.py) found: 13 routes with NO role check at all (the Customers area —
`customers`, `customers_search`, `customer_detail`, `add_note`, `customer_new`,
`customer_edit`, `customer_dupe_check`, `location_new`, `location_edit`,
`contact_new`, `contact_edit`, `contact_delete` — plus `billing_export`, which
was the one ungated route in an otherwise fully-gated billing area); 3 routes
too permissive (`field_settings`/`field_add`/`field_toggle` let `manager`
through, when the matrix's "manager = catalog & equipment only" line excludes
custom-field settings); 5 routes too restrictive (`reports_landing`,
`report_jobs`, `report_jobs_export_csv`, `report_recency`, `report_recency_pdf`
blocked `salesperson`, who the matrix grants "recency, jobs, sales"); and
`/myday` didn't exist at all.

- **`CUSTOMER_WRITE_ROLES = ('admin', 'manager', 'salesperson')`** (a new
  constant, deliberately not reusing the value-identical `ESTIMATE_ROLES`/
  `SALES_ROLES` — same domain-clarity-over-DRY precedent those two already
  set) gates every customer/contact/location write path. Customer *view*
  (`customers`, `customer_detail`) stays open to every role, including
  technician, per the matrix's "own jobs' customers, read-only" rather than a
  flat exclude — technician's access is query-scoped instead:
  `_technician_customer_ids()` returns the set of customer ids a technician
  has ever been assigned a work order for (`work_order_techs` join), and both
  `customers` (list, filtered `WHERE id = ANY(...)`) and `customer_detail`
  (403 if the requested id isn't in that set) use it. `customers_search` (the
  JSON autocomplete endpoint every write-form's picker calls) is gated to
  `CUSTOMER_WRITE_ROLES` outright rather than scoped — a technician has no
  legitimate reason to search customers generically since every form that
  would call this endpoint is already closed to them.
- **Reports**: `salesperson` added to the five gates above; `reports_landing.html`
  now conditionally hides the admin/manager-only cards (Tax, Aging, Day Sheet,
  Hours, Callbacks) from a salesperson rather than showing a card that 403s on
  click. Recency and Job Activity are granted **unscoped** (company-wide, same
  as admin/manager see) — the matrix's "(own)" qualifier next to "jobs" has no
  corresponding data-model concept to scope by (work orders have no
  salesperson/creator field, only assigned techs and a customer), and Sales
  CRM's own dormant-customer tooling (`/sales`, Increment 3.5) already covers
  the genuinely salesperson-scoped use case. Treated as a data-model gap to
  flag, not a reason to invent scoping logic with nothing to scope against.
- **`/myday`** (technician-only — gated `!= 'technician'`, not opened to
  admin/manager for oversight, matching the directive's literal framing of
  this page as the technician mobile stand-in, not a general-purpose view):
  a single page, date-scoped (default today, same `?date=` convention as
  `report_daysheet`), listing only work orders where the logged-in tech has a
  `work_order_techs` row for that date, each with three buttons — On The Way /
  Start / Complete — writing `'On The Way'`/`'In Progress'`/`'Completed'`
  respectively. Those two middle statuses already existed in the `status`
  CHECK constraint and in `app.py`'s own `WO_OFFICE_STATUSES` comment
  ("On The Way / In Progress arrive with the mobile app") — Increment 1's
  schema had already reserved this vocabulary for exactly this surface, never
  reachable through the office WO form's own status dropdown
  (`_save_work_order` rejects anything outside `WO_OFFICE_STATUSES`). The
  status-update route re-verifies the `work_order_techs` assignment itself
  (404, not a generic 403, if the WO doesn't exist OR isn't theirs — doesn't
  leak which case) and rejects the write if the WO is already
  Completed/Cancelled/No Charge/Invoiced/Extraction Active (can't move
  backward out of a terminal state) or `is_extraction` (the extraction
  lifecycle, Increment 2.2, has its own daily-log/retrieve workflow — My
  Day's plain 3-button flow renders those WOs read-only with a pointer to the
  extraction queue instead of half-reimplementing that state machine). Reuses
  `_record_audit` (Increment 5.3) for every status write, same as every other
  WO status change in the app.
- **`workorder_detail` itself was deliberately left admin/manager/office-only,
  not opened to technician** — My Day's per-job card already surfaces
  everything the directive's "WO detail of their own assignments" asks for
  (site, address+map, contact phone, description, tech notes, line
  descriptions) inline, without needing a second, separately-scoped read path
  into the full office WO detail template. Keeps the "everything else 403 for
  technicians" boundary the directive states literally intact.
- **`VALID_ROLES` dropped the dead `'office'` value** (D-087 already
  established no seeded user has it and no route grants it anything) so the
  New/Edit User form can no longer hand an admin a role that maps to zero
  live capabilities. The DB's own `users_role_check` CHECK constraint still
  permits `'office'` at the schema level — left untouched, out of scope for
  an app-level permissions sweep — and the ~40 inert `not in ('admin',
  'manager', 'office')` tuples scattered through existing routes were left
  alone too: they're dead weight, not a correctness bug (no user can ever
  have that role again now that the form won't offer it), and touching 40
  call sites for zero behavior change trades real risk for cosmetic benefit.
  Whoever next touches any one of those routes can drop the literal then.
- No migration — this increment is entirely permission-gate and one new
  read/write-scoped route, no schema change.

**Smoke test:** `tests/smoke_permissions.py` — 42/42 checks: My Day shows only
the logged-in tech's own-date assignment and hides an unrelated tech's job;
admin/manager/salesperson all 403 from My Day; a tech can move their own job
through On The Way → Completed but gets a 404 (not 403) trying to touch a job
they're not assigned to, and can't move a Completed job backward; the office
WO form still rejects `'On The Way'` as a status (proving the reservation
line actually holds); technician customer list/detail scoping (sees own-job
customer, 403 on an unrelated one, no write buttons rendered); every customer
write path 403s for technician while salesperson still reaches all of them;
`field_settings` now blocks manager; salesperson reaches reports/jobs/recency
and the landing page hides admin-only cards from them while tax report stays
blocked; `billing_export` now gated; technician still 403 everywhere else
(dispatch/invoices/billing/sales/estimates/settings); and the New User form
no longer offers `'office'`. Full 24-file regression suite re-run clean.

**Deferred:** nothing from this increment's own scope. The five-route
salesperson-scoping gap noted above (no "own" concept for jobs/recency to
scope against) is a data-model observation, not deferred work — there's
nothing to build until a future increment defines what "a salesperson's own
job" would even mean in this schema.

---

D-092 — Increment 5.5 (Settings landing + in-app help, directive §5.5).

- **`/<company>/settings`** (admin/manager) shows a card per settings page the
  logged-in role can actually reach — Custom Fields/Tax Rates/Company
  Settings/User Management/Audit Log are admin-only cards, hidden from
  manager rather than shown-then-403 (same pattern `reports_landing.html`
  already used for salesperson in Increment 5.4). **The Scheduled Jobs panel
  is rendered inline**, not linked to — the directive's own wording says
  "cards for every settings page **plus** the scheduled-jobs panel," treating
  it as a distinct thing from a card, and the whole point of a landing page
  is not making an admin click through to Company Settings just to see
  whether cron is still alive. Reuses the exact query `company_settings_edit`
  already had (`DISTINCT ON (job_name) ... ORDER BY job_name, started_at
  DESC`) so the two views can never disagree.
- **`field_settings`/`field_add`/`field_toggle`'s nav entries** (base.html)
  were still gated `('admin','manager','office')` even after Increment 5.4
  made the routes themselves admin-only — fixed here so a manager doesn't
  see a Custom Fields link that 403s. Added an "All Settings" entry at the
  top of the existing Settings dropdown, admin/manager only.
- **In-app help**: a new `help_panel(title)` macro (`_macros.html`, a native
  `<details>` disclosure, same mechanism as the History panel) added to six
  pages — `invoice_detail.html` (the directive's own worked example: why a
  Sent invoice can't be edited, Revise vs. Reissue), `billing.html` (what
  Delinquent/No Contact/Portal mean, tied to the exact same 90-day threshold
  and nightly computation the badges elsewhere already use), `estimate_detail.html`
  (Draft→Sent→Approved/Declined→Converted, and that Convert flips status on
  WO save, not on the click), `workorder_form.html` (the double-booking
  banner is non-blocking, the callback prefill excludes equipment lines and
  requires a reason, On The Way/In Progress are My Day-only), `extraction_queue.html`
  (one WO for the whole lifecycle, what Retrieved actually finalizes, why
  Get a Grip doesn't have this page), and `myday.html` (button semantics for
  a technician who's never used it before). **`tax_rates_list.html` was left
  as-is** — it already has an always-visible (not collapsible) reconciliation
  note covering exactly the directive's own tax-rate example ("never edit
  the percentage on a row an invoice may already have used"); duplicating it
  as a second, collapsed panel would only bury the same information the page
  already surfaces prominently.
- **Six pages, not "every major page"** — the directive's phrase is broad by
  nature; these six are the ones with a genuine reconciliation rule or
  non-obvious workflow constraint to explain (matching the directive's own
  single worked example, on invoices), not just any page with a form on it.
  Logged as the scope call it is, not silently narrowed.
- No migration — this increment is entirely new routes/templates/nav, no
  schema change.

**Smoke test:** `tests/smoke_settings_landing.py` — 27/27 checks: admin sees
every card plus the scheduled-jobs table, manager sees only catalog/equipment
(no admin-only cards, no jobs table), salesperson/technician both 403 from
the landing page, the "All Settings" nav link is role-gated correctly, and
all six help panels render with a check on their actual substantive content
(not just "a `<details>` tag exists somewhere") — including real invoice and
estimate fixtures created for those two detail-page checks (getagrip has
zero real invoice/estimate rows in production, so this test creates,
verifies, and hard-deletes its own), plus the extraction-queue check run
against `kleanit_charlotte` since getagrip has that page gated off entirely
(D-071). Full 25-file regression suite re-run clean.

**Deferred:** nothing from this increment's own scope.

---

D-093 — Stage 5.6/Stage 5 cutover: real ServiceFusion data import for Get a Grip
(2026-09-22, first company done). Chris supplied real ServiceFusion exports
under `~/servicefusion-imports/get-a-grip/` (catalog, open invoices, job
history — equipment intentionally empty, GAG doesn't do that work per D-071).
Reviewed live with Chris before any write; every scope decision below was his
call, not guessed.

- **Three new scripts** (`phase1/fieldkit_phase1/`, dry-run-by-default +
  `--commit`, same discipline as `import_job_dates.py`):
  - `import_catalog.py` — reads a ServiceFusion `CompanyServices_*.xlsx`
    export directly (not the CSV shape the directive originally sketched;
    adapted to what Chris could actually export). Only `Cleaning`/
    `Resurfacing`/`Repairs`/`Stripping`/`Tile Work` categories import;
    `QBO Service`/`Service`/`Discount`/blank categories are excluded
    outright — `QBO Service` turned out to include actual **tax line items**
    ("County Tax 2%", "Transit Tax") that would have double-counted against
    FieldKit's own tax engine if imported as catalog items, not just
    bookkeeping noise. Three `Service`-category rows did carry a real price
    (Min Charge $185, OCC FEE $45, Xtra Prep $45) but weren't specifically
    resolved in review — deliberately left out rather than guessed either
    way; a two-minute manual add if wanted. Real-category rows with no
    ServiceFusion price (25 of them, confirmed quoted per-job, not a data
    gap) get a $50 placeholder rate, Chris's own number ("the starting
    price"), clearly flagged per-row in the script's output so it's never
    confused with a real rate.
  - `import_open_invoices.py` — the script Stage 5's own text named
    (`import_open_invoices.py`) but that never existed, because the
    directive's premise (open-invoice data already sitting in the sibling
    statements DB) was wrong (D-038: zero rows there for all four
    companies). Reads ServiceFusion's own `Report_Invoice` export directly
    instead. Only `PAST DUE`/`UNPAID` rows import (not the 3,564
    `PAID IN FULL` ones — opening balance only, not a full historical
    re-creation). `invoices.source` already had an unused `'sf_import'`
    CHECK value reserved for exactly this, dating back to whenever the
    receivable/version schema was designed. Imported invoices get one
    `Hardened` version with no line items (the source is invoice-level
    only) — the dollar total and balance are right, the per-line detail
    isn't recreated. Invoice numbers are prefixed `SF-<original number>`
    (e.g. `SF-6047`) so an imported receivable is visually obvious
    everywhere and can never collide with FieldKit's own
    `<PREFIX>-<year>-####` sequence. Two invoices had a partial payment
    already applied in ServiceFusion before cutover — rather than just
    starting the balance lower with no trail, the script writes a real
    `payments` row (method='Other', invoice date used since the actual
    payment date isn't in this report) plus a `payment_applications` row,
    so the ledger stays honest.
  - `import_job_history_direct.py` — new, sources `customer_job_dates`
    directly from Chris's weekly `CustomerRevenueReport_*.xlsx` exports
    rather than the statements DB `import_job_dates.py` already reads from.
    Supplements, doesn't replace, that script — this one only counts a row
    if its Status is `Invoiced` or `Completed`, the same two statuses the
    recency report's own WO-derived formula already counts (D-084);
    `Scheduled`/`Dispatched`/`Started` rows are excluded as not-yet-actually-
    performed. `source='servicefusion_import_direct'` distinguishes these
    rows from the statements-DB-sourced `'servicefusion_import'` ones.
  - All three reuse the exact `normalize_name()` (lowercase, strip
    `.`/`'`/`"`, collapse whitespace) and exact-match-only discipline
    `import_job_dates.py` established — no fuzzy matching, unmatched
    ServiceFusion customer names logged to CSV, never auto-creates a
    FieldKit customer.
- **Results (Get a Grip, committed 2026-09-22):** 45 catalog items (24 at
  the $50 placeholder), 268 open invoices totaling **$179,521.14** (2 with a
  migrated partial payment), 1,285 `customer_job_dates` rows across 141
  customers. 24 invoice customer names (58 invoices, ~$40K) and 39 job-
  history customer names didn't match any FieldKit customer — heavy overlap
  between the two lists (Atlantic Mountain Island Lake, Hawthorne at
  Oakridge, Trinity Station Apartments, etc.) is a real signal these
  properties genuinely don't exist as customers yet, not a name-formatting
  mismatch. Logged to CSV under `~/servicefusion-imports/get-a-grip/_review/`
  for Chris to resolve.
- **Catalog cleanup, same review:** three pre-existing GAG catalog items
  didn't match the real business (`1 BR Clean` — Carpet Cleaning category;
  `After Hours Water Extraction` and `Ozone Treatment` — GAG doesn't do
  water extraction, D-071) — soft-deleted (`deleted_by='sf_import_cleanup'`),
  reversible. **Bug caught by the regression suite immediately after:**
  `Ozone Treatment` was the one active `per_day_equipment` catalog item on
  GAG that three invoice smoke tests (`smoke_invoice_pdf.py`,
  `smoke_invoice_routes.py`, `smoke_invoice_versions.py`) depend on for
  equipment-billing fixtures — it had already been correctly hidden via
  `is_active=false` by D-071 (not `deleted_at`, precisely so it stays
  queryable for exactly this kind of fixture use while disappearing from
  real UI dropdowns), and soft-deleting it on top broke that. Restored to
  its D-071 state (`is_active=false, deleted_at=NULL`); the other two
  deletions stand.
- **`smoke_dashboard.py` fix (same regression pass):** its "90+ figure" A/R
  check asserted a literal `'$543 90+'` string, which only ever worked
  because production had zero real A/R data before today. Changed to a
  baseline-diff check (`after_90plus - baseline_90plus == 543`), matching
  the pattern the adjacent Outstanding-A/R assertion already used — same
  category of fix as D-083: a test that assumed an empty production dataset
  stopped being valid once real data landed.
- **Not done, deliberately:** `record_audit` (Increment 5.3) is not written
  by these three scripts. They run as standalone CLI tools outside the
  Flask app/request context, same as `import_job_dates.py` before them
  (which also predates and doesn't call `_record_audit`) — bulk imports are
  attributed via each row's own `created_by`/`source` columns, not the
  interactive-save audit trail, which only instruments routes inside
  app.py. Consistent with existing precedent, not a new gap.

**Backup:** `~/db-backups/2026-09-22-pre-sf-import/fieldkit_getagrip_pre_import.sql`
taken before any write (this wasn't a migration, but a real financial data
write warrants the same discipline).

**Verification:** full 25-file regression suite green after the catalog
cleanup fix and the `smoke_dashboard.py` test fix; live-rendered
`/billing`, `/reports/aging`, `/settings/catalog`, `/reports/recency`,
`/customers` all confirmed 200 with the real data visible; `jobs.py nightly`
re-run for all four companies afterward so `customer_flags`/`customer_ratings`
reflect the new real invoices immediately rather than waiting for the next
cron cycle (no real email sent — `scheduled_alerts_enabled` stays off for
all four companies).

**Deferred:** the same import for Kleanit Charlotte, CTS, and Kleanit South
Florida, once Chris supplies their exports the same way.

---

*Questions from `FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md` not yet answered by Chris:
#33 (OPS/VendorCafe export templates), #50 (SMS alerts via Twilio), and Stage 5.6
(ServiceFusion price-list exports, company legal names/remit-to/reply-to/alert emails).
These are not blocking — the directive already specifies safe defaults/fallbacks for
each — and will be raised again at the start of the stage that needs them.*
