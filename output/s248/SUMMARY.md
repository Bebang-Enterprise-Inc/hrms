# S248 — Denise's Payment Plan synced into AP Master

**Sprint:** S248
**Phases completed in this PR:** 0, 1, 2, 3 (the Apps Script deploy phase)
**Phases pending:** 4 (24h monitor), 5–7 (~2026-05-27 migration to AP Master `Payment Plan` tab)
**Status:** PHASE_3_DEPLOYED (live + verified)
**Live deploy version:** v14 (WebApp v3.7)
**Production deployment ID:** `AKfycbw-AuqJq6OyMV6DGarGWEruDoez04OETlWFQoeppNjvzoeSOJOomPOZNsVPE9iuV6ZC_Q`

## What this PR does

Adds `seedFromDenisePaymentPlan_()` to the live AP Master Apps Script (`scripts/google_apps/s248_ap_view_hourly_sync_v37.gs`). Every hour at xx:12 PHT, the existing Cloud Scheduler tick now also pulls new rows from Denise's `Project: 2-Week Payment Plan` sheet into AP Master Suppliers SOA, in addition to the existing FPM + Compliance syncs.

**Zero manual work after this PR merges.** Denise's standalone sheet stops being a parallel silo — it becomes a data source for AP Master, like FPM and Compliance already are.

## Why this exists

Per the 2026-05-13 audit (`tmp/finance_ap_audit/audit_2026-05-13/DENISE_VS_INFRA_FINDINGS.md`), of Denise's ₱53.8M outstanding supplier AP:
- ₱0 was fully reconciled across AP Master + FPM + Compliance
- ₱23.6M was GHOST (no trail anywhere)
- ₱29.2M was FPM-only (RFP existed but no Compliance / no AP Master view)

CEO directive 2026-05-13 PHT: "I do not want her to work on a 3rd parallel sheet. She can transfer back to AP Master as soon as the 2-week project is over and all data is synced automatically with no manual work."

## What the seed does

Reads 4 tabs from Denise's sheet `13cyYaPLmjL0TPaeqyYd2esjJNYj-5qJCDS8OZLdhURU`:

| Tab | SOURCE tag in AP Master | CATEGORY | Purpose |
|---|---|---|---|
| Suppliers w/o FD & Middleby | `Denise PP` | `Supplier Payments` | Urgent AP (262 rows seeded) |
| Middleby | `Denise PP - Disputed (Middleby)` | `Disputed - Eventually Payable` | Disputed, kept tagged (7 rows) |
| Forward Dynamics | `Denise PP - Disputed (FD)` | `Disputed - Eventually Payable` | Disputed (0 rows new — all 61 FD rows already in AP via FPM) |
| Masterlist | `Denise PP - Masterlist` | `Supplier Payments` | Safety net (9 rows that weren't in the 3 working tabs) |

Per CEO 2026-05-14: Middleby and Forward Dynamics are disputed-but-eventually-payable. Their distinct SOURCE tags let Sam filter urgent vs disputed AP in AP Master views.

## First live run results

| Metric | Value |
|---|---|
| AP Master Suppliers SOA rows | **990 → 1268** (+278) |
| Head Office rows | unchanged 4493 (protected) |
| CAPEX rows | unchanged 173 (protected) |
| Denise rows scanned | 1327 |
| Denise rows skipped (already paid) | 440 |
| Denise rows skipped (blank) | 42 |
| Denise rows skipped (already in AP via FPM) | 283 |
| Denise rows deduped (Masterlist overlap with working tabs) | 284 |
| **Denise rows appended** | **278** |
| Math check | 440 + 42 + 283 + 284 + 278 = 1327 ✓ |

Dry-run predicted 278; live actual 278; match.

## What's NOT in this PR (deferred to follow-up sprints or this sprint's Phase 5-7)

- **Phase 4 (24h monitor):** verify that hourly Cloud Scheduler ticks keep working without regression. Auto-confirms via `_sync_log_v3` growth.
- **Phase 5-6 (migration ~2026-05-27):** add `Payment Plan` entry tab to AP Master with Denise's full 25-column schema, bulk-migrate her data, retire her standalone sheet.
- **Phase 7 (closeout):** rename Denise's sheet to `[ARCHIVED 2026-05-27] ...`, set comment-only ACL. NOTE: requires explicit Sam approval before any write to Denise's sheet metadata.
- **AP Master banner refresh (RF-7 from 2026-05-13 audit):** banner is hardcoded; not addressed here.
- **Procurement-bypass fix (RF-5):** SCM bypassing Compliance AppSheet for some suppliers (Max's, 3M Dragon, etc.); not addressed here.

## Files changed

- `scripts/google_apps/s248_ap_view_hourly_sync_v37.gs` — new file (71,248 chars; clone of v3.6 + Denise seed function)
- `docs/plans/2026-05-13-sprint-248-denise-sheet-sync.md` — sprint plan (was created earlier in this session)
- `docs/plans/SPRINT_REGISTRY.md` — S248 row added
- `output/s248/*` — all closeout evidence

## Verification

All 3 phase verification scripts pass:

```
$ python output/s248/verify_phase1.py  → PASS (28/28 source-code checks)
$ python output/s248/verify_phase2.py  → PASS (dry-run, math integrity)
$ python output/s248/verify_phase3.py  → PASS (live deploy, sheet delta, SOURCE distribution)
```

## Risks + mitigations

- **HTTP client timeout on live calls:** observed during Phase 3 deploy. Apps Script execution completed but client disconnected after ~5 min before logging finished. Subsequent hourly Cloud Scheduler ticks won't hit this because incremental loads are small (everything from this run is now `skipped_existing`). Mitigation: monitored via sheet delta, not HTTP response.
- **Forward Dynamics 0-append:** all 61 FD rows already exist via FPM seed (correct — no duplicates). Trade-off: those rows aren't tagged "Disputed (FD)" in AP Master. A follow-up patch can reclassify if Sam wants. Not blocking.
- **Status fallback to WITH FINANCE for unmapped:** 25 rows landed in WITH FINANCE (likely Denise statuses not in my mapping). Refinement possible based on observed unmapped values.

## Stop point

Per S027 Autonomous Closeout Contract: this PR ships Phase 0-3 only. Phase 4 (24h monitor) starts automatically via Cloud Scheduler. Phase 5-7 (migration) executes around 2026-05-27 as a separate work item.

**Per BEI PR-Handoff rule: agent does NOT merge. Sam merges + deploys.**
