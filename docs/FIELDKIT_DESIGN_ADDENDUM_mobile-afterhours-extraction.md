# FieldKit — Design Doc Addendum
*Session: June 30, 2026 | Topic: After-Hours Water Extraction — Mobile Capture & Retroactive Work Orders*
*Phase 6 (Mobile) design note. Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions.*
*Updated: July 3, 2026 — added the `equipment_incomplete` gap-forwarding section (Reconciliation Framework, Pattern 3) and aligned the billable-time reference.*

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

## When equipment isn't reported: the `equipment_incomplete` flag (Pattern 3)

Equipment is the one part of an after-hours extraction that **no backstop can reconstruct.** The `CLVisit` trail recovers *which property* and *roughly when*, but it cannot see *which machines, or how many* sat in the room — that is not physically observable. So when the tech forgets to log equipment, reconstruction fails at the source, and the correct move is Pattern 3 of the Reconciliation Framework: **forward the gap to the next human positioned to fill it** — not nag the exhausted 2am tech, and not leave the office guessing.

### How the flag gets set
- **Explicit:** the after-hours flow offers "couldn't log equipment now" so a tired tech can defer it in one tap instead of skipping the whole report.
- **Automatic:** any extraction confirmed via the **passive backstop path** finalizes with **zero equipment line items** — because the backstop inherently can't capture equipment — so it is auto-flagged.

Either way, the work order is created/finalized with `equipment_incomplete = true`. The extraction is still real, still billable for time; only the equipment lines are known-missing.

### Where the gap gets filled
The natural next touchpoint is the **follow-up visit** — a tech going out to check the drying state is standing in the room looking at the machines anyway. On a work order carrying the flag, the follow-up tech gets **"Confirm equipment on site"** as a required first task on arrival, reported the same registry-backed way (one box, autocomplete, no free text). Each pick becomes a draft per-day equipment line item, and — critically — its day-accrual is **backdated to the original extraction start**, not the follow-up date (Pattern 4: effective time = when the machine was actually placed). This reuses the backdated-start requirement already established for retroactive work orders below.

Confirming the equipment clears the flag. As everywhere else, the follow-up tech's picks are still **drafts the office confirms** — phone proposes, office commits.

### If there's no follow-up visit
The flag does not silently resolve and the system never invents equipment it has no record of. The unresolved flag **stays visible and countable on the office review queue** so Michele can chase it directly rather than have it rot. The invariant: equipment is either reported, explicitly forwarded and later confirmed, or a visible open gap — never silently billed and never silently dropped.

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
- `equipment_incomplete` flag, if equipment was deferred or auto-flagged (see above)

Michele opens it the next morning, confirms/adjusts, and **finalizes it into a real work order**. The queue item *is* the morning verbal report — just structured and already half-filled. Any `equipment_incomplete` flags remain visible on the queue until resolved.

---

## Dependencies & cross-references
- **Reconciliation Framework** (the four-pattern lens; this note is Patterns 1, 3, and 4 in practice) — see `FIELDKIT_DESIGN_ADDENDUM_reconciliation-framework.md`. The `equipment_incomplete` flag is that addendum's canonical Pattern 3 example.
- **Equipment Registry** and **per-day equipment billing** — see `FIELDKIT_DESIGN_ADDENDUM_catalog-and-equipment.md`.
- **Deployment/rollover engine** (day accrual, retrieval close-out, backdated start) — Phase 4 water-extraction queue.
- **Water Extraction Service min/increment rounding** — catalog addendum; pairs with the per-quarter-hour billing rule referenced above.
- **Billable interval capture for extraction** — the *timed-interval capture with backstop + backdated confirm* candidate brick (Reconciliation Framework addendum). Once built, it can drive the per-quarter-hour rounding from real time-on-site instead of manual entry. Note: this is **billable** time, not a payroll clock — techs are commission-paid and FieldKit has **no attendance timeclock**.

---

*Drafted: June 30, 2026*
*Updated: July 3, 2026*
*Phase 6 mobile design note. For merge into FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md.*
