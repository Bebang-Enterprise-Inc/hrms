# S230 Execution Summary

**Sprint:** S230 — Xentro Mall Device Registration + Estancia Local-Mapping Fix + Crew Enrollment
**Branch:** `s230-xentro-estancia-device-enrollment`
**Worktree:** `F:/Dropbox/Projects/BEI-ERP-s230-xentro-estancia-device-enrollment`
**Status:** AGENT_BUILD_COMPLETE — pending Sam's API container restart for heartbeat-watch
**Executed:** 2026-04-29 (Wednesday)

## Scope (revised inline per Sam directive 2026-04-29 11:30 PHT)

CEO directive: "let's not add to Frappe as well just make sure everyone is in the employee master and enroll to ADMS". S228 deferred Frappe inserts pending HR audit; S230 follows the same pattern. Original v2 plan's Phase 4 (Frappe inserts + Google Sheet sync) DROPPED.

Verified via live audit (live SSM 2026-04-29):
- All 12 Xentro Mall crew already in Master CSV + Frappe `tabEmployee.branch=XENTROMALL MONTALBAN`
- All 4 Estancia crew already in Master CSV; missing from Frappe `tabEmployee` (S228 anomaly A1 — out of S230 scope)
- The 16 Bio IDs Sam mentioned (assigned by Archie/Ron) match the Master CSV's existing assignments

## 6-System Reconciliation Matrix

| System | Estancia (UDP3252900249) | Xentro Mall (UDP3254701502) |
|---|---|---|
| **Server allowlist** `sn_mapping_all.csv` | ✅ Pre-existing `UDP3252900249,ESTANCIA` | ✅ Appended `UDP3254701502,XENTROMALL_MONTALBAN` (now 51 rows) |
| **Local Python** `hrms/utils/device_mapping.py` | ✅ Added `'UDP3252900249': 'ORTIGAS ESTANCIA'` (in worktree, pending merge) | ✅ Added `'UDP3254701502': 'XENTROMALL MONTALBAN'` (in worktree, pending merge) |
| **Master CSV** `data/_FINAL/EMPLOYEE_MASTER.csv` | ✅ 4 crew Active (9001827/30/32/35) — pre-existing, no change needed | ✅ 12 crew Active (9001838-47, 9001865, 9001866) — pre-existing, no change needed |
| **Frappe `tabEmployee`** | ⚠️ MISSING — 4 crew not in Frappe (anomaly A1, S228 scope, NOT S230) | ✅ All 12 crew exist with `branch=XENTROMALL MONTALBAN`, `company=BEBANG ENTERPRISE INC.`, `status=Active` |
| **Google Sheet** | (skipped per Sam directive — Master CSV is authoritative) | (skipped per Sam directive) |
| **ADMS `adms_device_cmd`** | 4 PRESERVED PENDING on home device since 2026-03-30 (will fire when device heartbeats) + 5 ACKED across C2 secondaries | 48 NEW PENDING pushed: 12 each on UDP3251200193, UDP3252900048, UDP3235200594, UDP3254701502 (the 24 already-ACKED on Marikina/Sta Lucia/Brittany kept untouched) |

## Phase Status

| Phase | Goal | Status |
|---|---|---|
| Phase 0 | Boot + Worktree + User-Input Gate + S228 concurrency | ✅ COMPLETE — Sam confirmed all 4 inputs; S228 detected (8 commits ahead, Frappe deferred per Sam) |
| Phase 1 | Server allowlist append + restart handoff | ✅ APPEND DONE (51 rows confirmed); ⏳ RESTART pending Sam's `manual_steps.md` Step 1 |
| Phase 2 | Local Python mapping update | ✅ COMPLETE — 50 entries, smoke test PASS, diff captured |
| Phase 3 | Cluster membership verification | ✅ COMPLETE — Estancia=C2 (6 devices), Xentro=C5 (6 devices), enrollment_plan.json built |
| Phase 4 | Employee Master + Frappe + Sheet | 🚫 SKIPPED per Sam directive (HR audit pending; Frappe inserts deferred to a future sprint) |
| Phase 5 | ADMS Enrollment via REST/SQL | ✅ COMPLETE — 48 USERINFO commands inserted (`INSERT 0 48` confirmed via SSM 27156561-e29c-41ff-9934-71e5f978fff9) with 96 actual tab bytes (2 per row); deduped against 24 already-ACKED Marikina/Sta Lucia rows |
| Phase 6 | Verification + heartbeat watch | 🟡 PARTIAL — server-side state verified; live heartbeat watch deferred until Sam executes Step 1 restart |
| Phase 7 | Closeout: PR + plan/registry update + worktree removal | ⏳ IN PROGRESS — this commit |

## Heartbeat Verdict (preliminary, pre-restart)

| Device | Verdict | Notes |
|---|---|---|
| UDP3252900249 (Estancia home) | `OFFLINE_PRE_EXISTING` | No heartbeat since 2026-03-30; same condition as before this sprint. Not a regression. Awaiting physical device deployment + cloud-server config. |
| UDP3254701502 (Xentro home) | `OFFLINE_NEW_PENDING_RESTART` | Net new device; awaitng Sam's API container restart (Step 1 of `manual_steps.md`) before it can heartbeat. After restart + physical device powering on at the store, the 12 PENDING USERINFO commands will fire. |
| UDP3251200193 / UDP3252900048 / UDP3235200594 (C5 secondaries) | `ONLINE_AWAITING_PICKUP` | Already heartbeating. The 12 new USERINFO commands per device will be picked up on next heartbeat (≤60s after this push). |

## Net effect

- 12 Xentro Mall crew gain enrollment on 4 additional devices each (SM East Ortigas + SM Taytay + Robinsons Antipolo + their new home Xentro Mall) — full C5 cluster cross-enrollment.
- Existing temp enrollments on SM Marikina + Sta Lucia East + Brittany Office are preserved (no churn during transition).
- Estancia 4 crew unchanged in ADMS — already cross-enrolled across C2; just waiting for home device.
- New devices `UDP3252900249` and `UDP3254701502` are now first-class entries in the local resolver (no more `KeyError` if punches arrive).

## Audit lineage

- v1 plan audit: `output/plan-audit/sprint-230-xentro-estancia-device-enrollment/AUDIT_SUMMARY.md` (10 CRITICAL + 21 WARNING)
- v2 plan amendments: 58 `v2-Bn` markers in plan body
- Live execution adjustments: scope reduced per Sam directive 2026-04-29 11:30 PHT (Frappe inserts dropped, Google Sheet skipped)

## Next steps (for Sam)

1. Review the PR (link will follow after `gh pr create`)
2. Merge to `production`
3. Run `manual_steps.md` Step 1 (API container restart) — this activates the new allowlist entry
4. Run `manual_steps.md` Step 3 (Frappe backend restart) AFTER deploy completes — this picks up the new `device_mapping.py`
5. Verify device heartbeats — should see 200 logs within 60s of restart
6. (Operational) Confirm physical Xentro Mall device is powered on and pointed at `adms.bebang.ph:8443`; confirm physical Estancia device same
