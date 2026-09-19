-- FieldKit Migration 017
-- Adds: tech-profile columns on users + scheduling columns on work_orders
--       (build directive Stage 2, Increment 2.1 — dispatch board).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   The dispatch board (§3.1) needs to know which users are field techs that can be
--   dropped onto the timeline, what color their blocks render in, and where their row
--   sorts. It also needs each work order's actual clock-time position on the board
--   (scheduled_start) separately from the two source columns (start_date,
--   arrival_window_start) that have driven the WO form since Phase 1 -- keeping both
--   lets existing WO-list/report code that reads start_date/arrival_window_start keep
--   working unchanged while the board reads one denormalized timestamp instead of
--   combining two columns in every query.
--
-- Design notes:
--   * color_hex is nullable at the column level but the app backfills it at read time
--     (12-color fixed palette, chosen by id % 12) rather than writing it here --
--     letting the palette itself live in Python (COLOR_PALETTE in app.py) instead of
--     being baked into a migration, matching how COMPANY_BRANDING already works.
--   * is_field_tech vs. can_be_dispatched vs. is_active_tech are three separate flags,
--     not one, because they answer three different questions the board and future
--     increments need separately: is_field_tech = "this user does field work at all"
--     (drives visibility on tech-facing UI later), can_be_dispatched = "eligible for
--     the board's timeline rows" (an office-only field tech, if that ever exists,
--     could be is_field_tech=TRUE but can_be_dispatched=FALSE), is_active_tech =
--     "currently employed/available" (a departed tech keeps historical WO assignment
--     rows intact -- work_order_techs.username is a plain VARCHAR, not a FK, per
--     CLAUDE.md -- but drops off the live board without deleting anything).
--   * scheduled_start is maintained by the WO save path (app.py), not a generated
--     column -- a work order can be saved with only start_date and no
--     arrival_window_start (directive doesn't require arrival time to be mandatory),
--     and a GENERATED column can't express "NULL when the second input is NULL"
--     cleanly alongside "otherwise combine them" without a matching CASE, which is
--     just as easy to keep in the one place (workorder_new/workorder_edit) that
--     already owns this column.
--   * catalog_estimated_duration_hours is the live sum of
--     work_order_line_items.estimated_minutes x quantity (design addendum §13,
--     docs/FIELDKIT_DESIGN_ADDENDUM_duration-and-rating.md) -- stored so the board
--     doesn't re-join catalog_items per block on every render. Recomputed on every WO
--     save; duration_overridden freezes estimated_duration_hours (the EXISTING column,
--     repurposed per the addendum as the scheduled/board-sizing duration) against that
--     recompute once the office manually adjusts it (the +-15-minute banner's [Keep]
--     choice sets this flag; [Use catalog] clears it).
--   * work_order_line_items.estimated_minutes is snapshotted from
--     catalog_items.estimated_minutes at line-add time, same pattern as price and
--     description already follow -- editable per line for an unusual job, and immune
--     to a later catalog edit changing the estimate on jobs already scheduled.
--     catalog_items.estimated_minutes itself already exists (added ahead of this
--     migration, alongside billing_behavior) -- nothing to add there.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS color_hex           VARCHAR(7),
    ADD COLUMN IF NOT EXISTS is_field_tech        BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS can_be_dispatched     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS phone_mobile          VARCHAR(20),
    ADD COLUMN IF NOT EXISTS default_start_time    TIME NOT NULL DEFAULT '08:00',
    ADD COLUMN IF NOT EXISTS is_active_tech         BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS dispatch_sort_order    INTEGER;

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS scheduled_start                 TIMESTAMP,
    ADD COLUMN IF NOT EXISTS catalog_estimated_duration_hours NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS duration_overridden              BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE work_order_line_items
    ADD COLUMN IF NOT EXISTS estimated_minutes INTEGER;

CREATE INDEX IF NOT EXISTS idx_wo_scheduled_start
    ON work_orders(scheduled_start) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_dispatchable
    ON users(can_be_dispatched, is_active_tech) WHERE is_active = TRUE;

-- Backfill scheduled_start for any existing WOs that already have both source
-- columns, so the board has something to show for pre-migration data instead of
-- every historical WO looking "unscheduled." A no-op for rows missing either
-- source column (scheduled_start stays NULL, same as the app would compute).
UPDATE work_orders
SET scheduled_start = start_date + arrival_window_start
WHERE scheduled_start IS NULL
  AND start_date IS NOT NULL
  AND arrival_window_start IS NOT NULL
  AND deleted_at IS NULL;
