# FieldKit — Design Doc Addendum
*Session: September 2026 | Topic: Visit Status Tracking, Dispatch Board Status Colors, Extraction Follow-Up Notes*
*Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions. Migration 029.*

---

## The problem this solves

Three gaps surfaced while building out test data for the water extraction queue:

1. **The extraction daily log has a `notes` column nobody writes to.** The office (and eventually the dedicated follow-up tech) needs a place to record *why* a job is still drying, not just which of four canned statuses applies.
2. **`work_orders.status` was being asked to do two jobs at once.** For a multi-day extraction job, `status = 'Extraction Active'` already describes the job's whole multi-day arc. There was no way to also express "is a human on-site working *right now*" without overloading that same field — and doing so would have broken the extraction lifecycle (a tech "completing" today's five-minute moisture check can't mean the same thing as completing the job).
3. **There's no tech-facing way to report field progress at all**, for extraction or regular jobs, and the dispatch board has no visual distinction between a job that's still scheduled and one that's already wrapped.

## Core decision: two independent state machines, not one

- **Work order status** (unchanged) — the job's overall lifecycle: `Scheduled → Completed / No Charge / Cancelled`, or for extraction jobs, `Scheduled → Extraction Active → Completed` once equipment is retrieved. Office-controlled. `No Charge` in particular is **office-only** — a tech in the field only ever reports Completed or Cancelled; No Charge is a billing decision made afterward (most often on callback visits where nothing new was found).
- **Visit status** (new) — describes *this specific trip*, independent of the work order's own status: `On The Way → Started → Completed / Cancelled`. Ephemeral per visit; resets every time a tech is dispatched. Applies uniformly to **every work order, extraction or not**, and to **every company**.

For a regular one-visit job these two collapse into what feels like one thing. For an extraction follow-up, they don't: the WO stays `Extraction Active` for days while each individual check-in visit runs its own tiny On The Way → Started → Completed arc. "Completed" on a visit means "today's check-in is done" — it does **not** close the work order. Closing an extraction job out is still exclusively the Retrieve action.

Per-tech granularity matters for multi-tech jobs (seeing that one tech is en route while another is already on-site), so visit status is tracked **per (work_order, tech)**, not per work order.

## Data model: `work_order_visit_status_log`

One append-only row per status change, timestamped. No separate "current status" column anywhere — consistent with how this codebase already treats every other derived status (`invoice_display_status`, `extraction_day_count`): computed on read from the log, never a second source of truth that can drift.

```sql
CREATE TABLE work_order_visit_status_log (
    id             SERIAL PRIMARY KEY,
    work_order_id  INTEGER NOT NULL REFERENCES work_orders(id),
    username       VARCHAR(100) NOT NULL,     -- whose visit this is
    status         VARCHAR(20) NOT NULL CHECK (status IN ('On The Way', 'Started', 'Completed', 'Cancelled')),
    changed_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by     VARCHAR(100) NOT NULL      -- normally = username; differs when office overrides on a tech's behalf
);
```

"Current visit status" for a (work_order, tech) pair is the row with the latest `changed_at`. Every insert also goes through `_record_audit()` like every other tracked entity, so the full history is visible the same way work order/invoice/customer history already is.

Real timestamps, not just a note field — per Chris: "it's not a common or crucial problem to be on top of employees in this manner, so it can just be a timestamp log of when statuses are changed," applied uniformly to single- and multi-tech jobs. This isn't attendance tracking; it's operational visibility (was this job actually worked when it says it was), and it's cheap to add now while the log table is being built anyway.

## Permissions

- **Regular visit status** (On The Way/Started/Completed/Cancelled): any tech assigned to the work order (`work_order_techs`) can set **their own** status on it. Office (admin/manager/office) can set or override any tech's status on any work order they have access to.
- **Extraction daily actions** (Mark Ready / Needs More Time / Missed Today / Retrieved): unchanged for office. Additionally opened up to whichever tech is named in the work order's own `followup_tech_username` field. No new "designation" flag was needed for this — that field already exists and already means exactly "the tech responsible for this job's follow-ups," so gating off it directly is simpler than introducing a redundant per-company role flag.

## Dispatch board: status color as the block, tech as an animated LED

