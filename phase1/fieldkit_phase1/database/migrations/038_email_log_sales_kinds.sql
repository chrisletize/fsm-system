-- FieldKit Migration 038
-- Widens email_log.kind to cover the sales emails
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-12
--
-- Chris, 2026-10-12: price-list requests "aren't landing on the office email",
-- and there was no way to check. The sales emails -- price-list requests and
-- the customer-intake copy -- called Resend and discarded the result, so a
-- rejected send still told the salesperson it had gone, and nothing was
-- recorded anywhere. email_log already existed for invoices and statements;
-- the sales paths simply never used it.
--
-- Pointing them at email_log needs kind to accept the two new values. They get
-- their own kinds rather than reusing the existing 'alert' precisely because
-- the question being asked is "did the PRICE LIST REQUEST send?" -- lumping
-- them in with every other alert would leave that as hard to answer as it is
-- now.
--
-- Historical rows are unaffected: this only widens what's permitted.

ALTER TABLE email_log DROP CONSTRAINT IF EXISTS email_log_kind_check;

ALTER TABLE email_log
    ADD CONSTRAINT email_log_kind_check
    CHECK (kind IN ('alert', 'estimate', 'invoice', 'statement',
                    'price_list_request', 'customer_intake'));

-- "Has this prospect's price list request gone out, and did it succeed?"
CREATE INDEX IF NOT EXISTS idx_email_log_kind_related
    ON email_log(kind, related_id, sent_at DESC);
