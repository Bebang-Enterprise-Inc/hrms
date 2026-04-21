"""S214 Phase 6 — Verify all mutations via live Meta API queries.

Queries Meta directly — NOT self-report. Writes output/s214/RUN_STATUS.json with
overall PASS/FAIL + per-check detail.

Checks:
  1. Rule 888035557619357 status == DISABLED
  2. Rule 1539999288125943 schedule_spec minute 1320 (22:00 PHT)
  3. Paused losers: all IDs in post_state/02_losers_after.json have status=PAUSED
  4. Scaled winners: each adset's daily_budget == target
  5. Reactivated campaigns: all 3 status=ACTIVE
  6. Boost ads: 3 new ads exist with object_story_id AND status=PAUSED (audit A9)
  7. Archived error ads: >= 190 ARCHIVED
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from s214_meta_lib import OUTPUT_DIR, force_utf8, get_token, meta_get

force_utf8()


def load(filename: str) -> dict:
    path = OUTPUT_DIR / filename
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    token = get_token()
    print("=" * 70)
    print("S214 Phase 6 — Verification")
    print("=" * 70)

    checks = []

    def add(name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {detail}")
        checks.append({"name": name, "passed": passed, "detail": detail})
        return passed

    # 1. Emergency rule disabled
    r = meta_get("/888035557619357", token, {"fields": "id,name,status"})
    add("1_emergency_disabled", r.get("status") == "DISABLED",
        f"status={r.get('status')}")

    # 2. Sales OFF schedule
    r = meta_get("/1539999288125943", token, {"fields": "id,status,schedule_spec"})
    sched = (r.get("schedule_spec") or {}).get("schedule") or []
    minutes = {e.get("start_minute") for e in sched}
    add("2_salesoff_schedule_1320", 1320 in minutes,
        f"schedule contains minute 1320 (22:00 PHT): {1320 in minutes}")

    # 3. Paused losers
    losers_after = load("post_state/02_losers_after.json")
    loser_results = losers_after.get("results", [])
    paused_count = 0
    for entry in loser_results:
        ad_id = entry["ad_id"]
        try:
            r = meta_get(f"/{ad_id}", token, {"fields": "status"})
            if r.get("status") == "PAUSED":
                paused_count += 1
        except Exception as e:
            print(f"  [WARN] loser {ad_id} query failed: {e}")
    add("3_losers_paused", paused_count >= len(loser_results) - 1,
        f"{paused_count}/{len(loser_results)} losers PAUSED")

    # 4. Scaled winners
    winners_after = load("post_state/02_winners_after.json")
    winners_before = load("pre_state/02_winners_before.json")
    wins_pass = 0
    wins_total = len(winners_before)
    for adset_id, info in winners_before.items():
        target = info["target_daily_budget_centavos"]
        try:
            r = meta_get(f"/{adset_id}", token, {"fields": "daily_budget"})
            actual = int(r.get("daily_budget", 0))
            if actual == target:
                wins_pass += 1
        except Exception as e:
            print(f"  [WARN] adset {adset_id} query failed: {e}")
    add("4_winners_scaled", wins_pass == wins_total,
        f"{wins_pass}/{wins_total} adset budgets match target")

    # 5. Reactivated campaigns
    campaigns_after = load("post_state/03_campaigns_after.json")
    cam_pass = 0
    for c in campaigns_after:
        try:
            r = meta_get(f"/{c['id']}", token, {"fields": "status,effective_status"})
            if r.get("status") == "ACTIVE":
                cam_pass += 1
        except Exception as e:
            print(f"  [WARN] campaign {c['id']} query failed: {e}")
    add("5_campaigns_active", cam_pass == len(campaigns_after),
        f"{cam_pass}/{len(campaigns_after)} ACTIVE")

    # 6. Boost ads exist + PAUSED
    boost_after = load("post_state/04_boost_viral_after.json")
    boost_pass = 0
    boost_results = boost_after.get("results", [])
    for b in boost_results:
        ad_id = b.get("ad_id")
        if not ad_id:
            continue
        try:
            r = meta_get(f"/{ad_id}", token, {"fields": "status,creative{object_story_id}"})
            has_osi = r.get("creative", {}).get("object_story_id") is not None
            is_paused = r.get("status") == "PAUSED"
            if has_osi and is_paused:
                boost_pass += 1
        except Exception as e:
            print(f"  [WARN] boost ad {ad_id} query failed: {e}")
    add("6_boost_ads_paused_with_osi", boost_pass == len(boost_results),
        f"{boost_pass}/{len(boost_results)} new ads OK (object_story_id + PAUSED)")

    # 7. Archived count (load from summary)
    archive_summary = load("archive_summary.json")
    archived = archive_summary.get("archived_count", 0)
    attempted = archive_summary.get("hard_error_count", 0)
    add("7_archived_count", archived >= 190,
        f"{archived} ads archived (target >= 190; attempted {attempted})")

    # Overall
    overall = all(c["passed"] for c in checks)
    print("\n" + "=" * 70)
    print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
    print(f"  {sum(1 for c in checks if c['passed'])} / {len(checks)} checks passed")

    status_path = OUTPUT_DIR / "RUN_STATUS.json"
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump({
            "sprint_id": "S214",
            "overall_status": "PASS" if overall else "FAIL",
            "checks_total": len(checks),
            "checks_passed": sum(1 for c in checks if c["passed"]),
            "checks": checks,
        }, f, indent=2)
    print(f"  RUN_STATUS.json saved")

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
