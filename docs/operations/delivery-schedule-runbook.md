# BEI Delivery Schedule Runbook (S234)

Operational runbook for managing the weekly cold + dry delivery cadence used
by `validate_order_schedule` (`hrms.api.store.validate_order_schedule`) and
the order-recommendation engine on `my.bebang.ph`.

## Ownership

| Role | Responsibility |
|------|----------------|
| Logistics lead | Authoritative cadence per store (which days are COLD / DRY) |
| Engineering | Maintains seeder (`scripts/s234_seed_delivery_schedule.py`) and cron skeleton (`scripts/s234_publish_next_week_cron.py`) |
| CEO (Sam) | Approves cron live-launch (currently DISABLED until logistics signoff) |

## Data model (read-only summary)

Two DocTypes, parent-child:

* **`BEI Delivery Schedule Week`** — one record per Monday-anchored week.
  Key fields: `week_start` (Date, Monday), `published` (Check), `entries` (Table).
* **`BEI Delivery Schedule Entry`** — child rows under a Week.
  Key fields: `store` (Link → Warehouse), `delivery_type` (COLD/DRY),
  `day_of_week` (Mon..Sun), `route_name` (Link → BEI Route, optional).

`hrms.api.store._get_next_deliveries` reads the latest Week (current or
fallback to last published) and walks its entries to compute
`next_cold_delivery` / `next_dry_delivery` per store.

When no entries match a store, the function returns synthesized defaults
(today + 2 days for cold, +3 for dry) tagged `schedule_source="default"`.

## Standard weekly publish flow (current state — 2026-05-03)

Two stores have published entries: **ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC**
and **AYALA UP TOWN CENTER**. The other 47 stores are on synthesized
defaults until logistics provides cadence.

### To add cadence for new stores (operational handoff)

1. Logistics fills `data/operational/delivery_cadence_<YYYY-MM-DD>.csv` (copy
   `delivery_cadence_template.csv`, follow the header documentation inline).
   Each row is one (`store`, `delivery_type`, `day_of_week`) tuple.
2. Engineer runs the seeder in dry-run mode against the CSV:
   ```bash
   python scripts/s234_seed_delivery_schedule.py \
       --csv data/operational/delivery_cadence_2026-05-04.csv \
       --week-start 2026-05-04
   ```
   The seeder defaults to `--dry-run=true` (safe-by-default). It prints
   `INTENT_SUMMARY` JSON and a sample of rows it would write. Nothing is
   committed to Frappe.
3. Engineer reviews the dry-run log under `tmp/s234/seed_dry_run_*.log`.
   Logistics confirms.
4. Engineer runs again with `--no-dry-run` to actually write:
   ```bash
   python scripts/s234_seed_delivery_schedule.py \
       --csv data/operational/delivery_cadence_2026-05-04.csv \
       --week-start 2026-05-04 \
       --no-dry-run
   ```
   The seeder wraps the Week + entries write in a Frappe savepoint
   (`s234_week_<YYYYMMDD>`) and rolls back on any exception, so a
   half-imported Week never ships (DM-2 compliance).
5. Verify post-write via the live probe:
   ```bash
   curl -sS "https://my.bebang.ph/api/ordering?action=validate_order_schedule&store=<STORE>" \
       -H "Cookie: sid=$SID" | jq '.data | {next_cold_delivery, next_dry_delivery, schedule_source}'
   ```
   `schedule_source` should be `"current"` or `"fallback_last_week"` for
   stores that just got entries. `"default"` means the store still hits
   the synthesized-defaults branch.

### Idempotency

Re-running the seeder with the **same** CSV against the same `--week-start`
is a no-op (no diffs). Re-running with a **different** CSV against the same
`--week-start` REPLACES the Week's entries to match the new CSV (delete +
insert under savepoint).

## Cron — automated next-week clone (CURRENTLY DISABLED)

`scripts/s234_publish_next_week_cron.py` is the cron skeleton. It clones the
latest published Week's entries forward into next-Monday's Week so the
schedule never goes stale.

### Activation procedure (deferred — DO NOT DO without Sam's go)

1. Logistics signs off on a stable cadence for all 47 default-stores. Until
   that happens, cloning forward would propagate synthesized-defaults state
   for stores that don't really have cadence yet.
2. Sam approves cron live-launch.
3. Engineer:
   * Sets `DISABLED_BY_DEFAULT = False` in `scripts/s234_publish_next_week_cron.py`,
     OR
   * Wires the cron call into `hrms/hooks.py` under `scheduler_events.weekly`:
     ```python
     scheduler_events = {
         "weekly": [
             "scripts.s234_publish_next_week_cron.run",
             # ...existing entries
         ]
     }
     ```
4. Verify with a one-off `--enable` run before the next Monday.
5. Open a follow-up sprint to track the activation; the S234 PR must NOT
   register the cron in `hooks.py`.

## Rollback procedures

### Bad week landed in production

Set `published=0` on the Week:
```bash
docker exec frappe_backend bench --site hq.bebang.ph execute frappe.client.set_value \
    --kwargs '{"doctype":"BEI Delivery Schedule Week","name":"BEI-SCHED-2026-XXXXX","fieldname":"published","value":0}'
```
The reader (`_get_next_deliveries`) falls back to the previous published
Week or to synthesized defaults.

### Wrong cadence imported

Re-run the seeder with the corrected CSV against the same `--week-start`.
Idempotency guarantees the entries get replaced wholesale.

### Lane A regression (defaults dict returns null again)

Roll back the relevant `hrms/api/store.py` commit (Lane A landed in S234 PR;
identify by `git log --oneline hrms/api/store.py | grep S234`) and redeploy.

## Smoke probe (Step 3.5 of `/merge-bei-erp`)

After every deploy, the smoke probe pings `validate_order_schedule` for
`ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC` (which has real cadence).
A null return means the schedule pipeline broke — STOP and investigate
before clearing branches. (Pre-S234, the probe pinged Estancia, which
always returned null because no entries existed for it; it canaried
nothing.)

## Reference

* Plan: `docs/plans/2026-05-03-sprint-234-ordering-schedule-defaults-and-data.md`
* Seeder: `scripts/s234_seed_delivery_schedule.py`
* Cron skeleton: `scripts/s234_publish_next_week_cron.py`
* Template: `data/operational/delivery_cadence_template.csv`
* Reader: `hrms/api/store.py:_get_next_deliveries`
* Smoke probe: `.claude/skills/merge-bei-erp/SKILL.md` (Step 3.5)
