-- FieldKit Migration 012
-- Adds: company_settings.extraction_explainer_text, invoices.work_site_label
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Increment 1.5 (invoice PDF, build directive §2.5):
--   1. A water-extraction invoice (any per-day equipment line present) gets a short
--      "Drying & monitoring process" paragraph pulled from
--      company_settings.extraction_explainer_text, explaining to the customer why
--      the invoice covers multiple days of equipment rather than a single visit.
--   2. The PDF spec requires "A hardened/sent version's PDF must be reproducible
--      byte-for-byte from the snapshot -- do not read the work order or catalog when
--      rendering a hardened version." Increment 1.2/1.3 never snapshotted the work
--      order's work_site_label anywhere on the invoice, even though the PDF layout
--      needs to show it (company block / customer / service location / work-site
--      label / PO-WTN). Without a snapshot, showing it on a hardened PDF would mean
--      live-joining work_orders, which directly violates that rule (the WO's
--      work_site_label could be edited after the invoice hardens). Snapshotting it
--      onto invoices (receivable-level -- it doesn't change across revisions, same
--      reasoning as why tax_county lives on invoice_versions and not here) closes
--      that gap the same way tax_county already does.
--
-- Design notes:
--   * Appendix B of the directive originally bundled company_settings.
--     extraction_explainer_text into migration 012 alongside email_log/
--     last_statement_at/version tax components/portal_is_primary_billing
--     (Increments 1.6-1.8's needs). Since only this column is needed for 1.5, and
--     those others don't exist to build against yet, this migration is scoped to
--     just what 1.5 needs -- "fold or split as needed" per the directive's own
--     Appendix B note. Increments 1.6-1.8 will each get their own migration number
--     for their own columns when the time comes.
--   * extraction_explainer_text is seeded with the same generic paragraph for all
--     four companies -- editable via /settings/company. [DEFAULTED] -- first-draft
--     wording, not final copy.
--   * invoices.work_site_label is backfilled from the source work order for any
--     existing invoice rows (none exist in production yet, but the migration is
--     correct either way) and populated going forward by _create_invoice_from_wo().

ALTER TABLE company_settings
    ADD COLUMN IF NOT EXISTS extraction_explainer_text TEXT;

UPDATE company_settings
SET extraction_explainer_text =
    'Water extraction and structural drying is a multi-day process. Our equipment ' ||
    'remains on site, actively monitored, until moisture levels return to a safe ' ||
    'range -- this invoice reflects the full number of days equipment was deployed, ' ||
    'not a single visit.'
WHERE extraction_explainer_text IS NULL;

ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS work_site_label VARCHAR(255);

UPDATE invoices i
SET work_site_label = wo.work_site_label
FROM work_orders wo
WHERE wo.id = i.work_order_id AND i.work_site_label IS NULL;
