-- S169 phase 1: lifecycle columns on pos_orders + new sync_verification status
BEGIN;

ALTER TABLE pos_orders
  ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
  ADD COLUMN IF NOT EXISTS order_status TEXT,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_pos_orders_cancelled_at_not_null
  ON pos_orders(location_id, business_date)
  WHERE cancelled_at IS NOT NULL;

COMMENT ON COLUMN pos_orders.cancelled_at IS
  'Set when Mosaic emits order.cancelled webhook, or when verify_mosaic_pos_sync.py tombstones an extra row. NULL = live order. See S169.';

-- Add extras_tombstoned to the sync_verification CHECK constraint
ALTER TABLE sync_verification DROP CONSTRAINT sync_verification_status_check;
ALTER TABLE sync_verification ADD CONSTRAINT sync_verification_status_check
  CHECK (status IN ('ok', 'missing', 'extra', 'healed', 'unresolved', 'api_error', 'extras_tombstoned'));

COMMIT;
