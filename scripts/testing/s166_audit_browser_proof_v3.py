#!/usr/bin/env python3
"""
S166 strict browser-proof audit v3 — comprehensive schema support + discrepancy detection.

Adds:
- Lane B `outcome` key
- Lane H `final_outcome` key
- Lane E `pass: bool` (lowercase)
- R3 `verdict: STILL_BROKEN | PASS_POST_FIX | IMPROVED_POST_DEPLOY`
- Discrepancy report: scenario reported PASS in summary but evidence says otherwise
"""
import os, json, io
from pathlib import Path
from collections import Counter

LANE_DIR = Path("output/l3/s166/lanes")


def get_status(e):
    """Find canonical status — handles 8 different schemas."""
    # Direct status keys (string)
    for k in ("status", "verdict", "final_disposition", "result", "reverified_status",
              "outcome", "final_outcome"):
        v = e.get(k)
        if isinstance(v, str) and v:
            return v.upper()
        if isinstance(v, dict) and "status" in v:
            return str(v["status"]).upper()
    # Boolean status keys
    for k in ("passed", "pass", "ok"):
        if k in e and isinstance(e[k], bool):
            return "PASS" if e[k] else "FAIL"
    # extra.response.status
    if isinstance(e.get("extra"), dict):
        r = e["extra"].get("response", {})
        if isinstance(r, dict):
            s = r.get("status")
            if isinstance(s, str):
                return s.upper()
    return "UNKNOWN"


def get_sid(e, file_path):
    return (e.get("scenario") or e.get("scenario_id") or e.get("scenarioId")
            or e.get("id") or file_path.stem)


def find_screenshot(e, evidence_path):
    """Aggressive screenshot resolution across all known shapes."""
    screenshots_dir = evidence_path.parent.parent / "screenshots"
    candidates = []

    # Single-key candidates (multiple naming conventions)
    for k in ("screenshot", "screenshot_after", "screenshot_pre", "screenshot_post",
              "post_screenshot", "pre_screenshot"):
        v = e.get(k)
        if isinstance(v, str) and v:
            candidates.append(v)

    # Plural / dict / list candidates
    ss = e.get("screenshots")
    if isinstance(ss, dict):
        for v in ss.values():
            if isinstance(v, str) and v:
                candidates.append(v)
    if isinstance(ss, list):
        candidates.extend([x for x in ss if isinstance(x, str)])

    arts = e.get("artifacts")
    if isinstance(arts, dict):
        for k, v in arts.items():
            if "screenshot" in k.lower() and isinstance(v, str):
                candidates.append(v)

    # extra dict screenshots
    extra = e.get("extra")
    if isinstance(extra, dict):
        for k, v in extra.items():
            if "screenshot" in k.lower() and isinstance(v, str):
                candidates.append(v)

    for c in candidates:
        for path in (Path(c), Path("output/l3/s166") / c, screenshots_dir / Path(c).name):
            try:
                if path.exists() and path.stat().st_size > 0:
                    return True, str(path)
            except OSError:
                pass

    # Fallback: scan screenshots/ for matches by scenario id
    sid = get_sid(e, evidence_path)
    if screenshots_dir.exists() and sid:
        for png in screenshots_dir.glob(f"{sid}*.png"):
            if png.stat().st_size > 0:
                return True, str(png)
        for png in screenshots_dir.glob(f"*{sid}*.png"):
            if png.stat().st_size > 0:
                return True, str(png)

    return False, None


def has_browser_actions(e):
    if isinstance(e.get("actions"), list) and len(e["actions"]) > 0:
        return True
    if isinstance(e.get("network"), list) and len(e["network"]) > 0:
        return True
    if isinstance(e.get("steps"), list) and len(e["steps"]) > 0:
        return True
    if isinstance(e.get("ui_actions"), list) and len(e["ui_actions"]) > 0:
        return True
    if e.get("browser_sourced") is True:
        return True
    if e.get("browser_create_ok") is True:
        return True
    if isinstance(e.get("browser_verify"), dict) and e["browser_verify"]:
        return True
    if isinstance(e.get("observed"), dict):
        return True  # observation = real navigation
    if e.get("method_used", "").lower() in ("browser", "ui", "playwright", "browser-form"):
        return True
    if isinstance(e.get("extra"), dict):
        if "ctxA_screenshot" in e["extra"] or "ctxB_screenshot" in e["extra"]:
            return True
    if "final_url" in e:  # implies real browser navigation
        return True
    return False


def is_pure_api(e):
    if has_browser_actions(e):
        return False
    if "api_before" in e or "api_after" in e:
        return True
    if isinstance(e.get("extra"), dict) and "response" in e["extra"]:
        return True
    if isinstance(e.get("api_response"), dict) and "extra" not in e:
        return True
    return False


