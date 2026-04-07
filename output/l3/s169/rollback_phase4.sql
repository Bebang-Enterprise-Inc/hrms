-- S169 Phase 4 ROLLBACK
BEGIN;
DROP VIEW IF EXISTS public.v_discount_identity_rolling_30d_usage CASCADE;
DROP VIEW IF EXISTS public.v_discount_identity_order_usage CASCADE;
DROP VIEW IF EXISTS public.v_monthly_store_summary CASCADE;
DROP VIEW IF EXISTS public.v_orders CASCADE;
DROP VIEW IF EXISTS public.v_system_daily_totals CASCADE;
DROP VIEW IF EXISTS public.v_ops_weekly CASCADE;
DROP VIEW IF EXISTS public.v_all_channel_daily CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.store_daily_baselines CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.payment_reconciliation CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.sales_dashboard_daily_store_metrics CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.store_daily_closing CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.daily_revenue CASCADE;
DROP MATERIALIZED VIEW IF EXISTS public.discount_summary CASCADE;

-- restore MV: discount_summary
CREATE MATERIALIZED VIEW public.discount_summary AS
 SELECT s.store_name,
    s.legal_entity,
    o.business_date,
    i.discount_name,
    dt.bir_category,
    dt.is_vat_exempt,
    count(DISTINCT o.id) AS order_count,
    count(*) AS item_count,
    sum(i.discount_amount) AS total_discount_amount,
    sum(i.vat_exempt_sales) AS vat_exempt_amount
   FROM (((pos_order_items i
     JOIN pos_orders o ON ((o.id = i.order_id)))
     JOIN stores s ON ((s.location_id = o.location_id)))
     LEFT JOIN discount_types dt ON ((dt.id = i.discount_id)))
  WHERE (i.discount_id IS NOT NULL)
  GROUP BY s.store_name, s.legal_entity, o.business_date, i.discount_name, dt.bir_category, dt.is_vat_exempt;

-- restore MV: daily_revenue
CREATE MATERIALIZED VIEW public.daily_revenue AS
 SELECT s.store_name,
    s.legal_entity,
    s.erpnext_cost_center,
    o.business_date,
    'POS'::text AS channel,
    count(*) AS order_count,
    sum(o.original_gross_sales) AS gross_revenue,
    sum(o.total_discounts) AS total_discounts,
    sum(o.gross_sales) AS net_revenue,
    sum(o.vatable_sales) AS vatable_sales,
    sum(o.vat_amount) AS output_vat,
    sum(o.vat_exempt_sales) AS vat_exempt_sales,
    sum(o.zero_rated_sales) AS zero_rated_sales,
    sum(o.net_sales) AS net_of_vat
   FROM (pos_orders o
     JOIN stores s ON ((s.location_id = o.location_id)))
  WHERE (o.payment_status = 'PAID'::text)
  GROUP BY s.store_name, s.legal_entity, s.erpnext_cost_center, o.business_date
UNION ALL
 SELECT s.store_name,
    s.legal_entity,
    s.erpnext_cost_center,
    w.business_date,
    COALESCE(w.platform, 'Online'::text) AS channel,
    count(*) AS order_count,
    sum(w.original_gross_sales) AS gross_revenue,
    sum(w.total_discounts) AS total_discounts,
    sum(w.gross_sales) AS net_revenue,
    sum(w.vatable_sales) AS vatable_sales,
    sum(w.vat_amount) AS output_vat,
    sum(w.vat_exempt_sales) AS vat_exempt_sales,
    sum(w.zero_rated_sales) AS zero_rated_sales,
    sum(w.net_sales) AS net_of_vat
   FROM (web_orders w
     JOIN stores s ON ((s.location_id = w.location_id)))
  GROUP BY s.store_name, s.legal_entity, s.erpnext_cost_center, w.business_date, w.platform;

