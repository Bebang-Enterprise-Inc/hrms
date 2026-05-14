# S249 — LIWANAG 3MD Transfer + MATA/NAÑOS Verification

**Status:** AGENT_BUILD_COMPLETE 2026-05-14 PHT
**Branch:** `s249-liwanag-3md-transfer-relievers`
**canonical_scope:** none

## Source

Ron Andrew Santos chat 2026-05-14 — 3 enrollment requests.

## Audit found 2/3 already satisfied

| Bio ID | Action | Reason |
|---|---|---|
| MATA 9001969 (Capital House) | NO_OP | Already enrolled via S241 (5/8) head-office-3 |
| LIWANAG 9000407 (Brittany→3MD) | **1 USERINFO + Master CSV update** | Roving QA, mass-enrolled 2026-03-04 on 47 devices but missing UDP3254800655 (S239 created it later) |
| NAÑOS 9001861 (ATC→Festival reliever) | NO_OP | Already enrolled at Festival Mall via S244 (5/10) |

## Execution

| Phase | Action | Result |
|---|---|---|
| W1 | Master CSV LIWANAG: store SHAW COMMISSARY → 3MD COMMISSARY, bio_dev BRITANY OFFICE → 3MD COMMISSARY | ✅ |
| W2 | 1 USERINFO insert at UDP3254800655 (PIN 9000407) | ID 12244, ACKED 391ms |
| W3 | Tab byte validation | 2 tabs ✓ |
| W4 | CHANGE_LOG | +4 rows |

## Workflow gap flagged

LIWANAG was on the 2026-03-04 mass-enrollment (47 devices) but new devices added later (UDP3254800655 in S239, UDP3254701583 in S244) didn't auto-extend her enrollment. Worth a separate sprint to automate "when a new device is added, also enroll all existing roving employees on it."

## Sam handoff

1. Merge PR
2. Reply to Ron: 3 done — MATA already at Capital House (S241), LIWANAG enrolled at 3MD + Master updated, NAÑOS Festival reliever already covered (S244)
