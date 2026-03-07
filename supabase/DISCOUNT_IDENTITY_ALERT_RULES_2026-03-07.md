# Discount Identity Alert Rules

Date: 2026-03-07
Scope: Supabase-side same-day and rolling 30-day discount identity alerts for Senior Citizen (`SC`) and optional `PWD`
SQL artifact: `F:\Dropbox\Projects\BEI-ERP\supabase\migrations\20260307_discount_identity_alerts.sql`

## Purpose

This rule set moves the strongest same-day Senior Citizen / PWD identity checks into Supabase so audit can:

- flag repeated names within the same store on the same day
- flag repeated reference numbers within the same store on the same day
- flag multi-store same-day reuse
- flag mismatch patterns where the same name rotates references or the same reference rotates names

The SQL now uses two persistence layers:

- `public.discount_abuse_alerts` for same-day incident alerts
- `public.discount_identity_30d_snapshots` for rolling 30-day review snapshots

Yes, rolling 30-day threshold tracking is part of the audit system design.

The system now has two layers:

- same-day alerts for stronger transactional red flags
- rolling 30-day threshold alerts for repeated name or ID usage within one store

## Source Logic

The migration creates:

- `public.v_discount_identity_order_usage`
- `public.v_discount_identity_rolling_30d_usage`
- `public.v_discount_identity_audit_queue`
- `public.discount_identity_30d_snapshots`
- `public.refresh_discount_identity_monitoring(...)`

That view:

- uses only paid POS orders
- collapses duplicate item rows inside one receipt into one identity row per order
- normalizes names and reference numbers even if older rows were not fully backfilled
- derives `discount_bir_category` from `discount_bir_category`, `discount_name_normalized`, or `discount_name`

This is intentional. Audit alerts should count distinct orders, not item lines.

The rolling 30-day layer lets audit query:

- names used more than `4` times in the last `30` days in one store
- reference numbers used more than `4` times in the last `30` days in one store
- rolling 30-day repeated names with multiple references
- rolling 30-day repeated reference numbers with multiple names

Important separation:

- same-day logic persists to `discount_abuse_alerts`
- rolling 30-day logic persists to `discount_identity_30d_snapshots`
- the audit queue view unions both layers and ranks them for review

This prevents trend-review rows from polluting the incident alert table.

## Alert Types

### Same-Day Alert Types

| Detection type | Scope | Identity axis | Condition | Severity |
| --- | --- | --- | --- | --- |
| `same_name_same_day_same_store` | one store, one day | normalized name | same normalized name appears in `2+` distinct paid orders in one store on one day | `medium` |
| `same_name_same_day_multi_store` | cross-store, one day | normalized name | same normalized name appears in `2+` distinct paid orders across `2+` stores on one day | `medium` |
| `same_name_diff_reference_same_day_same_store` | one store, one day | normalized name | same normalized name appears in `2+` distinct orders and has `2+` distinct normalized references | `high` |
| `same_name_diff_reference_same_day_multi_store` | cross-store, one day | normalized name | same normalized name appears across `2+` stores and has `2+` distinct normalized references | `high` |
| `same_reference_same_day_same_store` | one store, one day | normalized reference | same normalized reference appears in `2+` distinct paid orders in one store on one day | `high` |
| `same_reference_same_day_multi_store` | cross-store, one day | normalized reference | same normalized reference appears in `2+` distinct paid orders across `2+` stores on one day | `critical` |
| `same_reference_diff_name_same_day_same_store` | one store, one day | normalized reference | same normalized reference appears in `2+` distinct orders and has `2+` distinct normalized names | `critical` |
| `same_reference_diff_name_same_day_multi_store` | cross-store, one day | normalized reference | same normalized reference appears across `2+` stores and has `2+` distinct normalized names | `critical` |

### Rolling 30-Day Threshold Snapshot Types

| Detection type | Scope | Identity axis | Condition | Severity |
| --- | --- | --- | --- | --- |
| `rolling_30d_name_threshold_same_store` | one store, last 30 days | normalized name | same normalized name appears in more than `4` distinct paid orders in the last `30` days in one store | `review` |
| `rolling_30d_name_diff_reference_threshold_same_store` | one store, last 30 days | normalized name | same normalized name is used more than `4` times in the last `30` days and has `2+` normalized references | `high` |
| `rolling_30d_reference_threshold_same_store` | one store, last 30 days | normalized reference | same normalized reference appears in more than `4` distinct paid orders in the last `30` days in one store | `review` |
| `rolling_30d_reference_diff_name_threshold_same_store` | one store, last 30 days | normalized reference | same normalized reference is used more than `4` times in the last `30` days and has `2+` normalized names | `high` |

## Why The Rules Are Split This Way

The abuse pattern can rotate one side of the identity while keeping the other side constant.

- If you only monitor name reuse, abuse can rotate reference numbers.
- If you only monitor reference reuse, abuse can rotate names.
- If you monitor both axes separately, audit can see:
  - exact repeats
  - same name with changed reference
  - same reference with changed name
  - same-day cross-store reuse

This is why the SQL intentionally allows correlated alerts on the same incident cluster.

## How To Read Overlapping Alerts

One incident can produce more than one alert row.

Examples:

- Same name repeated twice in one store with the same reference:
  - `same_name_same_day_same_store`
  - `same_reference_same_day_same_store`

- Same name repeated twice in one store with different references:
  - `same_name_same_day_same_store`
  - `same_name_diff_reference_same_day_same_store`

- Same reference reused under different names:
  - `same_reference_same_day_same_store`
  - `same_reference_diff_name_same_day_same_store`

