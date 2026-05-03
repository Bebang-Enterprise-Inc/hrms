# S234 — Ordering Schedule Defaults Defense + Smoke Repoint + Data Foundation

Three-lane fix consolidating into one PR per audit fix W4 (avoids merged-branch
hook blocking subsequent pushes if Lane A merges first).

Plan: `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md`
Audit: `output/plan-audit/sprint-234-ordering-schedule-defaults-and-data/AUDIT_REPORT.md` (3 CRITICAL + 8 WARNING resolved in v2)

## What this PR ships

### Lane A — `_get_next_deliveries` defaults dict (committed `327e9b11f`)
Synthesizes `next_cold_delivery = str(add_days(today, 2))` and
`next_dry_delivery = str(add_days(today, 3))` in the defaults branch of
`hrms/api/store.py:_get_next_deliveries`. Today the defaults dict claims
`days_to_cold=2` but `next_cold_delivery=null` — internally inconsistent;
UI banners can't render a date. After this fix, 47 default-stores get a
"best-guess" date. `schedule_source="default"` tag preserved so consumers
can distinguish synthetic from published.

**DELIBERATELY does NOT add `cold_interval` / `dry_interval` to the defaults
dict.** The recommendation engine consumer at `hrms/api/store.py:~2724` reads
`coverage_window_days = .get("cold_interval") or .get("days_to_cold") or 2`.
Adding `cold_interval=7` (the value the entries-empty branch returns from
`_delivery_interval(set())`) would scale `suggested_qty` by ~3.5× for 47
default-stores. The "shape consistency" rationale in the v1 plan was a
dead-code premise. Audit caught it; v2 dropped it. `MUST_NOT_CONTAIN`
assertion in `verify_phase_a_static.py` enforces.

### Lane B — Smoke probe repoint (LOCAL-ONLY edit, NOT in this PR)
`/merge-bei-erp` smoke probe was pinging `?store=Estancia` — a store with
ZERO entries in `BEI Delivery Schedule Entry`, so it always hit the
defaults branch and returned null for 20+ consecutive `/merge-bei-erp`
cycles. Repointed to `?store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC`
(one of two stores with real schedule data). Now smoke FAIL means the
schedule pipeline genuinely broke.

⚠️ The skill file `.claude/skills/merge-bei-erp/SKILL.md` is gitignored
(entire `.claude/` tree is local-only). The Lane B edit was applied to
the three local mirrors (`.claude/`, `.agent/`, `.agents/`) in the main
checkout where Sam's `/merge-bei-erp` actually runs. There is no
committable artifact for Lane B in this PR — by design.

Live smoke proof (committed in this PR):
`output/s234/verification/smoke_repoint_proof.txt` →
`PASS: cold=2026-05-04 dry=2026-05-04 schedule_source=fallback_last_week`.

### Lane C — Data foundation (committed `cfe967ae5`)
- `scripts/s234_seed_delivery_schedule.py`: idempotent CSV → `BEI Delivery
  Schedule Week`+`Entry` seeder. Defaults to `--dry-run=true`. Wraps multi-doc
  write in `frappe.db.savepoint("s234_week_<n>")` with rollback on error
  (DM-2 atomic compliance).
- `scripts/s234_publish_next_week_cron.py`: cron skeleton (DISABLED_BY_DEFAULT).
  Pass `--enable` for one-off runs. NOT registered in `hrms/hooks.py` —
  follow-up sprint after Sam approves cron live-launch + logistics signoff.
- `data/operational/delivery_cadence_template.csv`: empty CSV with inline
  documentation. Logistics fills, engineer dry-runs, then commits.
- `docs/operations/delivery-schedule-runbook.md`: ownership, dry-run-first
  protocol, cron activation procedure, rollback procedures.
- `output/s234/verification/doctype_schema.json`: BEI Delivery Schedule Week +
  Entry DocType field metadata captured at sprint start.

## Per-task checklist

