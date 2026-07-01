# FieldKit — Reusable Bricks Catalog
*Started: June 30, 2026*

A running list of the genuinely **generic** pieces being built inside FieldKit that could be pried loose for future custom-software projects (LKit / other companies). No real effort goes here now — this just accretes as we go, so future-you has a shortlist instead of having to excavate.

**The one principle:** a brick is only reusable if it was *designed* to be pried loose. The more we hardcode for the four companies (correct for now), the more decoupling work later. So when a piece is genuinely generic, we tag it here.

---

## Brick #1 — "Suggest, don't restrict" autocomplete field ✅ built
A text input that suggests existing values as you type but never forces a choice — type a brand-new value and it's kept. Solves free-text drift (e.g. "Resurfacing/resurfacing/Resurface") without caging the user.

- **Where it lives:** CSS + JS in `base.html` (`.ac-*`, `initAutocompleteFields`), markup macro in `templates/_macros.html` (`autocomplete_field`).
- **How to reuse:** call the macro with a name, current value, and a list of suggestions. Any `<input class="js-autocomplete" data-suggestions='[...]'>` auto-initializes.
- **Generic core:** client-side filter, keyboard nav (↑/↓/Enter/Esc), mouse select, suggest-don't-restrict. No app-specific logic. Client-side only (no AJAX) — fine for bounded lists.
- **Decoupling note:** only dependency is the branding-color token in `base.html`. To extract, swap that one CSS variable.
- **First use:** catalog category field. Next: equipment registry category field.

---

## Candidate bricks spotted (not yet extracted)
Tag-only, for later:

- **Per-company settings-CRUD pattern** — list / add / edit / soft-delete under `/<company>/settings/<thing>`, role-gated, single-DB. (catalog, custom fields, users all follow it.)
- **Soft-delete-with-audit convention** — `deleted_at` / `deleted_by`, one-year retention, history-safe because line items snapshot their own values.
- **Role-gated route stack** — `login_required → company_access_required → with_branding` + inline role check.
- **Multi-tab company switcher** — database-per-company + `<company_key>` URL routing + session `company_access`.
- **Draft-confirm flow** — phone/system proposes, human commits (after-hours capture, passive backstop, equipment reporting).
- **Safe Docker volume rename** — dump → rebuild under correct name → restore → verify → retire (from the June infra cleanup).
- **Migration discipline** — numbered, idempotent (`IF NOT EXISTS`), "apply to all four DBs" header, partial indexes on `WHERE deleted_at IS NULL`.

---

*Add new bricks at the top of the built section as they prove out.*
