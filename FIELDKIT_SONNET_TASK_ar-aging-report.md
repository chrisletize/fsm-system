# FieldKit Phase 0 — Sonnet Task Prompt: A/R Aging Report

*Paste this alongside the general `FIELDKIT_SONNET_EXECUTION_PROMPT.md`. That prompt gives you the standing rules and stack; this one scopes a single feature. Do not restate the general rules — follow them.*

**⚠️ This is a PHASE 0 task — the statements site, not Phase 5 FieldKit.** Phase 0 conventions differ from the FieldKit app conventions in important ways (see Non-negotiables). Do not apply Phase 5 patterns here by reflex.

---

## What you're building

A new **A/R Aging Report** page on the Phase 0 statements site (`statements.cletize.com`). It answers one question for the office: *who owes us the most, and how delinquent is it?*

Requested by Patrick (office staff, collections). The primary view is one row per customer, sorted by total amount owed descending, with the balance broken into aging buckets so the shape of the delinquency is visible at a glance.

**The key insight that keeps this small:** Michele's existing statement upload already imports *all* invoices (paid and unpaid) into the `invoices` table with `invoice_date`, `invoice_total_due`, `customer_id`, and `company_id`. Every field this report needs is already there. **There is no new upload, no new parsing, and no new table.** This is a query, a template, and a print stylesheet. If you find yourself writing Excel-parsing code, stop — you've misread the task.

## Read first

- `FIELDKIT_PROJECT_REFERENCE.md` — Section 3 (Phase 0 codebase, file structure, DB schema) and Section 4 (existing features).
- `RECENCY_REPORT_INTEGRATION_NOTES.md` — the recency report is the closest existing analogue in structure, print handling, and page layout. Follow its patterns.
- The existing `backend/api/templates/recency_report.html` and `tax-report.html` — reuse the company selector, branding swap, and print CSS rather than inventing new ones.
- `branding.py` — per-company colors. All four companies get this report.

## Confirm these dependencies BEFORE writing code — flag any unresolved one with `[ESCALATE]`

1. **Database layout — resolve this first, everything depends on it.** The docs conflict. `FIELDKIT_PROJECT_REFERENCE.md` says Phase 0 is a **single DB `fsm_system`**, all companies sharing tables filtered by `company_id`. `RECENCY_REPORT_INTEGRATION_NOTES.md` describes **four separate DBs** (`fsm_gagrip`, `fsm_kleanit`, `fsm_cts`, `fsm_kleanit_fl`). Inspect the running system and determine which is actually true. Report what you find before writing any query. **Do not guess.**

2. **Which host serves production statements?** The reference doc describes Phase 0 on `ubuntu1` under systemd; there was a Docker migration to `ubuntu-business`. Confirm where the live app actually runs before editing files.

3. **Does `invoices` have an import timestamp?** Look for `created_at`, `imported_at`, or equivalent. The staleness banner (below) requires knowing when the current invoice snapshot landed. If no such column exists, **adding one is part of this task** — a small migration, defaulting to `NOW()` on insert. Flag this as a schema change before making it.

4. **What does Michele's upload actually do to existing rows?** There is a "Clear data per company" function. Determine whether her normal workflow is clear-then-reimport (table holds a single current snapshot) or incremental UPSERT (table accumulates). This changes how "data as of" is computed: a snapshot has one import date; an accumulating table needs `MAX(imported_at)`.

## Bucket definitions — exact semantics, do not improvise

Aging is by **invoice date**, not due date. All customers are considered due at net 30; late payment is tolerated in practice but is not a term.

```
age_days = report_run_date - invoice_date
```

| Column label | Condition | Meaning |
|---|---|---|
| Not Due (0–30) | `age_days <= 30` | Within terms |
| 30 (31–60) | `age_days BETWEEN 31 AND 60` | 30 days past due |
| 60 (61–90) | `age_days BETWEEN 61 AND 90` | 60 days past due |
| 90+ (91+) | `age_days >= 91` | 90+ days past due |

The bucket labeled "30" means **30 days past due**, not "0–30 days old." An invoice exactly 30 days old is Not Due. Print both the tier label and the day range in the column header exactly as written above — the office thinks in net tiers, but the day range removes all ambiguity for anyone reading a printed copy.

Include only rows where `invoice_total_due > 0`.

## Table structure

Column order is fixed — it was chosen for the printed version:

| Customer | Total Due | Not Due (0–30) | 30 (31–60) | 60 (61–90) | 90+ (91+) | Oldest Invoice |
|---|---|---|---|---|---|---|

