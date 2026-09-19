-- FieldKit Migration 011
-- Payments, applications, adjustments, and the payment-methods lookup
-- (build directive Stage 1, Increment 1.4).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   Increment 1.2 built invoice_balance() and the reopen/void payment guards ALREADY
--   written against this exact schema, gated behind to_regclass() so they were
--   vacuously "no payments possible yet" until this migration landed (see
--   docs/DECISIONS-MADE-DURING-BUILD.md D-009). This migration makes that real: from
--   here on, invoice_balance() actually subtracts applied payments and adjustments,
--   and the reopen/void guards actually enforce.
--
-- Design notes:
--   * payment_applications is APPEND-ONLY by design (no updated_at, no deleted_at) --
--     un-applying a payment inserts a reversal row (reverses_application_id, negative
--     amount) rather than mutating or deleting the original. This is the same
--     Pattern 2 (supersede, never mutate) the invoice engine already follows, applied
--     to money movement: the full history of what was applied and un-applied is
--     always reconstructable from the table itself.
--   * "Unapplied amount on a payment IS the credit" -- there is no separate credits
--     table. A payment's unapplied balance = payments.amount - refunded_amount -
--     SUM(non-reversed payment_applications.amount for that payment). Computed, not
--     stored (see customer_unapplied_credit() in app.py).
--   * invoice_adjustments reduces a receivable's balance directly (write-offs,
--     discounts, late fees) -- NOT a payment, no money changed hands. Positive amount
--     reduces balance, per the directive.
--   * v_invoice_balances is created here (not in migration 010) because it's the
--     first point these tables actually exist -- CREATE VIEW can't reference a table
--     that doesn't exist yet, unlike the Python helper which was written against this
--     schema two increments early and simply guarded with to_regclass().

CREATE TABLE IF NOT EXISTS payment_methods (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    requires_reference BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100),
    UNIQUE (name)
);

INSERT INTO payment_methods (name, requires_reference, sort_order) VALUES
    ('Check',      TRUE,  1),
    ('Credit Card', FALSE, 2),
    ('Paymode-X',  TRUE,  3),
    ('ACH',        TRUE,  4),
    ('Cash',       FALSE, 5),
    ('Other',      FALSE, 6)
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    payment_date DATE NOT NULL,                    -- effective/cash-basis date
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    payment_method_id INTEGER REFERENCES payment_methods(id),
    reference_number VARCHAR(100),
    notes TEXT,

    status VARCHAR(12) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'voided')),
    voided_at TIMESTAMP,
    voided_by VARCHAR(100),
    void_reason TEXT,

    refunded_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    refunded_at TIMESTAMP,
    refund_reference VARCHAR(100),
    refund_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS payment_applications (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(id),
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount NUMERIC(12,2) NOT NULL,                 -- negative on a reversal row
    applied_date DATE NOT NULL,
    reverses_application_id INTEGER REFERENCES payment_applications(id),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
    -- APPEND ONLY, deliberately: no updated_at/deleted_at. Un-applying inserts a
    -- reversal row; nothing here is ever mutated or removed.
);

CREATE INDEX IF NOT EXISTS idx_pa_payment ON payment_applications(payment_id);
CREATE INDEX IF NOT EXISTS idx_pa_invoice ON payment_applications(invoice_id);
CREATE INDEX IF NOT EXISTS idx_pa_open ON payment_applications(invoice_id) WHERE reverses_application_id IS NULL;

CREATE TABLE IF NOT EXISTS invoice_adjustments (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    effective_date DATE NOT NULL,
    amount NUMERIC(12,2) NOT NULL,                 -- positive reduces balance
    adjustment_type VARCHAR(20) NOT NULL CHECK (adjustment_type IN ('write_off', 'discount', 'late_fee', 'other')),
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,                     -- soft-delete allowed only same-day
    deleted_by VARCHAR(100)                        -- by the same user; app enforces this,
                                                     -- not the DB (see _delete_invoice_adjustment)
);

CREATE INDEX IF NOT EXISTS idx_ia_invoice ON invoice_adjustments(invoice_id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS payment_status_history (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER NOT NULL REFERENCES payments(id),
    event VARCHAR(30) NOT NULL,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_psh_payment ON payment_status_history(payment_id);

-- Same math as invoice_balance() in app.py, for list pages and the billing page
-- (the balance() Python helper is what individual pages and routes use; this view
-- is for set-based queries like "every invoice with a balance").
CREATE OR REPLACE VIEW v_invoice_balances AS
SELECT
    i.id AS invoice_id,
    COALESCE(iv.total, iv.subtotal) AS gross,
    COALESCE(pa.applied, 0) AS applied,
    COALESCE(adj.adjusted, 0) AS adjusted,
    COALESCE(iv.total, iv.subtotal) - COALESCE(pa.applied, 0) - COALESCE(adj.adjusted, 0) AS balance
FROM invoices i
LEFT JOIN invoice_versions iv ON iv.id = i.current_version_id
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS applied
    FROM payment_applications
    WHERE reverses_application_id IS NULL
    GROUP BY invoice_id
) pa ON pa.invoice_id = i.id
LEFT JOIN (
    SELECT invoice_id, SUM(amount) AS adjusted
    FROM invoice_adjustments
    WHERE deleted_at IS NULL
    GROUP BY invoice_id
) adj ON adj.invoice_id = i.id
WHERE i.deleted_at IS NULL;
