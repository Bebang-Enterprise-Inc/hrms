-- S165 — Mosaic POS Sync Verification
-- Ground-truth reconciliation of Mosaic meta.total vs pos_orders row counts.
-- Written nightly at 00:30 PHT by scripts/verify_mosaic_pos_sync.py.

CREATE TABLE IF NOT EXISTS sync_verification (
    location_id    INT NOT NULL,
    business_date  DATE NOT NULL,
    mosaic_total   INT,
    supabase_total INT,
    delta          INT GENERATED ALWAYS AS (COALESCE(mosaic_total,0) - COALESCE(supabase_total,0)) STORED,
    status         TEXT NOT NULL CHECK (status IN ('ok', 'missing', 'extra', 'healed', 'unresolved', 'api_error')),
    verified_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heal_attempted BOOL DEFAULT FALSE,
    error_message  TEXT,
    PRIMARY KEY (location_id, business_date, verified_at)
);

CREATE INDEX IF NOT EXISTS idx_sync_verification_status_recent
  ON sync_verification(status, verified_at DESC)
  WHERE status IN ('missing', 'unresolved', 'api_error');

CREATE INDEX IF NOT EXISTS idx_sync_verification_date
  ON sync_verification(business_date DESC);

COMMENT ON TABLE sync_verification IS
  'Ground-truth reconciliation of Mosaic POS vs Supabase pos_orders. Written nightly at 00:30 PHT by scripts/verify_mosaic_pos_sync.py. See S165.';