-- restore MV: store_daily_closing
CREATE MATERIALIZED VIEW public.store_daily_closing AS
 SELECT s.location_id,
    s.store_name,
    s.legal_entity,
    s.store_type,
    combined.business_date,
    combined.pos_orders,
    combined.web_orders,
    (combined.pos_orders + combined.web_orders) AS total_orders,
    combined.pos_original_gross,
    combined.pos_after_discount,
    combined.pos_net_of_vat,
    combined.pos_discounts,
    combined.pos_vat,
    combined.pos_vat_exempt,
    combined.web_gross,
    combined.web_delivery_fee,
    (combined.pos_original_gross + combined.web_gross) AS total_gross_sales,
    (combined.pos_after_discount + combined.web_gross) AS total_net_sales,
        CASE
            WHEN (combined.pos_original_gross > (0)::numeric) THEN round(((combined.pos_discounts / combined.pos_original_gross) * (100)::numeric), 1)
            ELSE (0)::numeric
        END AS discount_rate_pct,
        CASE
            WHEN (combined.web_orders > (0)::numeric) THEN 'POS+Web'::text
            ELSE 'POS'::text
        END AS data_sources
   FROM (stores s
     JOIN ( SELECT all_orders.location_id,
            all_orders.business_date,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.order_count
                    ELSE (0)::bigint
                END) AS pos_orders,
            sum(
                CASE
                    WHEN (all_orders.source = 'web'::text) THEN all_orders.order_count
                    ELSE (0)::bigint
                END) AS web_orders,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.orig_gross
                    ELSE (0)::numeric
                END) AS pos_original_gross,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.after_disc
                    ELSE (0)::numeric
                END) AS pos_after_discount,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.net_vat
                    ELSE (0)::numeric
                END) AS pos_net_of_vat,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.discounts
                    ELSE (0)::numeric
                END) AS pos_discounts,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.vat
                    ELSE (0)::numeric
                END) AS pos_vat,
            sum(
                CASE
                    WHEN (all_orders.source = 'pos'::text) THEN all_orders.vat_exempt
                    ELSE (0)::numeric
                END) AS pos_vat_exempt,
            sum(
                CASE
                    WHEN (all_orders.source = 'web'::text) THEN all_orders.after_disc
                    ELSE (0)::numeric
                END) AS web_gross,
            sum(
                CASE
                    WHEN (all_orders.source = 'web'::text) THEN all_orders.del_fee
                    ELSE (0)::numeric
                END) AS web_delivery_fee
           FROM ( SELECT pos_orders.location_id,
                    pos_orders.business_date,
                    'pos'::text AS source,
                    count(*) AS order_count,
                    sum(pos_orders.original_gross_sales) AS orig_gross,
                    sum(pos_orders.gross_sales) AS after_disc,
                    sum(pos_orders.net_sales) AS net_vat,
                    sum(pos_orders.total_discounts) AS discounts,
                    sum(pos_orders.vat_amount) AS vat,
                    sum(pos_orders.vat_exempt_sales) AS vat_exempt,
                    (0)::numeric AS del_fee
                   FROM pos_orders
                  WHERE (pos_orders.payment_status = 'PAID'::text)
                  GROUP BY pos_orders.location_id, pos_orders.business_date
                UNION ALL
                 SELECT web_orders.location_id,
                    web_orders.business_date,
                    'web'::text AS source,
                    count(*) AS count,
                    sum(web_orders.original_gross_sales) AS sum,
                    sum(web_orders.gross_sales) AS sum,
                    sum(web_orders.net_sales) AS sum,
                    sum(web_orders.total_discounts) AS sum,
                    sum(web_orders.vat_amount) AS sum,
                    sum(web_orders.vat_exempt_sales) AS sum,
                    sum(COALESCE(web_orders.delivery_fee, (0)::numeric)) AS sum
                   FROM web_orders
                  WHERE (web_orders.order_status_raw = 'Completed'::text)
                  GROUP BY web_orders.location_id, web_orders.business_date) all_orders
          GROUP BY all_orders.location_id, all_orders.business_date) combined ON ((s.location_id = combined.location_id)));