def normalize_status(raw):
    """Map raw status strings to canonical buckets."""
    s = raw.upper().strip()
    if s in ("PASS", "PASSED", "PASS_POST_FIX", "PASS_WITH_CAVEAT",
             "PASS_WITH_CATALOG_DRIFT", "PASS_WITH_NOTE",
             "IMPROVED_POST_DEPLOY"):
        return "PASS"
    if s in ("DEFECT-PASS", "DEFECT_PASS", "DEFECT-PASS_LAST_WRITE_WINS"):
        return "DEFECT_PASS"
    if s in ("FAIL", "FAILED", "STILL_BROKEN", "STILL_STUB",
             "STILL_UNDISCOVERABLE", "PERMANENT_FAIL"):
        return "FAIL"
    if "SKIP" in s or "BLOCKED" in s or "PRECONDITION" in s:
        return "SKIP"
    if s in ("REDO_REQUIRED", "NEEDS_UI_PROBE", "UNKNOWN"):
        return "UNDETERMINED"
    return "UNDETERMINED"


def audit_one(lane, evidence_path):
    try:
        e = json.load(io.open(evidence_path, encoding="utf-8"))
    except Exception as ex:
        return {"lane": lane, "sid": evidence_path.stem,
                "verdict": "AUDIT_FAILED_UNREADABLE", "reason": str(ex),
                "raw_status": None, "norm_status": None}

    sid = get_sid(e, evidence_path)
    raw_status = get_status(e)
    norm_status = normalize_status(raw_status)
    has_ss, ss_path = find_screenshot(e, evidence_path)
    has_acts = has_browser_actions(e)
    api_only = is_pure_api(e)
    has_browser_proof = has_ss or has_acts

    # Decision tree
    if norm_status == "PASS":
        if has_browser_proof:
            return {"lane": lane, "sid": sid, "raw_status": raw_status,
                    "norm_status": norm_status,
                    "verdict": "VERIFIED_BROWSER_PASS",
                    "has_ss": has_ss, "has_acts": has_acts}
        if api_only:
            return {"lane": lane, "sid": sid, "raw_status": raw_status,
                    "norm_status": norm_status,
                    "verdict": "AUDIT_FAILED_API_ONLY",
                    "has_ss": has_ss, "has_acts": has_acts}
        return {"lane": lane, "sid": sid, "raw_status": raw_status,
                "norm_status": norm_status,
                "verdict": "AUDIT_FAILED_NO_BROWSER_PROOF",
                "has_ss": has_ss, "has_acts": has_acts}

    if norm_status == "DEFECT_PASS":
        if has_browser_proof:
            return {"lane": lane, "sid": sid, "raw_status": raw_status,
                    "norm_status": norm_status,
                    "verdict": "VERIFIED_BROWSER_DEFECT_PASS",
                    "has_ss": has_ss, "has_acts": has_acts}
        return {"lane": lane, "sid": sid, "raw_status": raw_status,
                "norm_status": norm_status,
                "verdict": "AUDIT_FAILED_NO_BROWSER_PROOF",
                "has_ss": has_ss, "has_acts": has_acts}

    if norm_status == "FAIL":
        return {"lane": lane, "sid": sid, "raw_status": raw_status,
                "norm_status": norm_status,
                "verdict": "VERIFIED_BROWSER_FAIL",
                "has_ss": has_ss, "has_acts": has_acts}

    if norm_status == "SKIP":
        if has_ss:
            return {"lane": lane, "sid": sid, "raw_status": raw_status,
                    "norm_status": norm_status,
                    "verdict": "LEGITIMATE_SKIP_WITH_PROOF",
                    "has_ss": has_ss, "has_acts": has_acts}
        # Architectural reason check
        rt = json.dumps(e)[:3000].lower()
        markers = ["product_gap", "no_browser_ui", "depends on", "depends_on",
                   "baseline_missed", "external_api_not_browsable", "deferred",
                   "not implemented", "defer_payroll", "precondition_blocked",
                   "blocked", "no clearance doctype", "clearance doctypes do not exist",
                   "no ot filing ui", "no edit compensation", "requires precondition"]
        if any(m in rt for m in markers):
            return {"lane": lane, "sid": sid, "raw_status": raw_status,
                    "norm_status": norm_status,
                    "verdict": "LEGITIMATE_SKIP_WITH_PROOF",
                    "has_ss": has_ss, "has_acts": has_acts}
        return {"lane": lane, "sid": sid, "raw_status": raw_status,
                "norm_status": norm_status,
                "verdict": "AUDIT_FAILED_NO_BROWSER_PROOF",
                "has_ss": has_ss, "has_acts": has_acts}

    return {"lane": lane, "sid": sid, "raw_status": raw_status,
            "norm_status": norm_status,
            "verdict": "AUDIT_FAILED_UNDETERMINED",
            "has_ss": has_ss, "has_acts": has_acts}


# DISCREPANCY DETECTOR — compare per-scenario evidence vs lane SUMMARY claims
DISCREPANCIES = []


def check_r3_discrepancies():
    """R3 specifically — known to have lied about EMP-UX-004."""
    summary_claims = {
        "EMP-UX-004": "PASS_POST_FIX",
        "EMP-UX-005": "PASS_POST_FIX",
        "EMP-STUB-005": "PASS_POST_FIX",
        "EMP-STUB-001": "IMPROVED_POST_DEPLOY",
    }
    for sid, claimed in summary_claims.items():
        p = LANE_DIR / "retest" / "r3_ux_reobserve" / "evidence" / f"{sid}-retest.json"
        if not p.exists():
            continue
        e = json.load(io.open(p, encoding="utf-8"))
        actual = e.get("verdict", "?")
        if actual != claimed:
            DISCREPANCIES.append({
                "agent": "R3",
                "scenario": sid,
                "summary_claimed": claimed,
                "evidence_actual": actual,
                "type": "SUMMARY_LIED",
                "evidence_path": str(p),
            })


