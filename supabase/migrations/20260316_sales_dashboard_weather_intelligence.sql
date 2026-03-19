-- ============================================================================
-- Migration: sales dashboard weather intelligence foundation
-- Date: 2026-03-16
-- Purpose:
--   1. store hourly weather facts keyed by Mosaic location_id and Manila business date
--   2. expose a materialized daily feature layer for dashboard weather analytics
-- ============================================================================

create table if not exists public.weather_hourly (
    location_id integer not null references public.stores(location_id),
    observed_at_utc timestamptz not null,
    observed_at_manila timestamp without time zone not null,
    business_date date not null,
    hour_local smallint not null,
    precipitation numeric,
    precipitation_probability integer,
    weather_code integer,
    temperature_2m numeric,
    apparent_temperature numeric,
    wind_speed_10m numeric,
    wind_gusts_10m numeric,
    cloud_cover integer,
    synced_at timestamptz not null default now(),
    constraint weather_hourly_pkey primary key (location_id, observed_at_utc)
);

alter table public.weather_hourly
    add column if not exists observed_at_manila timestamp without time zone,
    add column if not exists business_date date,
    add column if not exists hour_local smallint,
    add column if not exists precipitation numeric,
    add column if not exists precipitation_probability integer,
    add column if not exists weather_code integer,
    add column if not exists temperature_2m numeric,
    add column if not exists apparent_temperature numeric,
    add column if not exists wind_speed_10m numeric,
    add column if not exists wind_gusts_10m numeric,
    add column if not exists cloud_cover integer,
    add column if not exists synced_at timestamptz;

create index if not exists idx_weather_hourly_business_date
    on public.weather_hourly (business_date, location_id);

create index if not exists idx_weather_hourly_location_hour
    on public.weather_hourly (location_id, observed_at_manila);

comment on table public.weather_hourly is
    'Hourly weather facts keyed by Mosaic location_id and UTC observation timestamp, with Asia/Manila local time derivatives for service-window analytics.';

comment on column public.weather_hourly.business_date is
    'Asia/Manila business date derived from observed_at_manila.';

comment on column public.weather_hourly.hour_local is
    'Local Manila hour used for lunch/dinner weather feature derivation.';

do $$
begin
    if exists (
        select 1
        from pg_matviews
        where schemaname = 'public'
          and matviewname = 'sales_dashboard_weather_daily_features'
    ) then
        execute 'drop materialized view public.sales_dashboard_weather_daily_features';
    elsif exists (
        select 1
        from pg_views
        where schemaname = 'public'
          and viewname = 'sales_dashboard_weather_daily_features'
    ) then
        execute 'drop view public.sales_dashboard_weather_daily_features';
    end if;
end $$;