-- restore MV: sales_dashboard_daily_store_metrics
CREATE MATERIALIZED VIEW public.sales_dashboard_daily_store_metrics AS
 WITH pos_sales AS (
         SELECT pos_orders.location_id,
            pos_orders.business_date,
            (count(*))::integer AS pos_orders,
            (COALESCE(sum(pos_orders.gross_sales), (0)::numeric))::numeric(14,2) AS pos_gross_sales,
            (COALESCE(sum(pos_orders.net_sales), (0)::numeric))::numeric(14,2) AS pos_net_sales_without_vat
           FROM pos_orders
          WHERE (pos_orders.payment_status = 'PAID'::text)
          GROUP BY pos_orders.location_id, pos_orders.business_date
        ), web_sales AS (
         SELECT web_orders.location_id,
            web_orders.business_date,
            (count(*))::integer AS web_orders,
            (COALESCE(sum(web_orders.gross_sales), (0)::numeric))::numeric(14,2) AS web_gross_sales,
            (COALESCE(sum(web_orders.net_sales), (0)::numeric))::numeric(14,2) AS web_net_sales_without_vat,
            (count(*) FILTER (WHERE (upper(COALESCE(web_orders.payment_gateway, ''::text)) = 'COD'::text)))::integer AS web_cod_orders,
            (COALESCE(sum(
                CASE
                    WHEN (upper(COALESCE(web_orders.payment_gateway, ''::text)) = 'COD'::text) THEN web_orders.gross_sales
                    ELSE (0)::numeric
                END), (0)::numeric))::numeric(14,2) AS web_cod_gross_sales,
            (COALESCE(sum(
                CASE
                    WHEN (upper(COALESCE(web_orders.payment_gateway, ''::text)) = 'COD'::text) THEN web_orders.net_sales
                    ELSE (0)::numeric
                END), (0)::numeric))::numeric(14,2) AS web_cod_net_sales_without_vat
           FROM web_orders
          WHERE (web_orders.order_status_raw = 'Completed'::text)
          GROUP BY web_orders.location_id, web_orders.business_date
        ), foodpanda_sales AS (
         SELECT foodpanda_orders.location_id,
            foodpanda_orders.business_date,
            (count(*))::integer AS foodpanda_orders,
            (COALESCE(sum(foodpanda_orders.subtotal), (0)::numeric))::numeric(14,2) AS foodpanda_subtotal,
            (COALESCE(sum((foodpanda_orders.subtotal / 1.12)), (0)::numeric))::numeric(14,2) AS foodpanda_vat_deducted_sales
           FROM foodpanda_orders
          WHERE (lower(foodpanda_orders.order_status) = 'delivered'::text)
          GROUP BY foodpanda_orders.location_id, foodpanda_orders.business_date
        ), pos_cups AS (
         SELECT o.location_id,
            o.business_date,
            (COALESCE(sum(i.quantity), (0)::bigint))::integer AS pos_cups_sold
           FROM (pos_order_items i
             JOIN pos_orders o ON ((o.id = i.order_id)))
          WHERE (o.payment_status = 'PAID'::text)
          GROUP BY o.location_id, o.business_date
        ), web_cups AS (
         SELECT o.location_id,
            o.business_date,
            (COALESCE(sum(i.quantity), (0)::bigint))::integer AS web_cups_sold
           FROM (web_order_items i
             JOIN web_orders o ON ((o.id = i.order_id)))
          WHERE (o.order_status_raw = 'Completed'::text)
          GROUP BY o.location_id, o.business_date
        ), foodpanda_cups AS (
         SELECT foodpanda_daily_item_metrics.location_id,
            foodpanda_daily_item_metrics.business_date,
            (COALESCE(sum(foodpanda_daily_item_metrics.qty_sold), (0)::bigint))::integer AS foodpanda_cups_sold
           FROM foodpanda_daily_item_metrics
          GROUP BY foodpanda_daily_item_metrics.location_id, foodpanda_daily_item_metrics.business_date
        ), store_days AS (
         SELECT DISTINCT pos_sales.location_id,
            pos_sales.business_date
           FROM pos_sales
        UNION
         SELECT DISTINCT web_sales.location_id,
            web_sales.business_date
           FROM web_sales
        UNION
         SELECT DISTINCT foodpanda_sales.location_id,
            foodpanda_sales.business_date
           FROM foodpanda_sales
        UNION
         SELECT DISTINCT foodpanda_cups.location_id,
            foodpanda_cups.business_date
           FROM foodpanda_cups
        )
 SELECT d.location_id,
    d.business_date,
    COALESCE(s.store_name, (d.location_id)::text) AS store_name,
    s.legal_entity,
    s.store_type,
    COALESCE(pos.pos_orders, 0) AS pos_orders,
    COALESCE(web.web_orders, 0) AS web_orders,
    COALESCE(fp.foodpanda_orders, 0) AS foodpanda_orders,
    ((COALESCE(pos.pos_orders, 0) + COALESCE(web.web_orders, 0)) + COALESCE(fp.foodpanda_orders, 0)) AS transactions,
    (COALESCE(pos.pos_gross_sales, (0)::numeric))::numeric(14,2) AS pos_gross_sales,
    (COALESCE(pos.pos_net_sales_without_vat, (0)::numeric))::numeric(14,2) AS pos_net_sales_without_vat,
    (COALESCE(web.web_gross_sales, (0)::numeric))::numeric(14,2) AS web_gross_sales,
    (COALESCE(web.web_net_sales_without_vat, (0)::numeric))::numeric(14,2) AS web_net_sales_without_vat,
    COALESCE(web.web_cod_orders, 0) AS web_cod_orders,
    (COALESCE(web.web_cod_gross_sales, (0)::numeric))::numeric(14,2) AS web_cod_gross_sales,
    (COALESCE(web.web_cod_net_sales_without_vat, (0)::numeric))::numeric(14,2) AS web_cod_net_sales_without_vat,
    (COALESCE(fp.foodpanda_subtotal, (0)::numeric))::numeric(14,2) AS foodpanda_subtotal,
    (COALESCE(fp.foodpanda_vat_deducted_sales, (0)::numeric))::numeric(14,2) AS foodpanda_vat_deducted_sales,
    (GREATEST((COALESCE(web.web_gross_sales, (0)::numeric) - COALESCE(web.web_cod_gross_sales, (0)::numeric)), (0)::numeric))::numeric(14,2) AS website_non_cod_gross_sales,
    (GREATEST((COALESCE(web.web_net_sales_without_vat, (0)::numeric) - COALESCE(web.web_cod_net_sales_without_vat, (0)::numeric)), (0)::numeric))::numeric(14,2) AS website_non_cod_net_sales_without_vat,
    COALESCE(pc.pos_cups_sold, 0) AS pos_cups_sold,
    COALESCE(wc.web_cups_sold, 0) AS web_cups_sold,
    COALESCE(fc.foodpanda_cups_sold, 0) AS foodpanda_cups_sold,
    ((COALESCE(pc.pos_cups_sold, 0) + COALESCE(wc.web_cups_sold, 0)) + COALESCE(fc.foodpanda_cups_sold, 0)) AS cups_sold,
    (((COALESCE(pos.pos_gross_sales, (0)::numeric) + COALESCE(web.web_gross_sales, (0)::numeric)) + COALESCE(fp.foodpanda_subtotal, (0)::numeric)))::numeric(14,2) AS total_gross_sales,
    (((COALESCE(pos.pos_net_sales_without_vat, (0)::numeric) + COALESCE(web.web_net_sales_without_vat, (0)::numeric)) + COALESCE(fp.foodpanda_vat_deducted_sales, (0)::numeric)))::numeric(14,2) AS total_net_sales_without_vat
   FROM (((((((store_days d
     LEFT JOIN stores s ON ((s.location_id = d.location_id)))
     LEFT JOIN pos_sales pos ON (((pos.location_id = d.location_id) AND (pos.business_date = d.business_date))))
     LEFT JOIN web_sales web ON (((web.location_id = d.location_id) AND (web.business_date = d.business_date))))
     LEFT JOIN foodpanda_sales fp ON (((fp.location_id = d.location_id) AND (fp.business_date = d.business_date))))
     LEFT JOIN pos_cups pc ON (((pc.location_id = d.location_id) AND (pc.business_date = d.business_date))))
     LEFT JOIN web_cups wc ON (((wc.location_id = d.location_id) AND (wc.business_date = d.business_date))))
     LEFT JOIN foodpanda_cups fc ON (((fc.location_id = d.location_id) AND (fc.business_date = d.business_date))));

