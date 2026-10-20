# FieldKit Mobile App — Consolidated Plan (pre-build)

*Started 2026-10-20. **Status: planning, nothing built.** This is the one place that
gathers everything known about the mobile app, ready for the long design discussion
Chris wants before any building starts. It's a working draft: decisions get recorded
here as they're made (each question in §9 gets an answer and a D-### number).*

**How this relates to the other docs**
- `MOBILE-APP-BACKLOG.md`: the index of every individual idea deferred to the app,
  with pointers. This plan merges all of them.
- `sf-reference/SF_MOBILE_APP_ANALYSIS.md` + `sf-reference/mobile-app/screenshots/`
  (30 screens): what ServiceFusion's app does, screen by screen.
- The design addenda for individual features (after-hours extraction, visit status,
  sales-tip location assistant): the detail behind specific rows below.

---

## 1. What we're merging

| Source | Date | What it contributes |
|---|---|---|
| `PROJECT-KNOWLEDGE/PHASE-1-PLANNING.md` (Mobile App — Technicians / Managers, Offline-First) | Jan 2026 | The original wish list: fast photos, payments in field, site maps, document library, offline-first, manager GPS + drag-drop reassign |
| `PROJECT-KNOWLEDGE/FUTURE-PLANS.md` (Phase 6) | Feb 2026 | Push notifications, voice notes, barcode scanning for equipment, "techs prefer it to ServiceFusion mobile" as the success bar |
| `FIELDKIT_COMPLETE_SYSTEM_DESIGN_v2.md` (Phase 6) | Jul 2026 | GPS reminders (10-min grace), clock in/out, extraction queue mobile view |
| `FIELDKIT_DESIGN_ADDENDUM_mobile-afterhours-extraction.md` | Jun–Jul 2026 | After-hours capture, iOS visit monitoring, "phone proposes, office commits" |
| `FIELDKIT_DESIGN_ADDENDUM_visit-status-tracking.md` | Sep 2026 | Visit status data model (live), GPS automation and damage-area reporting deferred to native |
| `FIELDKIT_DESIGN_ADDENDUM_sales-tip-location-assistant.md` | Oct 2026 | Google Maps place lookup + auto-tie for sales tips |
| `sf-reference/SF_MOBILE_APP_ANALYSIS.md` | Oct 2026 | 30 ServiceFusion screens: what to keep, improve or skip |
| What's live on the web today | — | My Day (visit status, extraction follow-ups, dry confirmation, per-piece retrieval), release forms, sales tips, sales visit wizard + card photos: the workflows and data the app plugs into |

---

## 2. Principles (proposed; confirm in the discussion)

1. **Techs first.** The bar from FUTURE-PLANS: techs prefer it to ServiceFusion's app.
   Every screen is designed for one hand, gloves, bad signal and a basement.
2. **Works offline.** Today's jobs plus the next two days cached; actions and photos
   queue and sync later (PHASE-1-PLANNING). An offline indicator is always visible
   (SF shows "Online" in the header; keep that).
3. **The phone proposes, a person confirms.** Nothing captured automatically
   (location, after-hours work, a property match) becomes a billable record or a
   silent link without someone confirming it.
4. **Same data, same rules as the web.** The app talks to the same four company
   databases through the same server; no second backend and no `company_id`. Role
   rules carry over: techs read-only on customers (D-091), pricing/invoicing
   office-side, visit status separate from job status (D-100).
