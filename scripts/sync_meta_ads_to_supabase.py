"""
Sync Meta Ads data to Supabase for on-demand analytics.
Fetches campaigns, ad sets, ads, insights (7d + 30d), and organic posts.

Usage:
    python scripts/sync_meta_ads_to_supabase.py              # Full sync
    python scripts/sync_meta_ads_to_supabase.py --ads-only   # Just ad inventory
    python scripts/sync_meta_ads_to_supabase.py --insights   # Just performance data
    python scripts/sync_meta_ads_to_supabase.py --organic    # Just organic posts

Designed to run weekly (Sunday night) via cron or manually before review.
"""

import json
import subprocess
import urllib.request
import urllib.parse
import ssl
import sys
import io
import time
import argparse
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

AD_ACCOUNT = 'act_843498792928069'
PAGE_ID = '102628625216977'
API_VERSION = 'v25.0'
BASE_URL = f'https://graph.facebook.com/{API_VERSION}'
ctx = ssl.create_default_context()

# Supabase config
SUPABASE_PROJECT = 'bei-erp'


def get_secret(name):
    """Fetch secret from Doppler."""
    result = subprocess.run(
        ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', name,
         '--project', 'bei-erp', '--config', 'dev', '--plain'],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def meta_api_get(endpoint, params, token):
    """GET request to Meta Graph API with pagination."""
    params['access_token'] = token
    url = f'{BASE_URL}/{endpoint}?' + urllib.parse.urlencode(params)
    all_data = []

    while url:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            print(f"  API Error: {e}")
            if 'too many' in str(e).lower() or '17' in str(e):
                print("  Rate limited. Waiting 60s...")
                time.sleep(60)
                continue
            break

        if 'error' in data:
            print(f"  API Error: {data['error'].get('message', 'Unknown')}")
            break

        all_data.extend(data.get('data', []))
        url = data.get('paging', {}).get('next')
        time.sleep(0.5)  # Rate limit courtesy

    return all_data


