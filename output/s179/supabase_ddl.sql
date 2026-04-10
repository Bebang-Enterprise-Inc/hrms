-- S179 Product Mix Per Channel - Supabase DDL
-- Executed: 2026-04-10

-- 1. Materialized View
CREATE MATERIALIZED VIEW product_channel_daily_mix AS
SELECT
  po.business_date,
  po.location_id,
  po.channel,
  pi.product_name,
  ARRAY_AGG(DISTINCT pi.product_id) AS product_ids,
  SUM(pi.quantity)::INT AS total_quantity,
  SUM(pi.gross_sales)::NUMERIC(15,2) AS total_gross_sales,
  SUM(pi.net_sales)::NUMERIC(15,2) AS total_net_sales,
  SUM(pi.vat_amount)::NUMERIC(15,2) AS total_vat_amount,
  SUM(pi.discount_amount)::NUMERIC(15,2) AS total_discount_amount,
  ROUND(AVG(pi.unit_price)::NUMERIC, 2) AS avg_unit_price,
  MIN(pi.unit_price)::NUMERIC(10,2) AS min_unit_price,
  MAX(pi.unit_price)::NUMERIC(10,2) AS max_unit_price,
  COUNT(DISTINCT po.id)::INT AS order_count
FROM pos_order_items pi
JOIN pos_orders po ON po.id = pi.order_id
WHERE po.payment_status = 'PAID'
GROUP BY po.business_date, po.location_id, po.channel, pi.product_name;

-- 2. UNIQUE INDEX (required for REFRESH CONCURRENTLY)
CREATE UNIQUE INDEX idx_pcdm_unique_grain
  ON product_channel_daily_mix (business_date, location_id, channel, product_name);

-- 3. Covering index for product_name queries
CREATE INDEX idx_pcdm_product
  ON product_channel_daily_mix (product_name);

-- 4. RPC wrapper function for hourly refresh via PostgREST
CREATE OR REPLACE FUNCTION public.refresh_product_channel_daily_mix()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET statement_timeout = '120s'
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY product_channel_daily_mix;
END;
$$;

-- 5. PostgREST access grants
GRANT SELECT ON product_channel_daily_mix TO anon, authenticated, service_role;
