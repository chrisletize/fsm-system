-- FieldKit Migration 041
-- Widens email_log.kind to cover the management-company change notice
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-27
--
-- Chris, 2026-10-27: the salesman may change an existing customer's management
-- company from the sales customer page (D-117). The change takes effect
-- immediately, and the managers are emailed to confirm it with him. That email
-- gets its own kind, like every other sales email (migrations 038, 039, 040),
-- so "were the managers told?" has an answer. kind is VARCHAR(20):
-- 'mgmt_company_change' is 19.
--
-- No column changes: customers.management_company_id already exists, and the
-- change itself is recorded in record_audit (migration 027) like any other edit
-- to a customer, so it shows in the customer's History panel.

ALTER TABLE email_log DROP CONSTRAINT IF EXISTS email_log_kind_check;

ALTER TABLE email_log
    ADD CONSTRAINT email_log_kind_check
    CHECK (kind IN ('alert', 'estimate', 'invoice', 'statement',
                    'price_list_request', 'customer_intake', 'sales_tip',
                    'customer_price_list', 'mgmt_company_change'));
