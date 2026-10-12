-- FieldKit Migration 037
-- Adds: sales_visit_photos.property_id / property_type; visit_id becomes nullable
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-12
--
-- Chris, 2026-10-12: a card photo should be addable to a prospect WITHOUT
-- logging a visit. Migration 032 hung photos off sales_visits exclusively
-- (visit_id NOT NULL) on the reasoning that a photo always came out of a
-- visit. That turns out to be too narrow -- a card arrives at a trade show, in
-- the post, handed over in a car park -- and forcing a fake visit to attach one
-- would corrupt the visit log, which is the one record managers read.
--
-- So a photo now belongs to a PROPERTY, and optionally also to the visit it was
-- taken on.
--
-- Design notes:
--   * property_id/property_type are polymorphic (prospect or customer), matching
--     sales_visits and every other sales_* table. No FK is possible, same as
--     elsewhere -- there is no single table to point at.
--   * Existing rows are backfilled from their visit, so EVERY photo has a
--     property regardless of how it arrived. That keeps the queries uniform:
--     nothing has to ask "visit photo or property photo?" to find out where a
--     card belongs, it just reads property_id. This is the point of doing the
--     backfill rather than leaving old rows NULL.
--   * The CHECK enforces that a photo is anchored to something. visit_id may
--     now be NULL, but property_id/property_type may not -- a photo that
--     belongs to nothing is unreachable from the UI and would sit in the
--     pending-cards queue forever with no property name against it.
--   * Deleting a photo stays a SOFT delete (CLAUDE.md), and deliberately leaves
--     the file on disk -- migration 032's reasoning, unchanged: a mis-tap must
--     not destroy the only record of someone's contact details. Chris asked for
--     a delete button for bad shots; soft delete is what that button does.

ALTER TABLE sales_visit_photos
    ADD COLUMN IF NOT EXISTS property_id   INTEGER,
    ADD COLUMN IF NOT EXISTS property_type VARCHAR(20);

-- Every existing photo came from a visit, so its property is the visit's.
UPDATE sales_visit_photos p
SET property_id   = sv.property_id,
    property_type = sv.property_type
FROM sales_visits sv
WHERE sv.id = p.visit_id
  AND p.property_id IS NULL;

ALTER TABLE sales_visit_photos ALTER COLUMN visit_id DROP NOT NULL;

-- Added only once the backfill above has run, or it would reject the table.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_visit_photos_anchored') THEN
        ALTER TABLE sales_visit_photos
            ADD CONSTRAINT chk_visit_photos_anchored
            CHECK (property_id IS NOT NULL AND property_type IN ('prospect', 'customer'));
    END IF;
END $$;

-- "Which cards belong to this property?" -- the prospect page's gallery.
CREATE INDEX IF NOT EXISTS idx_visit_photos_property
    ON sales_visit_photos(property_type, property_id)
    WHERE deleted_at IS NULL;
