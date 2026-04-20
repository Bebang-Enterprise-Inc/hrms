# S207 L3 Verification Summary

**Run timestamp (UTC):** 2026-04-20T03:37:17+00:00
**Totals:** passed=5 · skipped=4 · failed=0 · all_pass_or_skip=True

| # | Scenario | Status | Detail |
|---|---|---|---|
| L3-1_preview_first_half | preview_first_half | SKIP | skipped_reason=S207 preview_allocation not on container yet — re-run after merge + deploy |
| L3-2_preview_second_half | preview_second_half | SKIP | skipped_reason=S207 preview_allocation not on container yet — re-run after merge + deploy |
| L3-3_day_guard_day1 | day_guard_day1 | PASS | fired=True \| pht_date=2026-05-01 \| day=1 \| period_start=2026-04-16 |
| L3-4_day_guard_day16 | day_guard_day16 | PASS | fired=True \| pht_date=2026-04-16 \| day=16 \| period_start=2026-04-01 |
| L3-5_day_guard_noop | day_guard_noop | PASS | fired=False \| pht_date=2026-04-08 \| day=8 |
| L3-6_idempotency | idempotency | SKIP | skipped_reason=Set S207_APPLY_L3=1 to enable destructive idempotency test |
| L3-7_posting_date_is_payout_date | posting_date_is_payout_date | SKIP | skipped_reason=Requires L3-6 posted JEs (set S207_APPLY_L3=1) |
| L3-8_structures_bimonthly | structures_bimonthly | PASS | distinct_frequencies=["Bimonthly"] |
| L3-9_coa_coverage_all_stores | coa_coverage_all_stores | PASS | total_stores=49 \| complete_count=49 \| incomplete_count=0 |
