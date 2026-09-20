-- FieldKit Migration 022
-- Adds: customer_ratings (build directive Stage 3, Increment 3.2, per the
--       duration/rating addendum §14).
-- Run on: all four databases (Get a Grip, Kleanit Charlotte, CTS, Kleanit South Florida)
-- Date: 2026-09-20
--
-- Why this exists:
--   A letter-grade quick-glance signal per customer, recomputed nightly (same
--   pattern as the Delinquent Account auto-tag / customer_flags, migration 020) from
--   payment timeliness, cancellation rate, and job volume, with a manager override on
--   top so staff see the algorithm's read and the human judgment call side by side.
--
-- Design notes:
--   * One row per customer (customer_id PK), replaced wholesale each nightly run --
--     same "current answer, not history" shape as customer_flags.
--   * The three *_score columns are SIGNED contributions to the 100-point base (a
--     penalty is negative, the volume bonus is positive), not raw 0-100 sub-scores --
--     this makes composite_score = 100 + payment_timeliness_score +
--     cancellation_score + job_volume_score (then clamped) a direct, auditable sum
--     rather than a weighted-average formula hidden in application code.
--   * manager_adjustment is a numeric point delta (not a direct letter-grade
--     override) -- "a delta plus a required note" per the addendum -- applied on top
--     of composite_score before re-banding into adjusted_letter_grade. Clearing the
--     override (NULL) reverts display to the algorithmic grade.
--   * letter_grade/adjusted_letter_grade are computed in Python (band edges are a
--     tuning knob per the directive: "Constants at the top of jobs.py for tuning" --
--     see app.py's RATING_BANDS near _job_recompute_customer_ratings) and stored as
--     plain columns rather than a CHECK-constrained/generated column, so a future
--     band retune doesn't require a migration.

CREATE TABLE IF NOT EXISTS customer_ratings (
    customer_id                 INTEGER PRIMARY KEY REFERENCES customers(id),
    job_volume_score             NUMERIC(6,2) NOT NULL DEFAULT 0,
    payment_timeliness_score     NUMERIC(6,2) NOT NULL DEFAULT 0,
    cancellation_score           NUMERIC(6,2) NOT NULL DEFAULT 0,
    composite_score               NUMERIC(5,2) NOT NULL DEFAULT 100,
    letter_grade                  VARCHAR(1) NOT NULL DEFAULT 'A' CHECK (letter_grade IN ('A','B','C','D','F')),

    manager_adjustment            NUMERIC(6,2),
    manager_adjustment_note       TEXT,
    manager_adjustment_by         VARCHAR(100),
    manager_adjustment_at         TIMESTAMP,
    adjusted_letter_grade         VARCHAR(1) NOT NULL DEFAULT 'A' CHECK (adjusted_letter_grade IN ('A','B','C','D','F')),

    last_calculated_at            TIMESTAMP,
    calculated_by                 VARCHAR(100) NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_customer_ratings_grade
    ON customer_ratings(adjusted_letter_grade);
