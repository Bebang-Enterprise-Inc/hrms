# Defect #18 — BEI Incident Report `store` field reference inventory

> **Note:** Written retrospectively on 2026-04-09. Plan Task 4.1 required running the inventory grep with `| tee output/s172/diagnostics/DEFECT_18_REFERENCE_INVENTORY.md`, but the inventory was inlined directly into `DEFECT_18_DECISION.md` during execution and this standalone file was not created. Extracting now to satisfy the Phase 4 verification gate.

## Grep commands used

```bash
grep -rn "bei_incident_report\|BEI Incident Report\|incident_report" hrms/ 2>&1 | grep -v __pycache__
grep -rn "incident_report\|IncidentReport\|store" ../bei-tasks/components/ ../bei-tasks/app/dashboard/hr/disciplinary/ ../bei-tasks/app/api/ 2>&1 | grep -v node_modules
grep -rn "tabBEI Incident Report\|bei_incident_report.*store" hrms/ scripts/ 2>&1
```

## Backend references (hrms/)

| File | Line | Usage |
|---|---|---|
| `hrms/api/disciplinary.py` | 55 | `"doctype": "BEI Incident Report"` in create_incident_report |
| `hrms/api/disciplinary.py` | 58 | `"store": data.get("store")` — **writes** the store field from request payload |
| `hrms/api/disciplinary.py` | 226 | `"store": ir.store` in get_incident_detail return — **reads** the field |
| `hrms/api/disciplinary.py` | 96 | `subject=_("New Incident Report: {0}")` (log msg only) |
| `hrms/api/disciplinary.py` | 114 | `reference_doctype="BEI Incident Report"` (comment reference) |
| `hrms/api/disciplinary.py` | 157 | `"BEI Incident Report"` in get_incident_reports filter |
| `hrms/api/disciplinary.py` | 188, 191, 260, 263, 628 | `frappe.db.exists` / `frappe.get_doc` calls (DocType name only, no field access) |
| `hrms/api/disciplinary.py` | 716-719 | `frappe.db.count` status filters (no store field) |
| `hrms/hooks.py` | 322 | DocType registered in brain_sync list |
| `hrms/hr/doctype/bei_incident_report/bei_incident_report.json` | (schema) | field `store: Link Warehouse, reqd: 0` |
| `hrms/hr/doctype/bei_incident_report/bei_incident_report.py` | 1, 8 | DocType controller — no field-level logic touching `store` |
| `hrms/utils/brain_sync.py` | 74, 185, 187, 233 | DocType in sync manifest — brain sync reads the record as a whole, no field-level store access |

**Store-field consumers in hrms/: 2** (disciplinary.py line 58 write + line 226 read).

## Frontend references (bei-tasks/)

| File | Line | Usage |
|---|---|---|
| `lib/queries/hr-disciplinary.ts` | 12-26 | `interface IncidentReport` — has `branch?: string`, **NO `store` field** |
| `lib/queries/hr-disciplinary.ts` | 179-187 | `useCreateIncidentReport` mutation signature — does NOT send `store` or `branch` |
| `app/dashboard/hr/disciplinary/[id]/page.tsx` | 221-224 | Reads `caseDetail.branch` (not `caseDetail.store`) for display |
| `app/dashboard/hr/disciplinary/page.tsx` | 26-27, 96, 132 | Uses `IncidentReport` type + `useCreateIncidentReport` mutation — no store field in payload |

**Store-field consumers in bei-tasks/: 0** (the frontend interface uses `branch`, not `store`; no outgoing payload sends the field).

## Reports / SQL joins

```bash
grep -rn "tabBEI Incident Report.*store\|JOIN.*tabWarehouse.*BEI Incident Report" hrms/ scripts/
# → zero matches
```

**Reports and joins using `tabBEI Incident Report.store` as a Warehouse link: 0.**

## Summary counts

| Consumer class | Count |
|---|---|
| Backend files that WRITE `ir.store` | 1 (disciplinary.py, one line) |
| Backend files that READ `ir.store` | 1 (disciplinary.py, one line in get_incident_detail return) |
| Frontend files that reference `ir.store` | 0 (all use `branch`) |
| Reports/dashboards joining `ir.store` to `tabWarehouse` | 0 |
| Fixtures/seeds referencing the field with a Warehouse value | 0 |

**Total consumers: 2, both in disciplinary.py.** Both are trivially compatible with changing the field's Link target from Warehouse to Branch.

## Decision derived from this inventory

Based on ≤5 references and all of them being semantically "branch" anyway, **Option A (change field `options` from Warehouse to Branch)** is correct. Renaming the field (Option B) would be over-engineered for this case.

See `DEFECT_18_DECISION.md` for the full A vs B rationale and applied fix.
