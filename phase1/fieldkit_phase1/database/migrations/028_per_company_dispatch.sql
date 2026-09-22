-- FieldKit Migration 028
-- Adds: user_company_dispatch; drops: users.can_be_dispatched, users.is_active_tech
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-22
--
-- Why this exists:
--   Chris flagged (2026-09-22) that "can be dispatched" was a single global
--   flag on the user record: a tech with access to multiple companies showed
--   up on EVERY one of those companies' dispatch boards, with no way to say
--   "dispatchable for Kleanit Charlotte, but not for CTS" even though the
--   user legitimately needs account access to both. Same story for
--   is_active_tech ("uncheck when a tech leaves") -- a tech who leaves one
--   company's crew but stays active at another had no way to reflect that.
--
-- Design notes:
--   * Only can_be_dispatched/is_active_tech move to the new table --
--     is_field_tech, color_hex, dispatch_sort_order, phone_mobile,
--     default_start_time stay global columns on `users`. Those are personal/
--     identity properties (is a field tech at all, preferred color, sort
--     position, contact info) that don't vary by which company's board is
--     showing them, unlike "am I dispatchable AT THIS COMPANY" which
--     genuinely does.
--   * Lives in EVERY company's DB (this build's blanket migration rule) but,
--     matching `users` itself, only the canonical getagrip copy is ever
--     actually read (_company_techs already hardcodes get_db_connection
--     ('getagrip') -- see its own docstring/D-003: the other three DBs'
--     `users` tables are still out of sync with getagrip's real 8 rows, so
--     reading a per-company copy here would silently return nothing for
--     three of the four companies).
--   * Backfilled from the existing global flags before they're dropped: any
--     user with the old can_be_dispatched=TRUE gets one row per company
--     already in their company_access, carrying over is_active_tech's old
--     value too -- preserves today's actual dispatch-board behavior exactly:
--     nobody drops off a board they were already showing on just because
--     this migration ran. Chris can then narrow it down per company from
--     the user edit form.
CREATE TABLE IF NOT EXISTS user_company_dispatch (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    company_key VARCHAR(30) NOT NULL,
    can_be_dispatched BOOLEAN NOT NULL DEFAULT FALSE,
    is_active_tech BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),

    UNIQUE(user_id, company_key)
);

CREATE INDEX IF NOT EXISTS idx_ucd_user ON user_company_dispatch(user_id);
CREATE INDEX IF NOT EXISTS idx_ucd_lookup ON user_company_dispatch(company_key, can_be_dispatched, is_active_tech);

-- Backfill from the about-to-be-dropped global columns, one row per company
-- already in that user's company_access, only for users who were actually
-- dispatchable (no point creating an all-FALSE row for someone who never
-- had the box checked -- COALESCE(..., FALSE) at read time already treats
-- "no row" as not-dispatchable, same end state as an explicit FALSE row).
-- Guarded on the column still existing so a re-run after the DROP below
-- (idempotency check) doesn't error trying to SELECT a column that's gone.
DO $$
DECLARE
    u RECORD;
    co TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'users' AND column_name = 'can_be_dispatched') THEN
        FOR u IN EXECUTE 'SELECT id, company_access, is_active_tech FROM users WHERE can_be_dispatched = TRUE' LOOP
            FOR co IN SELECT jsonb_array_elements_text(u.company_access) LOOP
                INSERT INTO user_company_dispatch (user_id, company_key, can_be_dispatched, is_active_tech, created_by)
                VALUES (u.id, co, TRUE, u.is_active_tech, 'migration_028')
                ON CONFLICT (user_id, company_key) DO NOTHING;
            END LOOP;
        END LOOP;
    END IF;
END $$;

ALTER TABLE users DROP COLUMN IF EXISTS can_be_dispatched;
ALTER TABLE users DROP COLUMN IF EXISTS is_active_tech;
