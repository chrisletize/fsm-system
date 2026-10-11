-- FieldKit Migration 034
-- Adds: sales_prospects.general_email / general_phone,
--       sales_prospects.price_list_requested_at / _by / _to
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-11
--
-- Why this exists:
--   Chris, 2026-10-11, wanted a one-tap "request a price list" button for the
--   salesperson: it emails the OFFICE (never the prospect), and the office
--   sends the current pricing out by hand.
--
--   Dialling that in surfaced a real gap he spotted: a price-list request needs
--   an address to aim at, and sales_prospects had NO contact fields at all --
--   no email, no phone. In practice a property has a general leasing-office
--   address as well as named people with their own addresses, so the request
--   has to choose between several candidates. Hence the two halves of this
--   migration.
--
-- Design notes:
--   * general_email / general_phone are the PROPERTY's own details, the
--     prospect-side analogue of customers.billing_email -- but named for what
--     they are rather than for billing, because a leasing office's general
--     inbox is usually not where invoices should go. Named contacts keep using
--     sales_contacts.office_email / personal_email.
--   * Deliberately NOT copied into customers.billing_email on conversion
--     (Chris, 2026-10-11): auto-filling a billing address from a general
--     leasing inbox risks invoices landing somewhere nobody pays them from.
--     Conversion already passes through manager approval, where the real
--     billing address gets set on purpose.
--   * The three price_list_* columns record the LAST request only -- who asked,
--     when, and which address it was aimed at. That is enough to show "price
--     list requested Oct 11" on the prospect and to warn before firing a
--     duplicate at the office a day later. A full history table would be the
--     right call if these ever need reporting on; they don't yet.
--   * No "preferred pricing address" flag, unlike customer_contacts'
--     accepts_billing / accepts_statements / accepts_general. Chris chose
--     (2026-10-11) to pick the recipient each time rather than store a
--     preference, on the grounds that who actually handles pricing varies call
--     to call.
--   * No OCR, no automatic send to the prospect. The office emails the price
--     list manually and always will -- the button only raises the request.

ALTER TABLE sales_prospects
    ADD COLUMN IF NOT EXISTS general_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS general_phone VARCHAR(20),
    ADD COLUMN IF NOT EXISTS price_list_requested_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS price_list_requested_by VARCHAR(100),
    ADD COLUMN IF NOT EXISTS price_list_requested_to VARCHAR(255);
