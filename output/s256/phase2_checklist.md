# Phase 2 Checklist — v3.10 Patches: Intercompany + Dedup

| Task | Status | Evidence | Skipped? |
|---|---|---|---|
| 2.1 Build v3.10 from v3.9 | DONE | `scripts/google_apps/s256_ap_view_hourly_sync_v310.gs` (96,811 bytes) | NO |
| 2.2 Broaden intercompany predicate | DONE | `INTERCO_AFFILIATE_PATTERNS` const with 15 patterns (1 Bebang + 14 affiliates); `isIntercompany` uses `.some()` | NO |
| 2.3 Fix dedup race | DONE | `FPMSOA|payeeKey|amt` key added to existingIndex; `skipped_existing_fpm_soa` counter in Denise seed | NO |
| 2.4 Sanity grep | DONE | All 3 patterns present: INTERCO_AFFILIATE_PATTERNS, isIntercompany, skipped_existing_fpm_soa | NO |
| 2.5 verify_phase2.py | DONE | Exit 0 — ALL PASS | NO |
