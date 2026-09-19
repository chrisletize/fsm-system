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

---

*Questions from `FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md` not yet answered by Chris:
#33 (OPS/VendorCafe export templates), #50 (SMS alerts via Twilio), and Stage 5.6
(ServiceFusion price-list exports, company legal names/remit-to/reply-to/alert emails).
These are not blocking — the directive already specifies safe defaults/fallbacks for
each — and will be raised again at the start of the stage that needs them.*
