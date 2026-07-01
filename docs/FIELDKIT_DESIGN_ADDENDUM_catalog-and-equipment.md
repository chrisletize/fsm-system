# FieldKit — Design Doc Addendum
*Session: June 30, 2026 | Topic: Service Catalog Hardening + Per-Day Equipment + Equipment Registry*
*Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions.*
*This addendum **revises Section 1** (Services & Products Catalog) and **folds in §13** (`estimated_minutes`). Where it conflicts with the original Section 1, this document wins.*

---

## Summary of what changed and why

Section 1 modeled the catalog around **item_type: service vs product**. Working through ozone treatments and water-extraction equipment showed that "product" is the wrong axis — nobody cares that a dehumidifier is a physical object. What actually distinguishes these items is **how they bill**, and there turn out to be exactly two behaviors:

1. **Point-in-time** — quantity is known when the work is done; the item has a labor-time component that sizes the schedule block.
2. **Per-day equipment** — a machine is deployed, runs open-ended, and bills per day until someone retrieves it; it has no meaningful labor time and must not affect schedule-block sizing.

So `item_type` is replaced by `billing_behavior`. The services-vs-products *reporting* distinction Section 1 cared about is preserved for free: `standard` = service revenue, `per_day_equipment` = equipment revenue.

This change also **answers the open question left in §13** — which catalog items skip the `estimated_minutes × quantity` block math. The answer is: per-day equipment items (plus the Unit Number and Custom Service items, which simply carry no `estimated_minutes`).

---

## 1 (revised). Services & Products Catalog

### The two billing behaviors

**Standard (point-in-time)** — `billing_behavior = 'standard'`
- Bills `unit_price × quantity`.
- Quantity is set when the work is done.
- Carries `estimated_minutes`, so it feeds the dispatch-board block size (per §13).
- Covers every normal service **and** the hourly Water Extraction *Service* line. For an `hour` item, `estimated_minutes = 60`, so billed hours and time-on-site are the same axis — which is exactly correct for extraction labor.

**Per-day equipment** — `billing_behavior = 'per_day_equipment'`
- `unit_price` is a **daily rate**; quantity is **days deployed**; bills `unit_price × quantity` like everything else.
- **No `estimated_minutes`** → never contributes to schedule-block math. There is no per-placement labor charge and no pickup charge — the daily rate covers it (confirmed: Kleanit does not bill labor on equipment).
- Quantity is **not entered up front**. It **accrues** through the deployment/rollover engine (Phase 4 water-extraction queue) and **finalizes at retrieval**, when the office marks the unit picked up.
- Covers ozone machines and water-extraction equipment both.

`billing_behavior` is an **explicit column**, not inferred from `unit_of_measure = 'day'`. This flag is what gates the rollover engine and the block-math exemption — it needs to be a real field, not a string match on a units label.

### Category and billing behavior are separate dimensions
Ozone machines and water-extraction equipment share `billing_behavior = 'per_day_equipment'` but live in different categories (**Ozone** vs **Water Extraction**). Category is a display/reporting label; billing behavior is functional. Keeping them separate is exactly why "product" was the wrong single axis.

### How the two job types decompose
- **Water extraction job** = 1 Water Extraction *Service* line (hourly, `standard`) + N Extraction Equipment lines (`per_day_equipment`).
- **Ozone job** = N Ozone Machine lines (`per_day_equipment`), no service line at all.

Same per-day engine drives both equipment types; both are **open-ended** (we are assuming the office does not know up front how long ozone must run — stop condition is "office marks retrieved," same as water).

### Water Extraction Service: minimum + rounding
The Water Extraction *Service* line bills a minimum first hour, then pro-rates per quarter-hour past that at the same hourly rate. This is modeled as two optional catalog fields rather than special-cased in code:
- `minimum_quantity` — floor on billable quantity (Water Extraction = `1.0`).
- `billing_increment` — rounding step past the minimum (Water Extraction = `0.25`).

Both are **NULL on every item except Water Extraction**. The system auto-rounds whatever hours are entered. These earn their keep most once Phase 6 tech clock-in/out can feed *actual* hours in and let the rule round automatically — but they're cheap now and remove a manual-math error source for Michele.

### What carries over unchanged from original Section 1
The no-freeform rule, the **"Custom Service"** catch-all (`is_catch_all`), the **"Unit Number"** special item (`is_unit_number_field`), the editable per-line description, the three-layer tax exemption hierarchy (item → customer → location), and the `/<company>/settings/catalog` admin UX all stand as written.

### Revised Data Structure

