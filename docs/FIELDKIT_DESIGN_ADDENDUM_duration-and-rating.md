# FieldKit — Design Doc Addendum
*Session: June 17, 2026 | Topics: Job Duration & Schedule Time Estimation, Customer Rating System*
*Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions — paste directly into the master doc.*

---

## 13. Job Duration & Schedule Time Estimation

*Extends Section 1 (Services & Products Catalog) and Section 10 (Work Orders)*

### What it is
Catalog items carry an estimated duration. As line items are added to a work order, FieldKit computes a running total estimated job duration — the same mechanism as the existing job description live preview. That total becomes the default size of the job's block on the dispatch board. Office staff can override it, but get a warning if the override drifts too far from what the catalog says the job should take, in either direction.

### Why this matters
Schedule blocks are currently sized by guesswork. A job that needs 90 minutes and gets scheduled for 45 runs the tech late for the rest of the day — the same cascading problem that makes water extraction so painful, just applied to ordinary jobs. Catalog-driven estimates give dispatch a sane default and a guardrail without removing judgment.

### How it works
1. Each catalog item gets an `estimated_minutes` value — minutes per unit of that item's `unit_of_measure`.
2. When a line item is added to a work order, `estimated_minutes` is snapshotted onto the line item — same pattern as price and description today: pulled from the catalog default, editable per line if a specific job is unusual.
3. The work order's catalog-estimated duration is the live sum: `Σ (line_item.estimated_minutes × line_item.quantity)`.
4. This total auto-populates the work order's scheduled duration the first time line items are added. Once a human edits the scheduled duration directly — on the form, or by drag-resizing the block on the dispatch board — it stops auto-updating; a `duration_overridden` flag locks it in.
5. If line items change after that point, a non-blocking banner appears: *"Catalog estimate is now 90 min, scheduled is 45 min — update?"*

### One formula, no special-casing per unit type
Because the formula is always `estimated_minutes × quantity`, every `unit_of_measure` works the same way without exceptions:
- **each** — set `estimated_minutes` to the typical time for one unit (quantity is usually 1)
- **hour** — set `estimated_minutes` to 60; quantity (hours billed) naturally produces the right total
- **sq ft** — set `estimated_minutes` to a small per-sq-ft figure
- **flat rate** — quantity is normally 1, so it behaves like "each"

### Data Structure
```
catalog_items
└── estimated_minutes              -- NEW: minutes per unit of unit_of_measure

work_order_line_items
└── estimated_minutes              -- NEW: snapshotted from catalog at add time; editable per line

work_orders
├── estimated_duration_hours       -- EXISTING field, repurposed: this is the SCHEDULED duration
│                                      that actually sizes the dispatch board block. Auto-filled
│                                      from the catalog total; overridable.
├── catalog_estimated_duration_hours -- NEW: live computed total from line items (decimal hours),
│                                        recalculated whenever line items change. Reference value
│                                        only — used for the warning comparison, never user-edited.
├── duration_overridden            -- NEW: boolean. False until a user manually changes
│                                      estimated_duration_hours away from the catalog total.
│                                      Once true, line item changes no longer auto-overwrite it.
└── actual_duration_hours          -- EXISTING, unaffected (Phase 6 tech clock-in/out)
```

### Warning Logic
- Checked on work order save and on dispatch board drag-resize release.
- Fires if `estimated_duration_hours` differs from `catalog_estimated_duration_hours` by more than a tolerance band (suggested default: ±15 minutes — tune once there's real data to look at).
- Non-blocking, same pattern as the stale-billing-info check: *"These services typically take about {catalog} — this job is scheduled for {scheduled}."* → **[Use {catalog}]** **[Keep {scheduled} Anyway]**
- Fires in both directions: under-scheduled (risk of running the tech late) and over-scheduled (wastes capacity on the board).

### UX Flow
- Work order form: an "Estimated Duration" readout shows the live catalog total next to an editable "Scheduled Duration" field. They start equal; editing the second one breaks the link.
- Dispatch board: dragging a block's edge to resize triggers the same warning check on release.
- Catalog settings (`/<company>/settings/catalog`): `estimated_minutes` is one more field on the existing item add/edit form — no separate page needed.

---

## 14. Customer Rating System

*New section — suggested placement after Section 12 (Payments), before Part Three*

### What it is
A letter-grade rating (A–F) per customer, computed from job volume, payment timeliness, and cancellation rate, with a manager override on top. It's a quick-glance signal, not a policy — meant to answer one question fast: is this customer worth bending over backwards for on a last-second scheduling request?

### Inputs
| Factor | Direction | Source |
|---|---|---|
| Job volume | Positive | Count of completed work orders in the trailing 12 months. Rescheduled jobs don't count against a customer — only whether the work eventually got done. |
| Payment timeliness | Negative — heaviest weight | Invoice aging distribution (Current / 31-60 / 61-90 / 90+) — the same data already powering the Billing page and the Delinquent Account tag. |
| Cancellation rate | Negative | Work orders with status `Cancelled` (already an existing status — Section 7) ÷ total work orders scheduled, in the trailing 12 months. |

### Scoring
Start from a base score of 100 per customer:
- Subtract a payment penalty scaled to how far into the aging buckets their balances have sat — heaviest weight, since a customer who routinely rolls to 90+ days takes the biggest hit.
- Subtract a cancellation penalty scaled to cancellation rate.
- Add a small, capped volume bonus for frequency/loyalty.
- Floor at 0, ceiling at 100.

Map the composite score to a letter grade for display (starting bands — tune once there's real data):
```
A: 90-100   B: 75-89   C: 60-74   D: 40-59   F: <40
```

### Manager Override
A manual adjustment sits on top of the algorithmic grade — a delta plus a required note (e.g., *"B, bumped to A — longtime client, always pays eventually, just slow."*). Both the algorithmic grade and the adjusted grade are stored and visible, so staff see the system's read and the human judgment call side by side.

### Calculation Timing
Recomputed nightly for every customer — same pattern as the existing Delinquent Account auto-tag job (Section 2). One background job, not computed on the fly per page load.

### Data Structure
```
customer_ratings
├── customer_id
├── job_volume_score
├── payment_timeliness_score
├── cancellation_score
├── composite_score             -- 0-100
├── letter_grade                -- A-F, derived from composite_score
├── manager_adjustment          -- nullable; +/- delta
├── manager_adjustment_note     -- required if manager_adjustment is set
├── adjusted_letter_grade       -- composite grade + manager_adjustment, if present
├── last_calculated_at
└── calculated_by               -- 'system' for the nightly job
```

### UX Flow
- **Customer detail**: full breakdown — the three input scores, the algorithmic grade, and the manager override/note if one exists.
- **Work order create form**: a small grade badge next to the customer's name the moment they're selected — the exact moment a dispatcher decides how hard to accommodate a last-second request.
- **Dispatch board**: same small badge on the job block hover popup.

---

*One correction from earlier in this conversation: cancellations don't need a new "Cancelled" status — it already exists in the Section 7 work order lifecycle ("cancelled before any work; cannot be invoiced"). The rating system uses it as-is, no schema gap there.*

---

*Drafted: June 17, 2026*
*For merge into FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md*
