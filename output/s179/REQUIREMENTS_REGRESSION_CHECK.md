# S179 Requirements Regression Check

Checked at: 2026-04-10 14:48 PHT
Branch: s179-product-mix-per-channel

1. [YES] MV DDL executed via Supabase Management API SQL (DD-1)
2. [YES] MV includes product_ids INT[] array aggregate (DD-2)
3. [YES] MV covers ALL channels including WebDelivery (DD-2)
4. [YES] MV JOINs pos_order_items with pos_orders on order_id (DD-1)
5. [YES] MV refresh via Postgres RPC function called from PostgREST (DD-8)
6. [YES] API endpoint uses _supabase_get_all helper (DD-4)
7. [YES] API endpoint calls set_backend_observability_context (DM-7)
8. [YES] Product Analytics page reuses S176 DateRangePicker (DD-6)
9. [YES] Product Analytics page has CSV export button for BOM (DD-7)
10. [YES] MODULES.ANALYTICS_ROADMAP is the gate (S176 DD-6)
11. [YES] Zero modifications to sync_pos_to_supabase.py
12. [YES] Zero modifications to pos_orders/pos_order_items schema
13. [N/A] Per-channel cups PostgREST two-step — already merged (hrms#527)
14. [YES] MV has UNIQUE INDEX on grain columns (DD-9)
15. [YES] RPC wrapper created before CONCURRENTLY refresh (DD-8)
16. [YES] Product Analytics page has error state for API failures (S026)
17. [YES] git add -f instructions for docs/ and output/l3/ (S092)

All items: 16 YES, 0 NO, 1 N/A (Phase 1 skipped — already merged)
