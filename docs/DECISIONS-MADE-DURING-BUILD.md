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

---

*Questions from `FIELDKIT_DECISIONS_FOR_REVIEW_2026-09.md` not yet answered by Chris:
#33 (OPS/VendorCafe export templates), #50 (SMS alerts via Twilio), and Stage 5.6
(ServiceFusion price-list exports, company legal names/remit-to/reply-to/alert emails).
These are not blocking — the directive already specifies safe defaults/fallbacks for
each — and will be raised again at the start of the stage that needs them.*