def supabase_upsert(table, rows, token, url, on_conflict=None):
    """Upsert rows to Supabase via REST API."""
    if not rows:
        return 0

    # Batch in chunks of 50
    total = 0
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        req_url = f'{url}/rest/v1/{table}'
        if on_conflict:
            req_url += f'?on_conflict={on_conflict}'
        data = json.dumps(batch, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            req_url, data=data, method='POST',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'apikey': token,
                'Prefer': 'resolution=merge-duplicates'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            total += len(batch)
        except Exception as e:
            print(f"  Supabase error on {table}: {e}")
            if hasattr(e, 'read'):
                try:
                    print(f"  Body: {e.read().decode()[:200]}")
                except:
                    pass

    return total


def build_targeting_summary(targeting):
    """Generate human-readable targeting description."""
    if not targeting:
        return '', '', '', '', 0, 0

    geo = targeting.get('geo_locations', {})
    places = geo.get('places', [])
    custom = geo.get('custom_locations', [])
    regions = geo.get('regions', [])
    countries = geo.get('countries', [])

    # Geo summary
    geo_parts = []
    for p in places:
        name = p.get('name', '?')
        radius = p.get('radius', '?')
        unit = p.get('distance_unit', 'mi')
        geo_parts.append(f"{name} ({radius}{unit})")
    for c in custom:
        lat = c.get('latitude', 0)
        lng = c.get('longitude', 0)
        radius = c.get('radius', '?')
        unit = c.get('distance_unit', 'km')
        geo_parts.append(f"Pin {lat:.2f},{lng:.2f} ({radius}{unit})")
    for r in regions:
        geo_parts.append(f"Region: {r.get('name', r.get('key', '?'))}")
    for c in countries:
        geo_parts.append(f"Country: {c}")
    geo_str = '; '.join(geo_parts) if geo_parts else 'Broad'

    # Audiences
    custom_auds = targeting.get('custom_audiences', [])
    excluded = targeting.get('excluded_custom_audiences', [])
    aud_names = [a.get('name', a.get('id', '?')) for a in custom_auds]
    aud_str = ', '.join(aud_names) if aud_names else ''

    # Interests
    flex = targeting.get('flexible_spec', [])
    interests = []
    for spec in flex:
        for i in spec.get('interests', []):
            interests.append(i.get('name', '?'))
    int_str = ', '.join(interests) if interests else ''

    # Age
    age_min = targeting.get('age_min', 18)
    age_max = targeting.get('age_max', 65)

    # Full summary
    parts = []
    if geo_str != 'Broad':
        parts.append(f"Geo: {geo_str}")
    if aud_str:
        parts.append(f"Audiences: {aud_str}")
    if int_str:
        parts.append(f"Interests: {int_str}")
    parts.append(f"Age: {age_min}-{age_max}")
    if excluded:
        excl_names = [e.get('name', '?') for e in excluded]
        parts.append(f"Excl: {', '.join(excl_names)}")

    summary = ' | '.join(parts)

    # Placements
    platforms = targeting.get('publisher_platforms', [])
    placements = ','.join(platforms) if platforms else ''

    return summary, geo_str, aud_str, int_str, age_min, age_max


def build_creative_description(ad_name, creative_body, creative_type, call_to_action, link_url):
    """Generate a quick-eval description from available creative data."""
    parts = []

    # Type
    if creative_type:
        parts.append(f"[{creative_type}]")

    # Body snippet (first 80 chars)
    if creative_body:
        snippet = creative_body[:80].replace('\n', ' ').strip()
        if len(creative_body) > 80:
            snippet += '...'
        parts.append(snippet)

    # CTA
    if call_to_action:
        parts.append(f"CTA: {call_to_action}")

    # Link domain
    if link_url:
        try:
            from urllib.parse import urlparse
            domain = urlparse(link_url).netloc
            parts.append(f"→ {domain}")
        except:
            parts.append(f"→ {link_url[:40]}")

    return ' | '.join(parts) if parts else ad_name


def sync_campaigns(token, supa_token, supa_url):
    """Sync campaigns to Supabase."""
    print("Syncing campaigns...")
    campaigns = meta_api_get(f'{AD_ACCOUNT}/campaigns', {
        'fields': 'id,name,objective,status,effective_status,daily_budget,lifetime_budget,created_time',
        'limit': '100'
    }, token)

    rows = []
    for c in campaigns:
        rows.append({
            'id': c['id'],
            'name': c.get('name', ''),
            'objective': c.get('objective'),
            'status': c.get('status'),
            'effective_status': c.get('effective_status'),
            'daily_budget': int(c['daily_budget']) if c.get('daily_budget') else None,
            'lifetime_budget': int(c['lifetime_budget']) if c.get('lifetime_budget') else None,
            'created_time': c.get('created_time'),
            'synced_at': datetime.now(timezone.utc).isoformat()
        })

    count = supabase_upsert('meta_campaigns', rows, supa_token, supa_url)
    print(f"  {count} campaigns synced")
    return count


def sync_adsets(token, supa_token, supa_url):
    """Sync ad sets to Supabase with targeting details."""
    print("Syncing ad sets...")
    adsets = meta_api_get(f'{AD_ACCOUNT}/adsets', {
        'fields': 'id,name,campaign_id,status,effective_status,daily_budget,optimization_goal,billing_event,targeting,created_time',
        'limit': '200'
    }, token)

    rows = []
    for s in adsets:
        targeting = s.get('targeting', {})
        summary, geo, auds, ints, age_min, age_max = build_targeting_summary(targeting)
        platforms = targeting.get('publisher_platforms', [])

        rows.append({
            'id': s['id'],
            'campaign_id': s.get('campaign_id'),
            'name': s.get('name', ''),
            'status': s.get('status'),
            'effective_status': s.get('effective_status'),
            'daily_budget': int(s['daily_budget']) if s.get('daily_budget') else None,
            'optimization_goal': s.get('optimization_goal'),
            'billing_event': s.get('billing_event'),
            'targeting_summary': summary[:500],
            'targeting_geo': geo[:500],
            'targeting_audiences': auds[:500],
            'targeting_interests': ints[:500],
            'targeting_age_min': age_min,
            'targeting_age_max': age_max,
            'targeting_json': targeting,
            'placements': ','.join(platforms),
            'created_time': s.get('created_time'),
            'synced_at': datetime.now(timezone.utc).isoformat()
        })

    count = supabase_upsert('meta_adsets', rows, supa_token, supa_url)
    print(f"  {count} ad sets synced")
    return count


def sync_ads(token, supa_token, supa_url):
    """Sync ads with creative details to Supabase."""
    print("Syncing ads...")
    ads = meta_api_get(f'{AD_ACCOUNT}/ads', {
        'fields': 'id,name,campaign_id,adset_id,status,effective_status,creative{id,body,title,thumbnail_url,image_url,video_id,call_to_action_type,link_url,object_story_id,object_type}',
        'limit': '200'
    }, token)

    rows = []
    for ad in ads:
        creative = ad.get('creative', {})
        obj_type = creative.get('object_type', '')

        # Determine creative type
        if 'video' in ad.get('name', '').lower() or creative.get('video_id'):
            ctype = 'VIDEO'
        elif 'carousel' in ad.get('name', '').lower():
            ctype = 'CAROUSEL'
        elif '[Post]' in ad.get('name', '') or '[post]' in ad.get('name', ''):
            ctype = 'POST'
        elif '[IMG]' in ad.get('name', ''):
            ctype = 'IMAGE'
        else:
            ctype = obj_type or 'UNKNOWN'

        body = creative.get('body', '') or ''
        title = creative.get('title', '') or ''
        cta = creative.get('call_to_action_type', '') or ''
        link = creative.get('link_url', '') or ''

        desc = build_creative_description(
            ad.get('name', ''), body, ctype, cta, link
        )

        rows.append({
            'id': ad['id'],
            'campaign_id': ad.get('campaign_id'),
            'adset_id': ad.get('adset_id'),
            'name': ad.get('name', ''),
            'status': ad.get('status'),
            'effective_status': ad.get('effective_status'),
            'creative_id': creative.get('id'),
            'creative_body': body[:2000],
            'creative_title': title[:500],
            'creative_description': desc[:500],
            'creative_type': ctype,
            'creative_image_url': creative.get('thumbnail_url') or creative.get('image_url'),
            'creative_video_url': creative.get('video_id'),
            'call_to_action': cta,
            'link_url': link,
            'object_story_id': creative.get('object_story_id'),
            'synced_at': datetime.now(timezone.utc).isoformat()
        })

    count = supabase_upsert('meta_ads', rows, supa_token, supa_url)
    print(f"  {count} ads synced")
    return count


def sync_insights(token, supa_token, supa_url, date_preset='last_7d'):
    """Sync ad-level insights to Supabase."""
    print(f"Syncing insights ({date_preset})...")

    insights = meta_api_get(f'{AD_ACCOUNT}/insights', {
        'level': 'ad',
        'date_preset': date_preset,
        'fields': 'ad_id,ad_name,spend,impressions,clicks,ctr,cpc,cpm,frequency,reach,actions,cost_per_action_type',
        'limit': '500',
        'time_increment': '1'  # daily breakdown
    }, token)

    # Build daily rows
    daily_rows = []
    # Also accumulate period totals per ad for updating meta_ads
    ad_totals = {}

    for row in insights:
        ad_id = row.get('ad_id')
        report_date = row.get('date_start')

        # Extract actions
        purchases = 0
        cpa = 0
        link_clicks = 0
        post_engagement = 0
        video_views = 0
        for a in row.get('actions', []):
            atype = a.get('action_type')
            val = int(a.get('value', 0))
            if atype == 'purchase':
                purchases = val
            elif atype == 'link_click':
                link_clicks = val
            elif atype == 'post_engagement':
                post_engagement = val
            elif atype in ('video_view', 'video_play'):
                video_views = val
        for c in row.get('cost_per_action_type', []):
            if c.get('action_type') == 'purchase':
                cpa = float(c.get('value', 0))

        daily_rows.append({
            'ad_id': ad_id,
            'report_date': report_date,
            'spend': float(row.get('spend', 0)),
            'impressions': int(row.get('impressions', 0)),
            'clicks': int(row.get('clicks', 0)),
            'ctr': float(row.get('ctr', 0)),
            'cpc': float(row.get('cpc', 0)) if row.get('cpc') else 0,
            'cpm': float(row.get('cpm', 0)) if row.get('cpm') else 0,
            'frequency': float(row.get('frequency', 0)),
            'reach': int(row.get('reach', 0)) if row.get('reach') else 0,
            'purchases': purchases,
            'cpa_purchase': cpa,
            'link_clicks': link_clicks,
            'post_engagement': post_engagement,
            'video_views': video_views,
            'synced_at': datetime.now(timezone.utc).isoformat()
        })

        # Accumulate totals
        if ad_id not in ad_totals:
            ad_totals[ad_id] = {
                'spend': 0, 'impressions': 0, 'clicks': 0,
                'purchases': 0, 'frequency': 0, 'freq_count': 0
            }
        t = ad_totals[ad_id]
        t['spend'] += float(row.get('spend', 0))
        t['impressions'] += int(row.get('impressions', 0))
        t['clicks'] += int(row.get('clicks', 0))
        t['purchases'] += purchases
        t['frequency'] = max(t['frequency'], float(row.get('frequency', 0)))

    # Upsert daily data
    count = supabase_upsert('meta_ad_daily', daily_rows, supa_token, supa_url, on_conflict='ad_id,report_date')
    print(f"  {count} daily rows synced")

    # Update cached metrics on meta_ads
    prefix = 'last_7d' if date_preset == 'last_7d' else 'last_30d'
    ad_updates = []
    for ad_id, t in ad_totals.items():
        ctr = (t['clicks'] / t['impressions'] * 100) if t['impressions'] > 0 else 0
        cpa = (t['spend'] / t['purchases']) if t['purchases'] > 0 else 0

        # Flag logic
        is_flagged = False
        flag_reasons = []
        if t['frequency'] > 2.5:
            is_flagged = True
            flag_reasons.append('HIGH_FREQUENCY')
        if cpa > 200 and t['purchases'] > 0:
            is_flagged = True
            flag_reasons.append('HIGH_CPA')
        if ctr < 0.5 and t['spend'] > 500:
            is_flagged = True
            flag_reasons.append('LOW_CTR')
        if t['spend'] > 500 and t['purchases'] == 0:
            is_flagged = True
            flag_reasons.append('ZERO_PURCHASES')

        update = {
            'id': ad_id,
            f'{prefix}_spend': round(t['spend'], 2),
            f'{prefix}_impressions': t['impressions'],
            f'{prefix}_clicks': t['clicks'],
            f'{prefix}_purchases': t['purchases'],
            f'{prefix}_ctr': round(ctr, 3),
            f'{prefix}_cpa': round(cpa, 2),
            f'{prefix}_frequency': round(t['frequency'], 3),
            'synced_at': datetime.now(timezone.utc).isoformat()
        }

        # Only set flags on 30d data (more stable)
        if prefix == 'last_30d':
            update['is_flagged'] = is_flagged
            update['flag_reason'] = ', '.join(flag_reasons) if flag_reasons else None

        ad_updates.append(update)

    # Use PATCH per-ad to update only metrics (avoids NOT NULL violations for missing ads)
    ad_count = 0
    failed = 0
    for update in ad_updates:
        ad_id = update.pop('id')
        req_url = f'{supa_url}/rest/v1/meta_ads?id=eq.{ad_id}'
        data = json.dumps(update, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            req_url, data=data, method='PATCH',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {supa_token}',
                'apikey': supa_token,
                'Prefer': 'return=minimal'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            ad_count += 1
        except:
            failed += 1  # Ad not in meta_ads (deleted/archived) — skip silently
    print(f"  {ad_count} ad metric caches updated, {failed} skipped ({prefix})")

    return count


def sync_organic(token, supa_token, supa_url):
    """Sync organic page posts to Supabase."""
    print("Syncing organic posts...")
    page_token = get_secret('META_PAGE_TOKEN')

    from datetime import timedelta
    since = int((datetime.now() - timedelta(days=90)).timestamp())

    # Use limit=25 — Meta returns 500 ("reduce data") with limit=100 + engagement summaries
    posts = meta_api_get(f'{PAGE_ID}/posts', {
        'fields': 'id,message,created_time,shares,likes.summary(true),comments.summary(true)',
        'since': str(since),
        'limit': '25'
    }, page_token)

    rows = []
    for p in posts:
        likes = p.get('likes', {}).get('summary', {}).get('total_count', 0)
        comments = p.get('comments', {}).get('summary', {}).get('total_count', 0)
        shares = p.get('shares', {}).get('count', 0) if p.get('shares') else 0
        score = likes * 1 + comments * 3 + shares * 5

        rows.append({
            'id': p['id'],
            'message': (p.get('message') or '')[:2000],
            'created_time': p.get('created_time'),
            'likes': likes,
            'comments': comments,
            'shares': shares,
            'engagement_score': score,
            'synced_at': datetime.now(timezone.utc).isoformat()
        })

    count = supabase_upsert('meta_organic_posts', rows, supa_token, supa_url)
    print(f"  {count} organic posts synced")
    return count


def update_sync_state(sync_type, count, status, supa_token, supa_url, error=None, duration=0):
    """Record sync state."""
    supabase_upsert('meta_sync_state', [{
        'sync_type': sync_type,
        'last_sync': datetime.now(timezone.utc).isoformat(),
        'records_synced': count,
        'status': status,
        'error_message': error,
        'duration_seconds': round(duration, 2)
    }], supa_token, supa_url)


def main():
    parser = argparse.ArgumentParser(description='Sync Meta Ads to Supabase')
    parser.add_argument('--ads-only', action='store_true', help='Only sync ad inventory')
    parser.add_argument('--insights', action='store_true', help='Only sync performance data')
    parser.add_argument('--organic', action='store_true', help='Only sync organic posts')
    args = parser.parse_args()

    # Get tokens
    meta_token = get_secret('META_ACCESS_TOKEN')
    supa_url = get_secret('SUPABASE_URL')
    supa_token = get_secret('SUPABASE_SERVICE_ROLE_KEY')

    if not meta_token or not supa_url or not supa_token:
        print("ERROR: Missing required secrets. Check Doppler (bei-erp/dev):")
        print("  META_ACCESS_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    do_all = not (args.ads_only or args.insights or args.organic)

    print(f"=== Meta Ads → Supabase Sync ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===\n")

    total_start = time.time()

    if do_all or args.ads_only:
        # Sync inventory
        t = time.time()
        c1 = sync_campaigns(meta_token, supa_token, supa_url)
        update_sync_state('campaigns', c1, 'success', supa_token, supa_url, duration=time.time()-t)

        t = time.time()
        c2 = sync_adsets(meta_token, supa_token, supa_url)
        update_sync_state('adsets', c2, 'success', supa_token, supa_url, duration=time.time()-t)

        t = time.time()
        c3 = sync_ads(meta_token, supa_token, supa_url)
        update_sync_state('ads', c3, 'success', supa_token, supa_url, duration=time.time()-t)

    if do_all or args.insights:
        # Sync performance data
        t = time.time()
        c4 = sync_insights(meta_token, supa_token, supa_url, 'last_7d')
        update_sync_state('insights_7d', c4, 'success', supa_token, supa_url, duration=time.time()-t)

        time.sleep(2)  # Rate limit buffer

        t = time.time()
        c5 = sync_insights(meta_token, supa_token, supa_url, 'last_30d')
        update_sync_state('insights_30d', c5, 'success', supa_token, supa_url, duration=time.time()-t)

    if do_all or args.organic:
        t = time.time()
        c6 = sync_organic(meta_token, supa_token, supa_url)
        update_sync_state('organic', c6, 'success', supa_token, supa_url, duration=time.time()-t)

    duration = time.time() - total_start
    print(f"\n=== Sync complete in {duration:.1f}s ===")


if __name__ == '__main__':
    main()