5. **Location: no continuous GPS stream, no geofencing.** The after-hours addendum
   settled the mechanism: iOS **visit monitoring** (`CLVisit`), where iOS itself
   reports arrival/departure events at low power. It needs "Always" location
   permission, its times are fuzzy by several minutes (so it never bills on its own),
   and it must be disclosed honestly to techs as "saves you the paperwork, not
   watching you". Geofencing is out because iOS caps it at ~20 regions per app,
   against hundreds of properties. One-off actions like a sales tip take a single
   foreground reading. ⚠️ How much of this managers get to *see* (SF's live Team
   Locations map, PHASE-1's "GPS locations of techs") is the first decision on the
   agenda (§9 A1).
6. **Don't copy SF's workarounds.** No $0.00 line items as descriptions, no flags
   typed into customer names, no single status list mixing job and visit.

---

## 3. Who uses it

| User | What they need from the app |
|---|---|
| **Field tech** (role `technician`, or anyone `is_field_tech`) | Their jobs, navigation, status taps, photos, notes, extraction follow-ups, sales tips, reference docs |
| **Follow-up tech** (extraction, non-GAG companies) | Daily check-ins, dry confirmation, per-piece pickup, which may be on jobs they weren't dispatched to (`followup_tech_username`) |
| **Salesperson** (Chris O, role `salesperson`, sales-only lockdown D-101) | Today he uses the web Sales pages on a tablet. Open question: does the app include Sales, or does he stay on the web? (§9 F1) |
| **Managers / admins** (Chris, Michele, Walter…) | "Everyone's jobs", reassigning, where the team is (PHASE-1-PLANNING "different interface than tech view") |
| **Multi-company users** (e.g. braulio o: GAG + CTS) | A company switcher; jobs from each company kept separate |

---

## 4. Platform and infrastructure

### 4.1 Native vs PWA
FUTURE-PLANS said "PWA first, then native if needed". Since then, several designed
features **require native** capability:
- After-hours capture via iOS visit monitoring (CLVisit): background, native only
- Arrival/departure nudges and auto "On The Way" (visit-status addendum): native only
- Reliable background photo upload queues: much better native
- Push notifications: possible in a PWA on iOS, but limited

So the decision is really **which native approach**:
- **React Native / Expo**: one codebase for iOS and Android, JavaScript like the
  web front end, a big ecosystem. Native modules for CLVisit/geofencing exist.
- **Swift (iOS only)**: best access to CLVisit and background tasks, but iOS only and
  a different language from everything else in FieldKit.
- Recommendation to discuss: **React Native (Expo)** unless every tech is on
  iPhone and staying there, in which case Swift is a fair choice.

### 4.2 Building and distributing (the Mac mini)
- iOS builds need macOS and Xcode. **Chris now has a Mac mini on the Tailscale
  network** for this. It can host Xcode, the iOS simulator, signing certificates, and
  build/upload to TestFlight. (Expo can also build in the cloud with EAS; the Mac
  mini keeps it in-house.)
- **Apple Developer Program** membership (business account, $99/yr) is needed for
  TestFlight and distribution.
- Distribution options for a private company app: **TestFlight** (simplest, builds
  expire after 90 days), **Unlisted App Store** app (the earlier plan said
  "unlisted"), or **Custom Apps via Apple Business Manager**. Decide in §9 B3.
- **Android**: only if any tech uses Android. Ask the crews (§9 B2).
- Questions for the Mac mini session: macOS/Xcode version, whether it's always on,
  Tailscale reachability from the dev workflow, and backing up the signing
  certificates (losing them is painful).

### 4.3 The server side the app needs
FieldKit today is **server-rendered Flask with session cookies**. Only ~30 small JSON
endpoints exist, all built for web pages. The app needs:
- **A versioned JSON API** (e.g. `/api/v1/<company>/…`) in the same Flask app,
  reusing the same helpers and permission rules. No new database or second service.
- **Token auth for devices**: login issues a per-device token (revocable, so a lost
  phone can be cut off), still reading `fieldkit_getagrip.users` as the canonical login
  (D-003). New table: `device_sessions` (or `api_tokens`).
- **Push notifications**: APNs (Apple) and/or FCM (Android). The server already
  reaches the internet outbound (Resend), so it can send them. New table:
  `device_push_tokens`.
- **Photo storage**: the same `uploads/` folder pattern as release forms and card
  photos (outside git, included in the nightly backup, D-113). Plan for growth:
  thousands of photos a year. Store compressed originals plus thumbnails.
- **Sync design**: the app works offline, so every write needs a client-generated id
  (to make retries safe, the same idea as `payment_webhook_events` in the card-payments
  addendum) and a rule for conflicts, e.g. the office changed the job while the tech
  was offline.

### 4.4 Reaching the server from the field
- The web app is served at `https://fieldkit.cletize.com` (`APP_BASE_URL`) through the
  NPM reverse proxy on ubuntu-services into the DMZ. **Confirm** this is fully set up
  and reachable from cellular (FIELDKIT_PROJECT_REFERENCE still says the proxy host
  was "NOT yet created"; it's evidently working for Chris O in the field, but the doc
  is stale).
- The API is internet-facing, so it needs TLS (have it), rate limiting on login,
  token revocation, and no session cookies for the app.
- PHASE-1-PLANNING's reliability goals (backup server, multiple endpoints, read-only
  mode from cache) are a later phase; offline-first covers most of the day-to-day risk.

