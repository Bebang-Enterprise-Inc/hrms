# S189 Real-time BOM Consumption — Operational Runbook

**Last updated:** 2026-04-14
**Sprint plan:** `docs/plans/2026-04-13-sprint-189-realtime-bom-consumption.md`
**Mosaic API spec (authoritative):** `docs/api/MOSAIC_API_OPENAPI_2026-04-14.json` — always check this first for any Mosaic endpoint ambiguity; the markdown summary at `docs/api/MOSAIC_API.md` is derived from it.

## Purpose

S189 replaces BEI's diluted monthly average consumption (which caused the
Apr 4 + Apr 8 Ube Halaya stockouts) with a real-time Supabase pipeline that
computes material usage as POS/Web sales sync. Downstream features then get
live consumption without waiting for the nightly Frappe batch.

## Data flow (source of truth)

```
Mosaic POS → (webhook OR hourly poll) → pos_order_items
                                           ↓ Supabase trigger
                                     product_bom JOIN
                                           ↓
                                  daily_material_consumption
                                           ↓ views
                            ┌──────────────┼──────────────┐
                     v_daily_...    v_material_7day_avg   fn_material_dtl
                            ↓              ↓              ↓
                 bei-tasks /api/bom-consumption  /api/bom-dtl
                            ↓
                        /dashboard/... live panels
```

Parallel path for procurement:
```
daily_material_consumption → hourly GH Actions → Frappe Stock Entry (Draft)
                                                      ↓ 1 AM PHT finalize
                                                 Submitted SE → Stock Ledger
                                                      ↓
                               BEI Inventory Risk Snapshot.bom_consumption
                                                      ↓
                       commissary planning, inventory risk, reorder alerts
```

## Health signals (source of truth = our delivery evidence)

Do **not** use Mosaic's `GET /api/v1/webhooks` as a health signal — it returns
HTTP 500 for 11/12 groups in tests. Use these instead:

| Signal | Query | Healthy value |
|--------|-------|---------------|
| Webhook delivery coverage | `SELECT webhook_coverage_pct FROM v_webhook_coverage WHERE business_date = CURRENT_DATE` | >80% after stable registration |
| Reconciliation gaps | `SELECT COUNT(*) FROM pos_orders WHERE cancellation_reason='reconciled_from_mosaic_gap' AND cancelled_at >= NOW() - INTERVAL '24 hours'` | <10 per day |
| Consumption trigger activity | `SELECT MAX(updated_at) FROM daily_material_consumption WHERE business_date = CURRENT_DATE` | within last hour during business |
| Frappe SE sync | `SELECT COUNT(*) FROM daily_material_consumption_frappe_sync WHERE business_date = CURRENT_DATE AND sync_status='SUCCESS'` | matches material count in `v_daily_material_consumption` |

## Scheduled operations

| Workflow | Cron | What it does |
|----------|------|--------------|
| `daily-pos-sync.yml` | `:00` hourly 10AM–midnight PHT | Hourly POS sync (feeds pos_orders, triggers consumption) |
| `hourly-consumption-to-frappe.yml` | `:10` every hour + 1 AM PHT finalize | Push consumption to Frappe as Draft SE; submit at 1 AM |
| `daily-reconciliation-audit.yml` | 2 AM PHT | Parity audit: order counts, consumption, Frappe SE, store coverage |
| `s189-webhook-health.yml` (new) | hourly | Delivery-based health monitor with Chat alert on FAIL |
| `s189-webhook-registration-reconciler.yml` (new) | daily 3 AM PHT | Re-POST webhook registrations (self-heal against drift) |

## Detection

**Webhooks dark** (symptom: `webhook_coverage_pct=0%` for >24h):
- `scripts/s189_webhook_health_monitor.py --alert` posts Chat alert
- Not a crisis — poll catches everything within an hour
- Crisis only if POLL also stops (different alert from `daily-pos-sync` failure notification)

**Consumption trigger not firing** (symptom: `daily_material_consumption.updated_at`
stale despite new `pos_order_items`):
- Trigger was dropped or renamed → check `information_schema.triggers`
- Fix: re-run migration — `python scripts/apply_migration.py`

