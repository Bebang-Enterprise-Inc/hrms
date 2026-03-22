-- Sprint 46
-- Govern the daily_weather contract used by the sales intelligence dashboard.
-- Safe to run against environments where the table already exists.

create table if not exists public.daily_weather (
    location_id integer not null,
    business_date date not null,
    avg_temperature numeric,
    max_temperature numeric,
    min_temperature numeric,
    avg_humidity integer,
    total_precipitation numeric,
    weather_description text,
    weather_code integer,
    avg_wind_speed numeric,
    is_rainy boolean,
    rain_hours integer,
    business_impact text,
    synced_at timestamptz,
    constraint daily_weather_pkey primary key (location_id, business_date)
);

alter table public.daily_weather
    add column if not exists avg_temperature numeric,
    add column if not exists max_temperature numeric,
    add column if not exists min_temperature numeric,
    add column if not exists avg_humidity integer,
    add column if not exists total_precipitation numeric,
    add column if not exists weather_description text,
    add column if not exists weather_code integer,
    add column if not exists avg_wind_speed numeric,
    add column if not exists is_rainy boolean,
    add column if not exists rain_hours integer,
    add column if not exists business_impact text,
    add column if not exists synced_at timestamptz;

create index if not exists idx_daily_weather_business_date
    on public.daily_weather (business_date);

comment on table public.daily_weather is
    'Daily weather facts keyed by Mosaic location_id and Asia/Manila business_date.';

comment on column public.daily_weather.location_id is
    'Mosaic sales location_id used to join store sales to weather.';

comment on column public.daily_weather.business_date is
    'Asia/Manila business date, not UTC timestamp.';

comment on column public.daily_weather.business_impact is
    'Deterministic weather impact label from sync_weather_to_supabase.py.';
