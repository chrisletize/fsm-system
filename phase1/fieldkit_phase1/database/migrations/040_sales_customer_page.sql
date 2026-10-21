-- FieldKit Migration 040
-- Adds: customers.price_list_requested_at / _by / _to,
--       company_settings.sales_past_due_warning_enabled,
--       email_log kind 'customer_price_list'
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-21
--
-- Why this exists:
--   Chris, 2026-10-21: when the salesman visits a DORMANT CUSTOMER (already a
--   customer, not a prospect) there is nowhere to request a price list. That
--   button only existed on the prospect page, and the salesperson role is locked
--   out of customer pages (D-101). He now gets a sales-side customer page
--   (/<company>/sales/customers/<id>): read-only, sales-relevant only. It carries
--   the same price-list request as prospects. See D-116.
--
-- Design notes:
--   * Price-list tracking on customers mirrors migration 034 on sales_prospects
--     exactly (same three columns, same types): last request, by whom, to which
--     address. It sits beside sales_delayed_until (migration 035), the other
--     sales-owned fact already on customers.
--   * The request email logs under its own kind, 'customer_price_list' (kind is
--     VARCHAR(20), so not the longer 'customer_price_list_request'),
--     rather than reusing 'price_list_request' with a customer id. email_log
--     .related_id carries no type, so mixing the two would let customer 12's
--     delivery record show up on prospect 12's page.
--   * sales_past_due_warning_enabled: the customer page can warn "account past
--     due, check with the office before pitching" (from customer_flags
--     .is_delinquent, 90+ days per D-001). Chris asked for it built but
--     INACTIVE until beta: FieldKit has no reliable payment history yet. At
--     2026-10-21, 41 Get a Grip customers are flagged delinquent purely from
--     imported ServiceFusion invoices with no payments recorded. Per-company,
--     default FALSE, switched on by an admin in Company Settings, the same shape
--     as scheduled_alerts_enabled (migration 020).

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS price_list_requested_at TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS price_list_requested_by VARCHAR(100),
    ADD COLUMN IF NOT EXISTS price_list_requested_to VARCHAR(255);

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS sales_past_due_warning_enabled BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE email_log DROP CONSTRAINT IF EXISTS email_log_kind_check;

ALTER TABLE email_log
    ADD CONSTRAINT email_log_kind_check
    CHECK (kind IN ('alert', 'estimate', 'invoice', 'statement',
                    'price_list_request', 'customer_intake', 'sales_tip',
                    'customer_price_list'));
