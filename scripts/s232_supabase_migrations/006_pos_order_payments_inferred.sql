-- S232 Migration 006 — add `inferred` column to pos_order_payments.
-- Phase 4 — aggregator payment inference for orders with empty payment_methods.
-- All historical rows: inferred = false (existing payments are real).

ALTER TABLE pos_order_payments
    ADD COLUMN IF NOT EXISTS inferred BOOLEAN DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_pos_order_payments_inferred
    ON pos_order_payments (inferred) WHERE inferred = true;

COMMENT ON COLUMN pos_order_payments.inferred IS
  'S232: true when payment_type was synthesized by infer_payment_type() because the '
  'Mosaic webhook payload arrived with empty payment_methods on an aggregator order. '
  '~2% of FoodPanda/GrabFood orders match this pattern.';
