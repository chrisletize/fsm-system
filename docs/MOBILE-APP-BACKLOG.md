# FieldKit Mobile App — Backlog Index

*Index of ideas deferred to the mobile app. Created 2026-10-20. For the consolidated
plan and discussion agenda, start with `MOBILE-APP-PLAN.md`.*

Ideas meant for the mobile app (Phase 6) have been filed in several docs over
time. This page lists every one of them in one place, with a pointer to where
the detail lives. **When you defer something to the mobile app, add a line here**,
or it will be lost in whichever doc it was written in.

The web app already has stand-ins for several of these (noted below). Those
pages show the workflow the app should replace, and their routes and data model
are what the app should talk to.

## Platform and foundation

| Item | Detail in | Notes |
|---|---|---|
| PWA first, then React Native (iOS + Android, unlisted) | `FIELDKIT_TASKS.md` (Mobile App), `PROJECT-KNOWLEDGE/FUTURE-PLANS.md` (Phase 6) | Target was Q1 2027 in FUTURE-PLANS |
| Offline-first architecture | `PROJECT-KNOWLEDGE/PHASE-1-PLANNING.md` (Offline-First Mobile App) | |
| Job list + detail, status updates, clock in/out, job notes | `FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` (Phase 6) | Web stand-in: `/<company>/myday` |
| Before/after photo upload in 2–5 sec (ServiceFusion ~30 sec) | `FIELDKIT_PROJECT_REFERENCE.md`, `FIELDKIT_TASKS.md` | |

## Features designed and waiting on the app

| Item | Detail in | Web stand-in today |
|---|---|---|
| **After-hours water extraction capture** (one button, iOS visit monitoring, retroactive draft WO for office review) | `FIELDKIT_DESIGN_ADDENDUM_mobile-afterhours-extraction.md` | None; the office reconstructs it next morning |
| **GPS visit-status automation**: auto "On The Way" from the maps link, arrival nudge for "Started", departure nudge to close the visit | `FIELDKIT_DESIGN_ADDENDUM_visit-status-tracking.md` ("What's explicitly deferred to the native mobile app") | Manual buttons on My Day; data model live (migration 029) |
| **Damage-area reporting**: Where × What multi-select composed into notes | `FIELDKIT_DESIGN_ADDENDUM_visit-status-tracking.md` ("Damage-area reporting") | Free-text extraction notes |
| **Sales map, app edition**: a richer, prettier native version of the web sales map (Chris, 2026-10-27) | `MOBILE-APP-PLAN.md` §5 H, D-118 | Web `/sales-map` |
| **Near me**: closest properties to his current location, with distance and last visit (Chris, 2026-10-27) | `MOBILE-APP-PLAN.md` §5 H | — (web map has "my location" only) |
| **Plan a route**: tick pins, open as a multi-stop route in Apple/Google Maps (Chris, 2026-10-27) | `MOBILE-APP-PLAN.md` §5 H | — |
| **Sales tip location assistant**: Google Maps finds the property, auto-ties to an existing customer/prospect by address, pre-fills new prospects (Chris, 2026-10-20) | `FIELDKIT_DESIGN_ADDENDUM_sales-tip-location-assistant.md` | Tip form with free-text location (migration 039, D-115) |
| GPS reminders with a 10-minute grace window | `FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` (Phase 6) | |
| Extraction queue mobile view | `FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` (Phase 6) | Extraction section of My Day |

## ServiceFusion app reference

Chris shared screenshots of the ServiceFusion mobile app (2026-10-20, three batches)
as a feature reference. Notes, FieldKit equivalents, and decisions they raise are in
`sf-reference/SF_MOBILE_APP_ANALYSIS.md`; images are in
`sf-reference/mobile-app/screenshots/` (30 screens, complete). Notable items: a
company reference library (Get a Grip's colour charts and mixing instructions), and a
live team map, which raises the location-visibility decision below.

**Everything here, plus the SF reference, is merged into `MOBILE-APP-PLAN.md`, the
starting point for the mobile design discussion.**

## Shared principles across these designs

- **No continuous GPS stream, no geofencing.** Background iOS visit monitoring
  (`CLVisit`) for arrival/departure-driven features, which is fuzzy by minutes and
  never bills on its own; a single foreground reading for one-off actions like a
  sales tip. Disclosed honestly to techs. Why: battery, privacy, App Review, and
  iOS's ~20-region geofence cap (detail in the after-hours addendum). How much
  managers can see is an open decision (`MOBILE-APP-PLAN.md` §9 A1).
- **The phone proposes, the office (or the tech) confirms.** Nothing captured
  automatically becomes a billable record or a silent property match without a
  person confirming it.
- The app talks to the **same per-company databases and routes** as the web app.
  No separate backend, and no shared `company_id` table.
