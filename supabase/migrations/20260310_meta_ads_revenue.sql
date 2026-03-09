-- Meta Ads Revenue & Enhanced Analytics
-- Sprint S030: Analytics Agent 10x Report Upgrade

-- 1. Add revenue columns to meta_ads (cached period totals)
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS last_7d_purchase_value NUMERIC(12,2) DEFAULT 0;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS last_7d_roas NUMERIC(8,3) DEFAULT 0;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS last_30d_purchase_value NUMERIC(12,2) DEFAULT 0;
ALTER TABLE meta_ads ADD COLUMN IF NOT EXISTS last_30d_roas NUMERIC(8,3) DEFAULT 0;

-- 2. Add revenue to daily snapshots
ALTER TABLE meta_ad_daily ADD COLUMN IF NOT EXISTS purchase_value NUMERIC(12,2) DEFAULT 0;

-- 3. Add funnel_stage to campaigns
ALTER TABLE meta_campaigns ADD COLUMN IF NOT EXISTS funnel_stage TEXT;

-- 4. Recreate campaign summary view (add revenue, ROAS, funnel_stage)
DROP VIEW IF EXISTS v_meta_campaign_summary;
CREATE VIEW v_meta_campaign_summary AS
SELECT
    c.id AS campaign_id,
    c.name AS campaign_name,
    c.objective,
    c.status,
    c.funnel_stage,
    COUNT(DISTINCT s.id) AS adset_count,
    COUNT(DISTINCT a.id) AS ad_count,
    COUNT(DISTINCT a.id) FILTER (WHERE a.effective_status = 'ACTIVE') AS active_ads,
    COUNT(DISTINCT a.id) FILTER (WHERE a.is_flagged) AS flagged_ads,
    SUM(s.daily_budget) / 100.0 AS total_daily_budget_php,
    SUM(a.last_7d_spend) AS total_7d_spend,
    SUM(a.last_7d_purchases) AS total_7d_purchases,
    SUM(a.last_7d_purchase_value) AS total_7d_revenue,
    CASE WHEN SUM(a.last_7d_purchases) > 0
        THEN SUM(a.last_7d_spend) / SUM(a.last_7d_purchases)
        ELSE NULL END AS avg_7d_cpa,
    CASE WHEN SUM(a.last_7d_spend) > 0
        THEN SUM(a.last_7d_purchase_value) / SUM(a.last_7d_spend)
        ELSE NULL END AS avg_7d_roas,
    SUM(a.last_30d_spend) AS total_30d_spend,
    SUM(a.last_30d_purchases) AS total_30d_purchases,
    SUM(a.last_30d_purchase_value) AS total_30d_revenue,
    CASE WHEN SUM(a.last_30d_purchases) > 0
        THEN SUM(a.last_30d_spend) / SUM(a.last_30d_purchases)
        ELSE NULL END AS avg_30d_cpa,
    CASE WHEN SUM(a.last_30d_spend) > 0
        THEN SUM(a.last_30d_purchase_value) / SUM(a.last_30d_spend)
        ELSE NULL END AS avg_30d_roas
FROM meta_campaigns c
LEFT JOIN meta_adsets s ON s.campaign_id = c.id
LEFT JOIN meta_ads a ON a.adset_id = s.id
GROUP BY c.id, c.name, c.objective, c.status, c.funnel_stage;

-- 5. Funnel-level rollup view (new)
CREATE OR REPLACE VIEW v_meta_funnel_summary AS
SELECT
    COALESCE(c.funnel_stage, 'UNKNOWN') AS funnel_stage,
    COUNT(DISTINCT c.id) AS campaign_count,
    SUM(a.last_7d_spend) AS total_7d_spend,
    SUM(a.last_7d_purchases) AS total_7d_purchases,
    SUM(a.last_7d_purchase_value) AS total_7d_revenue,
    CASE WHEN SUM(a.last_7d_spend) > 0
        THEN SUM(a.last_7d_purchase_value) / SUM(a.last_7d_spend)
        ELSE NULL END AS roas_7d,
    CASE WHEN SUM(a.last_7d_purchases) > 0
        THEN SUM(a.last_7d_spend) / SUM(a.last_7d_purchases)
        ELSE NULL END AS cpa_7d