- **Total Due** is bold; it's the primary reference.
- **Oldest Invoice** is the date of the oldest open invoice for that customer. One column, print-friendly, and it answers "who do I call first" faster than the buckets do.
- **Bottom totals row**: column sums across all customers, plus a grand total. Present on screen and on print.
- **Default sort**: Total Due descending.
- **Secondary sort toggle**: sort by 90+ bucket descending. A customer owing $13k all Not Due is not a phone call; a customer owing $4k all in 90+ is. On-screen control only — the printed output reflects whatever sort is active.

**Explicitly out of scope — do not build these:**
- Credit/negative balance handling. This business never has negative customer totals.
- Minimum balance thresholds or small-balance filtering. Minimum invoice is $185 and every balance is worth chasing. Show everything.

## Staleness handling — a required feature, not a nicety

The invoice snapshot is only as fresh as Michele's last upload, but aging is computed from today's run date. If she uploaded three weeks ago, a customer may have paid, or may have silently rolled from 60 into 90+.

**Two dates in the report header, on screen AND on the printed output:**

```
A/R Aging Summary — Get A Grip of Charlotte
Report run: 09/14/2026 · Invoice data imported: 08/22/2026 (23 days ago)
```

**Plus a warning banner when the import is more than 7 days old** (on-screen; use the existing warning/alert styling from the recency report's pre-upload validation if one exists):

> ⚠️ Invoice data is 23 days old. Balances may not reflect recent payments.

The reasoning matters, so don't water it down: someone handing a printed report to a customer or a manager must not be able to accidentally represent three-week-old balances as current. Both dates on the print output is the whole point.

## Drill-down

Clicking a customer row expands the invoice-level detail behind that customer's balance:

`Invoice # | Invoice Date | Days Old | Bucket | Original Total | Balance Due`

**Pre-render the detail rows hidden** (`<tr class="detail-row">`) and toggle with a click handler. Do not build an AJAX endpoint — the data volume is small, pre-rendering beats a round trip, and it means the print stylesheet gets the clean version for free:

```css
@media print {
  .detail-row, .controls, .company-selector { display: none; }
}
```

One page, two renderings. Do not build a separate print render path.

## Per-customer detail print

Each expanded customer row gets a small **[Print Detail]** button producing a clean single-customer printable: customer name, company branding header, both dates, the aging summary for that one customer, and the full invoice-level table. This is a collections tool — Patrick takes it into a phone call about a problem account.

Print-detail output **does** include the invoice rows (unlike the summary print, which hides them).

## Page architecture

Follow the tax report / recency report pattern exactly:

- New route(s) in `backend/api/app.py`
- New template `backend/api/templates/aging_report.html`
- Link added from `index.html` alongside the existing report links
- Company selector with dynamic branding swap (same mechanism, all four companies)

**Difference from the other report pages: there is no upload step.** Select company → **[Run Report]** → table renders from data already in the database. That single-button simplicity is the point of the feature; preserve it.

## Build in verified increments (do not batch these)

1. **Dependency confirmation.** Resolve items 1–4 above. Report findings. Do not proceed until the DB layout question is settled.
2. **Schema, if needed.** Import-timestamp column + migration, applied to whichever DB structure is actually in use. Verify on every company's data before proceeding.
3. **Query + bare table.** Aging buckets, totals row, default sort. Verify bucket math by hand against a handful of known invoices — pick one invoice near each boundary (30/31, 60/61, 90/91) and confirm it lands in the expected column.
4. **Page + branding + staleness header.** All four companies render with correct colors and correct dates.
5. **Drill-down + sort toggle.**
6. **Print stylesheet + per-customer detail print.** Verify actual print preview, not just the CSS.

Deliver complete files each increment, give verification commands with expected output, and don't advance until the current increment is confirmed.

## Non-negotiables specific to this feature

- **Phase 0 conventions, not Phase 5.** If the DB turns out to be single-`fsm_system`, queries filter by `company_id` — this is the *opposite* of the Phase 5 FieldKit rule. Do not carry `get_db_connection(company_key)` patterns over without confirming they apply here.
- **The statements app Dockerfile uses `COPY`.** Every code change requires `docker compose up -d --build`, not a restart. A plain restart will appear to succeed and serve stale code.
- **Read the full current file before modifying it. Complete file replacements only** — no snippets, no `sed`.
- **Do not touch the import/upload path.** This feature is read-only against existing data. If a schema change is required for the import timestamp, that is the single exception and it must be flagged before it's made.
- **Both dates appear on every printed output.** Summary print and per-customer detail print alike.

---

*Feature task prompt. Companion to `FIELDKIT_SONNET_EXECUTION_PROMPT.md` and the design docs in `chrisletize/fsm-system`.*
