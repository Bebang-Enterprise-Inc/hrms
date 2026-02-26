# Connection Map: Warehouse & Logistics
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    Warehouse[Warehouse & Logistics]
    
    Commissary((Commissary))
    Procurement((Procurement))
    Inventory((Inventory))
    StoreOps((Store Ops))
    Finance((Finance))

    Warehouse ---|8 DATA: Stock Transfer, Dispatch| Commissary
    Warehouse ---|7 DATA: PO Receiving, GR| Procurement
    Warehouse ---|5 DATA: Stock Levels, Hubs| Inventory
    Warehouse ---|4 DATA: Orders, Receiving, FQI| StoreOps
    Warehouse ---|3 DATA: 3PL Billing, Logistics| Finance
```
