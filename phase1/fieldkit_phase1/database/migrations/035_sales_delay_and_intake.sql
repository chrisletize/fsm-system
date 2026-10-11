-- FieldKit Migration 035
-- Adds: sales-delay columns on sales_prospects AND customers,
--       new-customer intake fields on sales_prospects
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-11
--
-- Two features from Chris, 2026-10-11.
--
-- 1. SALES DELAY
--    Some properties should not be visited at all for a while -- the example
--    given was one we're suing for non-payment. A visit there is worse than no
--    visit. So a property can be put on hold for 6 or 12 months with a reason.
--
--    It applies to BOTH prospects and customers, because the case Chris
--    described is an existing customer, and sales_visits can be logged against
--    either. Hence the same four columns on both tables.
--
--    Crucially the salesperson can only REQUEST a delay, never apply one --
--    Chris was explicit. The request rides the existing approval_queue
--    (request_type 'delay_sales'), the same machinery that already gates a
--    prospect becoming a customer, and a manager approving it is what actually
--    writes these columns. That keeps "stop selling to this property" a
--    decision with a name against it, and it means no new approval plumbing.
--
-- 2. NEW-CUSTOMER INTAKE
--    The paper "New Customer Information" sheet becomes a wizard the property
--    manager fills in themselves on the salesperson's tablet. These columns
--    hold what that sheet collects and sales_prospects didn't already have.
--
--    billing_email is separate from general_email on purpose: the sheet asks
--    for both, and they genuinely differ -- the leasing office inbox is not
--    where invoices get paid from. (Same reasoning as migration 034's note
--    about not auto-filling customers.billing_email.)
--
--    The three portal booleans mirror PORTAL_TYPES ('OPS', 'VendorCafe',
--    'Paymode-X') which already exist for customers in
--    customer_compliance_portals. They're captured here as plain flags because
--    a prospect has no customer_id to hang a portal row off yet; real portal
--    rows get created at conversion. management_software is NOT a portal --
--    the handwritten "Yardi" on the sheet is the management system itself,
--    and VendorCafe is merely Yardi's vendor portal.
--
--    intake_completed_by_name/_title record WHO filled it in, which the paper
--    form never captured and which matters when the details are later
--    disputed.

-- ---------------------------------------------------------------- 1. delay
ALTER TABLE sales_prospects
    ADD COLUMN IF NOT EXISTS sales_delayed_until DATE NULL,
    ADD COLUMN IF NOT EXISTS sales_delay_reason  TEXT,
    ADD COLUMN IF NOT EXISTS sales_delay_set_by  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS sales_delay_set_at  TIMESTAMP NULL;

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS sales_delayed_until DATE NULL,
    ADD COLUMN IF NOT EXISTS sales_delay_reason  TEXT,
    ADD COLUMN IF NOT EXISTS sales_delay_set_by  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS sales_delay_set_at  TIMESTAMP NULL;

-- --------------------------------------------------------------- 2. intake
ALTER TABLE sales_prospects
    ADD COLUMN IF NOT EXISTS billing_email             VARCHAR(255),
    ADD COLUMN IF NOT EXISTS management_software       VARCHAR(80),
    ADD COLUMN IF NOT EXISTS portal_ops                BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS portal_vendorcafe         BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS portal_paymode            BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS intake_completed_at       TIMESTAMP NULL,
    ADD COLUMN IF NOT EXISTS intake_completed_by_name  VARCHAR(150),
    ADD COLUMN IF NOT EXISTS intake_completed_by_title VARCHAR(150);

-- Drives "is this property on hold" checks on every sales list, so both get an
-- index on exactly that question.
CREATE INDEX IF NOT EXISTS idx_prospects_delayed
    ON sales_prospects(sales_delayed_until)
    WHERE sales_delayed_until IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_customers_delayed
    ON customers(sales_delayed_until)
    WHERE sales_delayed_until IS NOT NULL AND deleted_at IS NULL;
