# S251 — Bulk 12-Employee Multi-Cluster Enrollment

**Status:** AGENT_BUILD_COMPLETE 2026-05-19 PHT
**Branch:** `s251-bulk-12-enrollments`
**canonical_scope:** none

## Done

- 65 PENDING USERINFO inserts (IDs 12257-12321) across 4 clusters
- 12 employees enrolled
- 57/65 ACKED at +50s (88%); 8 PENDING on offline devices auto-resolve on heartbeat
- 12 CHANGE_LOG rows
- 0 Master CSV mutations (6 missing PINs flagged for HR backfill)

## Breakdown

| Store | Cluster | Devices | Hires | Cmds |
|---|---|---|---|---|
| SM CLARK | C9 | 6 | 5 (PINGUL, NOCUM, SALAS, DE LEON, CALEZA) | 30 |
| NAIA T3 | C8 | 5 | 3 (ORIBIAS, PAGADUAN, CAÑADA) | 15 |
| AYALA EVO/VERMOSA/GENTRI | C3 | 5 | 3 (ROBLES, REYES, FLORDELIZA) | 15 |
| MARKET MARKET | C1 | 5 | 1 (GALVEZ) | 5 |

## Flagged

- **6 PINs NOT in Master CSV** (9001998 ROBLES, 9002000 REYES, 9002001 FLORDELIZA, 9002007 SALAS, 9002009 DE LEON, 9002011 CALEZA) — HR backfill needed
- **NOCUM 9001972 "Production"** mismatch with Master CSV's STORE CREW — same MANGUERA pattern; HR validation needed
- **8 PENDING on offline devices** (SM Grand Central 5, Robinsons Gentri 3) — auto-ACK on heartbeat

## Sam handoff

1. Merge PR
2. Reply to Ron: 12 enrolled across C1/C3/C8/C9; 57/65 ACKED, 8 pending on offline devices will auto-ACK
3. (Optional) Backfill Master CSV with 9001998-9002011 rows
