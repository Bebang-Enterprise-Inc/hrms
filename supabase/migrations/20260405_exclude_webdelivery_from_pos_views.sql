-- Exclude WebDelivery orders from POS subqueries in revenue views.
-- WebDelivery = website orders (bebang.ph) rung through Mosaic POS (service_channel_id=19).
-- These already exist in web_orders, so including them in POS totals double-counts revenue.
-- Safe to deploy now: zero WebDelivery orders exist yet. Prevents future double-counting.

-- ═══════════════════════════════════════════════════════════════════════════
-- 1. v_all_channel_daily — add channel filter to POS subquery
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW public.v_all_channel_daily AS
SELECT
    dates.business_date,
    pos.order_count   AS pos_orders,
    pos.gross_sales   AS pos_gross_sales,
    pos.net_sales     AS pos_net_sales,
    web.order_count   AS web_orders,
    web.gross_sales   AS web_gross_sales,
    web.net_sales     AS web_net_sales,
    fp.order_count    AS fp_orders,
    fp.gross_sales    AS fp_gross_sales,
    COALESCE(pos.order_count, 0) + COALESCE(web.order_count, 0) + COALESCE(fp.order_count, 0) AS total_orders,
    COALESCE(pos.gross_sales, 0) + COALESCE(web.gross_sales, 0) + COALESCE(fp.gross_sales, 0) AS total_gross_sales,
    (CASE WHEN pos.order_count > 0 THEN 1 ELSE 0 END
   + CASE WHEN web.order_count > 0 THEN 1 ELSE 0 END
   + CASE WHEN fp.order_count  > 0 THEN 1 ELSE 0 END) AS channel_count,
    CONCAT_WS(', ',
        CASE WHEN pos.order_count > 0 THEN 'POS' END,
        CASE WHEN web.order_count > 0 THEN 'Web' END,
        CASE WHEN fp.order_count  > 0 THEN 'FoodPanda' END
    ) AS data_sources

FROM (
    SELECT DISTINCT business_date FROM pos_orders WHERE payment_status = 'PAID'
    UNION
    SELECT DISTINCT business_date FROM web_orders WHERE order_status_raw = 'Completed'
    UNION
    SELECT DISTINCT business_date FROM foodpanda_orders WHERE LOWER(order_status) = 'delivered'
) dates

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(gross_sales)   AS gross_sales,
           SUM(net_sales)     AS net_sales
    FROM pos_orders
    WHERE payment_status = 'PAID'
      AND (channel IS NULL OR channel != 'WebDelivery')
    GROUP BY business_date
) pos USING (business_date)

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(gross_sales)   AS gross_sales,
           SUM(net_sales)     AS net_sales
    FROM web_orders
    WHERE order_status_raw = 'Completed'
    GROUP BY business_date
) web USING (business_date)

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(subtotal)      AS gross_sales
    FROM foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
    GROUP BY business_date
) fp USING (business_date)

ORDER BY dates.business_date;


-- ═══════════════════════════════════════════════════════════════════════════
-- 2. store_daily_closing — add channel filter to POS subquery
-- ═══════════════════════════════════════════════════════════════════════════

DROP MATERIALIZED VIEW IF EXISTS public.store_daily_closing;

CREATE MATERIALIZED VIEW public.store_daily_closing AS
SELECT
    s.location_id,
    s.store_name,
    combined.business_date,
    combined.total_orders,
    combined.total_original_gross   AS total_gross_sales,
    combined.total_after_disc       AS total_net_sales_w_vat,
    combined.total_net_vat          AS total_net_sales,
    combined.total_discounts,
    combined.total_vat,
    combined.total_vat_exempt,
    combined.total_del_fee          AS total_delivery_fee
FROM public.stores s
JOIN (
    SELECT
        location_id,
        business_date,
        SUM(order_count)    AS total_orders,
        SUM(orig_gross)     AS total_original_gross,
        SUM(after_disc)     AS total_after_disc,
        SUM(net_vat)        AS total_net_vat,
        SUM(discounts)      AS total_discounts,
        SUM(vat)            AS total_vat,
        SUM(vat_exempt)     AS total_vat_exempt,
        SUM(del_fee)        AS total_del_fee
    FROM (
        -- POS orders (excluding WebDelivery to avoid double-counting with web_orders)
        SELECT
            location_id,
            business_date,
            'pos'                            AS source,
            COUNT(*)                         AS order_count,
            SUM(original_gross_sales)        AS orig_gross,
            SUM(gross_sales)                 AS after_disc,
            SUM(net_sales)                   AS net_vat,
            SUM(total_discounts)             AS discounts,
            SUM(vat_amount)                  AS vat,
            SUM(vat_exempt_sales)            AS vat_exempt,
            0::NUMERIC                       AS del_fee
        FROM pos_orders
        WHERE payment_status = 'PAID'
          AND (channel IS NULL OR channel != 'WebDelivery')
        GROUP BY location_id, business_date

        UNION ALL

        -- Web/delivery orders
        SELECT
            location_id,
            business_date,
            'web'                            AS source,
            COUNT(*),
            SUM(original_gross_sales),
            SUM(gross_sales),
            SUM(net_sales),
            SUM(total_discounts),
            SUM(vat_amount),
            SUM(vat_exempt_sales),
            SUM(COALESCE(delivery_fee, 0))
        FROM web_orders
        WHERE order_status_raw = 'Completed'
        GROUP BY location_id, business_date
    ) all_orders
    GROUP BY location_id, business_date
) combined ON s.location_id = combined.location_id;

