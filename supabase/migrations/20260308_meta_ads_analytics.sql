-- Meta Ads Analytics Schema
-- Stores campaign/ad set/ad inventory + daily performance snapshots
-- Synced weekly from Meta Marketing API via sync_meta_ads_to_supabase.py

-- ============================================================
-- 1. CAMPAIGNS
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_campaigns (
    id TEXT PRIMARY KEY,                    -- Meta campaign ID
    name TEXT NOT NULL,
    objective TEXT,                          -- OUTCOME_SALES, OUTCOME_TRAFFIC, etc.
    status TEXT,                             -- ACTIVE, PAUSED, ARCHIVED
    effective_status TEXT,
    daily_budget INTEGER,                   -- in centavos (PHP * 100)
    lifetime_budget INTEGER,
    is_cbo BOOLEAN DEFAULT FALSE,           -- campaign budget optimization
    created_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. AD SETS
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_adsets (
    id TEXT PRIMARY KEY,                    -- Meta ad set ID
    campaign_id TEXT REFERENCES meta_campaigns(id),
    name TEXT NOT NULL,
    status TEXT,
    effective_status TEXT,
    daily_budget INTEGER,                   -- centavos
    optimization_goal TEXT,                 -- LINK_CLICKS, OFFSITE_CONVERSIONS, etc.
    billing_event TEXT,
    targeting_summary TEXT,                 -- human-readable targeting description
    targeting_geo TEXT,                     -- geo locations summary (e.g. "SM Megamall 15mi + Venice 4mi")
    targeting_audiences TEXT,               -- custom/lookalike audience names
    targeting_interests TEXT,               -- interest targeting summary
    targeting_age_min INTEGER,
    targeting_age_max INTEGER,
    targeting_json JSONB,                   -- full targeting blob for reference
    placements TEXT,                        -- "facebook,instagram,audience_network,messenger"
    created_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 3. ADS (the core inventory table)
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_ads (
    id TEXT PRIMARY KEY,                    -- Meta ad ID
    campaign_id TEXT REFERENCES meta_campaigns(id),
    adset_id TEXT REFERENCES meta_adsets(id),
    name TEXT NOT NULL,
    status TEXT,
    effective_status TEXT,
    creative_id TEXT,
    -- Creative details (denormalized for fast queries)
    creative_body TEXT,                     -- ad copy / post text
    creative_title TEXT,                    -- headline
    creative_description TEXT,              -- generated summary for quick evaluation
    creative_type TEXT,                     -- IMAGE, VIDEO, CAROUSEL, POST
    creative_image_url TEXT,                -- thumbnail/image URL
    creative_video_url TEXT,                -- video thumbnail or URL
    creative_thumbnail_hash TEXT,           -- for detecting creative changes
    call_to_action TEXT,                    -- ORDER_NOW, SHOP_NOW, LEARN_MORE
    link_url TEXT,                          -- destination URL
    object_story_id TEXT,                   -- source post ID if boosted
    -- Cached latest metrics (updated on each sync)
    last_7d_spend NUMERIC(12,2) DEFAULT 0,
    last_7d_impressions INTEGER DEFAULT 0,
    last_7d_clicks INTEGER DEFAULT 0,
    last_7d_purchases INTEGER DEFAULT 0,
    last_7d_ctr NUMERIC(6,3) DEFAULT 0,
    last_7d_cpa NUMERIC(10,2) DEFAULT 0,
    last_7d_frequency NUMERIC(6,3) DEFAULT 0,
    last_30d_spend NUMERIC(12,2) DEFAULT 0,
    last_30d_impressions INTEGER DEFAULT 0,
    last_30d_clicks INTEGER DEFAULT 0,
    last_30d_purchases INTEGER DEFAULT 0,
    last_30d_ctr NUMERIC(6,3) DEFAULT 0,
    last_30d_cpa NUMERIC(10,2) DEFAULT 0,
    last_30d_frequency NUMERIC(6,3) DEFAULT 0,
    -- Flags
    is_flagged BOOLEAN DEFAULT FALSE,
    flag_reason TEXT,                        -- "HIGH_FREQUENCY", "HIGH_CPA", "LOW_CTR", "WITH_ISSUES"
    created_time TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4. DAILY SNAPSHOTS (historical performance tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_ad_daily (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ad_id TEXT NOT NULL REFERENCES meta_ads(id),
    report_date DATE NOT NULL,
    spend NUMERIC(12,2) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    ctr NUMERIC(6,3) DEFAULT 0,
    cpc NUMERIC(10,2) DEFAULT 0,
    cpm NUMERIC(10,2) DEFAULT 0,
    frequency NUMERIC(6,3) DEFAULT 0,
    reach INTEGER DEFAULT 0,
    purchases INTEGER DEFAULT 0,
    cpa_purchase NUMERIC(10,2) DEFAULT 0,
    link_clicks INTEGER DEFAULT 0,
    post_engagement INTEGER DEFAULT 0,
    video_views INTEGER DEFAULT 0,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ad_id, report_date)
);

-- ============================================================
-- 5. ORGANIC POSTS (page posts for boost evaluation)
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_organic_posts (
    id TEXT PRIMARY KEY,                    -- page post ID
    message TEXT,                            -- post text
    created_time TIMESTAMPTZ,
    post_type TEXT,                          -- photo, video, link, status
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    engagement_score INTEGER DEFAULT 0,     -- likes*1 + comments*3 + shares*5
    permalink_url TEXT,
    image_url TEXT,
    is_boosted BOOLEAN DEFAULT FALSE,       -- already used as ad
    boosted_ad_id TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 6. AUDIT LOG (track all actions taken)
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_audit_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action TEXT NOT NULL,                    -- PAUSE, ACTIVATE, BUDGET_CHANGE, CREATE, etc.
    entity_type TEXT NOT NULL,              -- campaign, adset, ad
    entity_id TEXT NOT NULL,
    entity_name TEXT,
    reason TEXT,
    metrics_before JSONB,
    metrics_after JSONB,
    executed_by TEXT DEFAULT 'claude',
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 7. SYNC STATE (track last successful sync)
-- ============================================================
CREATE TABLE IF NOT EXISTS meta_sync_state (
    sync_type TEXT PRIMARY KEY,             -- 'ads', 'insights_7d', 'insights_30d', 'organic'
    last_sync TIMESTAMPTZ,
    records_synced INTEGER,
    status TEXT,                             -- 'success', 'error'
    error_message TEXT,
    duration_seconds NUMERIC(8,2)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_meta_ads_campaign ON meta_ads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_adset ON meta_ads(adset_id);
CREATE INDEX IF NOT EXISTS idx_meta_ads_status ON meta_ads(effective_status);
CREATE INDEX IF NOT EXISTS idx_meta_ads_flagged ON meta_ads(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_meta_ad_daily_date ON meta_ad_daily(report_date);
CREATE INDEX IF NOT EXISTS idx_meta_ad_daily_ad ON meta_ad_daily(ad_id, report_date);
CREATE INDEX IF NOT EXISTS idx_meta_organic_score ON meta_organic_posts(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_meta_audit_log_date ON meta_audit_log(executed_at);

-- ============================================================
-- VIEWS: Ready-to-query analytics
-- ============================================================

-- Full ad inventory with campaign + adset context
CREATE OR REPLACE VIEW v_meta_ad_inventory AS
SELECT
    a.id AS ad_id,
    a.name AS ad_name,
    a.effective_status,
    a.creative_type,
    a.creative_description,
    a.creative_body,
    a.call_to_action,
    a.link_url,
    a.creative_image_url,
    a.is_flagged,
    a.flag_reason,
    -- Ad set context
    s.name AS adset_name,
    s.daily_budget / 100.0 AS adset_daily_budget_php,
    s.optimization_goal,
    s.targeting_summary,
    s.targeting_geo,
    s.targeting_audiences,
    s.targeting_interests,
    s.targeting_age_min,
    s.targeting_age_max,
    s.placements,
    -- Campaign context
    c.name AS campaign_name,
    c.objective AS campaign_objective,
    c.status AS campaign_status,
    -- 7-day metrics
    a.last_7d_spend,
    a.last_7d_impressions,
    a.last_7d_clicks,
    a.last_7d_purchases,
    a.last_7d_ctr,
    a.last_7d_cpa,
    a.last_7d_frequency,
    -- 30-day metrics
    a.last_30d_spend,
    a.last_30d_impressions,
    a.last_30d_clicks,
    a.last_30d_purchases,
    a.last_30d_ctr,
    a.last_30d_cpa,
    a.last_30d_frequency,
    -- Computed
    CASE
        WHEN a.last_30d_purchases > 0 THEN a.last_30d_spend / a.last_30d_purchases
        ELSE NULL
    END AS computed_cpa_30d,
    a.synced_at AS last_synced
FROM meta_ads a
JOIN meta_adsets s ON a.adset_id = s.id
JOIN meta_campaigns c ON a.campaign_id = c.id;

-- Campaign-level rollup
CREATE OR REPLACE VIEW v_meta_campaign_summary AS
SELECT
    c.id AS campaign_id,
    c.name AS campaign_name,
    c.objective,
    c.status,
    COUNT(DISTINCT s.id) AS adset_count,
    COUNT(DISTINCT a.id) AS ad_count,
    COUNT(DISTINCT a.id) FILTER (WHERE a.effective_status = 'ACTIVE') AS active_ads,
    COUNT(DISTINCT a.id) FILTER (WHERE a.is_flagged) AS flagged_ads,
    SUM(s.daily_budget) / 100.0 AS total_daily_budget_php,
    SUM(a.last_7d_spend) AS total_7d_spend,
    SUM(a.last_7d_purchases) AS total_7d_purchases,
    CASE WHEN SUM(a.last_7d_purchases) > 0
        THEN SUM(a.last_7d_spend) / SUM(a.last_7d_purchases)
        ELSE NULL END AS avg_7d_cpa,
    SUM(a.last_30d_spend) AS total_30d_spend,
    SUM(a.last_30d_purchases) AS total_30d_purchases,
    CASE WHEN SUM(a.last_30d_purchases) > 0
        THEN SUM(a.last_30d_spend) / SUM(a.last_30d_purchases)
        ELSE NULL END AS avg_30d_cpa
FROM meta_campaigns c
LEFT JOIN meta_adsets s ON s.campaign_id = c.id
LEFT JOIN meta_ads a ON a.adset_id = s.id
GROUP BY c.id, c.name, c.objective, c.status;

-- Flagged ads requiring attention
CREATE OR REPLACE VIEW v_meta_flagged_ads AS
SELECT
    a.id AS ad_id,
    a.name AS ad_name,
    a.flag_reason,
    a.effective_status,
    c.name AS campaign_name,
    s.name AS adset_name,
    a.creative_description,
    a.last_30d_spend,
    a.last_30d_cpa,
    a.last_30d_frequency,
    a.last_30d_ctr,
    a.creative_image_url
FROM meta_ads a
JOIN meta_adsets s ON a.adset_id = s.id
JOIN meta_campaigns c ON a.campaign_id = c.id
WHERE a.is_flagged = TRUE
ORDER BY a.last_30d_spend DESC;

-- Weekly trend (for week-over-week comparison)
CREATE OR REPLACE VIEW v_meta_weekly_trend AS
SELECT
    date_trunc('week', d.report_date)::DATE AS week_start,
    c.name AS campaign_name,
    c.objective,
    SUM(d.spend) AS weekly_spend,
    SUM(d.impressions) AS weekly_impressions,
    SUM(d.clicks) AS weekly_clicks,
    SUM(d.purchases) AS weekly_purchases,
    CASE WHEN SUM(d.impressions) > 0
        THEN ROUND(SUM(d.clicks)::NUMERIC / SUM(d.impressions) * 100, 2)
        ELSE 0 END AS weekly_ctr,
    CASE WHEN SUM(d.purchases) > 0
        THEN ROUND(SUM(d.spend) / SUM(d.purchases), 2)
        ELSE NULL END AS weekly_cpa
FROM meta_ad_daily d
JOIN meta_ads a ON d.ad_id = a.id
JOIN meta_campaigns c ON a.campaign_id = c.id
GROUP BY 1, 2, 3
ORDER BY 1 DESC, weekly_spend DESC;

-- Top organic posts for boosting
CREATE OR REPLACE VIEW v_meta_boost_candidates AS
SELECT
    id AS post_id,
    message,
    created_time,
    likes,
    comments,
    shares,
    engagement_score,
    CASE
        WHEN engagement_score > 500 THEN 'VIRAL - Boost immediately'
        WHEN engagement_score > 200 THEN 'STRONG - Boost as awareness'
        WHEN engagement_score > 100 THEN 'GOOD - Consider for retargeting'
        ELSE 'AVERAGE - Monitor only'
    END AS recommendation,
    is_boosted,
    image_url
FROM meta_organic_posts
WHERE NOT is_boosted
ORDER BY engagement_score DESC;

-- ============================================================
-- RLS POLICIES
-- ============================================================
ALTER TABLE meta_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_adsets ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_ad_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_organic_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE meta_sync_state ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (sync scripts use service key)
CREATE POLICY "Service role full access" ON meta_campaigns FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_adsets FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_ads FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_ad_daily FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_organic_posts FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_audit_log FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON meta_sync_state FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- Authenticated users can read (for dashboards)
CREATE POLICY "Authenticated read" ON meta_campaigns FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_adsets FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_ads FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_ad_daily FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_organic_posts FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_audit_log FOR SELECT TO authenticated USING (TRUE);
CREATE POLICY "Authenticated read" ON meta_sync_state FOR SELECT TO authenticated USING (TRUE);
