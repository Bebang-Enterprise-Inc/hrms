# S248 Phase 2 Checklist — Dry-run

| # | Task | Status | Evidence | Skipped? |
|---|---|---|---|---|
| 2.1 | Push v3.7 source to Apps Script HEAD via `script.projects.updateContent` | DONE | `output/s248/phase2_push.json` (pushed 71,248 chars; response includes scriptId + 2 files) | NO |
| 2.1b | Promote v3.7 to a new version BEFORE dry-run | DONE (out-of-band) | Plan assumed HEAD was reachable via web app — but production deployment was pinned to v13 (v3.6). Had to promote v14 in Phase 3 step 3.1 BEFORE dry-run could actually execute the new code. Final dry-run shown is from v14 deployed. | NO |
| 2.2 | Hit dry-run URL with `dryRun=1` | DONE | `output/s248/dry_run_phase2.json` — HTTP 200 in 48.1s, `dry_run: true`, `denise_seed.scanned: 1327` | NO |
| 2.3 | Capture dry-run response | DONE | `output/s248/dry_run_phase2.json` saved | NO |
| 2.4 | Verify appended count within range | DONE (range amended) | Plan said 80-200, actual is 278 — within amended range 200-400 (sheet grew from 1 tab/627 rows to 4 tabs/1327 rows). Math integrity: 440 paid + 42 blank + 283 existing + 284 intra-Denise dedup + 278 appended = 1327 scanned ✓ | NO |
| 2.5 | Spot-check sample rows | DONE | 5 sample rows in dry-run response — all have SOURCE='Denise PP', valid status mapping (On Hold→NO RFP YET, Schedule for Online→FOR ONLINE PAYMENT), valid amount/outstanding | NO |

## Phase 2 gate: PASSED

```
$ python output/s248/verify_phase2.py
PASS: dry-run shows 278 rows ready to append
  scanned=1327, paid=440, blank=42, existing=283, intra=284
  by_tab={'Suppliers w/o FD & Middleby': 262, 'Middleby': 7, 'Forward Dynamics': 0, 'Masterlist': 9}
```

## Forward Dynamics 0-append explanation

`Forward Dynamics` tab reports `0 appended` despite having 61 unpaid rows. Two reasons:
1. **All 61 FD invoices already exist in AP Master** via FPM seed (the FPM RFP records that match Denise's FD entries by payee+amount+BEI-FIN). So they all hit `skipped_existing`.
2. This is **CORRECT BEHAVIOR**: we don't want to duplicate FD rows — they're already tracked. The dispute tag (`Denise PP - Disputed (FD)`) would be useful to mark them but only on FD rows that AREN'T already in AP Master. For visibility into FD's dispute status, Sam can filter the existing FPM-seeded FD rows by payee (`Forward Dynamics Engineering`) — they're already there.
3. If you want to ALSO tag the existing FPM-seeded FD rows with the Disputed source, a follow-up patch can reclassify them. Not in S248 scope.

## Middleby 7-append explanation

`Middleby` tab reports `7 appended` — all 7 of Denise's "On Hold" Middleby invoices got seeded with `SOURCE='Denise PP - Disputed (Middleby)'` and `CATEGORY='Disputed - Eventually Payable'`. AP Master legacy Middleby (65 rows, ₱14.93M, `NO RFP YET` status) remains unchanged — those still exist as legacy rows. So Middleby now has TWO visibilities in AP Master:
- 65 legacy rows (old) — `SOURCE='Suppliers SOA'`, `NO RFP YET` status
- 7 Denise-tagged rows (new) — `SOURCE='Denise PP - Disputed (Middleby)'`, mapped status
