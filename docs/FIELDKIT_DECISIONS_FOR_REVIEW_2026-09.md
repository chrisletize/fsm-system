# FieldKit — Decisions Made Without Your Input (for review)
*Companion to `FIELDKIT_BUILD_DIRECTIVE_2026-09.md` · September 18, 2026*

Every item below is a call I made while writing the directive where the design docs were
silent, contradictory, or where the built code had already drifted from the docs. Each one
is reversible. Mark any you disagree with and the VM instance can change course; the
directive tells it to log its own further decisions in `docs/DECISIONS-MADE-DURING-BUILD.md`.

Legend: **[SCOPE]** what's in/out · **[MODEL]** data/architecture · **[UX]** screen behavior ·
**[DEFAULT]** a default value · **[CONFLICT]** two docs disagreed · **[ASK]** worth a quick answer from you

---

## Scope & sequencing
1. **[SCOPE]** "Complete the website" = everything except the Phase 6 mobile app and its dependents (GPS/CLVisit, after-hours capture, photo upload). Web-side stand-ins were added where mobile was load-bearing (office-side status buttons, `equipment_incomplete` checkbox, backdated extraction start).
2. **[SCOPE]** Also excluded: business-card OCR, QuickBooks, card processing, LKit configurability, all AI/LLM features, payroll/commission engine (only the data it needs is exposed via the callbacks report).
3. **[SCOPE]** Build order: Invoicing/billing → Dispatch/extraction/reports → Estimates/rating/CRM/callbacks → Dashboard/data-quality/permissions/help → Cutover. This matches the August 22 plan; estimates moved after dispatch because invoicing and dispatch are what Michele needs to retire Phase 0.
4. **[SCOPE]** The statements site (Phase 0) is untouched except for read-only imports. You decide when to retire it.
5. **[SCOPE]** The final aesthetic/design pass stays a separate session with you; the VM instance keeps the current visual language.

