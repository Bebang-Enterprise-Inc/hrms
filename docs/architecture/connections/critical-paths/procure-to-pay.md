# Critical Path: Procure-to-Pay
**Scanned:** 2026-02-17 | **Commit:** 7e445d778

```mermaid
graph LR
    STORE["Store Staff<br/>(Store Ops)"]
    COMMISSARY["Commissary<br/>(Supervisor)"]
    WAREHOUSE["Warehouse<br/>(User)"]
    PROCUREMENT["Procurement<br/>(Buyer)"]
    FINANCE["Finance<br/>(AP)"]
    SUPERVISOR["Supervisor<br/>(Area)"]

    STORE -->|1. Submit<br/>Store Order| SUPERVISOR
    SUPERVISOR -->|2. Approve<br/>Order| COMMISSARY
    COMMISSARY -->|3. Create<br/>Material Request| WAREHOUSE
    WAREHOUSE -->|4. Approve<br/>MR| PROCUREMENT
    PROCUREMENT -->|5. Create<br/>Purchase Order| PROCUREMENT
    SUPERVISOR -->|6. Approve PO<br/>(Mae ≤500K)| PROCUREMENT
    FINANCE -->|7. Approve PO<br/>(Butch >500K)| PROCUREMENT
    PROCUREMENT -->|8. Send PO<br/>to Supplier| SUPPLIER
    SUPPLIER -->|9. Deliver<br/>Goods| WAREHOUSE
    WAREHOUSE -->|10. Create<br/>Goods Receipt| WAREHOUSE
    WAREHOUSE -->|11. Create<br/>Stock Entry| COMMISSARY
    COMMISSARY -->|12. Dispatch<br/>to Store| WAREHOUSE
    WAREHOUSE -->|13. Confirm<br/>Delivery| STORE
    STORE -->|14. Complete<br/>Receiving| PROCUREMENT
    PROCUREMENT -->|15. Create<br/>Invoice| FINANCE
    FINANCE -->|16. Verify<br/>3-Way Match| FINANCE
    FINANCE -->|17. Create<br/>Payment Request| PROCUREMENT
    FINANCE -->|18. Approve<br/>(L1 Review)| FINANCE
    FINANCE -->|19. Approve<br/>(L2 Budget)| FINANCE
    FINANCE -->|20. Approve<br/>(L3 CFO)| FINANCE
    FINANCE -->|21. Approve<br/>(L4 CEO if new supplier)| FINANCE
    FINANCE -->|22. Mark<br/>Payment Complete| PROCUREMENT
    PROCUREMENT -->|23. Upload<br/>Official Receipt| FINANCE

    SUPPLIER["External<br/>Supplier"]
```
