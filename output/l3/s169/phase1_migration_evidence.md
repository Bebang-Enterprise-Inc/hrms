# S169 Phase 1 Migration Evidence
Applied: 2026-04-07T18:44:47+08:00

## Columns added
[{"column_name":"cancellation_reason","data_type":"text","is_nullable":"YES"},{"column_name":"cancelled_at","data_type":"timestamp with time zone","is_nullable":"YES"},{"column_name":"completed_at","data_type":"timestamp with time zone","is_nullable":"YES"},{"column_name":"order_status","data_type":"text","is_nullable":"YES"}]
## Index
[{"indexname":"idx_pos_orders_cancelled_at_not_null","indexdef":"CREATE INDEX idx_pos_orders_cancelled_at_not_null ON public.pos_orders USING btree (location_id, business_date) WHERE (cancelled_at IS NOT NULL)"}]
## sync_verification CHECK
[{"pg_get_constraintdef":"CHECK ((status = ANY (ARRAY['ok'::text, 'missing'::text, 'extra'::text, 'healed'::text, 'unresolved'::text, 'api_error'::text, 'extras_tombstoned'::text])))"}]