# FieldKit — Design Doc Addendum
*Session: October 2026 | Topic: Sales Tip Location Assistant (mobile app)*
*Phase 6 (Mobile) design note. Written to match FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md conventions.*
*Status: **not built**. Requested by Chris on 2026-10-20, to be picked up when mobile app development starts.
Builds on sales tips (migration 039, D-115), which are live on the web today.*

---

## The problem this solves

Sales tips let anyone, usually a tech in the field, tell the salesman about a
property worth visiting: "they're doing a rehab with cabinet work." The hard part
is saying **which property**. A tech standing in a parking lot often doesn't know
the complex's real name or address, and may be looking at the building across the
street, not the one on their work order.

Today (web, option b), the tip form takes the job's customer pre-filled, or a
free-text location ("the complex across from the Elm St job"). The salesman ties
the tip to a real property when he logs the visit. That works, but the salesman
has to work out where the tech meant, and nothing notices when the "new" property
is already a customer or prospect.

## What Chris asked for (2026-10-20)

> When we do begin work on the mobile app, it should have an assistant to help
> identify locations using Google Maps to get property information when a tech or
> anyone is creating a tip, and by pulling address and property information fresh
> from the internet or if a matching address is in the system for that location
> then tie it to the customer automatically.

So there are two jobs:
1. **Identify the place:** use the phone's location and Google Maps to find the
   actual property, with its real name, address and details, fetched fresh.
2. **Match it to FieldKit:** if that address is already a customer or prospect,
   tie the tip to it automatically. If not, carry the place details along so the
   salesman can create the prospect without retyping anything.

---

## Core principle: the tech confirms, never types

The assistant proposes; the tech taps to confirm. Nothing gets tied silently on a
guess, the same "phone proposes, office commits" principle as the after-hours
extraction addendum. A wrong automatic match is worse than no match, because it
sends the salesman to the wrong building.

## The flow on the phone

1. Tech taps **Sales tip** (on a job, or from the home screen).
2. The app takes **one location fix**, in the foreground, at that moment only. It
   doesn't track the tech; this is a single reading, the same stance as the
   after-hours addendum's "visit monitoring, not GPS tracking". It needs
   "while using the app" location permission and nothing more.
3. The assistant shows **nearby properties**, closest first, from Google Places
   Nearby Search (filtered to apartment complexes, commercial buildings and similar
   place types). Each shows name, address and distance, plus a photo if one is
   available. The job's own property is pinned at the top when the tip started from
   a job.
   - **"Not listed"** opens a search box using Places Autocomplete, which also covers
     "the building across the street" when it's out of GPS range.
   - **"Use my exact spot"** is for when no listed place is right (e.g. a
     construction site with no name yet). It saves the reverse-geocoded address and
     coordinates only.
4. Tech taps the right place. The app fetches **Place Details** (name, formatted
   address, phone, website, coordinates, Google place id).
5. FieldKit checks for a **match** (below) and shows the result plainly:
   - "✓ Already a customer: Brookside Apartments" (tied; tap to undo)
   - "○ Already a prospect: Brookside Apartments" (tied; tap to undo)
   - "Possible match: Brookside Apts on Elm St — same place?" (yes/no)
   - "New to FieldKit": the tip carries the Google details
6. Tech says what they saw (voice dictation is fine on a phone) and sends. Email
   and follow-up lists work exactly as on the web today.

When the salesman logs the visit for a "new to FieldKit" tip, the wizard's step 1
offers **"Create prospect from this place"**, pre-filled with name, address, city,
state, ZIP, phone, website and coordinates. Nothing gets retyped.

## Matching to existing customers and prospects

The match runs **on the server**, against the company's own database (the tip
belongs to one company; DB-per-company rules unchanged). It checks in order and
stops at the first confident hit:

1. **Google place id**: exact, if we stored it before (see schema). This is the
   most reliable once it's populated.
