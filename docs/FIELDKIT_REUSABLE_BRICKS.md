# FieldKit — Reusable Bricks Catalog
*Started: June 30, 2026 · Last updated: July 2, 2026*

A running list of the genuinely **generic** pieces being built inside FieldKit that could be pried loose for future custom-software projects (LKit / other companies). No real effort goes here now — this just accretes as we go, so future-you has a shortlist instead of having to excavate.

**The one principle:** a brick is only reusable if it was *designed* to be pried loose. The more we hardcode for the four companies (correct for now), the more decoupling work later. So when a piece is genuinely generic, we tag it here.

---

## Brick #3 — Site-wide "Enter exits the field" policy ✅ built (Jul 2)
A single delegated keydown listener that makes Enter blur/close the focused field instead of implicitly submitting the form. Only an explicit button press submits. Kills the classic "hit Enter in a text box, accidentally filed a half-finished record" failure.

- **Where it lives:** one `document.addEventListener('keydown', ...)` block at the bottom of `base.html`'s scripts.
- **Deliberate exceptions:** textareas keep Enter for newlines; buttons still activate on Enter; **password fields keep Enter-to-log-in** (muscle memory).
- **Generic core:** zero app logic — tag/type checks only. Drop into any multi-field form app.
- **Plays nicely with Bricks #1/#2:** their own Enter handling (pick highlighted item) runs first on the input; this policy then blurs, which is the desired "exit" behavior.
- **First use:** everywhere, July 2 (prompted by the work order form).

---

## Brick #2 — Restricted combobox (type-to-filter, must resolve to a real id) ✅ built
A text input that filters a bounded option list as you type, but the *submitted* value is a hidden id that only ever holds a real record's id — edited or unmatched text clears it, and blur snaps the visible text back to the actual selection. Free text cannot sneak into the database. Server-side re-validation backs it up.

- **Where it lives:** CSS + JS in `base.html` (`.ac-*`, `initRestrictedComboFields`), markup macro in `templates/_macros.html` (`restricted_combo_field`).
- **How to reuse:** call the macro with a field name, options (`[{id, name, category?}]`), current id + label. Any `<input class="js-combo-restricted" data-options='[...]'>` inside an `.ac-wrap` with a sibling hidden input auto-initializes. Init is idempotent (`data-comboInit` guard) — safe to call `initRestrictedComboFields()` again after inserting rows dynamically.
- **Upgrade (Jul 2): change events.** The brick now dispatches a bubbling `change` event on the hidden input when a selection is made *or invalidated*. Consumers can react to picks with plain delegated listeners (the work order form loads customer locations/contacts this way).
- **Server-side companion:** always re-validate the id on POST (exists, not deleted, right type) — the client restriction is UX, not security.
- **Edit-page gotcha (solved in work orders):** if the option list filters to active-only records, editing an old record that references a retired option will silently clear it on blur. Merge referenced-but-inactive records into the options server-side on edit pages.
- **Uses so far:** equipment registry billing type; work order customer picker; work order line-item catalog + equipment-unit pickers (dynamic rows).

---

## Brick #1 — "Suggest, don't restrict" autocomplete field ✅ built
A text input that suggests existing values as you type but never forces a choice — type a brand-new value and it's kept. Solves free-text drift (e.g. "Resurfacing/resurfacing/Resurface") without caging the user.

- **Where it lives:** CSS + JS in `base.html` (`.ac-*`, `initAutocompleteFields`), markup macro in `templates/_macros.html` (`autocomplete_field`).
- **How to reuse:** call the macro with a name, current value, and a list of suggestions. Any `<input class="js-autocomplete" data-suggestions='[...]'>` auto-initializes.
- **Generic core:** client-side filter, keyboard nav (↑/↓/Enter/Esc), mouse select, suggest-don't-restrict. No app-specific logic. Client-side only (no AJAX) — fine for bounded lists.
- **Upgrade (Jul 2): never strand the user.** If the typed text filters the suggestion list to zero matches, the panel now shows the *full* list instead of closing. Custom text stays valid; the dropdown stays reachable.
- **Pattern (Jul 2): free text + server-side normalizer.** The work order arrival-time field pairs this brick with a flexible parser (`_parse_arrival_time`: "8:30am", "815", "8", "14:30" → `HH:MM`) so free typing lands cleanly in a typed column, with a friendly error instead of a 500 on garbage. Reuse the pairing anywhere free text feeds a typed column (times, dates, currency).
- **Decoupling note:** only dependency is the branding-color token in `base.html`. To extract, swap that one CSS variable.
- **Uses so far:** catalog category field; equipment registry category field; work order arrival time.

---

## Candidate bricks spotted (not yet extracted)
Tag-only, for later:

- **Two-row-type line item editor** (Jul 2) — one line-items panel, two visually distinct row types added by separate buttons (standard qty×price vs. per-day equipment with deployed/retrieved accrual), DOM-held state, serialize-to-hidden-JSON on submit, totals always recomputed server-side. Generic shape for any "order with heterogeneous lines" app.
- **Normalized-duplicate detection** (Jul 2) — expression index on `lower(regexp_replace(col, '[^a-zA-Z0-9]', '', 'g'))` + a debounced JSON check endpoint + a non-blocking warning banner. "Unit 308" / "#308" / "unit-308" all collide. Plain SQL, no AI. Reusable for any user-keyed freeform identity field.
- **Auto-generated-but-editable description** (Jul 2) — system composes text from structured fields, live-updates until the user hand-edits (dirty tracking), then stops overwriting; offers a "regenerate" action; deletions of source rows surgically remove just their line even when dirty.
- **Per-entity yearly sequence numbers** — `PREFIX-YYYY-0001`, derived from `MAX()` within year, UNIQUE constraint as the real guarantee.
- **Per-company settings-CRUD pattern** — list / add / edit / soft-delete under `/<company>/settings/<thing>`, role-gated, single-DB. (catalog, custom fields, users all follow it.)
- **Soft-delete-with-audit convention** — `deleted_at` / `deleted_by`, one-year retention, history-safe because line items snapshot their own values.
- **Role-gated route stack** — `login_required → company_access_required → with_branding` + inline role check.
- **Multi-tab company switcher** — database-per-company + `<company_key>` URL routing + session `company_access`.
- **Draft-confirm flow** — phone/system proposes, human commits (after-hours capture, passive backstop, equipment reporting).
- **Safe Docker volume rename** — dump → rebuild under correct name → restore → verify → retire (from the June infra cleanup).
- **Migration discipline** — numbered, idempotent (`IF NOT EXISTS`), "apply to all four DBs" header, partial indexes on `WHERE deleted_at IS NULL`.

---

*Add new bricks at the top of the built section as they prove out.*