-- restore MV: payment_reconciliation
CREATE MATERIALIZED VIEW public.payment_reconciliation AS
 SELECT s.store_name,
    o.business_date,
    p.payment_type,
    count(*) AS transaction_count,
    sum(p.paid_amount) AS total_collected,
    sum(p.returned_amount) AS total_change_given,
    sum((p.paid_amount - p.returned_amount)) AS net_collected
   FROM ((pos_order_payments p
     JOIN pos_orders o ON ((o.id = p.order_id)))
     JOIN stores s ON ((s.location_id = o.location_id)))
  WHERE (o.payment_status = 'PAID'::text)
  GROUP BY s.store_name, o.business_date, p.payment_type;

-- restore MV: store_daily_baselines
CREATE MATERIALIZED VIEW public.store_daily_baselines AS
 SELECT location_id,
    EXTRACT(dow FROM order_date) AS day_of_week,
    percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((order_count)::double precision)) AS median_orders,
    percentile_cont((0.1)::double precision) WITHIN GROUP (ORDER BY ((order_count)::double precision)) AS p10_orders,
    avg(order_count) AS avg_orders,
    stddev(order_count) AS stddev_orders,
    count(*) AS weeks_of_data
   FROM ( SELECT pos_orders.location_id,
            pos_orders.business_date AS order_date,
            count(*) AS order_count
           FROM pos_orders
          WHERE ((pos_orders.business_date >= (CURRENT_DATE - '56 days'::interval)) AND (pos_orders.payment_status = 'PAID'::text))
          GROUP BY pos_orders.location_id, pos_orders.business_date) daily
  GROUP BY location_id, (EXTRACT(dow FROM order_date));

