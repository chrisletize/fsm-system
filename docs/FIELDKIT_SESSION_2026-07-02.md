# FieldKit — Session Notes, July 2, 2026
**Build: Work Orders core (list / create / edit / detail) + double-booking detection**
Base commit at session start: `a681998`. Model: Claude Fable 5 (experiment — see Process Notes).

---

## What was built

**Migration 005** (all four DBs, clean apply, 14 statements each):
`work_orders`, `work_order_line_items`, `work_order_status_history`,
`work_order_techs`, plus partial indexes and the normalized `work_site_label`
expression index that backs double-booking detection. Extraction/dispatch columns
included now (extraction_status, extraction_day_count, parent_work_order_id,
arrival window) to avoid migration churn later.

**app.py** (+~730 lines): eight routes — list, live-search JSON, customer-context
JSON, dupe-check JSON, new, edit, delete, detail — plus `_save_work_order`,
`_parse_wo_line_items`, `_wo_form_data`, `_next_wo_number`, `_parse_arrival_time`.

**Templates:** `workorder_list.html` (live search mirroring the customers pattern,
accruing badge), `workorder_form.html` (the big one), `workorder_detail.html`
(read view — placement decision deferred), `base.html` (nav link + three brick
changes).

## Key decisions made this session

1. **Line items: two visually distinct row types** ("+ Add Service" /
   "+ Deploy Equipment"), confirmed via interactive mockup before code. Equipment
   rows are **unit-first**: picking the physical unit implies its billing type and
   daily rate — no way to mismatch. Daily rate not editable on equipment rows
   (catalog owns it); price editable on standard rows.
2. **Equipment days, Option 1 (manual bridge):** editable retrieved date now;
   blank = accruing (quantity/total NULL, list shows badge, subtotal shows $/day
   still ticking). Same-day set-and-pull bills **1 day** (floor). The future
   extraction engine takes over the same columns — nothing throwaway.
3. **work_order_techs keys on `username`, not user_id** — users are replicated via
   write_to_all_dbs with SERIAL ids that can drift across the four DBs; the whole
   codebase already references users by username. Table + simple checkbox UI now;
   dispatch board later is a view over the same data.
4. **Tags: not built, concept replaced.** Callbacks become their own category —
   work-order-like objects linked to the original WO, own reporting keyed to the
   responsible employee, with the pay asymmetry rule (offender returns unpaid;
   substitute tech is paid). Captured in FIELDKIT_TASKS.md Design Notes; feeds the
   payroll/commission module design.
5. **Detail page built, placement deferred.** WO# on the list → detail; "Edit →"
   goes straight to edit. Chris will live with both before deciding (SF's
   too-many-layers problem vs. losing polished detail views). Future idea: mini
   preview on hover/click from the dispatch calendar.
6. **Arrival window → single arrival time.** UI maps to `arrival_window_start`;
   the end column stays, unused, documented. Brick #1 autocomplete with half-hour
   suggestions + flexible server parser ("8:30am", "815", "8", "14:30" all parse;
   garbage returns a friendly form error). Editing an old WO nulls any saved end
   value — accepted.
7. **Statuses:** office-settable set only (Scheduled, Completed, No Charge,
   Cancelled); mobile/extraction statuses reserved in the CHECK constraint. Edit
   form shows a non-office status as a "(system)" option rather than forcing a
   change.
8. **Commercial + Contractors → "Job Site"** mapping: done, no longer pending.

## Brick work (see FIELDKIT_REUSABLE_BRICKS.md, updated)

- **Brick #1 upgrade:** zero-match filter now falls back to the full suggestion
  list instead of closing the panel (custom text no longer strands the dropdown).
- **Brick #2 upgrade:** dispatches a bubbling `change` event on its hidden input
  on selection/invalidation — consumers react with delegated listeners.
- **Brick #3 (new):** site-wide Enter policy — Enter blurs the field, never
  implicitly submits. Exceptions: textareas, buttons, password fields.
- **New pattern:** edit pages must merge referenced-but-inactive records into
  restricted-combobox option lists, or blur-snap silently clears them (data loss).
  Implemented in workorder_edit for catalog items, equipment units, and customers.
- Also noted: the Brick #2 catalog entry was missing from the committed bricks doc
  despite the a681998 commit message — added now.

## Gotchas hit / process learnings

- **Log tail races `docker compose restart`** — the tail can capture the *previous*
  boot plus the new term signal. Add `sleep 3` before `docker compose logs`.
  A `302` from curl after restart is itself proof the new code imported cleanly
  (broken import = crash-looping workers = failed curl).
- **Don't hand-predict grep verification counts.** Twice this session the expected
  count quoted in upload instructions was wrong while the upload was fine (line
  counts were the reliable check). New rule: every expected grep count is run
  against the generated file before being quoted. Line counts + one or two
  file-specific greps, all pre-verified.
- **Implicit form submission** (Enter in a text input submits) is a real hazard on
  a long form — hence Brick #3.
- Jinja templates were **render-tested off-server** (Jinja env + mock context,
  both new and edit modes with mixed line items) before upload — caught issues at
  zero cost to the live app. Worth keeping in the workflow.
- The `_parse_arrival_time` helper was **unit-tested against the exact code
  extracted from the generated app.py**, not a copy — same spirit as the grep rule.

## State at session end

- All work orders functionality confirmed working in production by Chris: create,
  edit, delete, dupe banner (future + past), accrual display, detail page,
  arrival field, Enter policy, description surgical removal.
- Files changed vs a681998: migration 005 (new), app.py (2,840 lines), base.html
  (792), workorder_list.html / workorder_form.html (801) / workorder_detail.html
  (new), docs updated.
- Registries for Get a Grip / CTS / Kleanit SF still empty (Kleanit Charlotte:
  276 units) — separate task.

## Next

Dispatch Board is the roadmap next-up (schema stubs ready; users table needs the
design v2 §4 scheduling columns). Alternative interim session: registry population
+ any work-order polish that surfaces from Michele/Joanna's first real use.
See HANDOFF prompt.
