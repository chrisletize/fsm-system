# FieldKit — Task List & Feature Backlog
*Last updated: July 2, 2026*

---

## 🔴 Immediate / Next Session

- [ ] **Commit July 2 work to GitHub** — migration 005, app.py, base.html,
      workorder_list/form/detail.html, docs (bricks catalog, session notes)
- [ ] **Decide next build:** Dispatch Board (roadmap order) vs. a short interim
      session (populate remaining equipment registries, minor work-order polish)
- [ ] **Populate equipment registries** for Get a Grip, CTS, Kleanit SF — only
      Kleanit Charlotte has real fleet data (276 units). Import script pattern exists.

---

## 🟡 Active Development — Phase 4 (Work Orders → Dispatch → Extraction → Reports)

- [x] **Work orders core** — COMPLETE July 2 (see Completed section for detail)
- [ ] **Dispatch board** — next major build. Schema stubs already in place
      (work_order_techs, arrival time, priority, status). Users table needs the
      scheduling columns from design v2 §4 (color_hex, can_be_dispatched, etc).
- [ ] **Water Extraction Queue** — rollover engine that owns deployed_at/retrieved_at
      and extraction_day_count. Requires the mobile after-hours extraction design
      (docs/FIELDKIT_DESIGN_ADDENDUM_mobile-afterhours-extraction.md).
- [ ] **Reports** — after dispatch + extraction exist.
- [ ] **Detail-page placement decision** — a full detail page now exists
      (`/<company>/workorders/<id>`; WO# on the list links to it, Edit link goes
      straight to edit). Chris wants to live with both paths before deciding where
      detail views vs. straight-to-edit apply, including a possible hover/click
      mini-preview on the future dispatch calendar. Revisit after dispatch board.

---

## 🟡 Work Orders — deferred details (not blocking)

- [ ] Tags system — REPLACED by the callback-category design (see Design Notes).
      Don't build tags.
- [ ] `arrival_window_end` column exists but is unused — UI collapsed to a single
      arrival time (maps to `arrival_window_start`). Keep the column in case the
      dispatch board wants windows back.
- [ ] Catalog "still-open soft spots" from the catalog addendum: category drift
      (free-text category, no managed list) and minimum fields for inline
      "+Add to Catalog" quick-add.
- [ ] Migrations-directory tidy-up (two 003s across two dirs) — deferred, don't
      renumber casually.

---

## 📝 Design Notes for Future Work (captured July 2)

### Callbacks as their own category (replaces tags idea)
- A callback is its own work-order-like object **linked to the original work order**
  — references its details, has its own lifecycle, and feeds a dedicated reporting
  system keyed to the employee(s) responsible for the original defective work.
- **Pay rule (critical, feeds payroll):** if the *offending* employee returns to
  correct their own job, they are **not paid** for the callback visit. If a
  *different* employee must go (scheduling/accommodation), that employee **is paid**.
  → The commission engine must know *why* a tech is on a job, not just that they
  were on it.
- Callback data also feeds the customer rating system (design addendum
  duration-and-rating) and eventually employee quality reporting.

### Payroll / commission module (early-stage, growing)
- All employees are paid on **commission for the work they do** — payroll
  compilation is a core deliverable of FieldKit, not an afterthought.
- Known open question (pre-existing): the commission **trigger event** —
  completion vs. invoicing vs. payment collection.
- New input (July 2): the callback pay asymmetry above.
- Existing payroll spreadsheet column layout still needs to be captured before
  any export is built.

---

## 🟡 Infrastructure

- [ ] **Ubuntu1 decommission** — Phase 0 still running at statements.cletize.com
      as systemd service. Michele must confirm fieldkit.cletize.com works for daily
      use first, then stop the old service and retire ubuntu1.
- [ ] **Real product domain** — app.fieldkit.cletize.com is temporary. Need a proper
      domain for franchise SaaS (fieldkit.io, getfieldkit.com, etc).
- [ ] **Non-admin user passwords** — patrick, walter, mikeyc, chriso still have
      unknown seed passwords. Reset when those users are ready to onboard.
- [ ] **LetiziGate ZFS mirror** — spare 500GB SATA SSD ready, procedure documented,
      not yet executed.
- [ ] **devkit.cletize.com** dev instance — reserved, deferred until FieldKit has
      live users.

---

## 🟢 Planned Features — Roadmap

### Invoicing (Phase 5)
- [ ] Invoice list / detail / create (ties to customer tax settings, cash-basis NC
      tax reporting by payment date)
- [ ] "Explain the drying/monitoring process" block on water extraction invoices
      (idea logged, not designed)