-- restore VIEW: v_all_channel_daily
CREATE OR REPLACE VIEW public.v_all_channel_daily AS
 SELECT dates.business_date,
    COALESCE(pos.order_count, (0)::bigint) AS pos_orders,
    COALESCE(pos.gross_sales, (0)::numeric) AS pos_gross_sales,
    COALESCE(pos.net_sales, (0)::numeric) AS pos_net_sales,
    COALESCE(web.order_count, (0)::bigint) AS web_orders,
    COALESCE(web.gross_sales, (0)::numeric) AS web_gross_sales,
    COALESCE(web.net_sales, (0)::numeric) AS web_net_sales,
    COALESCE(fp.order_count, (0)::bigint) AS fp_orders,
    COALESCE(fp.gross_sales, (0)::numeric) AS fp_gross_sales,
    ((COALESCE(pos.order_count, (0)::bigint) + COALESCE(web.order_count, (0)::bigint)) + COALESCE(fp.order_count, (0)::bigint)) AS total_orders,
    ((COALESCE(pos.gross_sales, (0)::numeric) + COALESCE(web.gross_sales, (0)::numeric)) + COALESCE(fp.gross_sales, (0)::numeric)) AS total_gross_sales,
    ((
        CASE
            WHEN (pos.order_count > 0) THEN 1
            ELSE 0
        END +
        CASE
            WHEN (web.order_count > 0) THEN 1
            ELSE 0
        END) +
        CASE
            WHEN (fp.order_count > 0) THEN 1
            ELSE 0
        END) AS channel_count,
    concat_ws('+'::text,
        CASE
            WHEN (pos.order_count > 0) THEN 'POS'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (web.order_count > 0) THEN 'Web'::text
            ELSE NULL::text
        END,
        CASE
            WHEN (fp.order_count > 0) THEN 'FP'::text
            ELSE NULL::text
        END) AS data_sources
   FROM (((( SELECT DISTINCT pos_orders.business_date
           FROM pos_orders
          WHERE (pos_orders.payment_status = 'PAID'::text)
        UNION
         SELECT DISTINCT web_orders.business_date
           FROM web_orders
          WHERE (web_orders.order_status_raw = 'Completed'::text)
        UNION
         SELECT DISTINCT foodpanda_orders.business_date
           FROM foodpanda_orders
          WHERE (lower(foodpanda_orders.order_status) = 'delivered'::text)) dates
     LEFT JOIN ( SELECT pos_orders.business_date,
            count(*) AS order_count,
            sum(pos_orders.gross_sales) AS gross_sales,
            sum(pos_orders.net_sales) AS net_sales
           FROM pos_orders
          WHERE (pos_orders.payment_status = 'PAID'::text)
          GROUP BY pos_orders.business_date) pos USING (business_date))
     LEFT JOIN ( SELECT web_orders.business_date,
            count(*) AS order_count,
            sum(web_orders.gross_sales) AS gross_sales,
            sum(web_orders.net_sales) AS net_sales
           FROM web_orders
          WHERE (web_orders.order_status_raw = 'Completed'::text)
          GROUP BY web_orders.business_date) web USING (business_date))
     LEFT JOIN ( SELECT foodpanda_orders.business_date,
            count(*) AS order_count,
            sum(foodpanda_orders.subtotal) AS gross_sales
           FROM foodpanda_orders
          WHERE (lower(foodpanda_orders.order_status) = 'delivered'::text)
          GROUP BY foodpanda_orders.business_date) fp USING (business_date))
  ORDER BY dates.business_date DESC;

-- restore VIEW: v_ops_weekly
CREATE OR REPLACE VIEW public.v_ops_weekly AS
 SELECT (date_trunc('week'::text, (business_date)::timestamp with time zone))::date AS week_start,
    ((date_trunc('week'::text, (business_date)::timestamp with time zone) + '6 days'::interval))::date AS week_end,
    sum(pos_orders) AS pos_orders,
    sum(pos_gross_sales) AS pos_gross_sales,
    sum(web_orders) AS web_orders,
    sum(web_gross_sales) AS web_gross_sales,
    sum(fp_orders) AS fp_orders,
    sum(fp_gross_sales) AS fp_gross_sales,
    sum(total_orders) AS total_orders,
    sum(total_gross_sales) AS total_gross_sales,
    count(*) AS days_with_data,
    max(channel_count) AS max_channels
   FROM v_all_channel_daily
  GROUP BY (date_trunc('week'::text, (business_date)::timestamp with time zone))
  ORDER BY ((date_trunc('week'::text, (business_date)::timestamp with time zone))::date) DESC;

-- restore VIEW: v_system_daily_totals
CREATE OR REPLACE VIEW public.v_system_daily_totals AS
 SELECT business_date,
    count(*) AS store_count,
    sum(total_orders) AS total_orders,
    sum(pos_orders) AS pos_order_count,
    sum(web_orders) AS web_order_count,
    sum(total_gross_sales) AS total_gross_sales,
    sum(total_net_sales) AS total_net_sales,
    sum(pos_original_gross) AS pos_original_gross_sales,
    sum(pos_after_discount) AS pos_gross_sales,
    sum(web_gross) AS web_gross_sales,
    sum(pos_discounts) AS total_discounts,
    sum(pos_vat) AS total_vat,
    round(avg(discount_rate_pct), 1) AS avg_discount_rate,
    count(*) FILTER (WHERE (data_sources = 'POS+Web'::text)) AS stores_with_web,
    count(*) FILTER (WHERE (data_sources = 'POS'::text)) AS stores_pos_only
   FROM store_daily_closing
  GROUP BY business_date
  ORDER BY business_date DESC;

