"""DOCX report generation tool for BEI Analytics Agent.

Wraps the weekly_report.py template so the agent can generate
branded DOCX reports via MCP tool call (no Bash required).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

from claude_agent_sdk import tool

# Add parent directory so we can import the template module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from templates.weekly_report import generate_weekly_report


@tool(
    "generate_report",
    "Generate a branded BEI Weekly Meta Ads DOCX report from a data dictionary",
    {
        "data_json": str,  # JSON string of the report data dict
        "output_filename": str,  # optional: filename for the DOCX (default: auto-generated)
    },
)
def generate_report(
    data_json: str,
    output_filename: str = "",
) -> dict[str, Any]:
    """Generate the weekly DOCX report and return the output path.

    Args:
        data_json: JSON string containing the report data dictionary.
            Required keys: week_ending, campaigns, flagged_ads, boost_candidates,
            weekly_trend, recommendations, ai_analysis, total_spend,
            total_purchases, avg_cpa.
        output_filename: Optional filename. Defaults to
            'BEI_Weekly_Meta_Ads_Report_YYYY-MM-DD.docx'.

    Returns:
        Dict with output_path, filename, and status.
    """
    print(f"[generate_report] CALLED with data_json length={len(data_json)}, output_filename={output_filename!r}")
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        print(f"[generate_report] JSON parse error: {e}")
        return {"error": f"Invalid JSON: {e}", "status": "failed"}

    # Validate required keys
    required = ["week_ending", "ai_analysis", "total_spend", "total_purchases", "avg_cpa"]
    missing = [k for k in required if k not in data]
    if missing:
        return {"error": f"Missing required keys: {missing}", "status": "failed"}

    # Build output path
    if not output_filename:
        we = data.get("week_ending", datetime.now().strftime("%Y-%m-%d"))
        output_filename = f"BEI_Weekly_Meta_Ads_Report_{we}.docx"

    # Use runs directory for output (writable, persisted via volume mount)
    runs_dir = os.path.join(os.path.dirname(__file__), "..", "runs")
    os.makedirs(runs_dir, exist_ok=True)
    output_path = os.path.join(runs_dir, output_filename)

    try:
        print(f"[generate_report] Generating DOCX at {output_path}")
        result_path = generate_weekly_report(data, output_path)
        file_size = os.path.getsize(result_path)
        print(f"[generate_report] SUCCESS: {result_path} ({file_size} bytes)")
        return {
            "output_path": result_path,
            "filename": output_filename,
            "file_size_bytes": file_size,
            "status": "success",
        }
    except Exception as e:
        print(f"[generate_report] ERROR: {e}")
        return {"error": str(e), "status": "failed"}
