-- ============================================================================
-- Migration: Discount identity alert operations
-- Date: 2026-03-07
-- Why: Operationalize the discount identity alert system with:
--   - one wrapper refresh function for daily execution
--   - one audit queue view ranked for review priority
--   - one pg_cron job to refresh yesterday's queue automatically
-- Notes:
--   - Same-day incidents stay in public.discount_abuse_alerts
--   - Rolling 30-day review rows stay in public.discount_identity_30d_snapshots
--   - Cron is scheduled in UTC. 16:35 UTC = 00:35 PHT the next day.
-- ============================================================================

create or replace function public.refresh_discount_identity_monitoring(
  p_business_date date default ((now() at time zone 'Asia/Manila')::date - 1),
  p_same_day_categories text[] default array['SC'],
  p_rolling_categories text[] default array['SC', 'PWD'],
  p_name_order_threshold integer default 4,
  p_reference_order_threshold integer default 4
)
returns jsonb
language plpgsql
as $$
declare
  v_same_day_count integer;
  v_rolling_count integer;
begin
  v_same_day_count := public.refresh_discount_identity_alerts(
    p_business_date,
    p_same_day_categories
  );

  v_rolling_count := public.refresh_discount_rolling_30d_identity_alerts(
    p_business_date,
    p_rolling_categories,
    p_name_order_threshold,
    p_reference_order_threshold
  );

  return jsonb_build_object(
    'business_date', p_business_date,
    'same_day_categories', p_same_day_categories,
    'rolling_categories', p_rolling_categories,
    'name_order_threshold', p_name_order_threshold,
    'reference_order_threshold', p_reference_order_threshold,
    'same_day_count', v_same_day_count,
    'rolling_30d_count', v_rolling_count,
    'refreshed_at', now()
  );
end;
$$;

create or replace view public.v_discount_identity_audit_queue as
with same_day_queue as (
  select
    'same_day'::text as queue_bucket,
    1::integer as queue_bucket_rank,
    a.business_date as event_date,
    a.business_date as window_start,
    a.business_date as window_end,
    a.scope,
    a.scope_key,
    a.location_id,
    a.store_name,
    a.discount_name,
    a.discount_bir_category,
    a.identity_type,
    a.identity_key,
    a.customer_name,
    a.reference_number,
    a.order_count,
    a.store_count,
    null::integer as active_day_count,
    null::integer as distinct_counterparty_count,
    a.detection_type,
    a.severity,
    coalesce((a.details ->> 'rapid_within_4h')::boolean, false) as rapid_within_4h,
    nullif(a.details ->> 'min_gap_minutes', '')::numeric as min_gap_minutes,
    coalesce(nullif(a.details ->> 'discount_amount_total', '')::numeric, 0::numeric) as discount_amount_total,
    a.resolved,
    a.notified_at,
    a.created_at,
    a.updated_at,
    a.details
  from public.discount_abuse_alerts a
  where a.resolved = false
),
rolling_queue as (
  select
    'rolling_30d'::text as queue_bucket,
    2::integer as queue_bucket_rank,
    s.as_of_date as event_date,
    s.window_start,
    s.window_end,
    s.scope,
    s.scope_key,
    s.location_id,
    s.store_name,
    s.discount_name,
    s.discount_bir_category,
    s.identity_type,
    s.identity_key,
    s.customer_name,
    s.reference_number,
    s.order_count,
    1::integer as store_count,
    s.active_day_count,
    s.distinct_counterparty_count,
    s.detection_type,
    s.severity,
    false as rapid_within_4h,
    null::numeric as min_gap_minutes,
    coalesce(nullif(s.details ->> 'discount_amount_total', '')::numeric, 0::numeric) as discount_amount_total,
    false as resolved,
    null::timestamptz as notified_at,
    s.created_at,
    s.updated_at,
    s.details
  from public.discount_identity_30d_snapshots s
  where s.as_of_date = (
    select max(as_of_date)
    from public.discount_identity_30d_snapshots
  )
),
queue_union as (
  select * from same_day_queue
  union all
  select * from rolling_queue
)
select
  q.queue_bucket,
  q.queue_bucket_rank,
  case q.severity
    when 'critical' then 1
    when 'high' then 2
    when 'medium' then 3
    when 'review' then 4
    else 9
  end as severity_rank,
  case when q.rapid_within_4h then 0 else 1 end as rapid_rank,
  q.event_date,
  q.window_start,
  q.window_end,
  q.scope,
  q.scope_key,
  q.location_id,
  q.store_name,
  q.discount_name,
  q.discount_bir_category,
  q.identity_type,
  q.identity_key,
  q.customer_name,
  q.reference_number,
  q.order_count,
  q.store_count,
  q.active_day_count,
  q.distinct_counterparty_count,
  q.detection_type,
  q.severity,
  q.rapid_within_4h,
  q.min_gap_minutes,
  q.discount_amount_total,
  q.resolved,
  q.notified_at,
  q.created_at,
  q.updated_at,
  q.details
from queue_union q
order by
  q.queue_bucket_rank,
  case q.severity
    when 'critical' then 1
    when 'high' then 2
    when 'medium' then 3
    when 'review' then 4
    else 9
  end,
  case when q.rapid_within_4h then 0 else 1 end,
  coalesce(q.min_gap_minutes, 999999::numeric),
  q.discount_amount_total desc,
  q.order_count desc,
  coalesce(q.active_day_count, 0) desc,
  q.event_date desc,
  q.location_id nulls last,
  q.identity_key;

do $job$
declare
  v_job record;
begin
  if exists (
    select 1
    from pg_extension
    where extname = 'pg_cron'
  ) then
    for v_job in
      select jobid
      from cron.job
      where jobname = 'refresh-discount-identity-monitoring'
    loop
      perform cron.unschedule(v_job.jobid);
    end loop;

    perform cron.schedule(
      'refresh-discount-identity-monitoring',
      '35 16 * * *',
      $cmd$
      select public.refresh_discount_identity_monitoring(
        ((now() at time zone 'Asia/Manila')::date - 1),
        array['SC'],
        array['SC', 'PWD'],
        4,
        4
      );
      $cmd$
    );
  else
    raise notice 'pg_cron extension is not installed; skipping refresh-discount-identity-monitoring schedule';
  end if;
end;
$job$;

comment on function public.refresh_discount_identity_monitoring(date, text[], text[], integer, integer) is
  'Refresh same-day SC alerts and rolling 30-day SC/PWD review snapshots for one Manila business date.';

comment on view public.v_discount_identity_audit_queue is
  'Audit-facing ranked queue combining unresolved same-day incidents and the latest rolling 30-day review snapshot.';