## Invoice model
6. **[MODEL]** Implemented the July 22 receivable/version decision exactly: `invoices` = receivable (`open`/`void`), `invoice_versions` = immutable presentations (`Live`/`Hardened`/`Sent`/`Superseded`), line items hang off versions.
7. **[MODEL]** **`Paid` is no longer a stored state.** It is derived from balance = 0 with at least one payment application. `Partially Paid` likewise. This answers open question Q1 from the decision record: one `transition_invoice()` function serving both levels, keyed by receivable id, acting on `current_version_id`.
8. **[MODEL]** `revision_number = 0` for originals (as you already decided); revisions no longer share a `UNIQUE(number, rev)` — the receivable owns the number.
9. **[MODEL]** Void requires all payment applications to be reversed first (Q6 from the decision record: "block until dispositioned"). The UI walks Michele through un-applying before void.
10. **[MODEL]** Reissue clones lines (your July 22 choice) into a brand-new receivable with a new number; both rows link to each other.
11. **[MODEL]** Revision requires the current version to be `Sent`; the new version starts Live with cloned lines and a required reason; tax/subtotal deltas are written on the history row when the new version hardens (Q4 — accountant-friendly dated delta). **[ASK]** confirm with your accountant that cash-basis reporting only on money movement is acceptable for revisions.
12. **[MODEL]** Migration 008's temporary credit columns are dropped. **A credit is an unapplied payment amount** — no separate credits table. Dispositions: apply elsewhere, refund. Write-offs of amounts owed *to you* go through a new `invoice_adjustments` table. Credits are shown loudly everywhere the customer appears.
13. **[MODEL]** Payments are recorded against a customer and then applied; recording from an invoice page pre-applies to that invoice. Over-application is rejected.
14. **[MODEL]** Balance is never stored; one helper + one SQL view compute it.
15. **[DEFAULT]** AR aging and delinquency age from the **original invoice date**, Net 30 assumed (Q3; matches Patrick's aging report spec). Revision does not reset the clock.
16. **[DEFAULT]** Delinquent = any open receivable more than 60 days past invoice date (design v2 said "60 days overdue"; with Net 30 that would be 90 days past invoice — I chose 60 days past invoice date as the simpler, stricter reading). **[ASK]** 60 or 90 days from invoice date?
17. **[SCOPE]** One invoice per work order; multi-WO batch invoicing deferred (migration 007's own note).
18. **[UX]** "No Charge" work orders cannot be invoiced; the create button is hidden.
19. **[UX]** Creating an invoice sets the WO status to `Invoiced`.
20. **[DEFAULT]** Invoice due date = invoice date + parsed `payment_terms` ("Net 30" → 30, "Due on Receipt" → 0, unknown → 30).
21. **[DEFAULT]** Water-extraction invoices get an explanatory "drying & monitoring" paragraph from a new `company_settings.extraction_explainer_text` with a seeded default. You'll want to edit the wording.

## Tax
22. **[MODEL]** `tax_rates` becomes effective-dated by versioning the whole row (`effective_from`/`effective_to`), anchored on `invoice_date` (your 5a plan). A 7.25% Mecklenburg row ending 2026-06-30 is inserted so historical dates resolve correctly.
23. **[MODEL]** Rate components (state/county/transit) are frozen onto the invoice version at harden so the cash-basis report never re-looks-up rates. Mecklenburg's 1% additional county tax is reported as its own component, matching the August statements-site rework.
24. **[DEFAULT]** Cash-basis allocation: each payment application allocates proportionally across taxable base and tax of the invoice's current version. Refunds appear as negatives in the period refunded.
25. **[DEFAULT]** Imported SF-era receivables carry `tax_total = 0` and are excluded from the FieldKit tax report, because their tax was already reported through Phase 0. **[ASK]** confirm — this is the point most likely to double-count or under-count if the cutover month straddles both systems.
26. **[ASK]** Kleanit SF / Florida: nonresidential cleaning is taxable in FL. Default: FL table left empty and `kleanit_sf` marked tax-exempt-by-default until you say otherwise.

## Email & documents
27. **[CONFLICT]** Design v2 and Phase 0 used Outlook/PowerShell drafts. The directive sends directly from FieldKit via the existing Resend integration, with PDF download as the manual path. Reply-to and from-name come from the new `company_settings`. Office gets a BCC copy.
28. **[DEFAULT]** Email templates are stored per company in `company_settings` with `{customer}`, `{number}`, `{total}`, `{balance}` placeholders.
29. **[MODEL]** Every send is logged in an `email_log` table.
30. **[DEFAULT]** PDFs are generated on demand and not stored; hardened versions render from the snapshot only, so reprints are byte-identical.
31. **[UX]** Statement PDF mimics the Phase 0 layout closely so customers see continuity.
32. **[MODEL]** Customers billed exclusively through a portal get a `portal_is_primary_billing` flag on their enrollment and are excluded from email batches by default.

## Compliance portals
33. **[DEFAULT]** All three portal exporters ship with a generic `.xlsx` layout until you supply the OPS import template and VendorCafe field list. The page says so. **[ASK]** can you get those templates?
34. **[UX]** Compliance page marks invoices `submitted` on export; accept/reject is manual with notes. No Paymode payment-matching yet.

## Cutover import
35. **[MODEL]** Open SF-era invoices are imported from the statements DB as `source='sf_import'` receivables with their original SF numbers, one "Imported Balance" line, `Sent` state, balance = `invoice_total_due`. Matching is by normalized customer name; unmatched rows go to a CSV for you/Michele. Dry-run first; the real run waits for your go-ahead.
36. **[MODEL]** Recency history (`customer_job_dates`, 1,851 rows) is imported the same way for the live recency report.
37. **[DEFAULT]** `_next_invoice_number` will ignore imported numbers when computing the next FieldKit sequence.

## Scheduling & extraction
38. **[CONFLICT]** Dispatch board is **vanilla JS**, not React/DnD Kit — the stack has no build step and the July 2 rule was "no bundler." Day view with drag/move/resize; week view read-only.
39. **[DEFAULT]** Board columns run from business-hours start − 1 h to end + 2 h, 30-minute slots; block minimum 30 min; tech colors auto-assigned from a 12-color palette.
40. **[DEFAULT]** Tech-capacity overlap on the board is a non-blocking red outline, no auto-bump (the January auto-bump sketch is dropped).
41. **[CONFLICT — significant]** **Extraction auto-roll no longer clones work orders nightly.** One work order lives from set-up through retrieval; billable days come from the per-line `deployed_at`/`retrieved_at` you already built; the board shows the active WO on the follow-up tech's row every day; a daily status log table records each day's status. `parent_work_order_id` is repurposed for the optional follow-up cleaning WO. Reason: cloning would create N duplicate rows per job and fight the accrual model built on July 2. The "Roll all to tomorrow" button survives as "Log today's status for all" so Michele's habit still has a target.
42. **[DEFAULT]** `is_extraction` auto-sets when a per-day equipment line is added; editable.
43. **[DEFAULT]** Partial retrieval (some units out) keeps the WO active; full retrieval completes it and fires the invoice prompt.
44. **[UX]** Day-5+ escalation goes to `company_settings.alert_email` from the nightly job.
45. **[DEFAULT]** Duration warning tolerance ±15 min (addendum's suggested default).
46. **[MODEL]** Hours report is honestly labelled "Scheduled hours" (no clock-in exists; commission-paid techs, no timeclock by design).

## Replacing tags
47. **[CONFLICT]** Tags were killed on July 2 but design v2 still leans on them. Each starter tag got a home: Callback → callback object; New Customer/Residential/Delinquent → derived badges; Misc Task → `is_internal_task` (customer becomes optional on internal tasks); Water Extraction → `is_extraction`; Requires Follow-Up → existing checkbox; Estimate/No-Charge → status + estimates.
48. **[MODEL]** Delinquent flag and rating are computed nightly into `customer_flags` / `customer_ratings`, not on page load.

## Scheduled jobs
49. **[MODEL]** Host cron on ubuntu-business runs `python jobs.py <task>` inside the app container (no in-process scheduler — multiple gunicorn workers would double-fire). A `job_runs` table + settings panel show last-run times. Needs `sudo` for `/etc/cron.d` or falls back to the `letize` user crontab.
50. **[DEFAULT]** Uninvoiced-job alerts: 15-minute sweep, 1-hour grace, emails `alert_email`; 5 PM weekday digest. No SMS (design v2 said "email + text") — no SMS provider exists. **[ASK]** do you want SMS via a provider (Twilio) added later?
51. **[DEFAULT]** `alert_email` defaults to your login email until you set per-company addresses.

## Estimates, requests, rating, callbacks, CRM
52. **[DEFAULT]** Estimate numbers: `GAG-EST-2026-0001` pattern.
53. **[DEFAULT]** Public estimate request form lives at `/request/<company_key>`, protected by a honeypot field and a 5-per-hour-per-IP in-memory limit; new requests email `alert_email`. You decide whether to link it from the company websites.
54. **[DEFAULT]** Rating formula constants (payment penalty, cancellation ×40, volume bonus capped at 10, callback −3 each) are guesses placed at the top of `jobs.py` for tuning with real data.
55. **[MODEL]** Callbacks are a work order with `callback_of_work_order_id` + `callback_responsible_username`, not a separate table; the callbacks report shows whether the responsible tech went back (unpaid) or another tech went (paid). Commission trigger event remains an open question — nothing pays out.
56. **[SCOPE]** Sales CRM follows `docs/SALES-SYSTEM.md` minus offline mode, voice notes, GPS proximity sort, and keyboard shortcuts. Weekly Monday report emails managers/admins + `alert_email`.
57. **[MODEL]** Dormant customers are computed from the live recency data against per-company thresholds (GAG 8 wk, KC 3, CTS 4, KSF 3 from the spec).

## Permissions & platform
58. **[DEFAULT]** `technician` role gets a minimal responsive `/myday` page with On The Way / Start / Complete buttons as the web stand-in for mobile status updates. Everything else 403.
59. **[MODEL]** A generic `record_audit` table (JSON diff) is added for customers, contacts, locations, WOs, invoices, payments, estimates, catalog, tax rates, users.
60. **[MODEL]** Customer merge re-points every child table in one transaction and soft-deletes the source with `merged_into_customer_id`.
61. **[SCOPE]** CSRF protection is **not** added (the existing forms have none; adding it touches every form). Flagged for a hardening pass before external users exist.
62. **[DEFAULT]** Next migration number is 009; the two historical "003" files are left alone (per your July note).
63. **[CONFLICT]** `CLAUDE.md` says the `users` table lives only in `fieldkit_getagrip`; the code and July 2 notes say it's replicated to all four via `write_to_all_dbs`. The VM instance is told to verify and correct `CLAUDE.md` at Stage 0.
64. **[SCOPE]** The July 22 decision record (`FIELDKIT_DECISION_payment-anchoring.md`) is **not in the GitHub repo** despite the session notes saying it was committed. Its content is restated in the directive; the VM instance should look for the file on the server and commit it if found.
65. **[SCOPE]** `docs/PROJECT-KNOWLEDGE/CURRENT-STATUS.md` in the repo is the February 2026 version; the directive's Stage 0 replaces it.

---

## Questions worth answering up front (the VM instance will otherwise use the defaults above)
- #16 Delinquent threshold: 60 or 90 days from invoice date?
- #25 Confirm imported SF balances are excluded from the FieldKit tax report.
- #26 Florida tax handling for Kleanit SF.
- #33 Can Michele get the OPS import template and VendorCafe field list?
- #50 SMS alerts wanted, or email only?
- Stage 5.6: ServiceFusion price-list exports for GAG / CTS / KSF catalogs, and company legal names / remit-to / reply-to / alert emails.