Audit should treat overlapping rows as one investigation cluster, not as separate incidents to count independently.

## Detail Payload

Each alert writes a `details` JSON payload with:

- `location_ids`
- `store_names`
- `order_ids`
- `bill_numbers`
- `receipt_numbers` where available
- `customer_names`
- `reference_numbers`
- `distinct_name_count` or `distinct_reference_count`
- `first_billed_at`
- `last_billed_at`
- `first_paid_at`
- `last_paid_at`
- `min_gap_minutes`
- `rapid_within_4h`
- `discount_amount_total`

The `rapid_within_4h` flag is not its own alert type in v1. It is a prioritization signal inside the alert payload.

## Recommended Audit Triage

Priority order:

1. `critical`
2. `high`
3. `medium`
4. `review`

Within the same severity, audit should sort first by:

1. `details.rapid_within_4h = true`
2. larger `order_count`
3. larger `store_count`
4. larger `discount_amount_total`

Same-day alerts should always be reviewed before rolling 30-day threshold snapshots.

## Audit Queue View

`public.v_discount_identity_audit_queue` is the audit-facing queue.

It combines:

- unresolved rows from `public.discount_abuse_alerts`
- the latest available `public.discount_identity_30d_snapshots`

It exposes ranking columns so audit can work the queue in this order:

1. `queue_bucket_rank`
2. `severity_rank`
3. `rapid_rank`
4. `min_gap_minutes`
5. `discount_amount_total desc`
6. `order_count desc`

Interpretation:

- `same_day` rows always come before `rolling_30d`
- `critical` comes before `high`, then `medium`, then `review`
- `rapid_within_4h = true` rises to the top within the same severity

Recommended query:

```sql
select *
from public.v_discount_identity_audit_queue
order by
  queue_bucket_rank,
  severity_rank,
  rapid_rank,
  coalesce(min_gap_minutes, 999999),
  discount_amount_total desc,
  order_count desc;
```

## Operational Guidance

What this SQL does well:

- same-day reuse inside one store
- same-day reuse across stores
- same name with rotating references
- same reference with rotating names
- rolling 30-day repeated usage above the `> 4` threshold
- rolling 30-day repeated usage with name/reference inconsistency

What it does not prove by itself:

- theft by a specific cashier
- whether a senior group availed legitimately on one receipt
- whether an entry issue was clerical or deliberate

Personnel-level attribution still needs:

- cashier or till session linkage
- CCTV windows
- voids, returns, and cash variance review

## Suggested Execution Order

Backfill or one-day test:

```sql
select public.refresh_discount_identity_alerts(date '2026-02-01', array['SC']);
```

Rolling 30-day threshold refresh:

```sql
select public.refresh_discount_rolling_30d_identity_alerts(
  date '2026-02-28',
  array['SC', 'PWD'],
  4,
  4
);
```

The threshold parameters are strict `>` comparisons.

- `4` means fire when usage is `5+`
- if you want fire at `4+`, pass `3`

One complete month:

```sql
do $$
declare
  d date := date '2026-02-01';
begin
  while d <= date '2026-02-28' loop
    perform public.refresh_discount_identity_alerts(d, array['SC']);
    d := d + interval '1 day';
  end loop;
end $$;
```

Optional scheduled refresh after POS sync approval:

```sql
select public.refresh_discount_identity_monitoring(
  date '2026-03-06',
  array['SC'],
  array['SC', 'PWD'],
  4,
  4
);
```

Operational wrapper:

```sql
select public.refresh_discount_identity_monitoring(
  ((now() at time zone 'Asia/Manila')::date - 1),
  array['SC'],
  array['SC', 'PWD'],
  4,
  4
);
```

Scheduled refresh now uses one cron job:

```sql
select cron.schedule(
  'refresh-discount-identity-monitoring',
  '35 16 * * *',
  $$select public.refresh_discount_identity_monitoring(
      ((now() at time zone 'Asia/Manila')::date - 1),
      array['SC'],
      array['SC', 'PWD'],
      4,
      4
    );$$
);
```

That runs at `00:35 PHT` and refreshes the prior Manila business date.

Use a post-sync hook instead if you later want immediate refresh after every daily POS load rather than one fixed scheduled refresh.

## Direct Rolling 30-Day Queries

Current rolling `30`-day names used more than `4` times in one store:

```sql
select *
from public.v_discount_identity_rolling_30d_usage
where discount_bir_category in ('SC', 'PWD')
  and identity_type = 'full_name'
  and order_count > 4
order by location_id, order_count desc, identity_key;
```

Current rolling `30`-day reference numbers used more than `4` times in one store:

```sql
select *
from public.v_discount_identity_rolling_30d_usage
where discount_bir_category in ('SC', 'PWD')
  and identity_type = 'reference_number'
  and order_count > 4
order by location_id, order_count desc, identity_key;
```

Current rolling `30`-day repeats with inconsistency:

```sql
select *
from public.v_discount_identity_rolling_30d_usage
where discount_bir_category in ('SC', 'PWD')
  and order_count > 4
  and distinct_counterparty_count > 1
order by location_id, identity_type, order_count desc, identity_key;
```

Persisted rolling `30`-day review snapshots after refresh:

```sql
select *
from public.discount_identity_30d_snapshots
where as_of_date = date '2026-02-28'
order by location_id, detection_type, order_count desc, identity_key;
```

## Recommended Default Scope

Start with `SC` only.

Reason:

- the February 2026 North vs Megamall audit showed the stronger suspicious pattern in `Senior Citizen`
- `PWD` same-day duplicate control was clean in that comparison window

After audit validates the workflow, expand to `array['SC', 'PWD']` if needed.