- [ ] Compliance portal exports (OPS, VendorCafe/Yardi, Paymode-X) — Michele
      currently submits manually

### Sales CRM (Phase 2–3)
- [ ] Prospect list / detail / visit log
- [ ] Estimate request queue (public-facing form → staff review)
- [ ] Salesperson dashboard (Chris O workflow)
- [ ] Business card scanning (Google Cloud Vision → contact import)

### Mobile App (Phase 6)
- [ ] PWA alongside Phases 4–5, then React Native (iOS + Android, unlisted)
- [ ] Job list + detail, clock in/out, job notes
- [ ] Before/after photo upload (target 2–5 sec vs ServiceFusion ~30 sec)
- [ ] Offline-first architecture
- [ ] iOS after-hours capture via CLVisit (design addendum exists)

### Designed, not built
- [ ] Customer rating system (A–F composite) — addendum exists
- [ ] Job duration estimation (`estimated_minutes` is already on catalog_items and
      `estimated_duration_hours` on work_orders) — addendum exists
- [ ] Stale billing info check at scheduling (90+ days, non-blocking)
- [ ] In-app help system (static panel + inline dependency markers) — after core
      modules are practically complete

---

## 🔵 Data Quality & Remediation Features
*Build before full staff onboarding.*

- [ ] **Customer merge** — HIGH PRIORITY. Merge duplicates, reassign all child
      records, side-by-side preview, soft-delete source with audit note.
- [ ] **Duplicate detection at creation** — name/address similarity warning
      (note: the work-order double-booking check now exists and is a good pattern
      template — normalized expression index + non-blocking banner).
- [ ] **Audit trail** — full change history on any record (status history on work
      orders is the first slice of this).
- [ ] Bulk status correction · Job reassignment · Contact deduplication ·
      Address validation API · Import conflict resolution · Undo window (30 min)

---

## 🤖 AI Features (Future — Post Local LLM Server)
- [ ] NC tax rate monitor (n8n now, LLM version later)
- [ ] Natural language report building
- [ ] Email drafting / Outlook triage (Microsoft Graph)
- [ ] n8n quality control layer (scheduling, billing completeness, invoice quality)
- ~~Double-booking alerts~~ — DONE July 2, and it needed no AI: plain SQL.

---

## ✅ Completed

### July 2, 2026 — Work Orders core
- [x] Migration 005 on all four DBs: work_orders, work_order_line_items,
      work_order_status_history, work_order_techs + indexes incl. normalized
      work_site_label expression index
- [x] Seven routes: list, live search, customer context JSON, dupe-check JSON,
      new, edit, delete (+ detail route = eight)
- [x] Work order numbers: GAG/KC/CTS/KSF-YYYY-#### per company per year
- [x] Two-row-type line items (standard + per-day equipment, unit-first selection,
      manual deployed/retrieved bridge until extraction engine exists,
      same-day = 1 billable day, server-side totals, catalog min-qty +
      billing-increment rounding honored)
- [x] work_site_label with customer-type-driven label (Unit Number / Job Site /
      Job Address + Residential prefill); Commercial+Contractors → "Job Site" done
- [x] Double-booking detection live: normalized match, 4-weeks-back +
      open-ended-forward window, non-blocking banner
- [x] Auto-generated editable job description with dirty tracking, regenerate,
      and surgical line removal on line-item delete
- [x] Status history recorded from day one; tech assignment (username-keyed,
      replication-safe) with checkbox UI
- [x] Work order detail page (read view) — placement decision deferred
- [x] Arrival time: single field, Brick #1 + flexible server parser
- [x] Brick upgrades: #1 full-list fallback, #2 change events, #3 (new) site-wide
      Enter policy; edit-page inactive-option merge pattern
- [x] Work Orders nav link (role-gated)

### June 30, 2026 — Catalog & Equipment
- [x] Migration 004: catalog_items + equipment_units (all four DBs)
- [x] Catalog CRUD + Equipment Registry CRUD at /<company>/settings/...
- [x] Kleanit Charlotte fleet imported: 276 real units
- [x] Bricks #1 and #2 built; GitHub brought to sync at a681998

### Earlier (Phase 0 / Phase 1 — see previous version of this file for detail)
- [x] Phase 0 statement generator in production; Phase 1 auth/RBAC, company-in-URL
      multi-tab architecture, customer module (CRUD, search, contacts, notes, tax
      settings, custom fields), user management, GitHub SSH auth, nightly backups

---

*Add new tasks at the top of the relevant section.*
*Move completed items to the ✅ Completed section.*