- **Block fill color** = the work order's actual `status` (Scheduled / Extraction Active / Completed / No Charge / Cancelled / Invoiced) — lets office see at a glance what's actually done vs. still open, without a job disappearing off the board when it's finished.
- **One dot per assigned tech** (unifies with the earlier "which tech is behind on a shared job" idea), built as an actual LED rather than a fade — dark/off when no visit has been logged, genuinely glowing (brightened fill + box-shadow halo) when lit, since a fade-to-transparent just makes the dot vanish rather than read as "off." Tech identity moved to a thin ring around the dot (`--tech-ring`) so the fill itself is free to mean status, not identity:
  - No visit logged yet → dark/off, identity ring only
  - On The Way → solid blue glow, no pulse
  - Started → red, pulsing dark→bright every ~1.7s
  - Completed → green, pulsing dark→bright every ~0.85s with a bigger glow — deliberately the loudest of the three (brightest, fastest, biggest halo), since that's the one that needs to catch office's eye and get invoiced
  - Cancelled → flat grey, no pulse

  Revised after first real use: the original version only animated `opacity` on top of the tech's own color, which (a) never actually showed red/green at all — just the assigned tech's own arbitrary color fading in and out — and (b) was hard to read for anyone with red/green color vision deficiency, since the only differentiator was hue at full-vs-faded opacity. Brightness/glow-based pulsing plus a real dark "off" state fixes both: status is now legible from animation intensity and speed alone, hue is a second cue rather than the only one, and the tech-identity ring keeps "whose job is this" from being lost.
- **Refresh cadence**: the dispatch board has no live-refresh today — it only reloads after the office's own drag/resize action. A tech's phone-side status tap wouldn't appear until something reloads it. Added a **60-second background poll** rather than push/websockets — explicitly agreed this doesn't need to be instant, and a slow poll is a small addition with no new infrastructure.
- **LEDs turn off once the invoice is actually sent** — `invoice_versions.sent_at` on the work order's `current_version_id`, which is a distinct event from just creating the invoice (creating one only moves `work_orders.status` to `Invoiced`; sending is its own transition, with its own timestamp). Once sent, `_dispatch_board_data` reports an empty visit-status map for that block regardless of what's actually in the log, so every tech's dot goes dark — the loop is closed, so a still-flashing LED would only be noise from that point on.

## What's explicitly deferred to the native mobile app

GPS-driven automation — auto-setting "On The Way" when a tech taps a maps link for navigation, a 15-minute arrival nudge to set "Started," a departure nudge to close out the visit — cannot be built as a web page. This isn't a sequencing preference, it's a platform floor: continuous background location and arrival/departure detection require native OS capability (the same reason the after-hours capture addendum specifies iOS `CLVisit` visit-monitoring rather than continuous GPS or geofencing — see `FIELDKIT_DESIGN_ADDENDUM_mobile-afterhours-extraction.md`). The same technique generalizes to daily status nudges once the native app exists; nothing about this design needs to be re-thought when it does.

What's being built now instead, so the office side is ready to receive that input the moment the native app ships:
- The full data model and permission logic above.
- The dispatch board's status-color + per-tech LED rendering.
- A phone-usable web page exposing the same visit-status and extraction actions as simple buttons, scoped to "my assigned jobs" — **this turned out to already exist** as `/myday` (directive §5.4, predating this work), gated to `role == 'technician'` and, at the time, writing its three statuses directly onto `work_orders.status`. That's exactly the design this addendum moves away from, so `/myday` was retrofitted rather than left alongside a second, competing page: it now posts to the shared `workorder_visit_status` route (visit log, not `work_orders.status`), gained the Extraction Follow-Ups section, and its permission check and nav link were broadened from "role is literally technician" to "is a field tech" (`session.is_field_tech`, set at login) — the same is_field_tech-over-role fix already applied elsewhere in this codebase (see `_company_techs`), which My Day had never picked up. A first pass at this work built a brand-new `/my-jobs` page instead of finding `/myday` — retired once the duplication was caught. The underlying `workorder_visit_status` route still returns JSON when called without `return_to`, so a real API for the native app is a thin addition later, not a rebuild.

## Extraction daily log: notes now actually save

`extraction_log()` accepts and stores a `notes` field on each daily status entry — the column already existed on `extraction_daily_log`; the route just never read it from the request. Fixed as part of this work since the follow-up tech's whole workflow depends on being able to say *why* a job needs more time, not just tick a canned status.

### Damage-area reporting (native app, not this pass)

Filed for whenever the native app build reaches this: a two-list multi-select — **Where** (Kitchen, Living Room, Bedroom, Bathroom, Guest/Ensuite Bath, Hallway, Closet, Whole Unit, **All Floors**, **All Ceilings**) crossed with **What** (Wall, Ceiling, Floor, Baseboard, Cabinetry) — composed into a readable notes sentence the same way `auto_description` is already assembled client-side from checkboxes elsewhere on the work order form. Not a nested checkbox tree per area (unwieldy on a phone); flat tag combinations instead, with the two "All ___" shortcuts covering the common case of "the whole floor is wet" without ticking every room.

---

## Dependencies & cross-references
- **Extraction Queue** (`FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` §8) — visit status sits alongside it, doesn't replace any of its mechanics (Retrieve, escalation, daily log).
- **Mobile after-hours extraction addendum** — same visit-monitoring technique this note defers the GPS-nudge half to.
- **Per-company dispatch settings** (migration 028, `user_company_dispatch`) — considered as a home for a new "designated extraction tech" flag; not needed, since `followup_tech_username` already carries that meaning per-job.

---

*Drafted: September 2026*
