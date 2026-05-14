# S248 Phase 1 Checklist — Write seedFromDenisePaymentPlan_()

| # | Task | Status | Evidence | Skipped? |
|---|---|---|---|---|
| 1.1 | Add `seedFromDenisePaymentPlan_()` function | DONE | `scripts/google_apps/s248_ap_view_hourly_sync_v37.gs` contains the function (71,248 chars total, +11,624 vs v3.6) | NO |
| 1.2 | Function reads from 4 tabs of Denise sheet | DONE | TAB_CONFIG array with 4 entries: Suppliers w/o FD & Middleby, Middleby, Forward Dynamics, Masterlist | NO |
| 1.3 | Build header→index map by NAME (not hardcoded) | DONE | `hIdx(name)` closure inside the loop | NO |
| 1.4 | Build dedup index from AP Master + intra-Denise | DONE | `existingIndex` (from caller) + `seenThisRun` (intra-Denise) | NO |
| 1.5 | Skip blank Supplier + outstanding ≤ 0 | DONE | `if (!supplier) { stats.skipped_blank++; continue; }` + `if (outstanding <= 0) { stats.skipped_paid++; continue; }` | NO |
| 1.6 | mapDeniseToApStatus_ helper with fallback to WITH FINANCE | DONE | `function mapDeniseToApStatus_` added; fallback returns 'WITH FINANCE' | NO |
| 1.7 | computeAgingBucket_ — already exists as `agingBucket` helper | DONE | Reuses existing `agingBucket(aging)` from v3.6 source | NO |
| 1.8 | Build 19-col row with correct SOURCE + CATEGORY per tab | DONE | `cfg.sourceTag` + `cfg.category` from TAB_CONFIG | NO |
| 1.9 | Append to Suppliers SOA only (Phase 1; routing deferred to Phase 6) | DONE | `newRowsByTab['Suppliers SOA']` is the only target tab | NO |
| 1.10 | Log every append via logEvent_v3_ | DONE | `'invoice_seeded_from_denise_pp'` event with source_denise_tab, source_tag, payee, invoice, amount | NO |
| 1.11 | Add Denise seed call into seedNewInvoicesFromSources_ AFTER FPM seed | DONE | try/catch block at line 585 (after FPM seed at line 577), updates `stats.denise_seed` | NO |
| 1.12 | Return stats with scanned/appended/skipped/by_tab | DONE | Stats dict includes scanned, appended, skipped_paid, skipped_blank, skipped_existing, deduped_intra_denise, by_tab (per-tab counts), sample_appended | NO |

## Phase 1 gate: PASSED

```
$ python output/s248/verify_phase1.py
Phase 1 verification: 28/28 checks
PASS: all 28 checks passed
```

Verification source: `output/s248/verify_phase1.py`. The script greps the patched source for 28 specific strings/patterns (function names, SOURCE tags, CATEGORY values, dedup logic, status-mapper branches). All present.

## Notes carried to Phase 2

- v3.7 source ready at `scripts/google_apps/s248_ap_view_hourly_sync_v37.gs` (tracked path for PR — `CEO/` was gitignored, hence the new location)
- Also at `tmp/s248/Code_v37.gs` (worktree-local copy)
- Push to Apps Script HEAD via API → required before any URL test can hit the new code
