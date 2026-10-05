-- FieldKit Migration 032
-- Adds: sales_visit_photos
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-05
--
-- Why this exists:
--   Chris, 2026-10-05: the sales workflow is driven by logging visits, and a
--   salesperson standing in a leasing office does not have time to type a
--   business card into a form. He photographs the card, logs the visit in
--   seconds, and the card gets transcribed into a real contact later.
--
--   So a visit can carry photos, and a photo tracks whether anyone has
--   actually turned it into a contact yet. That last part is the point:
--   without it, cards get photographed and forgotten. `transcribed_at IS NULL`
--   is the "cards awaiting entry" queue on the sales dashboard, and creating a
--   contact from a card clears it.
--
-- Design notes:
--   * Hangs off sales_visits, not sales_contacts, because the whole reason the
--     photo exists is that the contact does NOT exist yet. `contact_id` is
--     filled in afterwards, when the card becomes a real contact — so the
--     chain card -> contact stays visible.
--   * A real FK to sales_visits (unlike the sales_* property_id columns, which
--     are polymorphic and can't have one). contact_id gets an FK too; both
--     point at exactly one table.
--   * Image bytes live on disk at $UPLOAD_DIR/<company_key>/sales/<stored_filename>,
--     the same host-folder arrangement migration 030 introduced for signed
--     release forms (./uploads -> /data/uploads in docker-compose.yml). The DB
--     holds metadata only.
--   * stored_filename is always app-generated (visit<id>_<random>.<ext>), never
--     the uploaded name — same rule as work_order_attachments. Phone cameras
--     produce names like "IMG_0042.HEIC" that collide constantly, and more
--     importantly a user-supplied string must never reach a path we open.
--   * Soft delete per CLAUDE.md's blanket rule. Deleting a photo marks the row
--     and deliberately leaves the file on disk — the same reasoning as the
--     release forms, and it means a mis-tap can't destroy the only record of
--     someone's contact details.
--   * No OCR. Chris asked for photos specifically so details could be entered
--     manually later; reading cards automatically is a separate decision with
--     its own accuracy problems, and nothing here forecloses adding it.

CREATE TABLE IF NOT EXISTS sales_visit_photos (
    id                SERIAL PRIMARY KEY,
    visit_id          INTEGER NOT NULL REFERENCES sales_visits(id),
    photo_kind        VARCHAR(30) NOT NULL DEFAULT 'business_card',

    original_filename VARCHAR(255),
    stored_filename   VARCHAR(255) NOT NULL,
    content_type      VARCHAR(100),
    byte_size         INTEGER,

    -- the "awaiting entry" queue: NULL = nobody has typed this card in yet
    transcribed_at    TIMESTAMP NULL,
    transcribed_by    VARCHAR(100),
    contact_id        INTEGER NULL REFERENCES sales_contacts(id),
    notes             TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_visit_photos_visit
    ON sales_visit_photos(visit_id) WHERE deleted_at IS NULL;
-- Drives the dashboard queue, so it's indexed for exactly that question.
CREATE INDEX IF NOT EXISTS idx_visit_photos_pending
    ON sales_visit_photos(created_at DESC)
    WHERE transcribed_at IS NULL AND deleted_at IS NULL;
