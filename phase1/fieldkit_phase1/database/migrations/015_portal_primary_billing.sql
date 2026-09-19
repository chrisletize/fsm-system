-- FieldKit Migration 015
-- Adds: customer_compliance_portals.portal_is_primary_billing
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Increment 1.8 (build directive §2.8): a customer whose active portal enrollment
--   has portal_is_primary_billing = TRUE is billed exclusively through that portal —
--   the billing page marks them "Portal billing — no direct email" and excludes them
--   from email batches by default (they'd otherwise get double-billed: once by the
--   portal, once by FieldKit's own send-statements).
--
-- Design notes:
--   * invoices.portal_id / portal_status / portal_submitted_at / portal_submission_notes
--     / wtn_po_number already exist (migration 010) -- this is the one remaining
--     compliance-portal column the directive calls out, on the enrollment table
--     rather than the invoice.
--   * Appendix B bundled this into migration 012 originally; as with every migration
--     since, this build gives each increment its own number.

ALTER TABLE customer_compliance_portals
    ADD COLUMN IF NOT EXISTS portal_is_primary_billing BOOLEAN NOT NULL DEFAULT FALSE;
