# S207 L3 Verification Summary

**Run timestamp (UTC):** 2026-04-20T08:30:38+00:00
**Totals:** passed=8 · skipped=1 · failed=0 · all_pass_or_skip=True

| # | Scenario | Status | Detail |
|---|---|---|---|
| L3-1_preview_first_half | preview_first_half | PASS | total_slips=0 \| planned_count=0 \| period={"start": "2026-04-01", "end": "2026-04-15"} |
| L3-2_preview_second_half | preview_second_half | PASS | total_slips=0 \| planned_count=0 |
| L3-3_day_guard_day1 | day_guard_day1 | PASS | fired=True \| pht_date=2026-05-01 \| day=1 \| period_start=2026-04-16 |
| L3-4_day_guard_day16 | day_guard_day16 | PASS | fired=True \| pht_date=2026-04-16 \| day=16 \| period_start=2026-04-01 |
| L3-5_day_guard_noop | day_guard_noop | PASS | fired=False \| pht_date=2026-04-08 \| day=8 |
| L3-6_idempotency | idempotency | PASS | first_applied=0 \| second_applied=0 \| second_skipped_idempotent=0 |
| L3-7_posting_date_is_payout_date | posting_date_is_payout_date | SKIP | skipped_reason=No S206/S207 JEs exist yet — unit tests in test_s207_posting_date.py cover the math |
| L3-8_structures_bimonthly | structures_bimonthly | PASS | distinct_frequencies=["Bimonthly"] |
| L3-9_coa_coverage_all_stores | coa_coverage_all_stores | PASS | total_stores=49 \| complete_count=49 \| incomplete_count=0 |
