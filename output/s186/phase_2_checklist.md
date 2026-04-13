# S186 Phase 2 Checklist — Supplier Grid Page

| Task | Status | Evidence | Skipped? | If skipped, why? |
|------|--------|----------|----------|------------------|
| 7 MetricCard components | DONE | Total, Active, Missing BIR/SEC/Permit, Expiring, Pending POs | No | — |
| Clickable metric cards with URL filter | DONE | onClick → updateParams({ compliance: ... }) | No | — |
| Frozen left column (supplier name) | DONE | sticky left-0 z-40 bg-background | No | — |
| Frozen right column (actions) | DONE | sticky right-0 z-20 bg-background | No | — |
| Fullscreen mode with Escape exit | DONE | isFullscreen state + keydown listener | No | — |
| Density toggle (compact/comfortable) | DONE | h-12 / h-16 row height | No | — |
| URL-backed filters | DONE | useSearchParams + updateParams helper | No | — |
| Search debounce | DONE | 400ms setTimeout debounce | No | — |
| Status filter | DONE | Select with all 4 statuses | No | — |
| Sort by dropdown | DONE | Name, Total Spend, Total POs, Outstanding, On-Time % | No | — |
| Page size selector (50/100/200) | DONE | PAGE_SIZE_OPTIONS | No | — |
| Pagination controls | DONE | Previous/Next + page indicator | No | — |
| Loading skeletons | DONE | Skeleton rows during fetch | No | — |
| Empty state with CTA | DONE | Building2 icon + "Add your first supplier" | No | — |
| Row click → detail page | DONE | router.push to /suppliers/[id] | No | — |
| Actions dropdown (View, Edit, POs, Invoices) | DONE | DropdownMenu with Links | No | — |
| queryOptions import added | DONE | grep -c "queryOptions" in use-procurement.ts | No | — |
| supplierGridOptions hook | DONE | grep -c "supplierGridOptions" = 1 | No | — |
| contact_number (NOT phone) | DONE | Uses contact_number field | No | — |
| Doc badges with expiry warnings | DONE | DocBadge component with expired/expiring states | No | — |
