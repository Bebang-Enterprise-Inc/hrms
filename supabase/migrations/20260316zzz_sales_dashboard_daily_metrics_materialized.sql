-- ============================================================================
-- Migration: materialize sales dashboard daily metrics for cold-path speed
-- Date: 2026-03-16
-- Purpose:
--   1. replace the live aggregation view with a materialized view
--   2. add refresh helpers and indexes for dashboard/API cold-path stability
-- ============================================================================

do $$
begin
    if exists (
        select 1
        from pg_matviews
        where schemaname = 'public'
          and matviewname = 'sales_dashboard_daily_store_metrics'
    ) then
        execute 'drop materialized view public.sales_dashboard_daily_store_metrics';
    end if;

    if exists (
        select 1
        from information_schema.views
        where table_schema = 'public'
          and table_name = 'sales_dashboard_daily_store_metrics'
    ) then
        execute 'drop view public.sales_dashboard_daily_store_metrics';
    end if;
end $$;

create materialized view public.sales_dashboard_daily_store_metrics as
with pos_sales as (
    select
        location_id,
        business_date,
        count(*)::integer as pos_orders,
        coalesce(sum(gross_sales), 0)::numeric(14,2) as pos_gross_sales,
        coalesce(sum(net_sales), 0)::numeric(14,2) as pos_net_sales_without_vat
    from public.pos_orders
    where payment_status = 'PAID'
    group by location_id, business_date
),
web_sales as (
    select
        location_id,
        business_date,
        count(*)::integer as web_orders,
        coalesce(sum(gross_sales), 0)::numeric(14,2) as web_gross_sales,
        coalesce(sum(net_sales), 0)::numeric(14,2) as web_net_sales_without_vat,
        count(*) filter (
            where upper(coalesce(payment_gateway, '')) = 'COD'
        )::integer as web_cod_orders,
        coalesce(
            sum(case when upper(coalesce(payment_gateway, '')) = 'COD' then gross_sales else 0 end),
            0
        )::numeric(14,2) as web_cod_gross_sales,
        coalesce(
            sum(case when upper(coalesce(payment_gateway, '')) = 'COD' then net_sales else 0 end),
            0
        )::numeric(14,2) as web_cod_net_sales_without_vat
    from public.web_orders
    where order_status_raw = 'Completed'
    group by location_id, business_date
),
foodpanda_sales as (
    select
        location_id,
        business_date,
        count(*)::integer as foodpanda_orders,
        coalesce(sum(subtotal), 0)::numeric(14,2) as foodpanda_subtotal,
        coalesce(sum(subtotal / 1.12), 0)::numeric(14,2) as foodpanda_vat_deducted_sales
    from public.foodpanda_orders
    where lower(order_status) = 'delivered'
    group by location_id, business_date
),
pos_cups as (
    select
        o.location_id,
        o.business_date,
        coalesce(sum(i.quantity), 0)::integer as pos_cups_sold
    from public.pos_order_items i
    join public.pos_orders o on o.id = i.order_id
    where o.payment_status = 'PAID'
    group by o.location_id, o.business_date
),
web_cups as (
    select
        o.location_id,
        o.business_date,
        coalesce(sum(i.quantity), 0)::integer as web_cups_sold
    from public.web_order_items i
    join public.web_orders o on o.id = i.order_id
    where o.order_status_raw = 'Completed'
    group by o.location_id, o.business_date
),
foodpanda_cups as (
    select
        location_id,
        business_date,
        coalesce(sum(qty_sold), 0)::integer as foodpanda_cups_sold
    from public.foodpanda_daily_item_metrics
    group by location_id, business_date
),
store_days as (
    select distinct location_id, business_date from pos_sales
    union
    select distinct location_id, business_date from web_sales
    union
    select distinct location_id, business_date from foodpanda_sales
    union
    select distinct location_id, business_date from foodpanda_cups
)
select
    d.location_id,
    d.business_date,
    coalesce(s.store_name, cast(d.location_id as text)) as store_name,
    s.legal_entity,
    s.store_type,
    coalesce(pos.pos_orders, 0) as pos_orders,
    coalesce(web.web_orders, 0) as web_orders,
    coalesce(fp.foodpanda_orders, 0) as foodpanda_orders,
    coalesce(pos.pos_orders, 0) + coalesce(web.web_orders, 0) + coalesce(fp.foodpanda_orders, 0) as transactions,
    coalesce(pos.pos_gross_sales, 0)::numeric(14,2) as pos_gross_sales,
    coalesce(pos.pos_net_sales_without_vat, 0)::numeric(14,2) as pos_net_sales_without_vat,
    coalesce(web.web_gross_sales, 0)::numeric(14,2) as web_gross_sales,
    coalesce(web.web_net_sales_without_vat, 0)::numeric(14,2) as web_net_sales_without_vat,
    coalesce(web.web_cod_orders, 0) as web_cod_orders,
    coalesce(web.web_cod_gross_sales, 0)::numeric(14,2) as web_cod_gross_sales,
    coalesce(web.web_cod_net_sales_without_vat, 0)::numeric(14,2) as web_cod_net_sales_without_vat,
    coalesce(fp.foodpanda_subtotal, 0)::numeric(14,2) as foodpanda_subtotal,
    coalesce(fp.foodpanda_vat_deducted_sales, 0)::numeric(14,2) as foodpanda_vat_deducted_sales,
    greatest(
        coalesce(web.web_gross_sales, 0) - coalesce(web.web_cod_gross_sales, 0),
        0
    )::numeric(14,2) as website_non_cod_gross_sales,
    greatest(
        coalesce(web.web_net_sales_without_vat, 0) - coalesce(web.web_cod_net_sales_without_vat, 0),
        0
    )::numeric(14,2) as website_non_cod_net_sales_without_vat,
    coalesce(pc.pos_cups_sold, 0) as pos_cups_sold,
    coalesce(wc.web_cups_sold, 0) as web_cups_sold,
    coalesce(fc.foodpanda_cups_sold, 0) as foodpanda_cups_sold,
    coalesce(pc.pos_cups_sold, 0) + coalesce(wc.web_cups_sold, 0) + coalesce(fc.foodpanda_cups_sold, 0) as cups_sold,
    (
        coalesce(pos.pos_gross_sales, 0)
        + coalesce(web.web_gross_sales, 0)
        + coalesce(fp.foodpanda_subtotal, 0)
    )::numeric(14,2) as total_gross_sales,
    (
        coalesce(pos.pos_net_sales_without_vat, 0)
        + coalesce(web.web_net_sales_without_vat, 0)
        + coalesce(fp.foodpanda_vat_deducted_sales, 0)
    )::numeric(14,2) as total_net_sales_without_vat