---

## 5. Feature catalogue

**Phase key:** **v1** = first release techs use daily · **v2** = next · **later** = after
that · **decide** = needs Chris · **skip** = deliberately not building.
"SF #" = screenshot number in `sf-reference/mobile-app/screenshots/`.

### A. Sign-in, home, navigation
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Sign in, stay signed in, sign out | SF #01 | Web login | v1 | Per-device token (§4.3) |
| Company switcher | multi-company users | Web home page / switcher | v1 | Only if the user has more than one company |
| Online/Offline indicator + manual refresh | SF #01, #17 | — | v1 | Always visible |
| Home: a few big tiles, not eight | SF #01 | — | v1 | Proposed: My Work · Sales tip · Reference docs · (Extraction, non-GAG) · (Team, managers) |
| My Profile | SF #01 | — | later | Name/phone/photo; password reset already exists by email |

### B. My Work (job list)
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Past / Current / Future tabs | SF #18 | My Day (date picker) | v1 | "Current" = today plus anything still open |
| Job card: customer, unit/site line, arrival window, duration, address, job # | SF #18 | My Day lacks job # and duration | v1 | |
| Status icon per job = **my visit status** | SF #18, D-100 | Visit status (migration 029) | v1 | Job status shown secondary |
| Badges: callback, delinquent account, new customer, release on file | live web badges | Dispatch/WO pages | v1 | Replaces SF's "OCC ******occ release form in gag office" text |
| Calendar view | SF #18 (calendar icon) | Dispatch board (office) | v2 | |
| Search jobs | SF #18 | WO list search | v2 | |
| "Everyone's jobs" for managers | SF #18 (admin sees all), PHASE-1 | Dispatch board | decide | §9 A3 |

### C. Job detail
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Header, address, **Navigate** (Apple/Google Maps) | SF #21, PHASE-1 | My Day "Map →" link | v1 | |
| Description / work site / line items (read) | SF #21, #24 | WO detail | v1 | Uses `work_site_label` + auto-description, never $0 lines |
| Notes for techs (read) + **add job notes** | SF #21 | `notes_for_techs` (office-written) | v1 | New: tech-written notes need a home (notes table or WO notes) |
| Completion notes | SF #21 | — | v1 | Could be the note the tech writes when tapping Completed |
| Contact phone (tap to call) | — | My Day shows it | v1 | |
| Custom fields | SF #21 | Customer custom fields only | skip | Unused in SF ("Set Custom Fields…") |
| Additional visits | SF #21 | Follow-up WOs / extraction daily log | v2 | |
| Customer equipment (HVAC etc.) | SF #23 | — | skip | Empty in SF; not FieldKit's business |
| Tasks tab | SF #21 | Internal tasks | decide | §9 E3 |

### D. Status and location
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| On The Way / Started / Completed / Cancelled buttons | SF #26, D-100 | Live on My Day | v1 | Never changes job status. "Started" vs SF's "On Site" (§9 E4) |
| Auto "On The Way" when tapping Navigate | visit-status addendum | — | v2 | Native |
| Arrival nudge ("you're at X, tap Started?") and departure nudge | visit-status addendum, design v2 (10-min grace) | — | v2 | iOS visit monitoring (`CLVisit`), not geofencing (20-region cap). Fuzzy by minutes, so a nudge rather than an automatic status |
| Team locations for managers | SF #16, PHASE-1 | — | decide | §9 A1: live tracking, vs last known from status taps and visit events |

### E. Photos, signatures, documents, voice
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| **Before/after photos, 2–5 seconds** | PHASE-1, SF #20 | — | v1 | The headline feature. Compress on the phone, upload in the background, queue offline |
| Job documents (view/upload) | SF #22 | WO attachments (release forms) | v1 view / v2 upload | |
| **Signature capture** | SF #21 ("sign") | — | decide | Big idea: sign the **occupied release form on the phone**, replacing paper (D-102 flow). Or customer sign-off on completion. §9 E1 |
| Voice notes / dictation | FUTURE-PLANS | — | v2 | Dictation into text fields is free on iOS from day one |
| Damage-area reporting (Where × What) | visit-status addendum | — | v2 | Extraction notes |

