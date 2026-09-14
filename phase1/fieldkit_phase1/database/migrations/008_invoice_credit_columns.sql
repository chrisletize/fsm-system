-- 008_invoice_credit_columns.sql
-- Step 4 (Void + reissue): temporary structured home for the OPEN-CREDIT stamp
-- left behind when a PAID invoice is voided (Paid -> Void).
--
-- This is a HOLDING PLACE, not the credit system. The real `credits` table and
-- its resolution lifecycle (open -> refunded / applied / written-off) are their
-- own later step; at that point these three columns migrate into it and are
-- dropped from `invoices`.
--
-- Reconciliation framework: the void+reissue itself is Pattern 2 (supersede the
-- wrong-but-committed invoice, retain it). The credit it leaves behind is
-- Pattern 3 (incomplete -> forward the gap loudly to the human positioned to
-- resolve it, i.e. AR/Michele). A voided PAID invoice leaves real money against
-- no valid invoice: that is an OPEN PROBLEM to be resolved, never a balance left
-- to linger on the account.
--
-- Money type mirrors the rest of the invoice money columns: numeric(12,2).
--
-- APPLY TO ALL FOUR DATABASES:
--   fieldkit_getagrip / fieldkit_kleanit_charlotte / fieldkit_cts / fieldkit_kleanit_sf

ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS credit_amount    numeric(12,2),
    ADD COLUMN IF NOT EXISTS credit_status    varchar,
    ADD COLUMN IF NOT EXISTS credit_opened_at timestamp without time zone;

COMMENT ON COLUMN invoices.credit_amount IS
    'Orphaned amount_paid captured when a PAID invoice is voided (Paid->Void). Temporary home; migrates into the credits table when the resolution step ships.';

COMMENT ON COLUMN invoices.credit_status IS
    'Open-credit marker. Step 4 only ever writes ''open''. No CHECK constraint yet on purpose -- the full vocabulary is defined when the credit resolution step is built.';

COMMENT ON COLUMN invoices.credit_opened_at IS
    'Timestamp the open credit was recorded (set at Paid->Void).';
