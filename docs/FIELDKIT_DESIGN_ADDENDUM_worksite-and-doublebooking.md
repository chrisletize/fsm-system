# FieldKit — Design Doc Addendum
*Session: June 30, 2026 | Topics: Customer Type, Work-Site Location Field, Double-Booking Detection*
*Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions.*

---

## Summary

Three connected pieces, in dependency order:

1. **Customer Type** — a new field on customers (`multi_family` / `residential` / `contractor`).
2. **Work-Site Location Field** — promotes the old "Unit Number" out of the catalog (where it was a non-billable ghost line item) into a first-class, freeform field on the work order. Its label and prefill are driven by customer type.
3. **Double-Booking Detection** — a same-location duplicate check built on top of the work-site field. Reclassified out of "AI features" — it's a plain SQL window check and ships with Phase 4 scheduling.

---

## Customer Type *(new field on `customers`)*

### What it is
A simple classification of the account. Three values cover how this operation actually thinks about its customers:

- `multi_family` — property-management / apartment work; service locations have units.
- `residential` — homeowners; billing address usually equals the work address.
- `contractor` — general contractors and commercial accounts (commercial and contractor are interchangeable for this operation, so they collapse into one value; "contractor" is internal shorthand and accurate enough).

### Why it earns its place beyond this feature
- Drives the work-site field's label and prefill (below).
- Segment reporting (revenue/volume by customer type).
- Available later to the Customer Rating System (§14) if type-weighting ever proves useful.

### Data Structure
```
customers
└── customer_type             -- NEW: 'multi_family' | 'residential' | 'contractor'
```
*Hardcoded value set for now, consistent with the build-hardcoded-first principle; becomes part of the configurability layer before any external/franchise onboarding.*

---

## Work-Site Location Field *(replaces the old "Unit Number" catalog item)*

### The problem it fixes
"Unit Number" used to be a special catalog item (`is_unit_number_field`) added to a work order as a line item — but it isn't billable, taxable, or duration-bearing. A non-billable line item is a ghost in the line-item model: it threatens invoice totals and the `estimated_minutes` block math, and it forces the catalog to hold something that isn't a service. The fix isn't to make the ghost behave — it's to delete the reason it existed.

### The solution
A dedicated freeform field on the work order. It is **never** a line item. The line-item model stays pure (every line item is billable by definition), and `is_unit_number_field` is removed from the catalog (see the catalog addendum, corrected).

```
work_orders
└── work_site_label           -- NEW: freeform notation of where the work physically happened
                                 (e.g., "Unit #3430-308", "412 Oak St"). Distinct from
                                 service_location_id (structured/tax) and the billing address.
                                 Indexed/searchable.
```

### It does no structural work
The work order already carries `service_location_id`, which drives the county/tax lookup. So this field carries **no** tax or structural responsibility — it's pure human-readable notation. No collision with billing or tax logic.

### Label and prefill are cosmetic defaults, driven by customer type
The field is freeform text that accepts anything; customer type only decides what it's *called* and how it pre-fills. Because the label is a hint and not a constraint, edge cases self-handle (a contractor sent to an apartment? staff just type the unit into the "Job Site" field).

| Customer type | Field label | Prefill | Notes |
|---|---|---|---|
| `multi_family` | "Unit Number" | none | Complex is the service location; the unit is this field. Never redundant. |
| `contractor` | "Job Site" | none *(prefill deferred)* | Work often happens away from the on-file address, so it's useful here. |
| `residential` | "Job Address" | from service location | The only truly-redundant case; prefill makes it free — already correct, staff ignore it. |

**Contractor prefill is intentionally deferred** — it's nuanced (billing address vs varying job sites) and Chris wants to think through the structure later. It's a one-line behavior change whenever that's settled, so it's not blocking.

### Downstream effects
- **Auto-description generator** reads the unit/site from this field instead of from the old line item — same slotted-into-position behavior, cleaner source.
- **Searchability** — being a real column (not buried in `auto_description` text) makes "every work order at unit 308" an actual query, and it's the anchor for double-booking detection below.

---

## Double-Booking Detection *(Phase 4 scheduling — NOT an AI feature)*

### Reclassification
This currently sits in the backlog under "AI Features (post-LLM server)." It does not belong there. It's a plain windowed SQL query — no model, no inference, no GPU. **It ships with the Phase 4 scheduling module**, the moment work orders and `work_site_label` exist — months earlier than its current slot.

### What it does
At work-order create/schedule time, it checks for other work orders at the **same physical site** and, if found, raises a **non-blocking alert** for office staff to examine the recurrence for errors. Staff decide — the system flags, it never blocks.

### Matching key
Same `customer_id` **and** same `service_location_id` **and** a **normalized** `work_site_label` (trimmed, lowercased, punctuation-stripped). Both anchors matter:
- Normalization handles entropy — "Unit 308" vs "#308" must still match.
- The service-location anchor prevents false positives — "Unit 1" exists at fifty different complexes; the anchor disambiguates them.

Anchoring this way is what keeps the alert precise enough that staff trust it rather than tuning it out — the failure mode that kills every alerting feature.

### Asymmetric window
- **Forward — any future booking.** Two work orders scheduled for the same exact site, however far apart, are almost always an error. Open-ended forward.
- **Backward — any work order dated within the last 4 weeks**, regardless of status (Completed, In Progress, or recently scheduled). If that site was serviced in the last month, the new booking might be redundant; past 4 weeks it's probably a legitimately new job.

### Evolution from the January 2026 sketch
The original sketch matched on `customer_id + unit_number` over a symmetric **±2-week** window with a warning modal. This supersedes it: the key generalizes to `customer + service_location + normalized work_site_label` (so it now covers contractors and residential, not just multi-family units), and the window becomes asymmetric (open-forward / 4-weeks-back), which is more correct than the old symmetric version.

### Distinct from calendar overlap / auto-bump
Do not conflate with the January calendar design where two jobs collide in one **tech's time slot** (auto-bump to the nearest open slot). That's a tech-*capacity* collision. This is a same-*location* duplicate. Different checks, same Phase 4 scheduling module.

### Dependencies
- Work orders + scheduling (Phase 4).
- `work_site_label` and `customer_type` (this document).

---

## Corrections to the catalog addendum
`FIELDKIT_DESIGN_ADDENDUM_catalog-and-equipment.md` has been updated to reflect this session:
- `is_unit_number_field` **removed** from `catalog_items` (promoted to `work_site_label` here).
- The "Unit Number ghost-item" open soft spot is **resolved** by this document.
- The "snapshot cost" open soft spot was **already resolved** in the existing schema (`work_order_line_items.cost`), so it's closed too.

---

*Drafted: June 30, 2026*
*For merge into FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md (adds to §Customers, §Work Orders, and Phase 4 scheduling; reclassifies double-booking out of AI Features).*
