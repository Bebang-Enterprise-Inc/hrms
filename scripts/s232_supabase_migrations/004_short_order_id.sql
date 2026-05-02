-- S232 Migration 004 — Add short_order_id to pos_orders
-- Captures Mosaic's aggregator-side reference (e.g., FP-2502 for FoodPanda, GF-521F for Grab)
-- Verified present in API response for 17.2% of orders (43/250 at Araneta 2026-05-01).
-- NOT used as a dedup key (bill_number is sufficient) — captured for future aggregator reconciliation.

ALTER TABLE pos_orders
    ADD COLUMN IF NOT EXISTS short_order_id TEXT;

CREATE INDEX IF NOT EXISTS idx_pos_orders_short_order_id
    ON pos_orders (location_id, short_order_id)
    WHERE short_order_id IS NOT NULL;

COMMENT ON COLUMN pos_orders.short_order_id IS
  'S232: Mosaic aggregator-side reference. FP-XXXX for FoodPanda, GF-XXXX for GrabFood. NULL for in-store.';
