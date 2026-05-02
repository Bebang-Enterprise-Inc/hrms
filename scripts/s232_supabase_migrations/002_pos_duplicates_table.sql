-- S232 Migration 002 — pos_duplicates audit table
-- Renamed from "webhook_duplicates" per audit H4 (99.95% of dedups are poll-source)
-- Captures rejected payloads when bill_number twin found OR PostgREST 409 race occurs.

CREATE TABLE IF NOT EXISTS pos_duplicates (
    order_id BIGINT PRIMARY KEY,
    kept_order_id BIGINT NOT NULL,
    location_id BIGINT NOT NULL,
    business_date DATE NOT NULL,
    bill_number INT,
    source TEXT NOT NULL CHECK (source IN ('poll', 'webhook')),
    payload JSONB NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT NOT NULL CHECK (reason IN ('bill_number_twin', 'race_409', 'cluster_window_match', 'null_bill_cluster')),
    -- Indexes for audit queries
    CONSTRAINT pos_duplicates_kept_fk_check CHECK (kept_order_id <> order_id)
);

CREATE INDEX IF NOT EXISTS idx_pos_duplicates_kept ON pos_duplicates (kept_order_id);
CREATE INDEX IF NOT EXISTS idx_pos_duplicates_business_date ON pos_duplicates (business_date);
CREATE INDEX IF NOT EXISTS idx_pos_duplicates_location_business_bill ON pos_duplicates (location_id, business_date, bill_number);
CREATE INDEX IF NOT EXISTS idx_pos_duplicates_rejected_at ON pos_duplicates (rejected_at DESC);

COMMENT ON TABLE pos_duplicates IS
  'S232: audit table for transactions rejected by the bill_number-natural-key dedup logic. '
  'Each row represents a duplicate payload (different Mosaic id, same physical transaction). '
  'kept_order_id points to the pos_orders.id that was retained.';