**Frappe Stock Entry sync failing** (symptom: `daily_material_consumption_frappe_sync.sync_status='FAILED'`):
- Check `tmp/reconciliation/YYYY-MM-DD_audit.json` → `frappe_se_parity` failures
- Common causes: Frappe down, `FRAPPE_API_KEY` secret missing/rotated, warehouse not resolvable
- Fix: re-run `python scripts/s189_push_consumption_to_frappe.py --date YYYY-MM-DD`

**Migration drift** (symptom: `python scripts/apply_migration.py --status` shows CHECKSUM DRIFT):
- A migration file was edited after apply → investigate git blame
- Fix: create a NEW migration file with the corrective SQL; never edit applied migrations

## Recovery procedures

### Reseed `product_bom` from Frappe
When BOMs change in Frappe and the hook didn't fire, or data looks off:
```bash
python scripts/s189_seed_product_bom.py --dry-run  # preview
python scripts/s189_seed_product_bom.py            # apply
```

### Backfill consumption for a missed day
```bash
python scripts/s189_backfill_consumption.py --from 2026-04-10 --to 2026-04-10
python scripts/s189_verify_backfill.py --generate-expected --from 2026-04-10 --to 2026-04-10
python scripts/s189_verify_backfill.py --compare --dates 2026-04-10
```

### Re-push a day to Frappe
```bash
python scripts/s189_push_consumption_to_frappe.py --date 2026-04-10 --mode delta
python scripts/s189_push_consumption_to_frappe.py --date 2026-04-10 --mode finalize
```

### Re-register webhooks
```bash
python scripts/s189_webhook_registration_reconciler.py              # full reconcile
python scripts/s189_webhook_registration_reconciler.py --alert      # with Chat alert
python scripts/s189_webhook_registration_reconciler.py --dry-run    # preview
```

### Full rollback (nuclear)
1. `SELECT * FROM public.schema_migrations WHERE version LIKE '%s189%'` — verify applied
2. Apply `scripts/s189_rollback.sql` via Supabase SQL Editor
3. `DELETE FROM public.schema_migrations WHERE version='20260414_s189_realtime_bom_consumption'`
4. Redeploy Frappe without the BOM hook (remove from `hrms/hooks.py`)

## Escalation

- **Mosaic webhook delivery outage (>48h dark):** contact Mosaic support; do
  not try to fix on our side — our registrations and handler both work.
- **Supabase migration failure:** check `tmp/s189_webhook_audit/` + Mgmt API
  error, share with Sam. Do not rollback without approval.
- **Frappe Stock Ledger corruption from consumption SE:** cancel the
  submitted SE, investigate the trigger's `delta=0` short-circuit logic.

## Secrets needed

| Secret | Where | Consumer |
|--------|-------|----------|
| `SUPABASE_SERVICE_ROLE_KEY` | Doppler `bei-erp/dev` + GitHub Actions repo secret | Everything |
| `SUPABASE_MGMT_TOKEN` | Doppler + GH secret | `apply_migration.py`, reconciler |
| `FRAPPE_API_KEY` + `FRAPPE_API_SECRET` | Doppler + GH secret | Consumption push, feature verification |
| `MOSAIC_WEBHOOK_SECRET` (optional) | Frappe site config | HMAC signature verification |
| `NEXT_PUBLIC_SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` | Vercel env | bei-tasks frontend API routes |

## Migration policy

1. **New schema changes live in `supabase/migrations/YYYYMMDD_<slug>.sql`** —
   one file per logical change, ordered by timestamp prefix.
2. **All files must be idempotent** — `CREATE TABLE IF NOT EXISTS`,
   `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER`, `CREATE OR REPLACE` functions/views,
   DO blocks for constraint additions.
3. **Applied migrations are tracked in `public.schema_migrations`** with SHA256
   checksum. Editing an applied file → next run errors with CHECKSUM DRIFT.
4. **To fix an applied migration:** create a NEW corrective migration. Never
   edit the applied one.
5. **Backfilling history:** when adopting this system on a DB with pre-existing
   manually-applied migrations, use `python scripts/apply_migration.py --backfill
   --through <version>` to mark them applied without re-running.

## Post-deploy verification checklist

After any S189-related deploy, run:
```bash
python scripts/apply_migration.py --status       # no pending migrations
python scripts/s189_verify_features_alive.py     # 5/5 PASS
python scripts/s189_webhook_health_monitor.py    # overall PASS (eventually)
```
