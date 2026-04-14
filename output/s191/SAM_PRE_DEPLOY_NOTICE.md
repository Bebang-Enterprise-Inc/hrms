# S191 Pre-Deploy Notice — CEO (sam@bebang.ph)

**Sprint:** S191 — FoodPanda Unified Source (Per-Store Rolling Cutover Fix)
**Plan:** docs/plans/2026-04-14-sprint-191-foodpanda-unified-source.md
**Branch / PR:** `s191-foodpanda-unified-source` → production
**Impact:** **Backend-only.** No UI changes. No schema changes. No new endpoints.

## What changes when this deploys

| Surface | Before | After |
|---|---|---|
| Sales Analytics donut, Feb 2026 FP | ₱0 net | **~₱8.5M net** |
| Sales Analytics donut, Mar 2026 FP | ₱4.5M net | **~₱19.4M net** |
| Sales Analytics donut, Apr 2026 FP | ~₱9.5M net | **unchanged** |
| Leaderboard per-store FP column | Mosaic-only | unified (legacy + Mosaic) |
| Daily time-series FP line | non-zero only after Mar 27 | non-zero from Feb 1 |
| Overall delivery total (Feb + early Mar) | inflated by ~₱17M (MV double-count) | **corrected** |
| GrabFood everywhere | unchanged | **unchanged** (CEO directive — S191 does not touch GrabFood) |
| POS / WebDelivery / website | unchanged | **unchanged** |

## Why these numbers change

The Analytics dashboard was overwriting legacy FoodPanda Google-Sheet data with
Mosaic-only values once you entered the post-cutover window. Because the
FoodPanda→Mosaic rollout happened per store over ~1 week in late March (not on
a single global date), the global-date overwrite dropped legitimate pre-cutover
revenue for stores that were still on the legacy sheet.

S191 replaces the global-date overwrite with a per-(store, day) FULL OUTER JOIN
of the two sources. Mosaic wins when it has the complete day's data (≥50% of
the legacy count/gross); otherwise legacy wins. No legacy revenue is dropped.
No post-cutover Mosaic revenue is double-counted.

**This is visibility restoration, not revenue fabrication.** The ~₱17M of
previously-hidden March FoodPanda sales existed in `foodpanda_orders` Supabase
table the whole time — they were just being silently overwritten by the
Mosaic-only channel split helper.

## Downstream reports that will show new numbers

If you have any scheduled reports, board decks, commission calcs, or external
communications that quote the *old* (Mosaic-only) FoodPanda numbers for March
2026, they will no longer match the dashboard after this deploys. Pull the
old numbers from `output/s191/post_fix_reconciliation.md` before the deploy
day if you need to preserve a prior-version snapshot:

- Old Feb FP net: ₱0
- Old March FP net: ₱4,465,088
- Old March FP orders: 8,477

## L3 handoff

After the deploy lands, a fresh Claude session runs `/l3-v2-bei-erp` with
scenarios L3-191-01 through L3-191-15 (see plan). **Wait ≥ 5 minutes after
deploy** so the `summary_s191` / `overview_s191` / `fp_unified_v2` caches fully
supersede anything still holding a pre-deploy payload.

## Rollback

If anything is off, `output/s191/ROLLBACK_RUNBOOK.md` has the 7-step revert
procedure — ~10 minutes end-to-end, no schema to undo.