-- restore VIEW: v_orders
CREATE OR REPLACE VIEW public.v_orders AS
 SELECT o.id,
    o.location_id,
    o.business_date,
    o.bill_number,
    o.receipt_number,
    o.pax_count,
    o.service_type_id,
    o.original_gross_sales,
    o.gross_sales,
    o.net_sales,
    o.vatable_sales,
    o.vat_amount,
    o.vat_exempt_sales,
    o.zero_rated_sales,
    o.total_discounts,
    o.delivery_fee,
    o.payment_status,
    o.billed_at,
    o.paid_at,
    o.synced_at,
    o.updated_at,
    s.store_name,
    s.legal_entity,
    s.store_type,
    s.credential_group,
    s.go_live_date,
    s.is_active
   FROM (pos_orders o
     JOIN stores s ON ((o.location_id = s.location_id)));

-- restore VIEW: v_monthly_store_summary
CREATE OR REPLACE VIEW public.v_monthly_store_summary AS
 SELECT o.location_id,
    s.store_name,
    s.store_type,
    s.legal_entity,
    (date_trunc('month'::text, (o.business_date)::timestamp with time zone))::date AS month,
    count(*) AS order_count,
    count(DISTINCT o.business_date) AS active_days,
    sum(o.gross_sales) AS gross_sales,
    sum(o.net_sales) AS net_sales,
    sum(o.vat_amount) AS vat_amount,
    sum(o.vat_exempt_sales) AS vat_exempt_sales,
    sum(o.total_discounts) AS total_discounts,
    sum(o.delivery_fee) AS delivery_fees
   FROM (pos_orders o
     JOIN stores s ON ((o.location_id = s.location_id)))
  GROUP BY o.location_id, s.store_name, s.store_type, s.legal_entity, (date_trunc('month'::text, (o.business_date)::timestamp with time zone));

-- restore VIEW: v_discount_identity_order_usage
CREATE OR REPLACE VIEW public.v_discount_identity_order_usage AS
 WITH normalized_source AS (
         SELECT po.business_date,
            po.location_id,
            COALESCE(s.store_name, ('Location '::text || (po.location_id)::text)) AS store_name,
            po.id AS order_id,
            po.bill_number,
            po.receipt_number,
            po.billed_at,
            po.paid_at,
                CASE
                    WHEN (upper(COALESCE(poi.discount_bir_category, ''::text)) = ANY (ARRAY['SC'::text, 'PWD'::text])) THEN upper(poi.discount_bir_category)
                    WHEN (upper(COALESCE(poi.discount_name_normalized, poi.discount_name, ''::text)) ~~ '%SENIOR%'::text) THEN 'SC'::text
                    WHEN (upper(COALESCE(poi.discount_name_normalized, poi.discount_name, ''::text)) ~~ '%PWD%'::text) THEN 'PWD'::text
                    ELSE NULL::text
                END AS discount_bir_category,
            upper(NULLIF(TRIM(BOTH FROM regexp_replace(COALESCE(NULLIF(poi.discount_customer_full_name_normalized, ''::text), NULLIF(poi.discount_customer_full_name, ''::text), NULLIF(TRIM(BOTH FROM concat_ws(' '::text, poi.discount_customer_first_name, poi.discount_customer_last_name)), ''::text)), '\s+'::text, ' '::text, 'g'::text)), ''::text)) AS full_name_normalized,
            upper(NULLIF(regexp_replace(COALESCE(NULLIF(poi.discount_reference_number_normalized, ''::text), NULLIF(TRIM(BOTH FROM poi.discount_reference_number), ''::text), ''::text), '[^A-Za-z0-9]+'::text, ''::text, 'g'::text), ''::text)) AS reference_number_normalized,
            COALESCE(NULLIF(TRIM(BOTH FROM poi.discount_customer_full_name), ''::text), NULLIF(TRIM(BOTH FROM concat_ws(' '::text, poi.discount_customer_first_name, poi.discount_customer_last_name)), ''::text)) AS customer_name_display,
            COALESCE(NULLIF(TRIM(BOTH FROM poi.discount_reference_number), ''::text), NULLIF(TRIM(BOTH FROM poi.discount_reference_number_normalized), ''::text)) AS reference_number_display,
            upper(NULLIF(TRIM(BOTH FROM regexp_replace(COALESCE(poi.discount_name_normalized, poi.discount_name, ''::text), '\s+'::text, ' '::text, 'g'::text)), ''::text)) AS discount_name_normalized,
            COALESCE(poi.discount_amount, (0)::numeric) AS discount_amount
           FROM ((pos_order_items poi
             JOIN pos_orders po ON ((po.id = poi.order_id)))
             LEFT JOIN stores s ON ((s.location_id = po.location_id)))
          WHERE (po.payment_status = 'PAID'::text)
        ), identity_usage AS (
         SELECT normalized_source.business_date,
            normalized_source.location_id,
            normalized_source.store_name,
            normalized_source.order_id,
            normalized_source.bill_number,
            normalized_source.receipt_number,
            normalized_source.billed_at,
            normalized_source.paid_at,
            normalized_source.discount_bir_category,
            normalized_source.full_name_normalized,
            normalized_source.reference_number_normalized,
            max(normalized_source.customer_name_display) AS customer_name_display,
            max(normalized_source.reference_number_display) AS reference_number_display,
            max(normalized_source.discount_name_normalized) AS discount_name_normalized,
            round(sum(normalized_source.discount_amount), 2) AS discount_amount_total
           FROM normalized_source
          WHERE ((normalized_source.discount_bir_category IS NOT NULL) AND ((normalized_source.full_name_normalized IS NOT NULL) OR (normalized_source.reference_number_normalized IS NOT NULL)))
          GROUP BY normalized_source.business_date, normalized_source.location_id, normalized_source.store_name, normalized_source.order_id, normalized_source.bill_number, normalized_source.receipt_number, normalized_source.billed_at, normalized_source.paid_at, normalized_source.discount_bir_category, normalized_source.full_name_normalized, normalized_source.reference_number_normalized
        )
 SELECT business_date,
    location_id,
    store_name,
    order_id,
    bill_number,
    receipt_number,
    billed_at,
    paid_at,
    discount_bir_category,
    COALESCE(discount_name_normalized,
        CASE discount_bir_category
            WHEN 'SC'::text THEN 'SENIOR CITIZEN DISCOUNT'::text
            WHEN 'PWD'::text THEN 'PWD'::text
            ELSE discount_bir_category
        END) AS discount_name_normalized,
    full_name_normalized,
    reference_number_normalized,
    customer_name_display,
    reference_number_display,
    discount_amount_total
   FROM identity_usage;

