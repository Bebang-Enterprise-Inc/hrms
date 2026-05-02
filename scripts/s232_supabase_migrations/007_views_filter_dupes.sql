-- S232 Migration 007 — Filter is_duplicate=true rows out of analytics views.
-- Resolves audit blocker B2 (analytics drift persists after dedup ships).
--
-- Strategy:
--   1. v_pos_orders_live is the most-used view (5 references in sales_dashboard.py + JOINs from
--      v_orders, v_monthly_store_summary, v_all_channel_daily, v_discount_identity_order_usage).
--      Adding the filter here cascades to all downstream JOIN-based views automatically.
--   2. v_ingestion_reconciliation, v_store_internet_health, v_webhook_coverage read pos_orders
--      directly (not via v_pos_orders_live). Each needs its own filter.
--   3. v_sync_drift_monitor uses v_pos_orders_live for the live count → benefits from #1.
--
-- This is a CREATE OR REPLACE — preserves all existing column shapes.

-- 1. v_pos_orders_live: cascade to all JOIN-based downstream views
CREATE OR REPLACE VIEW v_pos_orders_live AS
 SELECT id,
    location_id,
    business_date,
    bill_number,
    receipt_number,
    pax_count,
    service_type_id,
    original_gross_sales,
    gross_sales,
    net_sales,
    vatable_sales,
    vat_amount,
    vat_exempt_sales,
    zero_rated_sales,
    total_discounts,
    delivery_fee,
    payment_status,
    billed_at,
    paid_at,
    synced_at,
    updated_at,
    channel,
    service_channel_id,
    cancelled_at,
    cancellation_reason,
    order_status,
    completed_at
   FROM pos_orders
  WHERE (cancelled_at IS NULL)
    AND COALESCE(is_duplicate, false) = false;

-- 2. v_ingestion_reconciliation
CREATE OR REPLACE VIEW v_ingestion_reconciliation AS
 SELECT business_date,
    ingestion_source,
    count(*) AS order_count,
    sum(gross_sales) AS gross_sales
   FROM pos_orders
  WHERE (business_date >= (CURRENT_DATE - '30 days'::interval))
    AND COALESCE(is_duplicate, false) = false
  GROUP BY business_date, ingestion_source
  ORDER BY business_date DESC, ingestion_source;

-- 3. v_store_internet_health
CREATE OR REPLACE VIEW v_store_internet_health AS
 SELECT location_id,
    business_date,
    count(*) AS total_orders,
    count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)) AS webhook_orders,
    count(*) FILTER (WHERE (ingestion_source = 'poll'::text)) AS poll_only_orders,
    round(((100.0 * (count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS webhook_pct
   FROM pos_orders
  WHERE (business_date >= (CURRENT_DATE - '7 days'::interval))
    AND COALESCE(is_duplicate, false) = false
  GROUP BY location_id, business_date
 HAVING ((count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)))::numeric < ((count(*))::numeric * 0.5))
  ORDER BY (round(((100.0 * (count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)))::numeric) / (NULLIF(count(*), 0))::numeric), 1));

-- 4. v_webhook_coverage
CREATE OR REPLACE VIEW v_webhook_coverage AS
 SELECT business_date,
    count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)) AS webhook_orders,
    count(*) FILTER (WHERE (ingestion_source = 'poll'::text)) AS poll_only_orders,
    count(*) AS total_orders,
    round(((100.0 * (count(*) FILTER (WHERE (ingestion_source = 'webhook'::text)))::numeric) / (NULLIF(count(*), 0))::numeric), 1) AS webhook_coverage_pct
   FROM pos_orders
  WHERE (business_date >= (CURRENT_DATE - '30 days'::interval))
    AND COALESCE(is_duplicate, false) = false
  GROUP BY business_date
  ORDER BY business_date DESC;

-- v_sync_drift_monitor: no change needed — it uses v_pos_orders_live for the live count,
-- which now filters duplicates. The drift comparison still uses sync_verification (not pos_orders).
