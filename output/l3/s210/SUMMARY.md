# S210 Phase 6 — E2E Summary

Run timestamp: 2026-04-20T14:56:49+08:00
Overall: **PASS**

## Scenarios

- e2e_test_3md: **PASS** — RR=S210-E2E-3MD-1776668200
- e2e_test_pinnacle: **PASS** — RR=S210-E2E-PIN-1776668204
- e2e_test_supplier_si: **PASS** — MATCHED

## Evidence files

- `output/l3/s210/e2e_test_3md.json`
- `output/l3/s210/e2e_test_pinnacle.json`
- `output/l3/s210/e2e_test_supplier_si.json`

## Note

E2E tests exercise the full data-path pipeline using a Python mirror of the Apps Script handler logic. When a human runs setup() in the Apps Script editor, the .gs equivalents take over and produce the same outcomes automatically on edit.