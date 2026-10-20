-- FieldKit Migration 039
-- Adds: sales_tips; widens email_log.kind for the tip notification
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-10-20
--
-- Why this exists:
--   Chris, 2026-10-20: "there are times we have a tip for our salesman to
--   follow up on." The worked example: a tech on a job sees a property doing
--   a rehab with cabinet work, and the salesman should go and talk pricing.
--   A tip is a follow-up that nobody has visited yet: it shows wherever
--   follow-ups show, and a visit closes it.
--
-- Design notes:
--   * Its own table, not a row in sales_visits. Follow-ups live ON a visit
--     (sales_visits.follow_up_*), so the only way to carry a tip there would be
--     a fake visit, putting something that never happened into the visit log
--     managers read (same reasoning as migration 037 decoupling card photos
--     from visits).
--   * The property is OPTIONAL, with location_text as the fallback. Chris chose
--     this (option b) for now: a tech in a parking lot may only know "the
--     complex across from the Elm St job". The CHECK keeps a tip from being
--     anchored to nothing. When the salesman logs the visit, the wizard's
--     step 1 picks or creates the real property and the tip is tied to it
--     then (closed_visit_id plus property_type/property_id backfilled).
--     Future mobile app (Chris, 2026-10-20): Google Maps assisted location
--     lookup that auto-ties to an existing customer/prospect by address. That
--     will add columns here (place_id, latitude/longitude, formatted
--     address); nothing in this shape has to change for it.
--   * source_work_order_id records which job the tip came from when it was
--     sent from My Day. FK to work_orders, matching the WO's own lifecycle.
--   * status open/done/dismissed rather than a boolean, because the two ways a
--     tip closes mean different things: done = someone visited (closed_visit_id
--     says which visit); dismissed = judged a dead end, which needs a reason.
--   * created_by doubles as "spotted by". It's the username of whoever
--     submitted the tip, the same as every other created_by in the schema.

CREATE TABLE IF NOT EXISTS sales_tips (
    id                    SERIAL PRIMARY KEY,
    property_type         VARCHAR(20)
                          CONSTRAINT sales_tips_property_type_check
                          CHECK (property_type IN ('prospect', 'customer')),
    property_id           INTEGER,
    location_text         TEXT,
    notes                 TEXT NOT NULL,
    source_work_order_id  INTEGER REFERENCES work_orders(id),
    due_date              DATE NOT NULL,
    status                VARCHAR(20) NOT NULL DEFAULT 'open'
                          CONSTRAINT sales_tips_status_check
                          CHECK (status IN ('open', 'done', 'dismissed')),
    closed_visit_id       INTEGER REFERENCES sales_visits(id),
    closed_at             TIMESTAMP,
    closed_by             VARCHAR(100),
    dismiss_reason        TEXT,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by            VARCHAR(100),
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by            VARCHAR(100),
    deleted_at            TIMESTAMP NULL,
    deleted_by            VARCHAR(100),
    -- type and id travel together
    CONSTRAINT sales_tips_property_pair_check
        CHECK ((property_type IS NULL) = (property_id IS NULL)),
    -- never anchored to nothing: a real property, or at least a description
    CONSTRAINT sales_tips_anchor_check
        CHECK (property_id IS NOT NULL OR NULLIF(btrim(location_text), '') IS NOT NULL),
    CONSTRAINT sales_tips_dismiss_reason_check
        CHECK (status <> 'dismissed' OR NULLIF(btrim(dismiss_reason), '') IS NOT NULL)
);

-- The lists only ever ask for open tips by due date.
CREATE INDEX IF NOT EXISTS idx_sales_tips_open_due
    ON sales_tips (due_date)
    WHERE status = 'open' AND deleted_at IS NULL;

-- "Close any open tips for this property" runs on every visit save.
CREATE INDEX IF NOT EXISTS idx_sales_tips_open_property
    ON sales_tips (property_type, property_id)
    WHERE status = 'open' AND deleted_at IS NULL;

-- New tips email the office, Michael and the salesperson. Logged under their
-- own kind, same reasoning as migration 038.
ALTER TABLE email_log DROP CONSTRAINT IF EXISTS email_log_kind_check;

ALTER TABLE email_log
    ADD CONSTRAINT email_log_kind_check
    CHECK (kind IN ('alert', 'estimate', 'invoice', 'statement',
                    'price_list_request', 'customer_intake', 'sales_tip'));
