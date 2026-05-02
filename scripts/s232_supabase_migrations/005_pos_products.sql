-- S232 Migration 005 — pos_products lookup table for cup-vs-addon classification
-- Resolves audit blocker (cup recount) — durable replacement for the price-based heuristic.

CREATE TABLE IF NOT EXISTS pos_products (
    product_id BIGINT PRIMARY KEY,
    product_name TEXT NOT NULL,
    default_price NUMERIC(10, 2),
    is_cup_drink BOOLEAN DEFAULT false,
    category TEXT,
    first_seen_at TIMESTAMPTZ DEFAULT now(),
    last_seen_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pos_products_is_cup_drink
    ON pos_products (is_cup_drink) WHERE is_cup_drink = true;

CREATE INDEX IF NOT EXISTS idx_pos_products_category
    ON pos_products (category);

COMMENT ON TABLE pos_products IS
  'S232: SKU master for Mosaic POS products. is_cup_drink distinguishes actual drink cups '
  'from addons/toppings/packaging. Used by cups_sold analytics to filter out non-cup line items.';

COMMENT ON COLUMN pos_products.is_cup_drink IS
  'S232: true if this product counts as a cup-drink for "cups sold" metric. false for '
  'addons (Ube Halaya, Macapuno, etc.), packaging (Cup 16 oz, Spoon), beverages (Bottled Water), '
  'and bags (Insulated Bag).';

-- Canonical cups_sold view: filters by is_cup_drink AND excludes is_duplicate parents/items.
CREATE OR REPLACE VIEW v_pos_cups_sold AS
SELECT
    po.location_id,
    po.business_date,
    SUM(poi.quantity)::int AS cups_sold,
    COUNT(DISTINCT po.id)::int AS distinct_orders
FROM pos_order_items poi
JOIN pos_orders po ON po.id = poi.order_id
JOIN pos_products pp ON pp.product_id = poi.product_id
WHERE pp.is_cup_drink = true
  AND COALESCE(po.is_duplicate, false) = false
  AND COALESCE(poi.is_duplicate, false) = false
GROUP BY po.location_id, po.business_date;

COMMENT ON VIEW v_pos_cups_sold IS
  'S232: canonical cups_sold rollup. Filters items to is_cup_drink=true AND parent/child '
  'is_duplicate=false. Use this view for analytics, not raw COUNT(*) on pos_order_items.';
