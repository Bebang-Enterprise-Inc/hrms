-- S232 Migration 003 — pos_orders dedup fields (additive only, idempotent)
-- These columns were added in Phase 0.6 backfill via ALTER TABLE IF NOT EXISTS;
-- this migration formalizes the schema for future runs.

ALTER TABLE pos_orders
    ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS kept_order_id BIGINT,
    ADD COLUMN IF NOT EXISTS webhook_received_at TIMESTAMPTZ;

ALTER TABLE pos_order_items
    ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false;

ALTER TABLE pos_order_payments
    ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_pos_orders_is_duplicate
    ON pos_orders (is_duplicate) WHERE is_duplicate = true;

CREATE INDEX IF NOT EXISTS idx_pos_orders_kept_order_id
    ON pos_orders (kept_order_id) WHERE kept_order_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pos_order_items_is_duplicate
    ON pos_order_items (is_duplicate) WHERE is_duplicate = true;

COMMENT ON COLUMN pos_orders.is_duplicate IS
  'S232: true if this row is a duplicate of another (location_id, business_date, bill_number). '
  'kept_order_id points to the canonical row. Analytics views must filter WHERE is_duplicate = false.';

COMMENT ON COLUMN pos_orders.webhook_received_at IS
  'S232: when the webhook arrived; used as a fallback discriminator when bill_number is NULL. '
  'Backfilled from paid_at for historical poll-ingested rows.';
