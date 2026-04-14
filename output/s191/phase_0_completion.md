# S191 Phase 0 — Completion Report

| Task | Status | Evidence |
|---|---|---|
| 0.1 Branch created | ✅ | `s191-foodpanda-unified-source` from `origin/production @ 63139b5f1` |
| 0.2 BASELINE.md | ✅ | `output/s191/BASELINE.md` |
| 0.3 Baseline audit SQL | ✅ | `output/s191/baseline_audit.csv` (3087 rows), `BASELINE_SUMMARY.md`, `baseline_metrics.json` |
| 0.4 Dedup check | ✅ | `output/s191/baseline_dedup_check.md` — **0 dupes** → straight SUM |
| 0.5 Caller inventory | ✅ | `output/s191/foodpanda_call_sites_audit.md` — 15 call sites A–O, all covered |

## HARD BLOCKERS — all PASS

- **0-1 (variance + unified total):**
  - March unified GROSS = ₱21,721,417 (≥ ₱20M) ✅
  - Overlap GROSS variance = ₱844,257 (≤ ₱2M) ✅
  - Max single-store-day GROSS variance = ₱37,724 (≤ ₱150K) ✅
- **0-2 (dedup):** 0 duplicate `order_id` in Feb–Mar 2026 delivered FP orders → straight SUM allowed ✅
- **0-3 (caller coverage):** every enumerated call site is bound to a Phase 2/3 task ✅

## Baseline grep counts (anchor for verify_s191.py)

```
foodpanda_vat_deducted_sales        : 6   (expect 5 post-fix — Phase 3.6 removes one)
fp_bucket = split.pop               : 1   (expect 0 post-fix — Phase 2.1 replaces)
_get_unified_foodpanda_totals       : 0   (expect ≥ 4 post-fix)
_get_unified_foodpanda_totals_aggregate : 0 (expect ≥ 2 post-fix)
set_backend_observability_context   : 5   (expect 5 post-fix — unchanged)
grabfood                            : 28  (expect 28 post-fix — anti-regression)
```

## Monthly ground truth (from audit)

| Month | Legacy gross | Mosaic gross | Unified gross (expected) |
|---|---|---|---|
| 2026-02 | ₱9,506,654 | ₱0 | ₱9,506,654 (all legacy) |
| 2026-03 | ₱21,722,238 | ₱5,000,718 | ₱21,721,417 (legacy wins most days) |
| 2026-04 | ₱0 | ₱10,691,820 | ₱10,691,820 (all Mosaic) |

March unified NET (`gross/1.12` for legacy + Mosaic's exact net_sales on overlap) = **₱19,394,423**.

Proceeding to Phase 1.