create materialized view public.sales_dashboard_weather_daily_features as
with hourly_rollup as (
    select
        wh.location_id,
        wh.business_date,
        max(wh.apparent_temperature)::numeric(10,2) as apparent_temperature_max,
        avg(wh.wind_speed_10m)::numeric(10,2) as avg_hourly_wind_speed,
        max(coalesce(wh.wind_gusts_10m, wh.wind_speed_10m))::numeric(10,2) as max_wind_speed,
        sum(case when coalesce(wh.precipitation, 0) > 0 then 1 else 0 end)::integer as precipitation_hours,
        max(coalesce(wh.precipitation, 0))::numeric(10,2) as max_hourly_precipitation,
        bool_or(coalesce(wh.weather_code, 0) in (95, 96, 99)) as storm_flag,
        avg(case when wh.hour_local between 11 and 14 then wh.apparent_temperature end)::numeric(10,2) as lunch_apparent_temperature,
        avg(case when wh.hour_local between 17 and 20 then wh.apparent_temperature end)::numeric(10,2) as dinner_apparent_temperature,
        sum(case when wh.hour_local between 11 and 14 and coalesce(wh.precipitation, 0) > 0 then 1 else 0 end)::integer as lunch_precipitation_hours,
        sum(case when wh.hour_local between 17 and 20 and coalesce(wh.precipitation, 0) > 0 then 1 else 0 end)::integer as dinner_precipitation_hours,
        max(case when wh.hour_local between 11 and 14 then coalesce(wh.precipitation, 0) else 0 end)::numeric(10,2) as lunch_peak_precipitation,
        max(case when wh.hour_local between 17 and 20 then coalesce(wh.precipitation, 0) else 0 end)::numeric(10,2) as dinner_peak_precipitation,
        count(*)::integer as hourly_points
    from public.weather_hourly wh
    group by wh.location_id, wh.business_date
),
joined as (
    select
        dw.location_id,
        dw.business_date,
        dw.avg_temperature,
        dw.max_temperature,
        dw.min_temperature,
        dw.avg_humidity,
        dw.total_precipitation,
        dw.weather_description,
        dw.weather_code,
        dw.avg_wind_speed,
        dw.business_impact,
        coalesce(hr.apparent_temperature_max, dw.max_temperature)::numeric(10,2) as apparent_temperature_max,
        coalesce(hr.avg_hourly_wind_speed, dw.avg_wind_speed)::numeric(10,2) as avg_hourly_wind_speed,
        coalesce(hr.max_wind_speed, dw.avg_wind_speed, 0)::numeric(10,2) as max_wind_speed,
        coalesce(hr.precipitation_hours, dw.rain_hours, 0) as precipitation_hours,
        coalesce(hr.max_hourly_precipitation, 0)::numeric(10,2) as max_hourly_precipitation,
        coalesce(hr.storm_flag, false) as storm_flag,
        hr.lunch_apparent_temperature,
        hr.dinner_apparent_temperature,
        coalesce(hr.lunch_precipitation_hours, 0) as lunch_precipitation_hours,
        coalesce(hr.dinner_precipitation_hours, 0) as dinner_precipitation_hours,
        coalesce(hr.lunch_peak_precipitation, 0)::numeric(10,2) as lunch_peak_precipitation,
        coalesce(hr.dinner_peak_precipitation, 0)::numeric(10,2) as dinner_peak_precipitation,
        coalesce(hr.hourly_points, 0) as hourly_points,
        dw.synced_at
    from public.daily_weather dw
    left join hourly_rollup hr
        on hr.location_id = dw.location_id
       and hr.business_date = dw.business_date
),
rolling as (
    select
        j.*,
        avg(j.max_temperature) over (
            partition by j.location_id
            order by j.business_date
            rows between 28 preceding and 1 preceding
        )::numeric(10,2) as trailing_28d_avg_max_temperature
    from joined j
)
select
    r.location_id,
    r.business_date,
    r.avg_temperature,
    r.max_temperature,
    r.min_temperature,
    r.avg_humidity,
    r.total_precipitation,
    r.weather_description,
    r.weather_code,
    r.avg_wind_speed,
    r.business_impact,
    r.apparent_temperature_max,
    r.avg_hourly_wind_speed,
    r.max_wind_speed,
    r.precipitation_hours,
    r.max_hourly_precipitation,
    r.storm_flag,
    r.lunch_apparent_temperature,
    r.dinner_apparent_temperature,
    r.lunch_precipitation_hours,
    r.dinner_precipitation_hours,
    r.lunch_peak_precipitation,
    r.dinner_peak_precipitation,
    r.hourly_points,
    (r.hourly_points > 0) as hourly_backed,
    case
        when r.trailing_28d_avg_max_temperature is null then null
        else round(r.max_temperature - r.trailing_28d_avg_max_temperature, 2)
    end as temperature_anomaly_vs_28d,
    case
        when r.trailing_28d_avg_max_temperature is null then 'normal'
        when (r.max_temperature - r.trailing_28d_avg_max_temperature) <= -1.5 then 'cooler_than_normal'
        when (r.max_temperature - r.trailing_28d_avg_max_temperature) >= 1.5 then 'hotter_than_normal'
        else 'normal'
    end as temperature_state,
    case
        when coalesce(r.total_precipitation, 0) = 0 and coalesce(r.precipitation_hours, 0) = 0 then 'dry'
        when coalesce(r.storm_flag, false)
            or coalesce(r.max_hourly_precipitation, 0) >= 7.5
            or coalesce(r.total_precipitation, 0) >= 20
            or coalesce(r.precipitation_hours, 0) >= 6 then 'disruptive_rain'
        when coalesce(r.max_hourly_precipitation, 0) < 2.5
            and coalesce(r.precipitation_hours, 0) <= 2 then 'passing_showers'
        else 'wet'
    end as rain_severity,
    case
        when coalesce(r.max_wind_speed, 0) >= 45 then 'high'
        when coalesce(r.max_wind_speed, 0) >= 25 then 'moderate'
        else 'low'
    end as wind_disruption_level,
    case
        when coalesce(r.lunch_peak_precipitation, 0) >= 7.5
            or coalesce(r.lunch_precipitation_hours, 0) >= 2 then 'disruptive_lunch_rain'
        when coalesce(r.lunch_precipitation_hours, 0) > 0 then 'showery_lunch'
        when coalesce(r.lunch_apparent_temperature, 0) >= 34 then 'hot_lunch'
        else 'stable_lunch'
    end as service_window_weather_summary_lunch,
    case
        when coalesce(r.dinner_peak_precipitation, 0) >= 7.5
            or coalesce(r.dinner_precipitation_hours, 0) >= 2 then 'disruptive_dinner_rain'
        when coalesce(r.dinner_precipitation_hours, 0) > 0 then 'showery_dinner'
        when coalesce(r.dinner_apparent_temperature, 0) >= 34 then 'hot_dinner'
        else 'stable_dinner'
    end as service_window_weather_summary_dinner,
    case
        when coalesce(r.storm_flag, false)
            or coalesce(r.max_hourly_precipitation, 0) >= 7.5
            or coalesce(r.total_precipitation, 0) >= 20
            or coalesce(r.precipitation_hours, 0) >= 6 then true
        when coalesce(r.max_hourly_precipitation, 0) < 2.5
            and coalesce(r.precipitation_hours, 0) <= 2 then false
        when coalesce(r.total_precipitation, 0) > 0 then true
        else false
    end as is_rainy,
    r.synced_at
from rolling r;

create unique index if not exists idx_sales_dashboard_weather_daily_features_pk
    on public.sales_dashboard_weather_daily_features (location_id, business_date);

create index if not exists idx_sales_dashboard_weather_daily_features_business_date
    on public.sales_dashboard_weather_daily_features (business_date, location_id);

grant select on public.weather_hourly to authenticated;
grant select on public.sales_dashboard_weather_daily_features to authenticated;

comment on materialized view public.sales_dashboard_weather_daily_features is
    'Daily weather intelligence features for the sales dashboard, derived from daily_weather and weather_hourly.';

create or replace function public.refresh_sales_dashboard_weather_daily_features()
returns void
language plpgsql
as $$
begin
    refresh materialized view public.sales_dashboard_weather_daily_features;
end;
$$;