CREATE UNIQUE INDEX idx_store_daily_closing_pk
    ON public.store_daily_closing (location_id, business_date);


-- ═══════════════════════════════════════════════════════════════════════════
-- 3. refresh_sales_dashboard_daily_store_metrics — add channel filter
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION public.refresh_sales_dashboard_daily_store_metrics()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Truncate and reload the materialized table
    TRUNCATE TABLE public.sales_dashboard_daily_store_metrics;

    INSERT INTO public.sales_dashboard_daily_store_metrics (
        location_id, business_date,
        pos_orders, pos_gross_sales, pos_net_sales_without_vat,
        web_orders, web_gross_sales, web_net_sales_without_vat,
        foodpanda_orders, foodpanda_gross_sales,
        transactions, pos_gross_sales_all, pos_net_sales_without_vat_all,
        web_gross_sales_all, web_net_sales_without_vat_all,
        foodpanda_gross_sales_all,
        top_pos_product, top_pos_product_qty,
        refreshed_at
    )
    SELECT
        s.location_id,
        s.business_date,
        coalesce(pos.pos_orders, 0) as pos_orders,
        coalesce(pos.pos_gross_sales, 0)::numeric(14,2) as pos_gross_sales,
        coalesce(pos.pos_net_sales_without_vat, 0)::numeric(14,2) as pos_net_sales_without_vat,
        coalesce(web.web_orders, 0) as web_orders,
        coalesce(web.web_gross_sales, 0)::numeric(14,2) as web_gross_sales,
        coalesce(web.web_net_sales_without_vat, 0)::numeric(14,2) as web_net_sales_without_vat,
        coalesce(fp.foodpanda_orders, 0) as foodpanda_orders,
        coalesce(fp.foodpanda_gross_sales, 0)::numeric(14,2) as foodpanda_gross_sales,
        coalesce(pos.pos_orders, 0) + coalesce(web.web_orders, 0) + coalesce(fp.foodpanda_orders, 0) as transactions,
        coalesce(pos.pos_gross_sales, 0)::numeric(14,2) as pos_gross_sales_all,
        coalesce(pos.pos_net_sales_without_vat, 0)::numeric(14,2) as pos_net_sales_without_vat_all,
        coalesce(web.web_gross_sales, 0)::numeric(14,2) as web_gross_sales_all,
        coalesce(web.web_net_sales_without_vat, 0)::numeric(14,2) as web_net_sales_without_vat_all,
        coalesce(fp.foodpanda_gross_sales, 0)::numeric(14,2) as foodpanda_gross_sales_all,
        top_product.product_name as top_pos_product,
        top_product.qty as top_pos_product_qty,
        now() as refreshed_at
    FROM (
        SELECT DISTINCT location_id, business_date
        FROM public.pos_orders WHERE payment_status = 'PAID'
    ) s
    LEFT JOIN (
        select location_id, business_date,
            count(*)::integer as pos_orders,
            coalesce(sum(gross_sales), 0)::numeric(14,2) as pos_gross_sales,
            coalesce(sum(net_sales), 0)::numeric(14,2) as pos_net_sales_without_vat
        from public.pos_orders
        where payment_status = 'PAID'
          and (channel is null or channel != 'WebDelivery')
        group by location_id, business_date
    ) pos on s.location_id = pos.location_id and s.business_date = pos.business_date
    LEFT JOIN (
        select location_id, business_date,
            count(*)::integer as web_orders,
            coalesce(sum(gross_sales), 0)::numeric(14,2) as web_gross_sales,
            coalesce(sum(net_sales), 0)::numeric(14,2) as web_net_sales_without_vat
        from public.web_orders
        where order_status_raw = 'Completed'
        group by location_id, business_date
    ) web on s.location_id = web.location_id and s.business_date = web.business_date
    LEFT JOIN (
        select location_id, business_date,
            count(*)::integer as foodpanda_orders,
            coalesce(sum(subtotal), 0)::numeric(14,2) as foodpanda_gross_sales
        from public.foodpanda_orders
        where lower(order_status) = 'delivered'
        group by location_id, business_date
    ) fp on s.location_id = fp.location_id and s.business_date = fp.business_date
    LEFT JOIN LATERAL (
        select i.product_name, sum(i.quantity)::integer as qty
        from public.pos_order_items i
        join public.pos_orders o on o.id = i.order_id
        where o.payment_status = 'PAID'
          and o.location_id = s.location_id
          and o.business_date = s.business_date
          and (o.channel is null or o.channel != 'WebDelivery')
        group by i.product_name
        order by qty desc
        limit 1
    ) top_product on true;
END;
$$;