```
catalog_items
├── id
├── company_id                -- catalog is per-company
├── billing_behavior          -- CHANGED (replaces item_type): 'standard' | 'per_day_equipment'
├── name                      -- "Bathtub Resurface", "Ozone Machine", "Custom Service"
├── default_description       -- pre-fills the description box when added to a work order
├── category                  -- display grouping: "Resurfacing", "Cleaning", "Ozone", "Water Extraction", "Admin"
├── unit_price                -- standard: price per unit; per_day_equipment: DAILY rate
├── unit_of_measure           -- 'each' | 'sq ft' | 'hour' | 'flat rate' | 'day'   (NEW: 'day')
├── estimated_minutes         -- NEW (from §13): minutes per unit; NULL for per_day_equipment,
│                                Unit Number, and (by default) Custom Service. NULL contributes 0
│                                to block math.
├── minimum_quantity          -- NEW: billable-qty floor (Water Extraction = 1.0); NULL otherwise
├── billing_increment         -- NEW: billable-qty rounding step (Water Extraction = 0.25); NULL otherwise
├── is_taxable                -- does this item carry sales tax?
├── cost                      -- internal cost for margin calculation
├── is_unit_number_field      -- special: this item's value slots into the job description as unit number
├── is_catch_all              -- true for "Custom Service" — requires description to be filled
├── sort_order
├── is_active
├── created_by / updated_by
└── deleted_at
```

---

## Equipment Registry (NEW)

### What it is
A per-company list of the **actual physical machines** the business owns — "Ozone #2", "Dehumidifier #4" — each pointing at the per-day catalog item it bills as. This replaces the current sideways solution of naming every physical machine as its own catalog line item.

### Why a registry instead of one-catalog-item-per-machine
Line items today are quietly doing two jobs at once:
- **Billing** — how many machine-days to charge → wants a *generic* per-day item ("Dehumidifier — $X/day").
- **Tracking** — which *physical unit* sat at which property → wants *specific* identity.

Naming each machine as its own catalog item conflates these, bloats the catalog with the fleet, and leans on free-typed names — the exact entropy the no-freeform rule exists to prevent ("Dehumidifier #4" / "dehumid 4" / "the big fan"). The registry separates the two cleanly: the **catalog** holds the billing type, the **registry** holds the physical unit, and a unit points at its billing type.

### Tech experience stays one box
Reporting equipment is still a single box for the tech — it just **autocompletes from the registry** instead of accepting free text. A tired tech taps "Ozone #2" from a list rather than fat-fingering a new spelling. All the added structure lives on the office/build side; the tech experience gets *simpler and less error-prone*. The tech's pick becomes a draft line item the office confirms against the catalog before it commits (see the mobile addendum for the draft-confirm flow).

### Data Structure
```
equipment_units
├── id
├── company_id
├── name                      -- physical unit label: "Ozone #2", "Dehumidifier #4"
├── catalog_item_id           -- FK → catalog_items; the per_day_equipment billing type this unit bills as
├── is_active                 -- unit in service / retired
├── notes                     -- optional: serial #, purchase date, condition
├── created_by / updated_by
└── deleted_at
```

### Line-item link
When a unit is deployed on a work order, its line item references **both** the billing type and the physical unit:
```
work_order_line_items  (additions for per-day equipment)
├── equipment_unit_id         -- NEW, nullable: set when this line is a per-day equipment deployment
├── deployed_at               -- NEW, nullable: deployment start (per-day items only)
├── retrieved_at              -- NEW, nullable: set when office marks unit picked up; closes accrual
└── quantity                  -- finalizes to billable days at retrieval (derived from deploy/retrieve)
```
*(The accrual/rollover mechanics themselves live in the Phase 4 water-extraction queue; the catalog's job is only to define the item types, the registry, and the fields the engine writes to.)*

### Future payoff this unlocks
Because each deployment ties to a specific unit, the system can later flag a machine that's been deployed N days and never marked retrieved — both a billing safeguard and a "where is unit #4" fleet-tracking answer.

---

## Still-open catalog soft spots (not resolved this session)
Captured so they aren't lost — these were on the hardening list before the ozone/equipment thread took over:

- [ ] **Unit Number ghost-item rules** — it's a line item but not billable, taxable, or duration-bearing; needs explicit handling so it can't corrupt invoice totals or block math.
- [ ] **Category drift** — `category` is currently free text per item; decide whether it becomes a managed per-company list to prevent "Resurfacing/resurfacing/Resurface" entropy.
- [ ] **Minimum required fields** for a valid catalog item — governs the inline "+Add to Catalog" quick-add so it can't spawn half-formed items.
- [ ] **Snapshot `cost`** (not just price) onto work-order line items, so historical margin survives a later catalog price/cost change.
- [ ] **Catalog seeding** — import from a ServiceFusion price list vs hand-build per company; affects the Phase 2 "catalog ready for work orders" milestone.
- [ ] **Retain `item_type`?** — this addendum drops it in favor of `billing_behavior`. Confirm nothing downstream needed the literal service/product label that `billing_behavior` doesn't already provide.

---

*Drafted: June 30, 2026*
*For merge into FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md (revises §1, folds in §13).*
