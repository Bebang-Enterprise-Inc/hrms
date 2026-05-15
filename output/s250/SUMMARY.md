# S250 — SM Southmall 2-Employee C6 Cluster Enrollment

**Status:** AGENT_BUILD_COMPLETE 2026-05-15 PHT
**Branch:** `s250-smsm-sadio-orayan-enrollment`
**canonical_scope:** none

## Done

| Bio ID | Name | Position | Result |
|---|---|---|---|
| 9001920 | ORAYAN, MITCHEL G. | Cashier | Enrolled on full C6 (6 devices) — first-ever ADMS enrollment |
| 9001929 | SADIO, KIANA JANE J. | Store Crew (Master) | Enrolled on full C6 (6 devices) — first-ever ADMS enrollment |

12 USERINFO commands (IDs 12245-12256). Tab byte validation: 2 per command.

**ACK rate at +35s: 10/12 (83%)** — 2 PENDING at UDP3251600215 BF Homes (offline-device pattern, will auto-ACK on next heartbeat).

## Pre-write audit

- Both Active in Master CSV with `store_location=SM SOUTHMALL` since S228 2026-04-28
- Both NEVER enrolled in ADMS (zero punches anywhere) — S228 Master-only gap, same as JIMENEZ in S249
- SM Southmall device CNYG242061620 healthy

## Flagged

- **SADIO designation:** Ron said "Production" but Master says STORE CREW — same MANGUERA-style mistake from S252; kept Master CSV designation
- **S228 backfill gap continues:** Many Bio IDs in 9001882-9001932 range imported 2026-04-28 still un-enrolled in ADMS, only triggered when Ron requests individually. Would benefit from a dedicated S228 backfill sprint.

## Sam handoff

1. Merge PR
2. Reply to Ron: Both enrolled at SM Southmall + full C6 cluster, 10/12 ACKED, 2 pending on BF Homes will auto-ACK on heartbeat