from store_days d
left join public.stores s on s.location_id = d.location_id
left join pos_sales pos on pos.location_id = d.location_id and pos.business_date = d.business_date
left join web_sales web on web.location_id = d.location_id and web.business_date = d.business_date
left join foodpanda_sales fp on fp.location_id = d.location_id and fp.business_date = d.business_date
left join pos_cups pc on pc.location_id = d.location_id and pc.business_date = d.business_date
left join web_cups wc on wc.location_id = d.location_id and wc.business_date = d.business_date
left join foodpanda_cups fc on fc.location_id = d.location_id and fc.business_date = d.business_date;

create unique index if not exists idx_sales_dashboard_daily_store_metrics_pk
    on public.sales_dashboard_daily_store_metrics (location_id, business_date);

create index if not exists idx_sales_dashboard_daily_store_metrics_business_date
    on public.sales_dashboard_daily_store_metrics (business_date, location_id);

create index if not exists idx_sales_dashboard_daily_store_metrics_location_date
    on public.sales_dashboard_daily_store_metrics (location_id, business_date);

grant select on public.sales_dashboard_daily_store_metrics to authenticated;

comment on materialized view public.sales_dashboard_daily_store_metrics is
    'Materialized unified daily store metrics for the sales dashboard. Refreshed after POS, Web, FoodPanda order, and FoodPanda cup syncs.';

create or replace function public.refresh_sales_dashboard_daily_store_metrics()
returns void
language plpgsql
as $$
begin
    refresh materialized view public.sales_dashboard_daily_store_metrics;
end;
$$;
