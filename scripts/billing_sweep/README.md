# Billing Sweep Toolkit

Read-only probes + live-fire smoke runner for the BKI→Store PI generator (S238 ICT-003).

## What it does

Validates that every BEI store's Company books accept a Draft PI generated when BKI submits a paired Sales Invoice. Walks all 49 candidate buyer Companies, creates a test SI per store, asserts the cascaded PI fields, then cancels and force-deletes the SI (cascade kills the PI).

All scripts run inside the Frappe backend Docker container via SSM (`i-026b7477d27bd46d6`).

## Files

| File | Purpose |
|---|---|
| `multi_store_smoke.py` | Full 49-store sweep. Create→submit→assert→cancel→delete per store. |
| `probe_per_store_readiness.py` | Per-store readiness check: Customer/Warehouse/cost_center/CoA accounts/PHP currency/required custom fields. |
| `probe_perpetual_inventory.py` | Per-Company `enable_perpetual_inventory` + `stock_received_but_not_billed` audit. |
| `probe_stock_defaults.py` | Wider Company stock default audit. |
| `probe_order_per_store.py` | Finds one real existing BEI Store Order per store to populate `custom_bei_store_order` link. |
| `probe_one_failure_full_trace.py` | Triggers a single failing store with full traceback capture (bypasses `frappe.log_error` truncation). |
| `probe_sweep_aftermath.py` | Post-sweep cleanup verification — checks no leftover SI/PI/orphan rows. |
| `run_*.py` | SSM wrappers for each probe. Use gzip+base64 file exfil to avoid SSM stdout truncation. |

## Pattern (SSM file exfil)

The SSM `get_command_invocation` response truncates `StandardOutputContent` at roughly 24KB. To return large JSON, the probes write to `/tmp/sNNN_*.json` inside the container and the wrapper does:

```bash
docker cp $BACKEND:/tmp/sNNN_result.json /tmp/sNNN_result.json
gzip -c /tmp/sNNN_result.json > /tmp/sNNN_result.json.gz
echo S244_FILE_BEGIN
base64 -w0 /tmp/sNNN_result.json.gz; echo
echo S244_FILE_END
```

The wrapper extracts between the markers, base64-decodes, gunzips, and writes to disk. Reuse this pattern for any probe that produces >24KB of output.

## How to re-run the full sweep

```bash
cd F:/Dropbox/Projects/BEI-ERP
python scripts/billing_sweep/run_perp.py        # confirm Company config state
python scripts/billing_sweep/run_probe.py       # confirm per-store readiness
python scripts/billing_sweep/run_order_probe.py # refresh STORE_ORDER_MAP
# edit multi_store_smoke.py with refreshed map if needed
python scripts/billing_sweep/run_sweep.py       # live-fire — creates+cleans up test SIs
python scripts/billing_sweep/run_aftermath.py   # verify cleanup
```

Each probe writes its result alongside the wrapper (e.g., `run_probe.py` → `probe_result.json`).

## Cleanup guarantee

`multi_store_smoke.py` maintains a `CREATED` list of all artifacts and runs `_final_cleanup()` in a top-level finally block. The aftermath probe verifies leftover_si=0, leftover_pi=0, orphan_pi=0 before declaring a successful sweep.

## Output committed to repo

`output/l3/billing-sweep-2026-05-11/` (SUMMARY, DEFECTS, GAP_ANALYSIS, evidence/*.json).
