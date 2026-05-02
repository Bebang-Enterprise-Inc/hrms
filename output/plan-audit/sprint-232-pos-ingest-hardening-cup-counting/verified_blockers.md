# S232 — Verified Blockers (Post Adversarial Fact-Check)

**Audit completed:** 2026-05-02
**Plan:** `docs/plans/2026-05-02-sprint-232-pos-ingest-hardening-cup-counting.md`
**Fact-check verdict:** 5/5 highest-stakes blockers SUPPORTED with literal file evidence; 0 hallucinations.

---

## Final Blocker Status

| ID | Title | Severity | Fact-Check | Status |
|----|-------|---------:|:----------:|:------:|
| **A1** | Phase 1 unique index will fail on existing 945 dupes | CRITICAL | SUPPORTED | OPEN |
| **A2** | PostgREST 409 unhandled in supabase_upsert | CRITICAL | (inferred from A1) | OPEN |
| **A3** | Webhook handler bypasses dedup helper | BLOCKER | (system-arch only — not adv. checked) | OPEN |
| **A4** | Migration filename collision (003, 005) | CRITICAL | SUPPORTED | OPEN |
| **A5** | Phase 2.2 wrong column name (`item_name` vs `product_name`) | CRITICAL | SUPPORTED | OPEN |
| **B1** | discount_abuse + marketing_giveaways read pos_orders directly | CRITICAL | SUPPORTED | OPEN |
| **B2** | ~10 other views uncovered | BLOCKER | (system-arch only) | OPEN |
| **B3** | pos_orders_raw uncovered | BLOCKER | (system-arch only) | OPEN |
| **B4** | pos_order_items orphan rows | CRITICAL | SUPPORTED | OPEN |
| **C1** | Phases 2-6 lack verifier templates | BLOCKER | (zero-skip only) | OPEN |
| **C2** | L3 doesn't assert cup count = 2,941 | BLOCKER | (deployment only) | OPEN |
| **C3** | No L3 scenario for cancellation + retry | BLOCKER | (deployment only) | OPEN |
| **C4** | No L3 scenario for backfill correctness | BLOCKER | (deployment only) | OPEN |

**13 confirmed blockers + 10 high-priority items.**

## What I am amending inline (autonomous mode)

The plan needs structural amendments. Auto-mode + clear blocker fixes = apply now. Specifically inlining:

1. **A1 (phase ordering)** — move backfill BEFORE index creation
2. **A4 (filename collision)** — renumber all 7 migrations
3. **A5 (column name bug)** — fix Phase 2.2 SQL
4. **B1 (direct queries)** — add explicit task for discount_abuse + marketing_giveaways
5. **B2 (view audit)** — make Phase 5.2 exhaustive
6. **B3 (pos_orders_raw)** — add scope decision task to Phase 0
7. **B4 (item orphans)** — add cascade to Phase 5
8. **C1 (verifier templates)** — point Phases 2-6 to a shared template helper
9. **C2 (cup count L3)** — add cup-recount scenario
10. **C3 (cancel + retry L3)** — add tombstone-survival scenario
11. **C4 (backfill L3)** — add count-delta scenario
12. **A2/A3** — add 409-handling specification
13. **H1-H4** — fix budget arithmetic, S197 cron text, webhook_review_queue ghost row, pos_duplicates rename

Will write a consolidated "Audit v2 Amendments" section to the plan and update task tables for affected phases.

## What I am NOT auto-applying

- **H5 (multi-terminal bill_number scope)** — needs an empirical Mosaic probe at SM Megamall before it's actionable. Adding as a Phase 7.4a task instead of inline fix.
- **H7 (kept-row tie-breaker)** — minor disambiguation; will inline as a 1-line clarification.
- **H8 (webhook_received_at NULL backfill)** — operational detail; will inline as Phase 5 sub-task.
- **MED/LOW items** — flag in v2 amendments but don't restructure plan.
