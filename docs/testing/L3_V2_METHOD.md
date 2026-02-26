# L3 v2 Testing Method

Last updated: 2026-02-24

## Goal

Run L3 tests like a real user where possible (browser login, navigation, click/type/upload/submit), with evidence and reproducible reports.

## Source of Truth

- Scenario catalog: `docs/testing/scenarios/index.yaml`
- Module scenario files: `docs/testing/scenarios/modules/`
- Flow scenario files: `docs/testing/scenarios/flows/`
- Regression banks: `docs/testing/scenarios/regressions/`

## Execution Stack

1. `python scripts/testing/l3_manifest_check.py`
1. `python scripts/testing/l3_v2_runner.py --module <module|all>`
1. `python scripts/testing/l3_generate_run_report.py --run-file output/l3/runs/l3_v2_run_<timestamp>.json`

## Runner Types

- Python browser runners (strict evidence):
  - `communication` -> `scripts/testing/l3_comm_support_runner.py`
  - `expense` -> `scripts/testing/l3_expense_runner.py`
  - `biometric` -> `scripts/testing/l3_biometric_runner.py`
- Playwright suite runners (module smoke from `tests/e2e`):
  - `maintenance`, `store-ops`, `hr`, `finance`, `billing`, `scm`

## Evidence Output

- Run summaries: `output/l3/runs/`
- Python runner evidence: `output/l3/evidence/`
- Browser traces/screenshots: `output/l3/artifacts/`
- Playwright suite raw+summary reports: `output/l3/playwright/<run_id>/<module>/suite_*/`
- Human-readable run report: `docs/testing/reports/l3_v2_run_<run_id>.md`

## Current Full Run Baseline

- Run file: `output/l3/runs/l3_v2_run_20260224_220707_297963.json`
- Report file: `docs/testing/reports/l3_v2_run_20260224_220707_297963.md`
- Result: 8 PASS, 1 FAIL, 1 NOT_IMPLEMENTED

Pass modules in current baseline:
- `maintenance`, `store-ops`, `hr`, `communication`, `biometric`, `finance`, `billing`, `scm`

Non-pass modules in current baseline:
- `expense` = FAIL (real submit succeeded but strict sidebar navigation assertion failed)
- `stock-counting` = NOT_IMPLEMENTED (manifest has ready module but no mapped runner and no scenario IDs)

Recent deploy validation:
- Backend deploy workflow (fix branch source): `22307345306`
- Expense module PASS after deploy: `output/l3/runs/l3_v2_run_20260223_211538_339791.json`
- Expense runner currently passed via fallback account on latest full run (`ACCOUNT_USED=test.area@bebang.ph`, `ATTEMPTS=2`).
- Frontend auth/loading fix deployed to Vercel and validated with reruns:
  - `output/l3/runs/l3_v2_run_20260223_214054_293876.json` (maintenance)
  - `output/l3/runs/l3_v2_run_20260223_214141_555536.json` (all modules)

## Reliability Rules

- Keep `index.yaml` updated first before changing runner mappings.
- Treat FAIL as FAIL. Do not relabel as "finding" or "expected".
- Keep regression scenarios append-only.
- Maintain per-module artifacts so failures are auditable and reproducible.
- For maintenance flow (`TC-STAFF-013`), enforce route verification (`/dashboard/rm/new`) and validate submit success via API response (`POST /api/store`) plus UI confirmation checks.
- `python scripts/testing/l3_manifest_check.py` must pass before claiming baseline integrity.
- Full strict L3-v2 is only true when catalog scenario count equals executed scenario count per module/flow.
