# Defect #18 — Decision: Option A (change field options to Branch)

## Reference inventory

### Backend (`hrms/`)
- `hrms/api/disciplinary.py:58` — `"store": data.get("store")` in `create_incident_report` — reads from request payload
- `hrms/api/disciplinary.py:226` — `"store": ir.store` in `get_incident_detail` return — passes through
- `hrms/hr/doctype/bei_incident_report/bei_incident_report.json` — field `store: Link Warehouse, reqd: 0`
- `hrms/utils/brain_sync.py` — uses the DocType name only, no `.store` field access
- `hrms/hooks.py` — DocType registration only

### Frontend (`bei-tasks/`)
- `lib/queries/hr-disciplinary.ts:12-26` — `interface IncidentReport` has `branch?: string`, **no `store` field**
- `lib/queries/hr-disciplinary.ts:179-187` — `useCreateIncidentReport` mutation signature does NOT send `store` or `branch`
- `app/dashboard/hr/disciplinary/[id]/page.tsx:221` — reads `caseDetail.branch` (not `store`)

### Reports / queries / joins
**None.** No SQL query in the codebase JOINs `tabBEI Incident Report.store` to `tabWarehouse` or `tabBranch`. No filter uses `store=` as a Warehouse reference.

## Why Option A is correct

1. **Only one consumer writes the field** — `create_incident_report`, via `data.get("store")`. If we change the field options from Warehouse to Branch, any value the caller sends will validate against `tabBranch` instead.
2. **No data migration needed** — the field is `reqd: 0`, the frontend has never sent it, and in production the column is likely all NULL. Changing Link target does not corrupt existing NULL values.
3. **Field name stays `store`** — no rename migration, no fixture updates, no dashboards break.
4. **Frontend already thinks in Branch** — the `IncidentReport` interface has `branch?: string`, not `store`. Changing the Link target to Branch aligns backend with frontend semantics.

## Why Option B is wrong for this case

Renaming `store` → `warehouse` would:
- Require a doctype rename migration (risky on an active DocType)
- Break any existing backups/exports that reference `store`
- Not match the actual user-facing concept (HR thinks in terms of the employee's store/branch, not a Warehouse inventory location)
- Still require the same backend payload fix

## The fix

1. Change `bei_incident_report.json` field `store.options` from `"Warehouse"` to `"Branch"`
2. In `create_incident_report`, if `data.get("store")` is empty, default to the employee's current branch (so the IR is tagged even when the frontend doesn't send the field explicitly)
3. Add `set_backend_observability_context` per DM-7

## Risk assessment

- **Data loss risk:** none (column is nullable and currently unused for real Warehouse links)
- **API break risk:** none (the field is optional and no existing caller sends a valid Warehouse name anyway — that's the bug)
- **UI break risk:** none (frontend doesn't display `store`, it displays `branch` from elsewhere)
- **Migration risk:** low — `bench migrate` applies the schema change; existing NULLs stay NULL; new inserts validate against Branch

## Note on incident_type vs incident_category mismatch (out of scope for S172)

Observed during inventory but NOT part of Defect #18: the frontend `useCreateIncidentReport` mutation sends `incident_type`, but the backend `create_incident_report` requires `incident_category`. This is a separate bug that would also block the create path — flagging for a follow-up sprint. Not fixing in S172 since it's not in the canonical defect list.
