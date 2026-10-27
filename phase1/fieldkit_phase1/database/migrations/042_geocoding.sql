-- FieldKit Migration 042
-- Adds: map coordinates + geocoding bookkeeping on customers and sales_prospects
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-27
--
-- Why this exists:
--   The salesman's map (D-118, Chris 2026-10-27) pins every prospect and
--   customer, which needs coordinates. sales_prospects has had latitude/longitude
--   since migration 025 (never filled); customers had none.
--
-- Design notes:
--   * Geocoded with the US Census Bureau geocoder: free, no API key, and its
--     results are public domain, so they can be stored permanently. (Google's
--     terms restrict storing its coordinates; see the sales-tip location
--     assistant addendum.)
--   * geocoded_address is the exact address string that was sent. The nightly
--     job re-geocodes a row whenever its current address no longer matches it,
--     so an address edited in FieldKit moves its pin by the next morning with no
--     trigger and no hook on every save path.
--   * geocode_status records the outcome (matched / tie / no_match /
--     incomplete / error) so the office can see which addresses need fixing,
--     rather than those properties silently missing from the map.
--   * Census first; OpenStreetMap (Photon, ODbL) as a fallback for addresses
--     Census can't place, usually complexes too new for its street files. The
--     fallback is accepted only on an exact house number + ZIP/city match.
--     geocode_source records which one placed the pin.
--   * Customers are geocoded from the customer's own address. Service locations
--     aren't geocoded: the map shows properties, and the customer record is the
--     property.

ALTER TABLE customers
    ADD COLUMN IF NOT EXISTS latitude          DECIMAL(10, 8),
    ADD COLUMN IF NOT EXISTS longitude         DECIMAL(11, 8),
    ADD COLUMN IF NOT EXISTS geocoded_at       TIMESTAMP,
    ADD COLUMN IF NOT EXISTS geocode_status    VARCHAR(20)
        CONSTRAINT customers_geocode_status_check
        CHECK (geocode_status IN ('matched', 'tie', 'no_match', 'incomplete', 'error')),
    ADD COLUMN IF NOT EXISTS geocoded_address  TEXT,
    ADD COLUMN IF NOT EXISTS geocode_source    VARCHAR(10);

ALTER TABLE sales_prospects
    ADD COLUMN IF NOT EXISTS geocoded_at       TIMESTAMP,
    ADD COLUMN IF NOT EXISTS geocode_status    VARCHAR(20)
        CONSTRAINT sales_prospects_geocode_status_check
        CHECK (geocode_status IN ('matched', 'tie', 'no_match', 'incomplete', 'error')),
    ADD COLUMN IF NOT EXISTS geocoded_address  TEXT,
    ADD COLUMN IF NOT EXISTS geocode_source    VARCHAR(10);
