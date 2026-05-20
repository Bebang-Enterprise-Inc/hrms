# S255 — AP System Hardening Summary

**Sprint:** S255
**Branch:** s255-ap-system-hardening-team-requests
**Status:** ✅ ALL PHASES COMPLETE — production on v3.9 (versionNumber=16)
**Completed:** 2026-05-20 PHT
**Plan:** `docs/plans/2026-05-19-sprint-255-ap-system-hardening-team-requests.md` v1.1

## 11-item completion table

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Bridge accountant role in /finance-ap skill | DONE (pre-S255, verified P0.9 + amended in 9a.3) | 3 SKILL.md mirrors, 10 Bridge mentions each, sha256 match |
| 2 | AP Master schema cleanup (phantom cols + Remarks + grids 22→19/19/20) | DONE | Phase 1 — SOA col 20 deleted, grids resized, row 18 data preserved |
| 3 | CLASSIFICATION → GOODS/SERVICES rename (display-only) | DONE | Phase 1.6 — 4 v3.9 sites (lines 70, 506, 668, 1035); internal `classification` field key preserved (23 occurrences); PP col 15 renamed to BILLED ENTITY (avoids duplicate with col 23 GOODS/SERVICES) |
| 4 | FPM seed intercompany routing | DONE | Phase 2 — tight predicate (PAYEE Bebang + transfer-keyword AND NOT govt-keyword); 331 rows migrated HO→Intercompany; 25 ambiguous logged; existingIndex extended to 4 tabs |
| 5 | 3M Dragon manual-invoice SOURCE class | DONE (forward-looking) | Phase 5 — `Denise PP - Manual` SOURCE class wired in v3.9 Denise seed; 0 existing rows reclassified because plan v1.1's "12 stranded rows" estimate was stale (current 3M Dragon rows have valid invoice numbers, properly tagged Denise PP - Masterlist) |
| 6 | Angela's 2 staging tabs → filter views on PP col I | DONE | Phase 6 — 2 filter views created (filterViewIds 1449517352 + 1281333422); targets col I (mapped STATUS via mapDeniseToApStatus_); sample: 7 FOR ONLINE PAYMENT, 73 CHECK READY/RELEASED |
| 7 | Dedup cleanup on Suppliers SOA | DONE | Phase 4 — 19 Denise PP-sourced dupes deleted using `invNoVariants_()` normalization (matches seed's normalization); 0 deletable dupes remain |
| 8 | Banner refresh (RF-7 fix) | DONE | Phase 3 — `recomputeBanners_(ss)` function added, wired into doRefreshAllTabs_v3_; all 5 banners (SOA/HO/CAPEX/PP/Intercompany) match data sum within ₱0.0000 delta |
| 9 | Denise PP ACL audit | DONE | Phase 8 — Roberose downgraded to commenter (verified live); 2 deferred (joevic@ identity; bea.garcia.intern@ role); 3 Bridge users kept as writer (AUTHORIZED) |
| 10 | Status sync wiring to PP tab (gated, off by default) | DONE | Phase 7 — `payment_plan_mirror_disabled = false` const; mirror early-exit when flag=true; syncStatusFieldsFromFPM_ dynamically includes PP tab when flag=true; cutover runbook written |
| 11 | Bridge DD readiness | DONE | Phase 9a — Bridge access audited across 8 sheets (5 users on FPM, 3 on Denise PP, 0 elsewhere); DD-package checklist written; /finance-ap SKILL.md updated with DD Readiness section |

## Deploy outcome

- **v3.9 source**: 93,194 bytes (in target range [86K, 110K])
- **versionNumber**: 16 (was 15)
- **Production deployment ID**: `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q` (unchanged — URL intact)
- **Dry-run gate**: 4/4 assertions PASS via staging deployment (deleted after promotion)
- **Live sync trigger**: HTTP 200, 148s duration, 80 rows appended
- **Post-deploy verification**: 5/5 assertions PASS
- **Cloud Scheduler**: PAUSED 2026-05-20T07:18 PHT → RESUMED 2026-05-20T09:06 PHT (1h 48m paused)

## AP Master state (after Phase 9b.6 live cycle)

| Tab | Cols | Rows (incl banner+hdr) | Total Outstanding |
|---|---:|---:|---:|
| Suppliers SOA | 19 | ~1,256 | PHP 127.4M |
| Head Office | 19 | ~4,227 (was 4,558, –331 migrated) | PHP 128.2M |
| CAPEX | 20 | ~155 | PHP 8.9M |
| Payment Plan | 30 | ~580 (mirror running) | PHP 89.3M |
| **Intercompany (NEW)** | **19** | **~349 (331 migrated + 18 ambiguous-not-migrated)** | **PHP 108.6M** |

## In-flight amendments applied (deviation from plan v1.1)

The plan v1.1 specified Phase 2.5 update existingIndex (line 428). For zero-defect, expanded scope to also update:
- Line 290 (`syncStatusFieldsFromFPM_` iteration) — verified working at Phase 9b.7 (4 tabs seen)
- Line 1144 (FPM seed `newRowsByTab`) — verified by intercompany_count=0 in 9b.6 live run
- FPM seed stats init + Intercompany routing classification block

Phase 3 amendments (caught + fixed during execution):
- Row 7 column count off-by-one (range A7:N7 had 15 elements → fixed to A7:O7)
- CAPEX header row 19 (not 17) — HEADER_ROWS map added to both v3.9 + Python

Phase 5 finding (zero-defect honesty): plan v1.1's "12 stranded Invoice No. rows" was stale — current data has 0. v3.9 patch is forward-looking; no backfill needed.

## Closeout artifacts

- `output/s255/SUMMARY.md` (this file)
- `output/s255/DEFECTS.md`
- `output/s255/{phase0..phase9b}_checklist.md` (10 files)
- `output/s255/verify_phase{0..9a, 9b implicit}.py` (10 scripts, all PASS)
- `output/s255/baseline_state.json` + `post_change_state.json` (via banner_verification.json + post_deploy_verify.json)
- `output/s255/v39_dryrun.json` + `v39_dryrun_verify.json` + `v39_deployment.json` + `v39_dryrun_deployment.json`
- `output/s255/intercompany_routing_log.json` + `intercompany_ambiguous.json`
- `output/s255/dedup_cleanup_log.json`
- `output/s255/3m_dragon_reclassification_log.json`
- `output/s255/acl_change_log.json` + `sam_acl_approval.json` + `sam_acl_approval.draft.json` + `joevic_inquiry_draft.md`
- `output/s255/bridge_access_audit.json` + `dd_package_checklist.md`
- `output/s255/cloud_scheduler_pause_log.json` (paused_at + resumed_at)
- `output/s255/script_source_backup_v38.gs` (87,425 bytes — committed evidence, survives worktree closeout)
- `output/s255/post_deploy_sync.json` + `post_deploy_verify.json`
- `output/s255/payment_plan_cutover_runbook.md`
- `output/s255/angela_denise_chat_draft.md`
- `scripts/google_apps/s255_ap_view_hourly_sync_v39.gs` (the deployed source)
- `.claude/skills/finance-ap/` + `.agent/skills/finance-ap/` + `.agents/skills/finance-ap/` (skill, references, SKILL.md updated)
- This plan file (status to COMPLETED at PR-ready)
- `docs/plans/SPRINT_REGISTRY.md` (S255 row to COMPLETED at PR-ready)

## Awaiting Sam

1. **Merge the PR** (created at Phase 9b.11; not auto-merged per PR-Handoff rule)
2. **Review Phase 8 deferrals**: joevic@ identity + bea.garcia.intern@ role (logged in `acl_change_log.json` and `joevic_inquiry_draft.md`)
3. **Decide on Bridge access expansion** (logged in `dd_package_checklist.md`): grant Bridge READER on FPM (already has 5 users)/Compliance/Bank Balances/Cashflow for DD?
4. **Decide on remaining ambiguous Intercompany rows** (logged in `intercompany_ambiguous.json`): 25 rows on HO that match PAYEE Bebang but fail predicate — 18 govt-remittance (correctly stay), 7 phrasing-mismatch transfers (Sam can opt to migrate manually)

## Sprint signoff

- Single-owner approval model: Sam Karazi (CEO)
- All 11 backlog items DONE
- v3.9 production live + verified working
- Zero defects flagged in DEFECTS.md
- Plan v1.1 amendments resolved 17/17 audit blockers

S255 → READY TO MERGE.