-- restore VIEW: v_discount_identity_rolling_30d_usage
WITH base AS (
         SELECT ((CURRENT_DATE - '29 days'::interval))::date AS window_start,
            CURRENT_DATE AS window_end,
            v_discount_identity_order_usage.business_date,
            v_discount_identity_order_usage.location_id,
            v_discount_identity_order_usage.store_name,
            v_discount_identity_order_usage.order_id,
            v_discount_identity_order_usage.bill_number,
            v_discount_identity_order_usage.receipt_number,
            v_discount_identity_order_usage.billed_at,
            v_discount_identity_order_usage.paid_at,
            v_discount_identity_order_usage.discount_bir_category,
            v_discount_identity_order_usage.discount_name_normalized,
            v_discount_identity_order_usage.full_name_normalized,
            v_discount_identity_order_usage.reference_number_normalized,
            v_discount_identity_order_usage.customer_name_display,
            v_discount_identity_order_usage.reference_number_display,
            v_discount_identity_order_usage.discount_amount_total
           FROM v_discount_identity_order_usage
          WHERE ((v_discount_identity_order_usage.business_date >= ((CURRENT_DATE - '29 days'::interval))::date) AND (v_discount_identity_order_usage.business_date <= CURRENT_DATE))
        ), name_usage AS (
         SELECT base.window_start,
            base.window_end,
            base.location_id,
            max(base.store_name) AS store_name,
            base.discount_bir_category,
            max(base.discount_name_normalized) AS discount_name,
            base.full_name_normalized AS identity_key,
            array_agg(DISTINCT base.customer_name_display ORDER BY base.customer_name_display) FILTER (WHERE (base.customer_name_display IS NOT NULL)) AS customer_names,
            array_agg(DISTINCT base.reference_number_display ORDER BY base.reference_number_display) FILTER (WHERE (base.reference_number_display IS NOT NULL)) AS reference_numbers,
            array_agg(DISTINCT base.order_id ORDER BY base.order_id) AS order_ids,
            array_agg(DISTINCT (base.bill_number)::text ORDER BY (base.bill_number)::text) FILTER (WHERE (base.bill_number IS NOT NULL)) AS bill_numbers,
            array_agg(DISTINCT (base.receipt_number)::text ORDER BY (base.receipt_number)::text) FILTER (WHERE (base.receipt_number IS NOT NULL)) AS receipt_numbers,
            array_agg(DISTINCT base.business_date ORDER BY base.business_date) AS business_dates,
            (count(DISTINCT base.order_id))::integer AS order_count,
            (count(DISTINCT base.business_date))::integer AS active_day_count,
            (count(DISTINCT base.reference_number_normalized))::integer AS distinct_counterparty_count,
            min(base.billed_at) AS first_billed_at,
            max(base.billed_at) AS last_billed_at,
            min(base.paid_at) AS first_paid_at,
            max(base.paid_at) AS last_paid_at,
            round(sum(base.discount_amount_total), 2) AS discount_amount_total
           FROM base
          WHERE (base.full_name_normalized IS NOT NULL)
          GROUP BY base.window_start, base.window_end, base.location_id, base.discount_bir_category, base.full_name_normalized
        ), reference_usage AS (
         SELECT base.window_start,
            base.window_end,
            base.location_id,
            max(base.store_name) AS store_name,
            base.discount_bir_category,
            max(base.discount_name_normalized) AS discount_name,
            base.reference_number_normalized AS identity_key,
            array_agg(DISTINCT base.customer_name_display ORDER BY base.customer_name_display) FILTER (WHERE (base.customer_name_display IS NOT NULL)) AS customer_names,
            array_agg(DISTINCT base.reference_number_display ORDER BY base.reference_number_display) FILTER (WHERE (base.reference_number_display IS NOT NULL)) AS reference_numbers,
            array_agg(DISTINCT base.order_id ORDER BY base.order_id) AS order_ids,
            array_agg(DISTINCT (base.bill_number)::text ORDER BY (base.bill_number)::text) FILTER (WHERE (base.bill_number IS NOT NULL)) AS bill_numbers,
            array_agg(DISTINCT (base.receipt_number)::text ORDER BY (base.receipt_number)::text) FILTER (WHERE (base.receipt_number IS NOT NULL)) AS receipt_numbers,
            array_agg(DISTINCT base.business_date ORDER BY base.business_date) AS business_dates,
            (count(DISTINCT base.order_id))::integer AS order_count,
            (count(DISTINCT base.business_date))::integer AS active_day_count,
            (count(DISTINCT base.full_name_normalized))::integer AS distinct_counterparty_count,
            min(base.billed_at) AS first_billed_at,
            max(base.billed_at) AS last_billed_at,
            min(base.paid_at) AS first_paid_at,
            max(base.paid_at) AS last_paid_at,
            round(sum(base.discount_amount_total), 2) AS discount_amount_total
           FROM base
          WHERE (base.reference_number_normalized IS NOT NULL)
          GROUP BY base.window_start, base.window_end, base.location_id, base.discount_bir_category, base.reference_number_normalized
        )
 SELECT name_usage.window_start,
    name_usage.window_end,
    name_usage.location_id,
    name_usage.store_name,
    name_usage.discount_bir_category,
    name_usage.discount_name,
    'full_name'::text AS identity_type,
    name_usage.identity_key,
    name_usage.customer_names[1] AS customer_name,
        CASE
            WHEN (name_usage.distinct_counterparty_count = 1) THEN name_usage.reference_numbers[1]
            ELSE NULL::text
        END AS reference_number,
    name_usage.order_count,
    name_usage.active_day_count,
    name_usage.distinct_counterparty_count,
    name_usage.discount_amount_total,
    jsonb_build_object('customer_names', to_jsonb(COALESCE(name_usage.customer_names, ARRAY[]::text[])), 'reference_numbers', to_jsonb(COALESCE(name_usage.reference_numbers, ARRAY[]::text[])), 'order_ids', to_jsonb(name_usage.order_ids), 'bill_numbers', to_jsonb(COALESCE(name_usage.bill_numbers, ARRAY[]::text[])), 'receipt_numbers', to_jsonb(COALESCE(name_usage.receipt_numbers, ARRAY[]::text[])), 'business_dates', to_jsonb(name_usage.business_dates), 'first_billed_at', name_usage.first_billed_at, 'last_billed_at', name_usage.last_billed_at, 'first_paid_at', name_usage.first_paid_at, 'last_paid_at', name_usage.last_paid_at) AS details
   FROM name_usage
