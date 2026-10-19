-- FieldKit Migration 004b
-- Adds: password_reset_tokens
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-05-28 (applied); file reconstructed 2026-10-19
--
-- RECONSTRUCTED FILE. This table shipped with commit 678174f ("User
-- management + password reset email flow", 2026-05-28), whose message calls it
-- "migration 004, all 4 DBs" -- but the .sql was never committed, and the
-- number 004 was later taken by 004_catalog_and_equipment.sql. Numbered 004b
-- here so it sorts next to its original slot without colliding. Rebuilt from
-- `pg_dump -s` of the live table (identical in all four DBs). Every statement
-- is IF NOT EXISTS, so it's a no-op against a database that already has it.
--
-- Used by: user_reset_password / reset_password routes in app.py. Tokens are
-- single-use (used_at), 24-hour expiry (expires_at), and issuing a new token
-- invalidates any prior unused one for that user.
--
-- Design notes:
--   * Hard FK to users(id), unlike most username references in this schema
--     (user_company_dispatch and user_sessions are the other two):
--     a reset token is always issued and redeemed against getagrip.users (the
--     canonical login table), and the table exists in the other three DBs only
--     to keep schemas identical.
--   * No updated_*/deleted_* columns: tokens are consumed by setting used_at,
--     never edited or soft-deleted.

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    token       VARCHAR(128) NOT NULL UNIQUE,
    expires_at  TIMESTAMP NOT NULL,
    used_at     TIMESTAMP,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by  VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_prt_token   ON password_reset_tokens (token);
CREATE INDEX IF NOT EXISTS idx_prt_user_id ON password_reset_tokens (user_id);
