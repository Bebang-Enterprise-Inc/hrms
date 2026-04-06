# SCOPE WARNING — S163

**Plan:** docs/plans/2026-04-06-sprint-163-store-ordering-doctypes-product-grouping.md
**Total estimated units:** 91 (above 80-unit ceiling per S089 rule)
**Phases:** 11
**Repos:** hrms (backend, fixtures) + bei-tasks (frontend)
**User decision (2026-04-06):** Option B — monolithic execution. User explicitly chose to proceed.

## Risk acknowledgement
- Context exhaustion risk above phase 6
- L3 MUST run in fresh session (per S099 handoff rule + plan instruction)
- CSV deletion deferred to post-L3 cutover (Phase 11.1 explicitly says "After Phase 10 evidence proves...")
- Vertical slice strategy: Frozen Mango first

## Mitigation in this session
- Defensive drift checks at end of each phase
- Hard handoff at Phase 10 — STOP before L3
- Plan status will be DEPLOYED (not COMPLETED) at session end per S099
