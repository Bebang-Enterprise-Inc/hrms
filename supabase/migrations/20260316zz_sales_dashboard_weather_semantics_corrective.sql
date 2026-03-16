-- ============================================================================
-- Migration: sales dashboard weather semantics corrective pass
-- Date: 2026-03-16
-- Purpose:
--   1. make temperature-first weather analytics use apparent temperature
--   2. stop escalating prolonged light drizzle into disruptive rain
--   3. tighten lunch/dinner disruption rules to require intensity, not just duration
-- ============================================================================

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
        avg(coalesce(j.apparent_temperature_max, j.max_temperature)) over (
            partition by j.location_id
            order by j.business_date
            rows between 28 preceding and 1 preceding
        )::numeric(10,2) as trailing_28d_avg_apparent_temperature_max
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
    case
        when coalesce(r.apparent_temperature_max, r.max_temperature, 0) >= 33
            and coalesce(r.total_precipitation, 0) = 0
            and coalesce(r.weather_code, 0) < 3 then 'peak'
        when coalesce(r.storm_flag, false)
            or coalesce(r.max_hourly_precipitation, 0) >= 7.5
            or coalesce(r.total_precipitation, 0) >= 20
            or (
                coalesce(r.max_hourly_precipitation, 0) >= 4
                and coalesce(r.precipitation_hours, 0) >= 4
            )
            or (
                coalesce(r.precipitation_hours, 0) >= 6
                and coalesce(r.total_precipitation, 0) >= 10
            ) then 'disruptive_rain'
        when coalesce(r.max_hourly_precipitation, 0) < 2.5
            and coalesce(r.precipitation_hours, 0) <= 2
            and coalesce(r.total_precipitation, 0) > 0 then 'passing_showers'
        when coalesce(r.total_precipitation, 0) > 0 then 'wet'
        when coalesce(r.apparent_temperature_max, r.max_temperature, 0) <= 27 then 'cool'
        else 'normal'
    end as business_impact,
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
        when r.trailing_28d_avg_apparent_temperature_max is null then null
        else round(coalesce(r.apparent_temperature_max, r.max_temperature) - r.trailing_28d_avg_apparent_temperature_max, 2)
    end as temperature_anomaly_vs_28d,
    case
        when r.trailing_28d_avg_apparent_temperature_max is null then 'normal'
        when (coalesce(r.apparent_temperature_max, r.max_temperature) - r.trailing_28d_avg_apparent_temperature_max) <= -1.5 then 'cooler_than_normal'
        when (coalesce(r.apparent_temperature_max, r.max_temperature) - r.trailing_28d_avg_apparent_temperature_max) >= 1.5 then 'hotter_than_normal'
        else 'normal'
    end as temperature_state,
    case
        when coalesce(r.total_precipitation, 0) = 0 and coalesce(r.precipitation_hours, 0) = 0 then 'dry'
        when coalesce(r.storm_flag, false)
            or coalesce(r.max_hourly_precipitation, 0) >= 7.5
            or coalesce(r.total_precipitation, 0) >= 20
            or (
                coalesce(r.max_hourly_precipitation, 0) >= 4
                and coalesce(r.precipitation_hours, 0) >= 4
            )
            or (
                coalesce(r.precipitation_hours, 0) >= 6
                and coalesce(r.total_precipitation, 0) >= 10
            ) then 'disruptive_rain'
        when coalesce(r.max_hourly_precipitation, 0) < 2.5
            and coalesce(r.precipitation_hours, 0) <= 2
            and coalesce(r.total_precipitation, 0) > 0 then 'passing_showers'
        else 'wet'
    end as rain_severity,
    case
        when coalesce(r.max_wind_speed, 0) >= 45 then 'high'
        when coalesce(r.max_wind_speed, 0) >= 25 then 'moderate'
        else 'low'
    end as wind_disruption_level,
    case
        when coalesce(r.lunch_peak_precipitation, 0) >= 7.5
            or (
                coalesce(r.lunch_peak_precipitation, 0) >= 4
                and coalesce(r.lunch_precipitation_hours, 0) >= 2
            ) then 'disruptive_lunch_rain'
        when coalesce(r.lunch_precipitation_hours, 0) > 0 then 'showery_lunch'
        when coalesce(r.lunch_apparent_temperature, 0) >= 34 then 'hot_lunch'
        else 'stable_lunch'
    end as service_window_weather_summary_lunch,
    case
        when coalesce(r.dinner_peak_precipitation, 0) >= 7.5
            or (
                coalesce(r.dinner_peak_precipitation, 0) >= 4
                and coalesce(r.dinner_precipitation_hours, 0) >= 2
            ) then 'disruptive_dinner_rain'
        when coalesce(r.dinner_precipitation_hours, 0) > 0 then 'showery_dinner'
        when coalesce(r.dinner_apparent_temperature, 0) >= 34 then 'hot_dinner'
        else 'stable_dinner'
    end as service_window_weather_summary_dinner,
    case
        when coalesce(r.storm_flag, false)
            or coalesce(r.max_hourly_precipitation, 0) >= 7.5
            or coalesce(r.total_precipitation, 0) >= 20
            or (
                coalesce(r.max_hourly_precipitation, 0) >= 4
                and coalesce(r.precipitation_hours, 0) >= 4
            )
            or (
                coalesce(r.precipitation_hours, 0) >= 6
                and coalesce(r.total_precipitation, 0) >= 10
            ) then true
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

grant select on public.sales_dashboard_weather_daily_features to authenticated;

comment on materialized view public.sales_dashboard_weather_daily_features is
    'Daily weather intelligence features for the sales dashboard, with apparent-temperature anomaly and conservative rain disruption thresholds.';

create or replace function public.refresh_sales_dashboard_weather_daily_features()
returns void
language plpgsql
as $$
begin
    refresh materialized view public.sales_dashboard_weather_daily_features;
end;
$$;