### F. Water extraction (Kleanit Charlotte, CTS, Kleanit SF; never Get a Grip, D-071)
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Daily follow-up check-ins + notes | live My Day | Live | v1 | |
| Dry confirmation gating final pickup | D-103 | Live | v1 | |
| Per-piece retrieval | D-103 | Live | v1 | |
| **Scan equipment units** (QR/barcode on each dehu/fan) at deploy and pickup | FUTURE-PLANS "barcode scanning (equipment tracking)", SF #06 scanner | `equipment_units` registry | v2 | This is where barcode scanning pays off, not SF's catalog |
| After-hours capture, one button + backstop | after-hours addendum | — | v2 | Native visit monitoring; drafts to office review queue |
| Extraction queue mobile view | design v2 | Web `/extraction` | v2 | For managers |

### G. Customers and properties
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Customer view, read-only, own jobs' customers only | SF #19, #29, D-091 | Live on web | v1 | No customer editing by techs; SF's edit screen is skipped |
| Structured badges instead of name flags (OPS portal, billing needed) | SF #19 | Portals, billing flags exist | v1 | Depends on the name-prefix cleanup (CURRENT-STATUS 6a) |
| **Site maps** (apartment complex layouts) | PHASE-1 | — | v2 | Per-property PDF/image: "which building is 21-102?" |

### H. Sales
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| **Send a sales tip** (from a job or anywhere) | D-115 | Live on web | v1 | Free text to start |
| Sales tip location assistant (Google Maps, auto-tie) | tip addendum | — | v2 | Chris, 2026-10-20 |
| Salesperson's full Sales module (visit wizard, card photos, follow-ups, intake wizard) | live web | Live on tablet web | decide | §9 F1: keep on web, or bring into the app |

### I. Manager / office-lite
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| All techs' jobs, by tech | PHASE-1, SF #18 | Dispatch board | v2 | |
| Reassign / reschedule (drag-drop) | PHASE-1 | Dispatch board (web, smooth per D-098) | later | The web board may be enough on a tablet |
| Create job / estimate from the phone | SF #14, #12, #15 | Web forms | decide | §9 C2 |
| Internal/calendar tasks with types (Call/Email/Misc) | SF #10 | Internal tasks (no types) | decide | §9 E3 |

### J. Billing in the field
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Show estimated charges (read) | SF #24 | Line items + tax engine (matches SF: Mecklenburg 8.25% → $27.64 on $335) | v1 | Read-only |
| Techs add/price line items, add-ons | SF #24, PHASE-1 "modify invoices" | Office-side | decide | §9 C1. Invoices harden/freeze totals; field edits would need office review |
| Collect payment / send a pay link | PHASE-1, card-payments addendum (D-104) | Designed, processor not chosen | later | Waits on the processor choice |
| Apply deposit, email/print job | SF #25 | Web | skip for techs | Office work |

### K. Time and expenses
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Clock in/out, time log | SF #01, design v2 | — | decide | §9 D1. SF's last clock-out was May 2024 (looks unused); touches payroll |
| Add time / drive & labor charges | SF #24 | — | decide | Tied to D1 |
| Add expense (billable) | SF #24 | — | skip unless asked | |

### L. Reference library
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| **Company documents** (colour charts, mixing instructions, manuals, cheat sheets), available offline | SF #03 (GAG's 4 PDFs), PHASE-1 "document library" | — | v1 | Office uploads per company. Could ship on the web first (§9 G1) |
| My Files / Shared With Me | SF #02, #04 | — | skip | Empty in SF |

### M. Notifications
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Push: new job assigned, job moved/changed/cancelled | FUTURE-PLANS | — | v1 | The single biggest "better than SF" win for techs |
| Push: sales tip for the salesperson | D-115 | Email today | v2 | |
| Push: extraction reminders, after-hours backstop | after-hours addendum | — | v2 | |

### N. Catalog and inventory
| Feature | Source | FieldKit today | Phase | Notes |
|---|---|---|---|---|
| Browse catalog (read-only) | SF #06–#08 | Web catalog | later | Only useful if techs price work (C1) |
| Create catalog items from the phone | SF #06 "Create" | — | skip | Junk "$0.00" items in SF came from this |
| Stock inventory levels | SF #09 | — | skip | Empty in SF |

---

## 6. What we're deliberately not copying from ServiceFusion
- One mixed status list (job and visit). FieldKit keeps them separate (D-100).
- $0.00 line items used as descriptions ("Unit # 21-102 vacant"). Use `work_site_label`.
- Flags typed into customer names. Use structured fields and badges.
- Techs editing customer records and billing contacts (SF #29 shows an AvidBill AP
  inbox stored as a contact email).
