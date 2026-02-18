-- Migration: Revoke anon access from financial views
-- Date: 2026-02-18
-- Reason: Financial reporting data should only be accessible to authenticated users.
--         The Supabase anon key should not grant access to revenue/sales data.

-- Revoke anon from all financial views and materialized views
REVOKE SELECT ON store_daily_closing FROM anon;
REVOKE SELECT ON v_system_daily_totals FROM anon;
REVOKE SELECT ON v_all_channel_daily FROM anon;
REVOKE SELECT ON v_ops_weekly FROM anon;
REVOKE SELECT ON foodpanda_store_mapping FROM anon;

-- Ensure authenticated still has access
GRANT SELECT ON store_daily_closing TO authenticated;
GRANT SELECT ON v_system_daily_totals TO authenticated;
GRANT SELECT ON v_all_channel_daily TO authenticated;
GRANT SELECT ON v_ops_weekly TO authenticated;
GRANT SELECT ON foodpanda_store_mapping TO authenticated;
