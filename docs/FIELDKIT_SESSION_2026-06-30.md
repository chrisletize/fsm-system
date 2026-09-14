# FieldKit — Session Notes, June 30, 2026
*Focus: Service-catalog foundation hardening, then first build increment toward the Jobs module.*

## Shipped & tested this session
- **Migration 004** (`phase1/fieldkit_phase1/database/migrations/004_catalog_and_equipment.sql`) — `catalog_items` + `equipment_units`, applied clean to all four DBs.
- **Catalog CRUD** — routes at `/<company>/settings/catalog` (list / new / edit / delete, admin+manager, soft delete); `catalog_list.html`, `catalog_form.html`; nav link added to `base.html`. Tested: add/edit/delete, Standard vs Per-Day Equipment, the minutes-field grey-out JS.
- **Reusable autocomplete brick** — `base.html` CSS+JS, `templates/_macros.html`, retrofit onto the catalog Category field. Suggest-don't-restrict, keyboard nav. Tested incl. the new-value round-trip. (See `FIELDKIT_REUSABLE_BRICKS.md`.)

## Design decided this session (addenda in project)
- **Two billing behaviors** replace service/product: `billing_behavior` = `standard` | `per_day_equipment`. `per_day_equipment` bills daily rate × days, no `estimated_minutes`, no schedule-block impact; days accrue via the Phase 4 queue. Added `day` unit; merged §13 `estimated_minutes`; added `minimum_quantity` / `billing_increment` for the water-extraction min+round rule (null except water ext.).
- **Equipment registry** (`equipment_units`) replaces the one-catalog-item-per-machine hack; each physical unit points at a per-day catalog item; tech reports via registry autocomplete.
- **Unit Number ghost** promoted out of the catalog to a first-class `work_orders.work_site_label` (freeform; label/prefill by customer type); `is_unit_number_field` removed.
- **`customer_type` already exists** (4 values: Multi Family, Contractors, Residential, Commercial). Plan: keep all four, map Commercial+Contractors to the same "Job Site" behavior cosmetically — **needs final nod**, then update the worksite addendum.
- **Double-booking detection** reclassified from "AI features" to **Phase 4 scheduling** (plain SQL). Asymmetric window: any-future + 4-weeks-back (any status). Key: customer + service_location + normalized `work_site_label`.
- **After-hours mobile capture** (Phase 6): visit monitoring (`CLVisit`), not continuous GPS / not geofencing; one-button + passive backstop; draft-confirm; **retroactive/backdated work-order creation** the Phase 4 engine must support; office review queue.
- **DB-per-company** → no `company_id` on catalog tables (the database is the partition).

Addenda: `FIELDKIT_DESIGN_ADDENDUM_catalog-and-equipment.md`, `..._mobile-afterhours-extraction.md`, `..._worksite-and-doublebooking.md`.

## Infra notes
- Stack dirs renamed in June: live app under `~/docker/fieldkit-prod/fsm-system/phase1/fieldkit_backend/`; containers `fieldkit-prod-app-1` / `fieldkit-prod-db-1`; migrations dir `phase1/fieldkit_phase1/database/migrations/` (used as canonical going forward).

## Parked for next time
- **Equipment registry UI** — table exists; needs routes + form (reuses the autocomplete macro). *Natural next increment.*
- **Migrations-directory tidy-up** — two `003`s across two dirs; defer to a focused session, don't rush a renumber.
- **Stray uncommitted templates** — `user_form.html` / `user_list.html` modified on server, never committed; review diff and commit.
- **customer_type** — confirm cosmetic Commercial/Contractors mapping; update worksite addendum.
- **Remaining catalog soft spots** — category drift (now *mitigated* by autocomplete, not enforced), min-required-fields for inline "+Add to Catalog", retain-`item_type` confirm, catalog seeding (SF price list vs hand-build).
- **Tailscale** — set key to never-expire (still outstanding from June 25).
- **Then: Work Orders (Phase 4)** — the big build the catalog now unblocks.
