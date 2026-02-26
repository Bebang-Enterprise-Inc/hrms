# L3 Scenario Catalog (v2)

This folder is the modular scenario source for `$l3-v2`.

Method reference:
- `docs/testing/L3_V2_METHOD.md`

## Structure

- `COMMON.md`: global scenario rules and fixtures
- `modules/`: L3 module scenarios
- `flows/`: cross-module/L4 flow scenarios
- `regressions/`: append-only regression banks
- `index.yaml`: command map, coverage map, and plan-domain alignment

## Build from Legacy Monolith

The legacy file `docs/testing/TEST_SCENARIOS.md` is still preserved.

Regenerate modular files from it:

```bash
python scripts/testing/build_l3_scenario_catalog.py
```

## Validate Catalog Integrity + Coverage

```bash
python scripts/testing/l3_manifest_check.py
```

What it checks:
- All files in `index.yaml` exist
- Scenario IDs are unique across ready modules/flows
- Prefix coverage matches module command mapping
- Domain coverage is compared against `docs/plans/2026-02-23-full-system-flow-gaps-v2.md`

## Execution Rule

`$l3-v2` must read `index.yaml` first, then execute only requested module/flow files.

## Run L3 v2 Modules

List module readiness:

```bash
python scripts/testing/l3_v2_runner.py --list
```

Execute one module:

```bash
python scripts/testing/l3_v2_runner.py --module communication
```

Execute all ready modules (non-ready and non-implemented runners are reported as FAIL/GAP):

```bash
python scripts/testing/l3_v2_runner.py --module all
```

Generate documentation from a run JSON:

```bash
python scripts/testing/l3_generate_run_report.py --run-file output/l3/runs/l3_v2_run_<timestamp>.json
```
