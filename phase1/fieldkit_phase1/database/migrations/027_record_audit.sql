-- FieldKit Migration 027
-- Adds: record_audit
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   Build directive Stage 4, Increment 5.3 (§5.3): a table_name/record_id/action/
--   changed_by/changed_at/diff audit trail written by the save paths of customers,
--   contacts, locations, work orders, invoices/versions, payments, estimates,
--   catalog, tax rates, and users, read by a "History" panel on customer/WO/
--   invoice/payment detail and an admin-only global view.
--
-- Design notes:
--   * Append-only (no updated_at/deleted_at) -- same convention as
--     contact_property_history/estimate_status_history/customer_merge_log: an
--     audit row is never edited or removed, only ever added to. Auditing its own
--     audit trail would be a strange category error.
--   * diff is JSONB, not a full before/after row snapshot -- {"column": {"old":
--     ..., "new": ...}} for only the columns that actually changed on an update,
--     or the full new-row dict on a create, or the full pre-delete row dict on a
--     soft-delete. Keeps rows small and the History panel's rendering simple
--     (iterate diff.keys()) without needing two full row snapshots per write.
--   * table_name is a plain VARCHAR, not a foreign key or CHECK-constrained enum
--     -- record_audit outlives any one entity type's schema and is written from
--     many different call sites; a hard-coded list here would just be one more
--     thing to keep in sync by hand.
CREATE TABLE IF NOT EXISTS record_audit (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    diff JSONB,

    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_record ON record_audit(table_name, record_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user ON record_audit(changed_by, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON record_audit(changed_at DESC);
