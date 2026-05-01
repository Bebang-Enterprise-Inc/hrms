# S225 Investigation + Fix Scripts

This directory holds the working scripts produced during S225 investigation
(2026-04-26 → 2026-05-01) for the 49-store canonical sweep. They are
preserved here as reference for future debugging — many can be re-run
verbatim against the live production site to re-audit the same conditions.

All scripts are designed to run inside the Frappe backend container via SSM:

```python
import boto3, time, base64
inner = open('scripts/s225/<NAME>.py','r').read()
enc = base64.b64encode(inner.encode()).decode()
ssm = boto3.client('ssm', region_name='ap-southeast-1')
cmds = [
    'BACKEND=$(docker ps --filter name=frappe_backend --format "{{.ID}}" | head -1)',
    f'echo {enc} | base64 -d > /tmp/x.py',
    'docker cp /tmp/x.py $BACKEND:/tmp/x.py',
    'docker exec $BACKEND /home/frappe/frappe-bench/env/bin/python /tmp/x.py 2>&1',
]
r = ssm.send_command(InstanceIds=['i-026b7477d27bd46d6'], DocumentName='AWS-RunShellScript',
    Parameters={'commands': cmds, 'executionTimeout': ['180']})
```

## Investigation scripts (read-only)

| Script | Purpose |
|---|---|
| `audit_6_fail_stores.py` | Per-store config dump (Company, Warehouse, Customer, BEI Routes, recent WRs/MRs) for the v8 fail set + 2 working stores for comparison. |
| `audit_two_stores.py` | Earlier 2-store config audit (SM MARIKINA + AYALA VERMOSA). |
| `find_marikina.py` / `find_marikina_company.py` | Fuzzy search for SM MARIKINA Company + Warehouse + Customer + accounts (used to resolve the canonical name disambiguation). |
| `inspect_bei_route_schema.py` | Dump BEI Route + BEI Route Stop DocType field metadata. |
| `check_bei_routes.py` / `check_routes_summary.py` | Route assignment audits per store. |
| `check_pm001_*.py` | Bin-state checks at PCS-BKI for PM001 (the v8 baseline blocker item). |
| `enumerate_seeded.py` | Find all SEs with a given remarks prefix (e.g., `S229%`). |
| `investigate_remaining.py` | Post-sweep DB inspection of MR + Order + Bin states. |
| `probe_allowed_target.py` | Probe `_get_allowed_target_companies()` — found SM MARIKINA `is_group=1` exclusion. |
| `probe_dispatch_latency.py` | Time `get_ready_for_dispatch` API + check for missing MRs. |
| `probe_orderable_3_stores.py` | Check `get_orderable_items` returns for stores — found 0 routes case. |
| `probe_sm_marikina_chain.py` | Trace MR → SE → WR for SM MARIKINA (parametrize MR_NAME). |
| `probe_sm_marikina_error_log.py` | Pull Frappe Error Log entries for SM MARIKINA's recent SE — found `Target warehouse must belong to one of:` validation. |
| `verify_v7_fixes_still_applied.py` | Idempotent re-check that the 4 production fixes are intact. |

## Fix scripts (mutating — apply with caution)

| Script | What it changes |
|---|---|
| `fix_routes_and_seed.py` | Adds 15 BEI Routes for stores authorized by Sam 2026-04-29 (NAIA T3, Ortigas Estancia, Ortigas Greenhills, Robinsons Antipolo, SM Sta Rosa) + seeds PM stock at hubs. |
| `fix_3_blocked_stores_routes.py` | Adds 9 BEI Routes for AYALA EVO CITY, ROBINSONS PLACE DASMARINAS, XENTROMALL MONTALBAN. Idempotent. |
| `fix_item_valuation_and_company.py` | Sets `valuation_rate = 1.0` on 41 PM/FG/KL items + fixes AYALA VERMOSA Company default_inventory_account. |
| `fix_sm_marikina_accounts.py` / `fix_remaining_bsmi.py` | Repoints SM MARIKINA's broken BSMI→SMK account references. |
| `fix_sm_marikina_is_group.py` | Sets SM MARIKINA Company `is_group=0` so it appears in `_get_allowed_target_companies()`. The fix that enabled v15 49/49. |

## Seed + teardown scripts

| Script | Purpose |
|---|---|
| `seed_v6_full_pm.py` | Comprehensive PM-stock seed at PCS-BKI + 3MD hubs. Used by both narrow and full sweeps. |
| `seed_v5_boost.py` / `seed_narrow.py` / `seed_comprehensive.py` / `seed_test_stock.py` | Earlier seed iterations (less coverage). Kept for reference. |
| `teardown_seeded_stock.py` / `teardown_v3.py` / `teardown_v4_v5_v6.py` / `teardown_comprehensive.py` | Cancel S229-labeled SEs + revert Stock Settings flags. Use the latest (`teardown_v4_v5_v6.py`) for any S229% pattern. |