- Catalog creation from the phone, empty inventory, empty file folders, unused custom fields.

## 7. Proposed v1 (a starting point for the discussion, not a decision)
A release techs would choose over ServiceFusion on day one:
1. Sign in, company switcher, offline indicator; today + 2 days cached
2. My Work (past/current/future), job cards with badges
3. Job detail: navigate, call, notes for techs, line items (read), release-form status
4. Visit status buttons (same as My Day)
5. **Fast before/after photos** with an offline queue
6. Tech job notes and completion notes (with iOS dictation)
7. Extraction follow-ups: check-in, dry confirmation, per-piece pickup (non-GAG)
8. Send a sales tip
9. Reference library (offline)
10. Push notifications for job assigned/changed

Server work for v1: the JSON API, device tokens, push, photo storage, sync ids.

**v2 candidates:** arrival/departure nudges and auto "On The Way", after-hours capture,
equipment QR scanning, sales tip location assistant, signatures/digital release
forms, site maps, damage-area reporting, manager views, voice notes.

## 8. New data the app will need (for planning migrations)
- `device_sessions` / `api_tokens`: per-device login, revocable
- `device_push_tokens`: APNs/FCM tokens per user and device
- `job_photos` (or generalise `work_order_attachments`): before/after tag, thumbnail,
  taken_at, uploaded_by, client-generated id for safe retries
- Tech-written job notes / completion notes: a place for them (decide: new table vs
  WO notes)
- `company_documents`: the reference library, per company
- Site maps per customer/service location
- Signatures (if E1 is a go): signer name, image, signed_at, linked document
- `sales_tips` place columns: already specified in the tip addendum
- Equipment QR codes on `equipment_units` (if F scanning is a go)

All migrations to all four databases, as always.

## 9. Discussion agenda (every open question in one list)

**A. Philosophy and scope**
1. **Tech location:** the app will already use background visit monitoring for
   after-hours capture and arrival nudges. Do managers see a **live** team map (SF #16,
   PHASE-1's "GPS locations of techs", which means continuous tracking), or only
   **last known position** from status taps and visit events? And during work hours
   only, or always? The answer sets the permission prompt, the disclosure to techs,
   and App Review.
2. Is the proposed v1 (§7) the right first release? What's missing or not needed?
3. Do managers get an "everyone's jobs" view in the app, or stay on the web dispatch board?

**B. Platform**
1. React Native (Expo) or Swift?
2. Any techs on Android?
3. Distribution: TestFlight, unlisted App Store, or Apple Business Manager custom app?
   Apple Developer account in which company's name?
4. Mac mini setup: always on? Xcode version? Where do signing certificates get backed up?

**C. Field authority**
1. Can techs add or price line items in the field (SF and PHASE-1 say yes; FieldKit
   today says office only)? If yes, does the office review them before invoicing?
2. Can techs create jobs or estimates from the phone?
3. Collect payments in the field: still wanted? (Waits on the processor choice, D-104.)

**D. Time**
1. Clock in/out and time logs: wanted? Who uses the data (payroll, job costing)?

**E. Field details**
1. Signature capture: digital occupied-release forms on the phone? Customer sign-off?
2. Photo rules: before/after required on certain job types? How long are photos kept?
3. Tasks: does a tech need a task list, and do tasks need types (Call/Email/Misc)?
4. "Started" or "On Site" as the visit-status word?
5. Damage-area lists (Where × What): are the lists in the visit-status addendum right?

**F. Sales**
1. Does Chris O's Sales module move into the app, or stay on the tablet web?
2. When to build the tip location assistant (v1 or v2)?

**G. Content and data**
1. Reference library: build on the web now, ahead of the app?
2. Site maps: who has them, and in what form (PDF, photos)?
3. Customer-name prefix cleanup (86 customers): approve? (Needed for clean badges.)

**H. From the addenda** (carried over unresolved)
1. Tip assistant: geocode the ~5,300 existing customers for proximity matching?
2. Tip assistant: route a tip about another company's customer to that company?
3. After-hours capture: re-read its "Honest caveats" (fuzzy timing never bills;
   location is a trust matter with the techs) and confirm the design still stands.

---

*Next step: the design discussion. Record answers here and in
`DECISIONS-MADE-DURING-BUILD.md`, then turn §7 into a build directive like
`FIELDKIT_BUILD_DIRECTIVE_2026-09.md`.*
