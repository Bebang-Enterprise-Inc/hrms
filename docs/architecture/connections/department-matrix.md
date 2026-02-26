# Department Interaction Matrix
**Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

---

## 12×12 Department Interaction Matrix

Departments (row = sender, column = receiver):
- SO = Store Ops | IN = Inventory | HS = HR Self-Service | HM = HR Management
- EX = Expenses/PCF | SU = Supervisor Tools | FI = Finance | PR = Procurement
- WH = Warehouse | CO = Commissary | PJ = Projects | CC = Cross-cutting

Connection types: **DATA** (shared DocType/Link), **APPROVAL** (cross-dept approval flow), **NOTIFY** (GChat/email notification), **SHARED** (both read same DocType)

| Sender → | SO | IN | HS | HM | EX | SU | FI | PR | WH | CO | PJ | CC |
|----------|----|----|----|----|----|----|----|----|----|----|----|----|
| **SO** | — | 3 DATA,SHARED | 1 DATA | 1 DATA | 1 DATA | 3 APPROVAL,NOTIFY,DATA | 2 DATA,NOTIFY | — | 3 DATA,NOTIFY,APPROVAL | 3 DATA,NOTIFY,SHARED | 2 DATA,NOTIFY | 4 DATA,NOTIFY,SHARED |
| **IN** | 2 DATA,SHARED | — | — | 1 NOTIFY | — | 1 APPROVAL | 2 DATA,APPROVAL | — | 2 DATA,SHARED | 2 DATA,SHARED | — | 2 DATA,NOTIFY |
| **HS** | 1 DATA | — | — | 2 DATA,APPROVAL | 1 DATA | 1 DATA | — | — | — | — | — | 3 DATA,NOTIFY,SHARED |
| **HM** | 1 DATA | — | 3 DATA,APPROVAL,NOTIFY | — | — | 2 DATA,APPROVAL | 2 DATA,NOTIFY | — | — | — | — | 3 DATA,NOTIFY,SHARED |
| **EX** | 1 DATA | — | 1 DATA | — | — | 1 APPROVAL | 4 DATA,APPROVAL,NOTIFY,SHARED | — | — | — | — | 2 DATA,NOTIFY |
| **SU** | 3 DATA,NOTIFY,APPROVAL | 1 DATA | 2 DATA,SHARED | 2 DATA,NOTIFY | — | — | 1 NOTIFY | — | — | — | 1 DATA | 3 DATA,NOTIFY,SHARED |
| **FI** | 1 DATA | 1 DATA | 1 NOTIFY | — | 2 DATA,NOTIFY | — | — | 3 DATA,APPROVAL,SHARED | 2 DATA,NOTIFY | 1 DATA | 1 DATA | 2 DATA,NOTIFY |
| **PR** | — | 1 DATA | — | — | — | — | 4 DATA,APPROVAL,SHARED,NOTIFY | — | 3 DATA,APPROVAL,NOTIFY | 1 DATA | — | 2 DATA,NOTIFY |
| **WH** | 3 DATA,NOTIFY,SHARED | 2 DATA,SHARED | — | — | — | 1 DATA | 1 DATA | 2 DATA,SHARED | — | 3 DATA,NOTIFY,SHARED | 1 DATA | 2 DATA,NOTIFY |
| **CO** | 3 DATA,NOTIFY,SHARED | 2 DATA,SHARED | — | — | — | — | 2 DATA,NOTIFY | 1 DATA | 3 DATA,NOTIFY,SHARED | — | — | 2 DATA,NOTIFY |
| **PJ** | 3 DATA,NOTIFY,APPROVAL | — | — | — | — | 1 NOTIFY | 2 DATA,NOTIFY | — | 1 DATA | — | — | 2 DATA,NOTIFY |
| **CC** | 2 DATA,SHARED | 1 DATA | 3 DATA,NOTIFY,SHARED | 2 DATA,SHARED | 1 DATA | 2 DATA,SHARED | 1 DATA | 1 DATA | — | — | 1 DATA | — |

**Total connections: 147** (unique directional pairs × type)

---

## Connection Count Summary

| Department | Outbound | Inbound | Total |
|-----------|----------|---------|-------|
| Store Ops | 23 | 20 | **43** |
| Finance | 17 | 22 | **39** |
| Cross-cutting | 14 | 24 | **38** |
| Warehouse | 17 | 14 | **31** |
| HR Management | 13 | 12 | **25** |
| Procurement | 14 | 11 | **25** |
| Commissary | 13 | 12 | **25** |
| Supervisor Tools | 14 | 10 | **24** |
| Inventory | 10 | 11 | **21** |
| HR Self-Service | 8 | 9 | **17** |
| Projects | 9 | 7 | **16** |
| Expenses/PCF | 9 | 6 | **15** |

---

## Highest-Traffic DocTypes (shared across 3+ departments)

| DocType | Departments | Access Type |
|---------|-------------|-------------|
| Warehouse (store record) | SO, IN, HS, HM, SU, WH, CO, PJ, CC | Link field in nearly every module |
| Employee | HS, HM, SU, CC, PR | Link field |
| BEI Store Order | SO, SU, WH, CO, CC | DATA + NOTIFY |
| BEI Distribution Trip | SO, WH, CO, FI | DATA + NOTIFY |
| Material Request | SO, IN, WH, CO | SHARED (supply chain spine) |
| Stock Entry | IN, WH, CO | SHARED |
| BEI Approval Queue | SO, HS, SU, CC | DATA + NOTIFY |
| Leave Application | HS, HM, SU | APPROVAL + DATA |
| BEI Billing Schedule | FI, WH, PR, PJ | DATA + SHARED |
| BEI Payment Request | FI, PR, PJ | DATA + APPROVAL |

---

## Per-Department Connection Diagrams

See [per-department/](per-department/) directory for detailed connection maps per department.
