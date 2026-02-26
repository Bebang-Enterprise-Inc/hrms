# Flow Catalog - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Evidence Window:** 2026-02-26 (`docs/architecture/flows/*`, `docs/testing/scenarios/index.yaml`, `docs/plans/system-flow-gaps-v3-full-route-map.md`)

## Purpose

This catalog is the index for end-to-end business flows across departments.
It links architecture flow diagrams, L3 scenario coverage state, and route-map coverage tags.

## Flow Coverage Matrix

| Flow ID | Architecture Flow | Department Chain (source flow file) | Flow Doc | `index.yaml` Flow Key | L3 Flow Status | Primary Scenario File | Route Map Coverage Tag |
|---|---|---|---|---|---|---|---|
| 01 | Hire-to-Onboard | HR -> Store Ops | `docs/architecture/flows/01-hire-to-onboard.md` | `hire-to-onboard` | `ready` | `docs/testing/scenarios/flows/hire-to-onboard.md` | `hire-to-onboard` |
| 02 | Clock-In to Payslip | All Employees -> HR -> Finance | `docs/architecture/flows/02-clock-in-to-payslip.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `hr`)* | `module-level` |
| 03 | Leave Request to Approval | Employee -> Supervisor -> HR | `docs/architecture/flows/03-leave-approval.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `hr`)* | `module-level` |
| 04 | Store Order to Delivery | Store Ops -> Area Supervisor -> Warehouse -> Commissary -> Logistics -> Store Receiving | `docs/architecture/flows/04-store-order-delivery.md` | `dispatch-warehouse-commissary` | `ready` | `docs/testing/scenarios/flows/dispatch-warehouse-commissary.md` | `dispatch-warehouse-commissary` |
| 05 | Purchase Requisition to Payment | Store/Commissary -> Procurement -> Warehouse -> Finance | `docs/architecture/flows/05-pr-to-payment.md` | `procure-to-pay` | `ready` | `docs/testing/scenarios/flows/procure-to-pay.md` | `procure-to-pay` |
| 06 | Expense to Reimbursement | Employee (Store) -> Finance (Accounting) -> PCF Custodian | `docs/architecture/flows/06-expense-reimbursement.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `expense`)* | `module-level` |
| 07 | Daily Store Cycle | Store Staff -> Store Supervisor -> Finance | `docs/architecture/flows/07-daily-store-cycle.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `store-ops`)* | `module-level` |
| 08 | Maintenance Request to Completion | Store -> Projects -> Finance | `docs/architecture/flows/08-maintenance.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `maintenance`)* | `module-level` |
| 09 | Employee Separation / Clearance | HR -> All Departments -> Finance | `docs/architecture/flows/09-separation.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(domain covered under `hire-to-onboard` prefixes: `employee_clearance`)* | `module-level` |
| 10 | Store Visit and Coaching | Area Supervisor -> Store -> HR | `docs/architecture/flows/10-store-visit.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `store-ops`/`communication`/`hr`)* | `module-level` |
| 11 | Inventory Cycle Count to Variance | Store/Auditor -> Supervisor Approval -> Warehouse/Finance | `docs/architecture/flows/11-cycle-count.md` | *(not listed in flows)* | *(no dedicated flow status)* | `docs/testing/scenarios/stock-counting.md` (module command) | `module-level` |
| 12 | 3PL Billing Cycle | Logistics -> Finance -> Store | `docs/architecture/flows/12-3pl-billing.md` | *(not listed in flows)* | *(no dedicated flow status)* | *(module-level: `billing`/`finance`)* | `module-level` |

## What This Means

1. Dedicated L3 flow keys currently exist for three cross-department flows: `procure-to-pay`, `dispatch-warehouse-commissary`, and `hire-to-onboard`.
2. The remaining architecture flows are still tested via module-level catalogs (not dedicated flow keys in `index.yaml`).
3. The full route map is registry-bound at `169/169`, so route-level coverage indexing exists even where flow-level specialization is still module-based.

## Source of Truth Links

- Flow diagrams and traces: `docs/architecture/flows/`
- L3 scenario manifest: `docs/testing/scenarios/index.yaml`
- Full route-level map: `docs/plans/system-flow-gaps-v3-full-route-map.md`
- Route registry: `docs/testing/ROUTE_REGISTRY.md`

## Refresh Procedure

```powershell
python scripts/testing/l3_manifest_check.py
python scripts/docs/documentation_truth_check.py --frontend-path C:\Users\Sam\Projects\Claude\bei-tasks --max-age-days 7
```