FROM meta_campaigns c
LEFT JOIN meta_adsets s ON s.campaign_id = c.id
LEFT JOIN meta_ads a ON a.adset_id = s.id
WHERE c.status = 'ACTIVE'
GROUP BY COALESCE(c.funnel_stage, 'UNKNOWN');

-- 6. Creative performance view (new)
CREATE OR REPLACE VIEW v_meta_creative_performance AS
SELECT
    a.creative_type,
    COUNT(*) AS ad_count,
    SUM(a.last_7d_spend) AS total_7d_spend,
    SUM(a.last_7d_purchases) AS total_7d_purchases,
    SUM(a.last_7d_purchase_value) AS total_7d_revenue,
    CASE WHEN SUM(a.last_7d_purchases) > 0
        THEN SUM(a.last_7d_spend) / SUM(a.last_7d_purchases)
        ELSE NULL END AS avg_cpa,
    CASE WHEN SUM(a.last_7d_spend) > 0
        THEN SUM(a.last_7d_purchase_value) / SUM(a.last_7d_spend)
        ELSE NULL END AS avg_roas,
    AVG(a.last_7d_ctr) AS avg_ctr,
    AVG(a.last_7d_frequency) AS avg_frequency
FROM meta_ads a
JOIN meta_campaigns c ON a.campaign_id = c.id
WHERE c.status = 'ACTIVE' AND a.effective_status = 'ACTIVE'
GROUP BY a.creative_type;

-- 7. Recreate weekly trend view (4-week window, add revenue + ROAS + funnel)
DROP VIEW IF EXISTS v_meta_weekly_trend;
CREATE VIEW v_meta_weekly_trend AS
SELECT
    date_trunc('week', d.report_date)::DATE AS week_start,
    c.name AS campaign_name,
    c.objective,
    c.funnel_stage,
    SUM(d.spend) AS weekly_spend,
    SUM(d.impressions) AS weekly_impressions,
    SUM(d.clicks) AS weekly_clicks,
    SUM(d.purchases) AS weekly_purchases,
    SUM(d.purchase_value) AS weekly_revenue,
    CASE WHEN SUM(d.impressions) > 0
        THEN ROUND(SUM(d.clicks)::NUMERIC / SUM(d.impressions) * 100, 2)
        ELSE 0 END AS weekly_ctr,
    CASE WHEN SUM(d.purchases) > 0
        THEN ROUND(SUM(d.spend) / SUM(d.purchases), 2)
        ELSE NULL END AS weekly_cpa,
    CASE WHEN SUM(d.spend) > 0
        THEN ROUND(SUM(d.purchase_value) / SUM(d.spend), 2)
        ELSE NULL END AS weekly_roas
FROM meta_ad_daily d
JOIN meta_ads a ON d.ad_id = a.id
JOIN meta_campaigns c ON a.campaign_id = c.id
WHERE d.report_date >= CURRENT_DATE - INTERVAL '28 days'
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, weekly_spend DESC;

-- 8. Recreate boost candidates view (add days_old + suggested_boost_budget)
DROP VIEW IF EXISTS v_meta_boost_candidates;
CREATE VIEW v_meta_boost_candidates AS
SELECT
    id AS post_id,
    message,
    created_time,
    EXTRACT(DAY FROM NOW() - created_time)::INTEGER AS days_old,
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
    CASE
        WHEN engagement_score > 5000 THEN 'PHP 15,000-25,000 (5-7 days)'
        WHEN engagement_score > 1000 THEN 'PHP 5,000-15,000 (3-5 days)'
        WHEN engagement_score > 500  THEN 'PHP 2,000-5,000 (3 days)'
        WHEN engagement_score > 200  THEN 'PHP 1,000-2,000 (2 days)'
        ELSE 'PHP 500-1,000 (test)'
    END AS suggested_boost_budget,
    is_boosted,
    image_url
FROM meta_organic_posts
WHERE NOT is_boosted
ORDER BY engagement_score DESC;

-- RLS: new views inherit from base tables (no separate policies needed for views)
