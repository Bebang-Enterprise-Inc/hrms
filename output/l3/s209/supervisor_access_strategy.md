# S209 Supervisor Access Strategy (P0-T7 output)

**Probe date:** 2026-04-20
**Decision:** HYBRID — only `test.area@bebang.ph` needs per-warehouse grant; `test.supervisor@bebang.ph` has universal receiving access via pre-existing roles.

## Findings

### Custom fields on `tabWarehouse`
- `custom_area_supervisor` (Link → User) — EXISTS
- `custom_store_supervisor` — **DOES NOT EXIST**
- Other fields: `custom_pcf_enabled` (Check), `custom_territory_cluster` (Select)

### Role assignments (live `tabHas Role`)
| User | Relevant roles |
|---|---|
| `test.area@bebang.ph` | Area Manager, Area Supervisor, Employee, HR User |
| `test.scm@bebang.ph` | Regional Manager, Supply Chain Manager, Warehouse Manager |
| `test.supervisor@bebang.ph` | Store Supervisor, Warehouse Manager, Warehouse User, HR User, Leave Approver, Projects User, Employee |
| `test.warehouse@bebang.ph` | Warehouse Manager, Warehouse User, Stock Manager, Stock User, Employee |

### User Permissions (Warehouse)
- `test.supervisor@bebang.ph` — **0 rows** (unrestricted)

## Strategy

Per plan §I two-branch decision:
- **Area supervisor leg (`test.area@bebang.ph`):** field EXISTS → `scripts/s209_grant_test_area_access.py` flips `Warehouse.custom_area_supervisor = test.area@bebang.ph` on all 49 canonical warehouses (idempotent, captures prior value to `output/l3/s209/area_access_snapshot.json`). Phase 6 reverts via `scripts/s209_revert_test_area_access.py`.
- **Receiving leg (`test.supervisor@bebang.ph`):** field DOES NOT EXIST, BUT the user already has `Store Supervisor + Warehouse Manager + Warehouse User` roles globally with 0 Warehouse User Permissions → **NO GRANT NEEDED**. The existing roles provide universal receiving access for the test window; no audit change required beyond the area-supervisor flip.

## Revert semantics

- `area_access_snapshot.json` captures pre-sweep `custom_area_supervisor` per warehouse. Phase 6 restore sets each warehouse back to its captured prior value (NULL if blank, string if previously set).
- No user role grants are added or removed during S209, so no role-revert step required.
- Revert audit log: `output/l3/s209/access_changes.log` records each warehouse touched, before/after values, and timestamp.

## Sources
- P0-T7 probe output: `tabCustom Field WHERE dt = 'Warehouse'` returned 3 rows; no `custom_store_supervisor`.
- `tabHas Role` queries for the 4 test users.
- `tabUser Permission WHERE user = 'test.supervisor@bebang.ph' AND allow = 'Warehouse'` returned 0 rows.
