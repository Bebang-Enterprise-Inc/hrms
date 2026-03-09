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
    "Generate a branded BEI Weekly Meta Ads DOCX report. Pass ALL data as a single JSON string in the data_json parameter. Returns the file path for upload.",
    {
        "data_json": str,
    },
)
async def generate_report(args: dict[str, Any]) -> dict[str, Any]:
    """Generate the weekly DOCX report from a JSON data string."""
    data_json = args["data_json"]
    print(f"[generate_report] CALLED with {len(data_json)} chars")

    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        print(f"[generate_report] JSON parse error: {e}")
        return {"content": [{"type": "text", "text": f"Error: Invalid JSON: {e}"}], "is_error": True}

    # Build output path
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
            "content": [
                {
                    "type": "text",
                    "text": f"Report generated successfully: {result_path} ({file_size} bytes). Use this path with upload_to_drive.",
                }
            ]
        }
    except Exception as e:
        print(f"[generate_report] ERROR: {e}")
        return {"content": [{"type": "text", "text": f"Error generating report: {e}"}], "is_error": True}