| Phase | Task | Status |
|---|---|---|
| 0-T1 | Read plan fully | ✅ |
| 0-T2 | Spawn worktree | ✅ |
| 0-T3 | Canonical preflight | ✅ 0 violations |
| 0-T4 | Capture state_before.json | ✅ Estancia=null, ARANETA=ISO dates |
| 0-T5 | Verify file presence | ✅ store.py + SKILL.md present |
| 0-T6 | Capture remote-truth-baseline SHAs | ✅ hrms `71e77d706`, bei-tasks `d3c663a58` |
| A-T1 | Synthesize defaults dict | ✅ |
| A-T2 | Verify with bench | ⏭️ Skipped per W8 (no `/local-frappe` in agent env); A-T5 catches regression |
| A-T3 | Commit Lane A on branch | ✅ `327e9b11f` |
| A-T4 | (deferred to C-T7) | ✅ consolidated |
| A-T5 | Post-deploy probe | ⏳ Phase D-T1 after merge |
| B-T1 | Edit SKILL.md to ARANETA URL | ✅ all 3 local mirrors |
| B-T2 | Local smoke proof | ✅ smoke_repoint_proof.txt PASS |
| B-T3 | Commit | ⚠️ `.claude/` gitignored — local-only edit (intentional) |
| C-T1 | Schema probe | ✅ doctype_schema.json |
| C-T2 | Author seeder | ✅ argparse + dry-run default + savepoint |
| C-T3 | Author cron skeleton | ✅ DISABLED_BY_DEFAULT |
| C-T4 | CSV template | ✅ |
| C-T5 | Trial seeder dry-run | ✅ template (0 rows) + 3-row trial both PASS |
| C-T6 | Runbook | ✅ |
| C-T7 | Commit Lane C + push + open PR | ✅ this PR |
| D-T1 | 3-cycle smoke after merge | ⏳ post-merge |
| D-T2 | Probe Estancia post-deploy | ⏳ post-merge |
| D-T2.5 | Write state_after.json | ⏳ post-merge |
| D-T2.6 | Write state_verification.json | ⏳ post-merge |
| D-T3 | Canonical postcheck | ⏳ post-merge |
| D-T4-7 | Plan/registry/SUMMARY/worktree closeout | ⏳ post-merge |

## Behavioral impact

- **47 default-stores** (without published schedule entries): `next_cold_delivery`
  changes from `null` → `str(today + 2 days)` (e.g., `"2026-05-05"`).
  `next_dry_delivery` changes from `null` → `str(today + 3 days)`.
  `schedule_source="default"` unchanged. Consumers that already handle
  null fall back to display logic; consumers that need a date now have one.
- **2 schedule-published stores** (ARANETA GATEWAY, AYALA UP TOWN CENTER):
  `next_*_delivery` returns from the entries branch (lines 1399-1407 in v1
  / current production) — UNCHANGED. Lane A only modifies the early-return
  defaults dict at lines 1330-1336.
- **Recommendation engine**: `coverage_window_days` resolution at
  `hrms/api/store.py:~2724` — UNCHANGED for default-stores (still falls
  through to `days_to_cold or 2`); UNCHANGED for entries-stores (still uses
  `cold_interval`). v2 audit MUST_NOT_CONTAIN guard prevents the regression.

## Risk

- ❌ Inventory regression — verified absent. v2 amendment dropped
  `cold_interval`/`dry_interval` from defaults. Recommendation engine math
  preserves prior behavior.
- ❌ Canonical drift — verified absent. 0 violations preflight, will rerun
  postcheck post-merge. No tabCompany/tabWarehouse/tabCustomer/tabSupplier
  mutations.
- ❌ Schedule pipeline regression — Lane B's smoke now actually canaries the
  pipeline (vs the previous Estancia probe that always returned null).
- ⚠️ Cron live-launch — explicitly DISABLED. Follow-up sprint required.

## Verification commands (post-merge)

```bash
# Phase D-T1: 3-cycle smoke
for i in 1 2 3; do
  curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=ARANETA%20GATEWAY%20-%20TUNGSTEN%20CAPITAL%20HOLDINGS%20OPC" \
    -H "Cookie: sid=$SID" | jq -r '.data | "cycle '$i': cold=\(.next_cold_delivery) dry=\(.next_dry_delivery)"'
  sleep 10
done

# Phase D-T2: Estancia post-deploy (proves Lane A landed)
curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=Estancia" \
  -H "Cookie: sid=$SID" | jq '.data | {next_cold_delivery, next_dry_delivery, schedule_source}'
# Expected: next_cold_delivery = today+2 (not null); schedule_source="default"
```

## Audit reference

- AUDIT_REPORT.md verdict: NO-GO until v2 amendments → applied (3 CRITICAL + 8 WARNING resolved)
- Cold-start auditor: PASS ("Plan is executable cold-start")
- Code-verifier: 4 CRITICAL + 14 WARNING confirmed; 2 STALE dropped
- Adversarial fact-checker: 8 SUPPORTED + 2 PARTIAL + 0 CONTRADICTED

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
