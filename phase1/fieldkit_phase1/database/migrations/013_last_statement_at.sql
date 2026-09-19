-- FieldKit Migration 013
-- Adds: customers.last_statement_at
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Increment 1.6 (statements, build directive §2.6): records when a customer's
--   statement was last generated, so the future full billing page (Increment 1.8)
--   can show a "last statement" column. Written by both the single-customer
--   statement download and the batch ZIP route (the directive only explicitly
--   mentions it under the batch bullet, but a statement is a statement regardless
--   of which path generated it — see docs/DECISIONS-MADE-DURING-BUILD.md).
--
-- Design notes:
--   * Appendix B originally bundled this into migration 012 alongside several other
--     increments' columns. As with migration 012 itself (see that file's header),
--     this build is giving each increment its own migration number for just what it
--     needs, rather than waiting to batch unrelated future columns together.

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS last_statement_at TIMESTAMP;
