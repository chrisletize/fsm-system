-- FieldKit Migration 043
-- Adds: customer_type 'Resident Pays'; customer_category_reviews (review queue)
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-27
--
-- Why this exists:
--   The customer category audit (D-119, Chris 2026-10-27). The June
--   ServiceFusion import defaulted every unrecognised name to 'Multi Family', so
--   thousands of individual people are filed as apartment complexes.
--
--   * 'Resident Pays': tenants who pay directly for a carpet cleaning their
--     complex doesn't offer. Chris: "resident pays really only exists with
--     carpet cleaning", and it sums up every individual Kleanit customer, so the
--     two Kleanits use Resident Pays INSTEAD of Residential, Get a Grip uses
--     Residential only, and CTS (umbrella: Get a Grip franchise + Kleanit) uses
--     both. Which types each company offers is application config
--     (COMPANY_CUSTOMER_TYPES in app.py). The CHECK below is the union, so the
--     schema stays identical across all four databases.
--   * customer_category_reviews: proposals the audit wasn't confident about,
--     waiting for someone in the office to accept or correct them on
--     /<company>/settings/customer-categories. Confident proposals are applied
--     directly and recorded in record_audit; this table holds only the rest.
--     It keeps decided rows (status <> 'pending') as the record of who decided
--     what.
--
-- sales_prospects.customer_type is NOT widened: prospects are properties the
-- salesman pursues, and a resident is never one.

ALTER TABLE customers DROP CONSTRAINT IF EXISTS customers_customer_type_check;
ALTER TABLE customers
    ADD CONSTRAINT customers_customer_type_check
    CHECK (customer_type IN ('Multi Family', 'Contractors', 'Residential', 'Commercial', 'Resident Pays'));

CREATE TABLE IF NOT EXISTS customer_category_reviews (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    current_type    VARCHAR(30),
    proposed_type   VARCHAR(30) NOT NULL,
    confidence      VARCHAR(10) NOT NULL
                    CONSTRAINT customer_category_reviews_confidence_check
                    CHECK (confidence IN ('high', 'medium', 'low')),
    reasons         TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CONSTRAINT customer_category_reviews_status_check
                    CHECK (status IN ('pending', 'accepted', 'changed', 'kept')),
    decided_type    VARCHAR(30),
    decided_by      VARCHAR(100),
    decided_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by      VARCHAR(100),
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by      VARCHAR(100),
    deleted_at      TIMESTAMP NULL,
    deleted_by      VARCHAR(100)
);

-- One open review per customer at a time.
CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_category_reviews_one_pending
    ON customer_category_reviews (customer_id)
    WHERE status = 'pending' AND deleted_at IS NULL;
