-- FieldKit Migration 019
-- Adds: work_orders.is_internal_task -- the "Misc Task" retired-tag replacement
--       (build directive Stage 2, Increment 2.4).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   ServiceFusion's "Misc Task" tag covered internal work with no billable customer
--   (a supply run, equipment maintenance, etc.). This build's work_orders.customer_id
--   has been NOT NULL since Phase 1 -- every WO-related query, report, and the
--   dispatch board assumes a customer. Rather than model internal tasks as a
--   different object, the directive keeps them as ordinary work_orders rows with
--   customer_id relaxed to nullable, gated by is_internal_task so the two can never
--   silently disagree (a WO is either customer work or explicitly internal, never
--   neither -- the CHECK constraint below enforces that at the DB level, not just in
--   app.py).
--
-- Design notes:
--   * The CHECK constraint (customer_id IS NOT NULL OR is_internal_task) is the
--     actual safety net -- app.py's _save_work_order() enforces the same rule on the
--     way in, but a DB-level constraint means a future direct-SQL fixture or a bug in
--     a different code path can't silently create an orphaned, customer-less WO that
--     isn't flagged as intentional.
--   * Every existing query that does `JOIN customers c ON c.id = wo.customer_id`
--     becomes a LEFT JOIN in app.py as part of this same increment -- an INNER JOIN
--     would silently drop internal-task WOs from every list/report/board they should
--     still appear on. Existing behavior for ordinary WOs (customer_id always
--     present) is unaffected: LEFT JOIN degrades to INNER JOIN's exact result set
--     when the joined column is never NULL.
--   * Internal-task WOs are not invoiceable (no customer to bill) -- guarded in
--     app.py's workorder_invoice_new, not by a schema constraint (an invoice
--     requires an actual customer_id on the invoices table too, so this is really
--     just an earlier, clearer error message).

ALTER TABLE work_orders
    ALTER COLUMN customer_id DROP NOT NULL;

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS is_internal_task BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'work_orders_customer_or_internal_chk'
    ) THEN
        ALTER TABLE work_orders
            ADD CONSTRAINT work_orders_customer_or_internal_chk
            CHECK (customer_id IS NOT NULL OR is_internal_task = TRUE);
    END IF;
END $$;