UNION ALL
 SELECT reference_usage.window_start,
    reference_usage.window_end,
    reference_usage.location_id,
    reference_usage.store_name,
    reference_usage.discount_bir_category,
    reference_usage.discount_name,
    'reference_number'::text AS identity_type,
    reference_usage.identity_key,
        CASE
            WHEN (reference_usage.distinct_counterparty_count = 1) THEN reference_usage.customer_names[1]
            ELSE NULL::text
        END AS customer_name,
    reference_usage.reference_numbers[1] AS reference_number,
    reference_usage.order_count,
    reference_usage.active_day_count,
    reference_usage.distinct_counterparty_count,
    reference_usage.discount_amount_total,
    jsonb_build_object('customer_names', to_jsonb(COALESCE(reference_usage.customer_names, ARRAY[]::text[])), 'reference_numbers', to_jsonb(COALESCE(reference_usage.reference_numbers, ARRAY[]::text[])), 'order_ids', to_jsonb(reference_usage.order_ids), 'bill_numbers', to_jsonb(COALESCE(reference_usage.bill_numbers, ARRAY[]::text[])), 'receipt_numbers', to_jsonb(COALESCE(reference_usage.receipt_numbers, ARRAY[]::text[])), 'business_dates', to_jsonb(reference_usage.business_dates), 'first_billed_at', reference_usage.first_billed_at, 'last_billed_at', reference_usage.last_billed_at, 'first_paid_at', reference_usage.first_paid_at, 'last_paid_at', reference_usage.last_paid_at) AS details
   FROM reference_usage;

COMMIT;
-- After rollback, REFRESH MATERIALIZED VIEWs as needed.