-- FieldKit Migration 016
-- Adds: frozen tax-component columns on invoice_versions, for the NC cash-basis
--       tax report (build directive Stage 1, Increment 1.10).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-19
--
-- Why this exists:
--   The tax report groups cash received by county and splits it into
--   state/county/transit reporting components (NC form E-500 layout). The rate that
--   applied is already frozen on the version as a single combined tax_rate_pct at
--   harden time (migration 010) -- correct for computing the invoice's tax_total, but
--   not enough to split that total back into its components without re-deriving from
--   tax_rates, which the freeze discipline established in this build (D-025, the PDF
--   invariant work; the equipment-label bake in transition_invoice's Hardened branch)
--   specifically avoids: a hardened invoice's downstream artifacts should never need
--   to re-read a table that can change after the fact. So this migration freezes the
--   state_pct/county_pct/transit_pct actually in effect at harden, straight from the
--   same tax_rates row _compute_invoice_tax() already looked up -- no new lookup
--   logic, just capturing more of what that function already resolves.
--
--   taxable_subtotal is also frozen here, one column beyond what the directive named
--   (state_pct/county_pct/transit_pct only) -- see docs/DECISIONS-MADE-DURING-BUILD.md
--   for why: the report's own formula ("taxable base = applied x (taxable subtotal /
--   total)") needs a taxable-only figure that invoice_versions.subtotal does NOT
--   provide (subtotal totals ALL lines, taxable or not -- e.g. an imported-balance
--   line or a non-taxable service line). Storing it directly avoids back-deriving it
--   from tax_total/tax_rate_pct (division by a frozen rate that can legitimately be
--   0%, which would make that derivation undefined for untaxed versions).
--
-- Design notes:
--   * All four columns NULL until harden, same discipline as tax_rate_pct/tax_total/
--     total (migration 010) -- a Live version has no frozen tax yet.
--   * Backfill DO block updates any already-Hardened-or-later version that predates
--     this migration, re-deriving from tax_rates as of invoice_date (same lookup
--     _compute_invoice_tax already performs) -- a no-op today since production has
--     zero real invoices (all Increment 1.1-1.9 work used only test fixtures that
--     were hard-deleted after each smoke test), but correct if this migration is ever
--     applied to a DB that already has real hardened invoices.

ALTER TABLE invoice_versions
    ADD COLUMN IF NOT EXISTS state_pct         NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS county_pct         NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS transit_pct        NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS taxable_subtotal   NUMERIC(12,2);

DO $$
DECLARE
    v RECORD;
    r RECORD;
    inv_date DATE;
    taxable NUMERIC(12,2);
BEGIN
    FOR v IN
        SELECT iv.id, iv.tax_county, iv.invoice_id
        FROM invoice_versions iv
        WHERE iv.state IN ('Hardened', 'Sent', 'Superseded')
          AND iv.deleted_at IS NULL
          AND iv.state_pct IS NULL
    LOOP
        SELECT invoice_date INTO inv_date FROM invoices WHERE id = v.invoice_id;

        SELECT COALESCE(SUM(total) FILTER (WHERE is_taxable), 0) INTO taxable
        FROM invoice_version_line_items
        WHERE version_id = v.id AND deleted_at IS NULL;

        UPDATE invoice_versions SET taxable_subtotal = taxable WHERE id = v.id;

        IF v.tax_county IS NOT NULL AND inv_date IS NOT NULL THEN
            SELECT state_pct, county_pct, transit_pct INTO r
            FROM tax_rates
            WHERE county = v.tax_county AND deleted_at IS NULL
              AND effective_from <= inv_date
              AND (effective_to IS NULL OR effective_to >= inv_date);

            IF FOUND THEN
                UPDATE invoice_versions
                SET state_pct = r.state_pct, county_pct = r.county_pct, transit_pct = r.transit_pct
                WHERE id = v.id;
            END IF;
        END IF;
    END LOOP;
END $$;
