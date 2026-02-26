# Store Ops — Department Connections
**Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph LR
    SO[Store Ops]

    SO -->|DATA: BEI Store Order Item| IN[Inventory]
    SO -->|SHARED: Stock Entry returns| IN
    IN -->|DATA: cycle_count → Warehouse| SO

    SO -->|APPROVAL: Order queue| SUP[Supervisor Tools]
    SUP -->|NOTIFY: Report flagged| SO
    SUP -->|DATA: Approval Queue| SO

    SO -->|DATA: BEI Store Receiving→Trip| WH[Warehouse]
    WH -->|DATA: Trip stops| SO
    WH -->|NOTIFY: 1 stop away| SO

    SO -->|DATA: Material Request| CO[Commissary]
    CO -->|NOTIFY: Order fulfilled| SO
    CO -->|DATA: FQI Report← Store| SO

    SO -->|DATA: Maintenance Request| PJ[Projects]
    PJ -->|NOTIFY: Charge pending| SO
    PJ -->|DATA: completion→Store| SO

    SO -->|DATA: POS Upload, Bank Deposit| FI[Finance]
    FI -->|NOTIFY: Billing sent| SO

    SO -->|NOTIFY: GChat on_store_order_update| CC[Cross-cutting]
    CC -->|DATA: Biometric→Employee| SO
    CC -->|SHARED: BEI Announcement| SO
    CC -->|SHARED: Approval Queue hook| SO

    SO -->|DATA: BEI Shift Record employee| HS[HR Self]
    HS -->|DATA: Leave Application| SO
```

## Key Connections Detail

| Connection | Type | DocType / Mechanism | Status |
|-----------|------|---------------------|--------|
| SO → Supervisor | APPROVAL | BEI Approval Queue (order-approvals) | LIVE |
| SO → Warehouse | DATA | BEI Store Receiving linked to BEI Distribution Trip | LIVE |
| SO → Commissary | DATA | Material Request (Material Transfer) created on order approval | LIVE |
| SO → Projects | DATA | BEI Maintenance Request (store → Warehouse link) | LIVE |
| SO → Finance | DATA | BEI POS Upload, BEI Bank Deposit | LIVE |
| Warehouse → SO | NOTIFY | GChat "1 stop away" via _send_delivery_notification | LIVE |
| Commissary → SO | NOTIFY | BEI Store Order status → Ready for Dispatch | LIVE |
| Projects → SO | NOTIFY | **Missing** — no GChat when charge is set (GAP-033) | BROKEN |
| CC → SO | NOTIFY | hooks.py on_store_order_update → GChat | LIVE |
