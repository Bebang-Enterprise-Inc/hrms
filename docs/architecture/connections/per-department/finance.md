# Connection Map: Finance & Accounting
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    Finance[Finance & Accounting]
    
    Procurement((Procurement))
    Expenses((Expenses))
    Projects((Projects))
    StoreOps((Store Ops))
    HRMgmt((HR Management))
    Warehouse((Warehouse))
    CrossCutting((Cross-cutting))

    Finance ---|6 DATA: Invoice, Payment Request| Procurement
    Finance ---|4 DATA: PCF Batch, GL| Expenses
    Finance ---|4 DATA: Maint Billing, Charges| Projects
    Finance ---|3 DATA: Billing, POS Data| StoreOps
    Finance ---|3 DATA: Payroll, Final Pay| HRMgmt
    Finance ---|3 DATA: 3PL Billing, Logistics| Warehouse
    Finance -->|3 NOTIFY: SOA, Billing Alerts| CrossCutting
```
