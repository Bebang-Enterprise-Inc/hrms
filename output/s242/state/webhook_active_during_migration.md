# S242 v1.1 Phase 2.3 — Webhook continuity during migration window

**Acknowledged risk:** `hrms/api/mosaic_webhook.py` REMAINS active during the
Phase 3 schema migration window. The webhook cannot be cleanly disabled
without modifying production Frappe configuration. Estimated migration
window: ~5 minutes.

## What can happen

During the brief window between:
- T0: Phase 3 begins (`DROP INDEX` + `CREATE UNIQUE INDEX ... (loc, date, bill, channel) ...`)
- T1: Phase 3 commits (single transaction)

Webhook deliveries fall into one of these cases:

1. **Bill_number is NULL** — webhook proceeds normally; no index dependency.
2. **Same-channel duplicate of an existing live row** — under both indexes
   (old or new) this would be rejected by the partial unique constraint.
   Webhook handler routes to `pos_duplicates` via the existing 409 fallback.
   No data loss.
3. **First write of a (loc, date, bill, channel) tuple where the same
   (loc, date, bill) already has a live row from a DIFFERENT channel** —
   this is the parallel-bill case S242 fixes. During migration:
   - If the webhook hits BEFORE the migration commits: old index 23505 →
     existing race_409 fallback writes to pos_duplicates as `race_409`.
     After cron resume in Phase 4, the polling sync will see no live row
     for this (bill, channel) and re-insert from Mosaic, with the new
     channel-aware index allowing both rows to coexist.
   - If the webhook hits AFTER the migration commits: new index allows the
     insert; webhook writes the live row directly. No issue.
   - If the webhook hits DURING the transaction: Postgres serializes — the
     webhook waits for the migration to commit, then sees the new index.
     No issue.

## Sentry capture

- Project: `bei-hrms`
- Any 23505 from `_upsert_completed_order` is captured by the `frappe.log_error`
  monkey-patch (per `.claude/rules/sentry-observability.md`).
- Phase 4.A.3 sweeps Sentry for migration-window errors and the affected
  order_ids are re-synced via the polling cron's next tick.

## Approved by

Single-owner CEO (Sam) per S242 plan §"signoff_authority: single-owner".
The accept-the-risk decision is documented in the plan's §B2 amendment.
