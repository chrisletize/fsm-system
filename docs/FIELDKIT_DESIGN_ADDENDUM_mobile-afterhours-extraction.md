# FieldKit — Design Doc Addendum
*Session: June 30, 2026 | Topic: After-Hours Water Extraction — Mobile Capture & Retroactive Work Orders*
*Phase 6 (Mobile) design note. Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions.*

---

## The problem this solves

After-hours emergency water extractions happen when the office is closed. Today there is **no work order** until the next morning, when the tech verbally reports what they did and the office reconstructs it. The tech is often exhausted — full workday, then up in the middle of the night — so the capture has to be **as close to zero effort as possible**, or it won't get used.

This note covers how the mobile app captures that work with one button, backstops the tech when they forget, lets them report equipment without typing, and how the office turns it into a finalized work order the next day.

---

## Core principle: phone proposes, office commits

Nothing the phone captures after hours becomes a billable record on its own. Every path produces a **draft** that lands in an office review queue for confirmation and finalization. This keeps fuzzy field data from silently becoming invoices, and it matches the draft-confirm pattern used elsewhere in FieldKit.

---

## Location capture: visit monitoring, not GPS tracking

### Do **not** use continuous GPS
A 24/7 location stream is a battery killer, a privacy problem, and the version App Review pushes back on. It's also the wrong tool for "where was the tech, and when did they arrive/leave."

### Do **not** use geofencing either
The obvious tool — region monitoring around each property — **caps at ~20 monitored regions per app on iOS.** With hundreds of service locations, that wall is fatal.

### Use **visit monitoring** (iOS `CLVisit`)
iOS detects **arrivals and departures on its own**, low-power, and hands the app a coordinate plus arrival and departure timestamps when a visit completes. The app doesn't watch GPS; iOS wakes it when a visit finishes. Crucially, it reports a visit **wherever it happens** — so we **reverse-match the coordinate to the nearest known property afterward**, which sidesteps the 20-region cap entirely. Android is more permissive here and the same architecture ports cleanly.

---

## Two capture paths

### Primary: one button
Tech taps **"Start Extraction"** → app grabs current location → matches it to the property → starts the clock → **stops automatically** on the departure visit event. This is the happy path: one press, tired-tech-friendly.

### Backstop: passive visit log
Because visit monitoring is quietly running, when the tech forgets the button the app can reconstruct it. Next morning: *"Looks like you were at **[property]** from 2:14–3:40am — log that as an extraction?"* One tap to confirm. If the property match is ambiguous, offer the top candidates from the visit's location rather than guessing.

---

## Honest caveats that shaped this design

**1. Passive timing is fuzzy.** `CLVisit` arrival/departure can be off by several minutes — fine for *which property, roughly when*, but Water Extraction bills **pro-rated per quarter-hour**. So passive data only ever produces a **draft the tech confirms or nudges**; the button press (or the tech's manual morning entry) stays the billing source of truth. **Never auto-bill off a fuzzy departure.**

**2. This is employee location tracking** — a trust matter as much as a technical one. Scope monitoring to work context, and be upfront with techs that it exists to **save them the 2am paperwork, not to watch them**. That framing keeps it both defensible to App Review and not resented by the people who have to leave the permission on "Always."

---

## Equipment reporting (one box, registry-backed)

After an extraction, the tech reports which machines they placed. This is a **single box** that **autocompletes from the Equipment Registry** (see the catalog addendum) — no free text. The tech taps "Ozone #2" / "Dehumidifier #4" from the list; each pick becomes a **draft per-day equipment line item** carrying the physical unit and its billing type, for the office to confirm against the catalog before finalizing. One box for the tired tech; structured, drift-free data for the office.

---

## Retroactive work order creation

This inverts the normal deployment flow and is the key constraint to bake in now. Normally: deploy → accrue days → retrieve. After-hours extraction means **the work happened with no work order at all**, and the work order is **born retroactively** carrying an **already-deployed machine and an already-elapsed first session**.

So the deployment/rollover engine (Phase 4 water-extraction queue) must support a **backdated start** — "create work order; first deployment day was last night" — not just forward-running deployments. The office review item, when finalized, creates the work order with `deployed_at` set to the captured start.

---

## The office review queue

The "Start Extraction" press (or a confirmed passive draft) drops a **pending work order** into an office review queue, **pre-filled** with:
- Property (from the location match)
- Start time (button press or visit arrival)
- End time (auto-stop on departure)
- Draft equipment line items (from the tech's registry picks)

Michele opens it the next morning, confirms/adjusts, and **finalizes it into a real work order**. The queue item *is* the morning verbal report — just structured and already half-filled.

---

## Dependencies & cross-references
- **Equipment Registry** and **per-day equipment billing** — see `FIELDKIT_DESIGN_ADDENDUM_catalog-and-equipment.md`.
- **Deployment/rollover engine** (day accrual, retrieval close-out, backdated start) — Phase 4 water-extraction queue.
- **Water Extraction Service min/increment rounding** — catalog addendum; pairs with the per-quarter-hour billing rule referenced above.
- **Actual hours from tech clock-in/out** — Phase 6; once available, can drive the rounding rule from real time-on-site instead of manual entry.

---

*Drafted: June 30, 2026*
*Phase 6 mobile design note. For merge into FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md.*
