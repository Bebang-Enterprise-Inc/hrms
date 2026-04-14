-- =============================================================================
-- S189: Real-time BOM Consumption Pipeline — ROLLBACK
-- Apply in order to undo all S189 Supabase changes.
-- =============================================================================

-- Phase 7: Reconciliation (reverse order)
DROP VIEW IF EXISTS public.v_store_internet_health;
DROP VIEW IF EXISTS public.v_webhook_coverage;
DROP VIEW IF EXISTS public.v_ingestion_reconciliation;
DROP INDEX IF EXISTS idx_pos_orders_ingestion;
ALTER TABLE public.pos_orders DROP COLUMN IF EXISTS ingestion_source;

-- Phase 6: Sync log
DROP TABLE IF EXISTS public.daily_material_consumption_frappe_sync;

-- Phase 4: DTL function
DROP FUNCTION IF EXISTS public.fn_material_dtl(TEXT, NUMERIC);

-- Phase 1: Triggers (drop triggers before functions)
DROP TRIGGER IF EXISTS trg_web_order_cancel_reversal ON public.web_orders;
DROP TRIGGER IF EXISTS trg_pos_order_cancel_reversal ON public.pos_orders;
DROP TRIGGER IF EXISTS trg_web_item_bom_consumption ON public.web_order_items;
DROP TRIGGER IF EXISTS trg_pos_item_bom_consumption ON public.pos_order_items;

DROP FUNCTION IF EXISTS public.fn_reverse_consumption_on_cancel_web();
DROP FUNCTION IF EXISTS public.fn_reverse_consumption_on_cancel();
DROP FUNCTION IF EXISTS public.fn_update_material_consumption_web();
DROP FUNCTION IF EXISTS public.fn_update_material_consumption_pos();

-- Phase 0: Views, then tables
DROP VIEW IF EXISTS public.v_material_7day_avg;
DROP VIEW IF EXISTS public.v_daily_material_consumption_by_store;
DROP VIEW IF EXISTS public.v_daily_material_consumption;
DROP TABLE IF EXISTS public.daily_material_consumption;
DROP TABLE IF EXISTS public.product_bom;
