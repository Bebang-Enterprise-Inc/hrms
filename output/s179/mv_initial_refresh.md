# MV Initial Refresh Timing

- **MV creation**: Completed (237,591 rows from pos_order_items JOIN pos_orders)
- **UNIQUE INDEX**: idx_pcdm_unique_grain on (business_date, location_id, channel, product_name)
- **Covering INDEX**: idx_pcdm_product on (product_name)
- **RPC refresh test**: 204 No Content in ~20 seconds (with SET statement_timeout = '120s')
- **Note**: Initial RPC call failed with 500 (statement timeout) before adding SET statement_timeout to function definition
- **Data stats**: 83 products, 6 channels, 44 stores, 2025-06-27 to 2026-04-10
