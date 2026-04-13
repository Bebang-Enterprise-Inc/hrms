# S186 Phase 1 Checklist — get_supplier_overview

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| Add get_supplier_overview endpoint | DONE | grep -c "def get_supplier_overview" = 1 | No | — |
| All supplier fields via as_dict() | DONE | frappe.get_doc().as_dict() | No | — |
| Live metrics (spend, outstanding, pending) | DONE | SQL queries, not stored fields | No | — |
| Items aggregated from tabBEI PO Item | DONE | Uses unit_cost (not rate), tabBEI PO Item (not Purchase Order Item) | No | — |
| Recent POs (last 20) | DONE | ORDER BY po_date DESC LIMIT 20 | No | — |
| Pending POs with full status strings | DONE | 'Pending Mae Approval' etc. | No | — |
| Pending GRs | DONE | POs without completed GR | No | — |
| Recent invoices | DONE | Last 20 sorted by invoice_date desc | No | — |
| Monthly spend (12 months) | DONE | DATE_FORMAT grouping | No | — |
| YTD/last month/avg monthly | DONE | Separate SQL queries | No | — |
| Sentry DM-7 | DONE | set_backend_observability_context | No | — |
| RBAC with Warehouse User | DONE | Same SUPPLIER_HUB_ALLOWED_ROLES | No | — |
