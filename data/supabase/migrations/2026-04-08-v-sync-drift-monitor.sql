-- S171 Phase 9: drift monitor view
-- Per-(store, date) drift between Mosaic count (from sync_verification) and the
-- current live Supabase count (from v_pos_orders_live wrapper view).
--
-- BI can SELECT * FROM public.v_sync_drift_monitor WHERE drift_now <> 0
-- to find any (store, date) tuple still drifting against Mosaic.
--
-- The view filters via v_pos_orders_live so it respects the S169 cancelled_at
-- wrapper -- tombstoned rows are excluded from the live count.

CREATE OR REPLACE VIEW public.v_sync_drift_monitor AS
WITH latest_sv AS (
    SELECT DISTINCT ON (location_id, business_date)
        location_id,
        business_date,
        mosaic_total,
        supabase_total,
        status,
        verified_at
    FROM public.sync_verification
    WHERE verified_at >= NOW() - INTERVAL '30 days'
    ORDER BY location_id, business_date, verified_at DESC
)
SELECT
    sv.location_id,
    sv.business_date,
    sv.mosaic_total,
    sv.supabase_total,
    sv.status                                                 AS last_status,
    sv.verified_at                                            AS last_verified_at,
    (
        SELECT COUNT(*)::int FROM public.v_pos_orders_live v
        WHERE v.location_id = sv.location_id
          AND v.business_date = sv.business_date
    )                                                         AS supabase_live_now,
    (
        sv.mosaic_total
        - (
            SELECT COUNT(*)::int FROM public.v_pos_orders_live v
            WHERE v.location_id = sv.location_id
              AND v.business_date = sv.business_date
        )
    )                                                         AS drift_now
FROM latest_sv sv;

COMMENT ON VIEW public.v_sync_drift_monitor IS
    'S171 drift monitor: per-(store, date) drift between Mosaic count (from '
    'sync_verification, latest verified_at per tuple) and current live Supabase '
    'count (from v_pos_orders_live -- the S169 cancelled_at wrapper). Refreshes '
    'live with every sync_verification insert; reads always reflect the current '
    'tombstone state. BI can SELECT to find any (store, date) where drift_now '
    '<> 0. See docs/plans/2026-04-08-sprint-171-mosaic-website-sync-full-validation.md.';
