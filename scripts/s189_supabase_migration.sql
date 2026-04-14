-- =============================================================================
-- S189: Real-time BOM Consumption Pipeline — Supabase Migration
-- Apply via Supabase SQL Editor (Dashboard).
-- Rollback: scripts/s189_rollback.sql
-- =============================================================================

-- ─── Phase 0: Schema ────────────────────────────────────────────────────────

-- T0.1: product_bom table
CREATE TABLE public.product_bom (
    id BIGSERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    material_code TEXT NOT NULL,
    material_name TEXT NOT NULL,
    grams_per_serving NUMERIC(8,2) NOT NULL,
    bom_source TEXT DEFAULT 'frappe_bom',
    bom_source_name TEXT,
    uom TEXT DEFAULT 'g',
    conversion_factor NUMERIC(8,4) DEFAULT 1.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_name, material_code)
);

CREATE INDEX idx_product_bom_product ON public.product_bom(product_name);
CREATE INDEX idx_product_bom_material ON public.product_bom(material_code);

COMMENT ON TABLE public.product_bom IS 'Bill of Materials: grams of each raw material per serving of each finished product. Seeded from Frappe BOM DocType by S189.';

-- T0.2: daily_material_consumption table
CREATE TABLE public.daily_material_consumption (
    id BIGSERIAL PRIMARY KEY,
    business_date DATE NOT NULL,
    material_code TEXT NOT NULL,
    material_name TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'POS',
    location_id INTEGER NOT NULL DEFAULT 0,
    total_cups INTEGER DEFAULT 0,
    total_grams NUMERIC(12,2) DEFAULT 0,
    total_kg NUMERIC(10,3) GENERATED ALWAYS AS (total_grams / 1000) STORED,
    uom TEXT DEFAULT 'g',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.daily_material_consumption
    ADD CONSTRAINT idx_dmc_unique UNIQUE (business_date, material_code, channel, location_id);

CREATE INDEX idx_dmc_date ON public.daily_material_consumption(business_date);
CREATE INDEX idx_dmc_material ON public.daily_material_consumption(material_code);
CREATE INDEX idx_dmc_date_material ON public.daily_material_consumption(business_date, material_code);
CREATE INDEX idx_dmc_location ON public.daily_material_consumption(location_id);

COMMENT ON TABLE public.daily_material_consumption IS 'Daily raw material consumption derived from POS+Web sales x BOM. Auto-populated by triggers on pos_order_items and web_order_items. S189.';

-- T0.3: Helper views

-- Aggregated daily consumption (all channels + locations combined)
CREATE OR REPLACE VIEW public.v_daily_material_consumption AS
SELECT
    business_date,
    material_code,
    material_name,
    SUM(total_cups) AS total_cups,
    SUM(total_grams) AS total_grams,
    SUM(total_grams) / 1000 AS total_kg,
    MAX(updated_at) AS updated_at
FROM public.daily_material_consumption
GROUP BY business_date, material_code, material_name
ORDER BY business_date DESC, total_grams DESC;

-- Per-store daily consumption
CREATE OR REPLACE VIEW public.v_daily_material_consumption_by_store AS
SELECT
    business_date,
    material_code,
    material_name,
    location_id,
    SUM(total_cups) AS total_cups,
    SUM(total_grams) AS total_grams,
    SUM(total_grams) / 1000 AS total_kg,
    MAX(updated_at) AS updated_at
FROM public.daily_material_consumption
WHERE location_id != 0
GROUP BY business_date, material_code, material_name, location_id
ORDER BY business_date DESC, total_grams DESC;

-- 7-day rolling average per material (PHT timezone)
CREATE OR REPLACE VIEW public.v_material_7day_avg AS
SELECT
    material_code,
    material_name,
    AVG(daily_kg) AS avg_kg_per_day,
    SUM(daily_kg) AS total_kg_7d,
    MIN(business_date) AS period_start,
    MAX(business_date) AS period_end,
    COUNT(DISTINCT business_date) AS days_with_data
FROM (
    SELECT business_date, material_code, material_name,
           SUM(total_grams)/1000 AS daily_kg
    FROM public.daily_material_consumption
    WHERE business_date >= (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Manila')::DATE - 7
    GROUP BY business_date, material_code, material_name
) daily
GROUP BY material_code, material_name;

-- ─── Phase 1: Triggers ──────────────────────────────────────────────────────

-- T1.1: POS order items trigger function
CREATE OR REPLACE FUNCTION public.fn_update_material_consumption_pos()
RETURNS TRIGGER AS $$
DECLARE
    v_business_date DATE;
    v_bom RECORD;
    v_delta INTEGER;
    v_location_id INTEGER;
BEGIN
    SELECT business_date, location_id INTO v_business_date, v_location_id
    FROM public.pos_orders
    WHERE id = NEW.order_id;

    IF v_business_date IS NULL THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        v_delta := COALESCE(NEW.quantity, 1);
    ELSIF TG_OP = 'UPDATE' THEN
        v_delta := COALESCE(NEW.quantity, 1) - COALESCE(OLD.quantity, 0);
        IF v_delta = 0 THEN
            RETURN NEW;
        END IF;
    END IF;

    FOR v_bom IN
        SELECT material_code, material_name, grams_per_serving
        FROM public.product_bom
        WHERE product_name = NEW.product_name
        AND is_active = TRUE
    LOOP
        INSERT INTO public.daily_material_consumption
            (business_date, material_code, material_name, channel, location_id,
             total_cups, total_grams)
        VALUES
            (v_business_date, v_bom.material_code, v_bom.material_name, 'POS',
             COALESCE(v_location_id, 0),
             v_delta,
             v_delta * v_bom.grams_per_serving)
        ON CONFLICT ON CONSTRAINT idx_dmc_unique
        DO UPDATE SET
            total_cups = daily_material_consumption.total_cups + v_delta,
            total_grams = daily_material_consumption.total_grams + (v_delta * v_bom.grams_per_serving),
            updated_at = NOW();
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- T1.2: Web order items trigger function
CREATE OR REPLACE FUNCTION public.fn_update_material_consumption_web()
RETURNS TRIGGER AS $$
DECLARE
    v_business_date DATE;
    v_bom RECORD;
    v_delta INTEGER;
    v_location_id INTEGER;
BEGIN
    SELECT business_date, location_id
    INTO v_business_date, v_location_id
    FROM public.web_orders
    WHERE id = NEW.order_id;

    IF v_business_date IS NULL THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        v_delta := COALESCE(NEW.quantity, 1);
    ELSIF TG_OP = 'UPDATE' THEN
        v_delta := COALESCE(NEW.quantity, 1) - COALESCE(OLD.quantity, 0);
        IF v_delta = 0 THEN
            RETURN NEW;
        END IF;
    END IF;

    FOR v_bom IN
        SELECT material_code, material_name, grams_per_serving
        FROM public.product_bom
        WHERE product_name = NEW.product_name
        AND is_active = TRUE
    LOOP
        INSERT INTO public.daily_material_consumption
            (business_date, material_code, material_name, channel, location_id,
             total_cups, total_grams)
        VALUES
            (v_business_date, v_bom.material_code, v_bom.material_name, 'Web',
             COALESCE(v_location_id, 0),
             v_delta,
             v_delta * v_bom.grams_per_serving)
        ON CONFLICT ON CONSTRAINT idx_dmc_unique
        DO UPDATE SET
            total_cups = daily_material_consumption.total_cups + v_delta,
            total_grams = daily_material_consumption.total_grams + (v_delta * v_bom.grams_per_serving),
            updated_at = NOW();
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- T1.3: Attach triggers
CREATE TRIGGER trg_pos_item_bom_consumption
    AFTER INSERT OR UPDATE ON public.pos_order_items
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_update_material_consumption_pos();

CREATE TRIGGER trg_web_item_bom_consumption
    AFTER INSERT OR UPDATE ON public.web_order_items
    FOR EACH ROW
    EXECUTE FUNCTION public.fn_update_material_consumption_web();

-- T1.4: POS order cancellation reversal
CREATE OR REPLACE FUNCTION public.fn_reverse_consumption_on_cancel()
RETURNS TRIGGER AS $$
DECLARE
    v_item RECORD;
    v_bom RECORD;
BEGIN
    IF NEW.cancelled_at IS NOT NULL AND OLD.cancelled_at IS NULL THEN
        FOR v_item IN
            SELECT product_name, quantity FROM public.pos_order_items
            WHERE order_id = NEW.id
        LOOP
            FOR v_bom IN
                SELECT material_code, grams_per_serving
                FROM public.product_bom
                WHERE product_name = v_item.product_name AND is_active = TRUE
            LOOP
                UPDATE public.daily_material_consumption
                SET total_cups = GREATEST(0, total_cups - COALESCE(v_item.quantity, 1)),
                    total_grams = GREATEST(0, total_grams - (COALESCE(v_item.quantity, 1) * v_bom.grams_per_serving)),
                    updated_at = NOW()
                WHERE business_date = NEW.business_date
                  AND material_code = v_bom.material_code
                  AND channel = 'POS'
                  AND location_id = COALESCE(NEW.location_id, 0);
            END LOOP;
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pos_order_cancel_reversal
    AFTER UPDATE ON public.pos_orders
    FOR EACH ROW
    WHEN (NEW.cancelled_at IS NOT NULL AND OLD.cancelled_at IS NULL)
    EXECUTE FUNCTION public.fn_reverse_consumption_on_cancel();

-- Web order refund reversal (web_orders uses refund_flag, not cancelled_at)
CREATE OR REPLACE FUNCTION public.fn_reverse_consumption_on_cancel_web()
RETURNS TRIGGER AS $$
DECLARE
    v_item RECORD;
    v_bom RECORD;
BEGIN
    IF NEW.refund_flag = TRUE AND (OLD.refund_flag IS NULL OR OLD.refund_flag = FALSE) THEN
        FOR v_item IN
            SELECT product_name, quantity FROM public.web_order_items
            WHERE order_id = NEW.id
        LOOP
            FOR v_bom IN
                SELECT material_code, grams_per_serving
                FROM public.product_bom
                WHERE product_name = v_item.product_name AND is_active = TRUE
            LOOP
                UPDATE public.daily_material_consumption
                SET total_cups = GREATEST(0, total_cups - COALESCE(v_item.quantity, 1)),
                    total_grams = GREATEST(0, total_grams - (COALESCE(v_item.quantity, 1) * v_bom.grams_per_serving)),
                    updated_at = NOW()
                WHERE business_date = NEW.business_date
                  AND material_code = v_bom.material_code
                  AND channel = 'Web'
                  AND location_id = COALESCE(NEW.location_id, 0);
            END LOOP;
        END LOOP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_web_order_cancel_reversal
    AFTER UPDATE ON public.web_orders
    FOR EACH ROW
    WHEN (NEW.refund_flag = TRUE AND (OLD.refund_flag IS NULL OR OLD.refund_flag = FALSE))
    EXECUTE FUNCTION public.fn_reverse_consumption_on_cancel_web();

-- ─── Phase 4: DTL Function ──────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.fn_material_dtl(
    p_material_code TEXT,
    p_current_soh_kg NUMERIC
)
RETURNS TABLE(
    material_code TEXT,
    material_name TEXT,
    current_soh_kg NUMERIC,
    avg_daily_kg NUMERIC,
    dtl_days NUMERIC,
    dtl_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.material_code,
        m.material_name,
        p_current_soh_kg,
        m.avg_kg_per_day,
        CASE WHEN m.avg_kg_per_day > 0
             THEN ROUND(p_current_soh_kg / m.avg_kg_per_day, 1)
             ELSE NULL END,
        CASE
            WHEN m.avg_kg_per_day = 0 THEN 'NO_DATA'
            WHEN p_current_soh_kg / m.avg_kg_per_day < 3 THEN 'CRITICAL'
            WHEN p_current_soh_kg / m.avg_kg_per_day < 7 THEN 'LOW'
            WHEN p_current_soh_kg / m.avg_kg_per_day < 14 THEN 'MEDIUM'
            ELSE 'HIGH'
        END
    FROM public.v_material_7day_avg m
    WHERE m.material_code = p_material_code;
END;
$$ LANGUAGE plpgsql;

-- ─── Phase 6: Sync log table ────────────────────────────────────────────────

-- T6.2: Frappe sync log
CREATE TABLE public.daily_material_consumption_frappe_sync (
    id BIGSERIAL PRIMARY KEY,
    business_date DATE NOT NULL,
    material_code TEXT NOT NULL,
    total_kg NUMERIC(10,3) NOT NULL,
    last_synced_grams NUMERIC(12,2) DEFAULT 0,
    frappe_stock_entry_name TEXT,
    sync_status TEXT DEFAULT 'PENDING',
    error_message TEXT,
    synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(business_date, material_code)
);

-- ─── Phase 7: Reconciliation ────────────────────────────────────────────────

-- T7.1: ingestion_source column on pos_orders
ALTER TABLE public.pos_orders
ADD COLUMN IF NOT EXISTS ingestion_source TEXT DEFAULT 'poll';

CREATE INDEX IF NOT EXISTS idx_pos_orders_ingestion ON public.pos_orders(ingestion_source);

-- T7.6: Reconciliation views
CREATE OR REPLACE VIEW public.v_ingestion_reconciliation AS
SELECT
    business_date,
    ingestion_source,
    COUNT(*) AS order_count,
    SUM(gross_sales) AS gross_sales
FROM public.pos_orders
WHERE business_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY business_date, ingestion_source
ORDER BY business_date DESC, ingestion_source;

CREATE OR REPLACE VIEW public.v_webhook_coverage AS
SELECT
    business_date,
    COUNT(*) FILTER (WHERE ingestion_source = 'webhook') AS webhook_orders,
    COUNT(*) FILTER (WHERE ingestion_source = 'poll') AS poll_only_orders,
    COUNT(*) AS total_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ingestion_source = 'webhook') /
        NULLIF(COUNT(*), 0), 1) AS webhook_coverage_pct
FROM public.pos_orders
WHERE business_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY business_date
ORDER BY business_date DESC;

CREATE OR REPLACE VIEW public.v_store_internet_health AS
SELECT
    location_id,
    business_date,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE ingestion_source = 'webhook') AS webhook_orders,
    COUNT(*) FILTER (WHERE ingestion_source = 'poll') AS poll_only_orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ingestion_source = 'webhook') /
        NULLIF(COUNT(*), 0), 1) AS webhook_pct
FROM public.pos_orders
WHERE business_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY location_id, business_date
HAVING COUNT(*) FILTER (WHERE ingestion_source = 'webhook') < COUNT(*) * 0.5
ORDER BY webhook_pct ASC;
