# S255 Phase 0 — Boot + Baseline Checklist

**Completed:** 2026-05-20 PHT
**Branch:** s255-ap-system-hardening-team-requests
**Baseline SHA:** 18e864a7b12a8f671ef5a8d90979d7a3022fdb67 (origin/production HEAD)

| Task | Status | Evidence | Notes |
|---|---|---|---|
| 0.1 — Read plan v1.1 + handoff | DONE | session context | plan v1.1 (60941 bytes) read in full |
| 0.2 — `git fetch` + worktree spawn from `origin/production` | DONE | worktree exists at `F:/Dropbox/Projects/BEI-ERP-s255-ap-system-hardening-team-requests` | HEAD checked out |
| 0.3 — baseline_sha.txt | DONE | `output/s255/baseline_sha.txt` = `18e864a7b12a8f671ef5a8d90979d7a3022fdb67` | non-empty + matches origin/production |
| 0.4 — backup v3.8 source to `output/` | DONE | `output/s255/script_source_backup_v38.gs` = 87,425 bytes | in [85000, 95000] range — survives worktree closeout per v1.1 |
| 0.5 — **PAUSE Cloud Scheduler** | DONE | `output/s255/cloud_scheduler_pause_log.json` | Job `ap-auto-view-hourly-refresh` (cron `0 * * * *`, asia-southeast1) paused 2026-05-20T07:18:00+08:00. Verified via `gcloud scheduler jobs describe` = PAUSED. **Resume in Phase 9b.5.** |
| 0.6 — AP Master grid snapshot | DONE | `output/s255/baseline_state.json` | 18 tabs; SOA=22 cols, HO=22 cols, CAPEX=22 cols, PP=30 cols (matches plan expectations) |
| 0.7 — Denise PP snapshot + 7-day editor list | DONE | `output/s255/denise_pp_baseline.json` | 9 tabs, 18 ACL entries, `bridge_user_present: true` (domain check) |
| 0.8 — Surface ownership matrix | DONE | `output/s255/S255_SURFACE_OWNERSHIP_MATRIX.csv` | 18 data rows (≥ 10 required) |
| 0.9 — Verify Bridge in 3 SKILL.md mirrors | DONE | 3 × 10 = 30 Bridge mentions | skill files ingested from main checkout (pre-existing, never committed to `origin/production`) |
| 0.10 — verify_phase0.py | DONE | `output/s255/verify_phase0.py` exits 0 | all 6 assertions pass |

## Drift / Observations (for Phase 8 attention)

**1. ACL drift on Denise PP** — Significant change between plan write (2026-05-19) and execution (2026-05-20):
- Plan referenced `accountant.outsource@bridge-ph.com` as the Bridge contact
- **Actual ACL today:** `accountant.outsource@bridge-ph.com` is **NOT PRESENT**; 3 other `bridge-ph.com` writers ARE present: `anna.r@bridge-ph.com` (Anna Ramos), `flor.a@bridge-ph.com` (flor.a), `bea.p@bridge-ph.com` (Bea Pads)
- **6 NEW BEI users since plan written:** drew@ (Andrew Manansala), liezel@ (Liezel Acero), bea.garcia.intern@ (Bea Garcia), maika@ (Maika Talisayon), marco@ (Marco Limosnero — possibly LIMOSNERO from S253), julius@ (Julius Tin-ga, reader)
- **Plan-referenced users still present:** Roberose (writer — still queued for downgrade), Joevic (writer — still needs identity check), James Tamaca (writer — new F&A manager, matches plan), Angela (writer), Denise (owner), Sam (commenter), Luwi (commenter), Je-Ann (writer)
- **Phase 8 escalation needed:** Sam to approve disposition of ALL 18 ACL entries, not just the 3 from v1.0 plan

**2. Cloud Scheduler timing** — Plan handoff said `xx:12 PHT`; actual cron is `0 * * * *` (xx:00). Job IDs match; just a timing-note difference.

**3. /finance-ap skill not on origin/production** — Skill was created in prior session in main checkout (180 lines, 3 mirrors byte-identical, 7-10 Bridge mentions each) but never committed/pushed. This sprint commits them as part of Phase 0.

**4. Cloud Scheduler pause confirmed live** — Hourly cycle WILL NOT run during Phases 1-9b.4. **CRITICAL:** Phase 9b.5 MUST resume the scheduler. If sprint aborts mid-execution, scheduler stays paused → AP sync silently dead. Add to handoff prompt if compaction happens.

## Gate result

```
$ python output/s255/verify_phase0.py
[OK] baseline_sha matches origin/production = 18e864a7b1
[OK] backup size 87425 bytes in [85000, 95000]
[OK] scheduler paused: job=ap-auto-view-hourly-refresh, state=PAUSED
[OK] AP Master baseline has 18 tabs incl. all entry tabs
[OK] ownership matrix has 18 data rows
[OK] .claude/skills/finance-ap/SKILL.md: 10 Bridge mentions
[OK] .agent/skills/finance-ap/SKILL.md: 10 Bridge mentions
[OK] .agents/skills/finance-ap/SKILL.md: 10 Bridge mentions
[OK] total Bridge mentions across 3 mirrors: 30
[OK] Denise PP has Bridge-domain ACL: ['anna.r@bridge-ph.com', 'flor.a@bridge-ph.com', 'bea.p@bridge-ph.com']

[PASS] Phase 0 gate — all assertions met
```

Phase 0 → DONE. Proceeding to Phase 1.