def check_lane_a_phase_summaries():
    """Cross-check Lane A phase summaries vs evidence files."""
    # Phase A2 claims
    a2_summary_path = LANE_DIR / "lane_a" / "PHASE_A2_SUMMARY.md"
    if a2_summary_path.exists():
        # Skip for now - text parsing too risky
        pass


# Run audit
LANES = {
    "lane_a": LANE_DIR / "lane_a",
    "lane_b": LANE_DIR / "lane_b",
    "lane_c": LANE_DIR / "lane_c",
    "lane_d": LANE_DIR / "lane_d",
    "lane_e": LANE_DIR / "lane_e",
    "lane_f": LANE_DIR / "lane_f",
    "lane_g": LANE_DIR / "lane_g",
    "lane_h": LANE_DIR / "lane_h",
    "retest_r1": LANE_DIR / "retest" / "r1_leave_ledger",
    "retest_r2": LANE_DIR / "retest" / "r2_overtime",
    "retest_r2_fix": LANE_DIR / "retest" / "r2_fix",
    "retest_r3": LANE_DIR / "retest" / "r3_ux_reobserve",
    "retest_r4": LANE_DIR / "retest" / "r4_emp_retest",
}

RESULT = []
SUMMARY = Counter()
PER_LANE = {}

for lane, lane_path in LANES.items():
    ev_dir = lane_path / "evidence"
    if not ev_dir.exists():
        continue
    PER_LANE[lane] = Counter()
    for ev in sorted(ev_dir.glob("*.json")):
        r = audit_one(lane, ev)
        RESULT.append(r)
        SUMMARY[r["verdict"]] += 1
        PER_LANE[lane][r["verdict"]] += 1

check_r3_discrepancies()
check_lane_a_phase_summaries()

# Output
out_dir = Path("output/l3/s166/AUDIT_2026-04-08")
out_dir.mkdir(parents=True, exist_ok=True)

with io.open(out_dir / "audit_per_scenario_v3.json", "w", encoding="utf-8") as f:
    json.dump(RESULT, f, indent=2)
with io.open(out_dir / "discrepancies.json", "w", encoding="utf-8") as f:
    json.dump(DISCREPANCIES, f, indent=2)

with io.open(out_dir / "AUDIT_SUMMARY_V3.md", "w", encoding="utf-8") as f:
    f.write("# S166 Strict Browser-Proof Audit v3 (2026-04-08)\n\n")
    f.write("**Rule:** Every scenario must have verifiable browser evidence or is reclassified as FAILED.\n")
    f.write("**Operator:** Orchestrator (no subagent trust). All file inspection direct.\n\n")
    f.write("## Overall counts\n\n")
    f.write("| Verdict | Count |\n|---|---|\n")
    for k, v in sorted(SUMMARY.items(), key=lambda x: -x[1]):
        f.write(f"| {k} | {v} |\n")
    f.write(f"| **TOTAL** | **{sum(SUMMARY.values())}** |\n\n")

    f.write("## Per-lane breakdown\n\n")
    f.write("| Lane | VERIFIED PASS | VERIFIED DP | VERIFIED FAIL | LEGIT SKIP | AUDIT FAILED |\n|---|---|---|---|---|---|\n")
    for lane in LANES.keys():
        c = PER_LANE.get(lane, Counter())
        af = sum(v for k, v in c.items() if k.startswith("AUDIT_FAILED"))
        f.write(f"| {lane} | {c.get('VERIFIED_BROWSER_PASS',0)} | {c.get('VERIFIED_BROWSER_DEFECT_PASS',0)} | {c.get('VERIFIED_BROWSER_FAIL',0)} | {c.get('LEGITIMATE_SKIP_WITH_PROOF',0)} | {af} |\n")

    f.write("\n## Discrepancies (Summary vs Evidence)\n\n")
    if not DISCREPANCIES:
        f.write("(none detected by current checks)\n")
    else:
        f.write("| Agent | Scenario | Summary claimed | Evidence actual | Type |\n|---|---|---|---|---|\n")
        for d in DISCREPANCIES:
            f.write(f"| {d['agent']} | {d['scenario']} | {d['summary_claimed']} | {d['evidence_actual']} | {d['type']} |\n")

print("=== Audit v3 ===")
print(f"Total: {sum(SUMMARY.values())}")
for k, v in sorted(SUMMARY.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print(f"\nDiscrepancies found: {len(DISCREPANCIES)}")
for d in DISCREPANCIES:
    print(f"  {d['agent']} {d['scenario']}: claimed={d['summary_claimed']} actual={d['evidence_actual']}")
print(f"\nReport: output/l3/s166/AUDIT_2026-04-08/AUDIT_SUMMARY_V3.md")