2. **Normalized address**: lowercase, punctuation and spaces stripped, the same
   comparison `customer_dupe_check()` in `app.py` already uses for duplicate-customer
   detection (`lower(regexp_replace(address, '[^a-zA-Z0-9]', '', 'g'))`). Compared
   against `customers.address`, `service_locations.address` and
   `sales_prospects.address`. Normalize common suffixes first (Street/St,
   Drive/Dr, Suite/Ste/#), because Google formats addresses differently from how
   the office typed them.
3. **Proximity**: within ~75 m of a prospect's stored coordinates.
   `sales_prospects` already has `latitude`/`longitude` (migration 025), but
   `customers` and `service_locations` **don't**. See open questions.
4. **Name similarity**, as a *suggestion only*, never an automatic tie:
   "Brookside Apts" vs "Brookside Apartments". It shows as "Possible match", and the
   tech decides.

Address, place-id and proximity hits auto-tie (with undo). A name-only hit just
suggests.

**Cross-company:** the property may already be *another* company's customer, e.g.
a Kleanit property that Get a Grip has never served. That's worth knowing but must
not cross-write. Reuse the read-only cross-company check that `/sales-overview`'s
"Customer Check" already does, and show it as information: "Also a Kleanit
Charlotte customer".

## Schema additions (when built)

All on `sales_tips`, nullable, added by a new migration to all four DBs. The
existing table doesn't change shape:

| Column | Purpose |
|---|---|
| `place_id` | Google place id, the stable key for future matches |
| `place_name`, `place_address` | What Google returned, kept separate from `location_text` (what a person typed) |
| `place_phone`, `place_website` | Pre-fill for "create prospect from this place" |
| `latitude`, `longitude` | Where the tip is about (the chosen place), not where the tech stood |
| `match_method` | `place_id` / `address` / `proximity` / `manual` / `none`, so wrong auto-ties can be audited and the rules tuned |

Consider also `sales_prospects.google_place_id` (set when a prospect is created
from a place), so the next tip about that building matches on step 1.

## Google Maps Platform: practical notes

- **APIs:** Places API (New) for Nearby Search, Autocomplete and Place Details;
  Geocoding API for reverse geocoding "use my exact spot".
- **Route the calls through the FieldKit server**, not straight from the app. The
  API key stays on the server, calls can be logged and rate-limited, and matching
  happens in the same round trip. The production server already reaches the
  internet for outbound requests (Resend email).
- **Cost:** billed per request; use field masks so each call only pays for the
  fields it needs. At FieldKit's volume (tips are occasional, not per job) this
  should be small, but set a billing budget and alert in the Google Cloud console
  on day one.
- **Terms of service, check at build time:** Google restricts how long most Places
  content can be stored. Place ids can be kept, but other fields (and coordinates)
  have caching limits. Data a person **confirms** and saves as a FieldKit record,
  like a prospect's address, is ours. Raw Google responses shouldn't be stored as
  a long-term cache. Read the current Maps Platform terms before deciding what
  `place_*` columns keep and for how long.
- The web sales wizard's address autocomplete uses **Photon** (free, no key) via
  the `address_lookup` macro in `_macros.html`. That is the existing swap point if
  the web side should move to Google too; the mobile app can use Google from the
  start.

## About the "assistant"

The core of the assistant is the guided pick-a-place flow above. An optional
extra: let the tech describe the place in plain words ("the new build behind the
Harris Teeter on Providence") and have an AI model turn that into a Places search
query, alongside the GPS list. Worth trying once the basic flow is in hands, not
needed for v1.

## Possible web stopgap (not requested, noted for completeness)

Mobile browsers can give a one-shot location (`navigator.geolocation`) too, so a
lighter version of steps 2–5 could be added to today's web tip form before the app
exists. Chris chose to wait for the mobile app, so this is only noted in case the
free-text tips prove hard for the salesman in practice.

## Open questions for when this is picked up

1. Backfill coordinates for existing **customers / service locations** so proximity
   matching works against them? A one-off geocode of ~5,300 active customers across
   the four companies (as of 2026-10-19) plus their service locations, which has a
   cost and its own ToS limits on storing coordinates.
   Without it, customer matching relies on address normalization alone.
2. Should a tip about another company's customer be **routed to that company**
   instead (e.g. a GAG tech spots a Kleanit customer's rehab)?
3. The match radius (75 m is a starting guess; large complexes may need more).
4. Should techs also see **"already tipped"** (an open tip on this place) to avoid
   duplicates?

## Acceptance criteria

- A tech can send a tip for the property they're standing at in three taps plus
  the description, without typing a name or address.
- A tip about an existing customer or prospect ties to it automatically, and the
  tech sees which one and can undo.
- A tip about a new property arrives with name, address and phone filled in, and
  the salesman can create the prospect from it in one tap.
- No location is collected except the single reading when a tip is made.
- Every automatic tie records how it was matched (`match_method`).

## Dependencies & cross-references

- **Sales tips** (migration 039, D-115): the table and flow this extends.
- **Mobile after-hours extraction addendum**: the same one-shot,
  no-tracking location principle.
- **Visit-status tracking addendum**: the other GPS features deferred to the
  native app.
- `customer_dupe_check()` in `app.py`: the normalized-address SQL to reuse.
- `docs/MOBILE-APP-BACKLOG.md`: the index of everything waiting on the mobile app.

---

*Drafted: October 20, 2026*
