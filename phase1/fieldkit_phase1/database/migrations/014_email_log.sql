-- FieldKit Migration 014
-- Adds: email_log table, company_settings.invoice_email_template /
--       statement_email_template
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Increment 1.7 (email delivery, build directive §2.7): every invoice/statement
--   send goes through Resend and gets logged here (kind, recipients, subject,
--   Resend's message id, status, error) so a failed send is visible and traceable,
--   not silent. The two template columns hold the editable subject/body templates
--   ({customer}/{number}/{total}/{balance} placeholders) the send dialog pre-fills
--   from.
--
-- Design notes:
--   * Appendix B originally bundled email_log into migration 012 alongside several
--     other increments' columns; as with every migration since 012 itself, this
--     build gives each increment its own migration number for just what it needs.
--   * email_log has no company_id column (consistent with every other table in this
--     schema) -- the database IS the company.
--   * Seeded template defaults are first-draft copy, editable via /settings/company.
--     [DEFAULTED]

CREATE TABLE IF NOT EXISTS email_log (
    id                 SERIAL PRIMARY KEY,
    kind               VARCHAR(20) NOT NULL CHECK (kind IN ('invoice', 'statement', 'estimate', 'alert')),
    related_id         INTEGER,
    to_emails          TEXT NOT NULL,
    subject            VARCHAR(255),
    resend_message_id  VARCHAR(255),
    status             VARCHAR(20) NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'failed')),
    error              TEXT,
    sent_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_by            VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_email_log_kind_related ON email_log(kind, related_id);
CREATE INDEX IF NOT EXISTS idx_email_log_sent_at ON email_log(sent_at);

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS invoice_email_template TEXT,
    ADD COLUMN IF NOT EXISTS statement_email_template TEXT;

UPDATE company_settings
SET invoice_email_template =
    'Hi {customer},' || E'\n\n' ||
    'Please find attached invoice {number} for {total}.' || E'\n\n' ||
    'Balance due: {balance}.' || E'\n\n' ||
    'Thank you for your business.'
WHERE invoice_email_template IS NULL;

UPDATE company_settings
SET statement_email_template =
    'Hi {customer},' || E'\n\n' ||
    'Please find attached your current account statement.' || E'\n\n' ||
    'If you have any questions, please contact our office.'
WHERE statement_email_template IS NULL;
