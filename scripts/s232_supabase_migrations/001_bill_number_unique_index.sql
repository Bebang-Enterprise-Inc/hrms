-- S232 Migration 001 — Unique partial index on pos_orders natural key
-- Resolves audit A1 (must run AFTER Phase 0.6 backfill flagged existing dupes)
--
-- The WHERE clause `AND is_duplicate = false` is critical: it allows the index
-- to ship despite the 2,462 historical dupes that Phase 0.6 marked. Going forward,
-- new INSERTs with a colliding bill_number for an existing live (non-duplicate)
-- order will fail with PG error 23505 (unique violation). The poll script
-- handles 23505 by routing the rejected row to pos_duplicates.
--
-- Idempotent: uses IF NOT EXISTS pattern via dropping/recreating-conditional.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname = 'pos_orders_bill_number_natural_key'
  ) THEN
    CREATE UNIQUE INDEX pos_orders_bill_number_natural_key
      ON pos_orders (location_id, business_date, bill_number)
      WHERE bill_number IS NOT NULL AND is_duplicate = false;
  END IF;
END $$;

-- Sanity check: confirm the index exists
SELECT 'pos_orders_bill_number_natural_key' AS index_name,
       EXISTS (
         SELECT 1 FROM pg_indexes
         WHERE schemaname = 'public'
           AND indexname = 'pos_orders_bill_number_natural_key'
       ) AS exists_after_migration;
