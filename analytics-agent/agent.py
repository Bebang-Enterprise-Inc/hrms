"""BEI Analytics Agent — autonomous weekly Meta Ads analysis.

Uses the Claude Agent SDK (claude-agent-sdk) with ANTHROPIC_API_KEY
for headless Docker deployment. The SDK handles the agentic loop,
tool execution, and message routing.
"""

import asyncio
import glob as globmod
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
)

from tools.supabase_tool import query_supabase
from tools.drive_tool import upload_to_drive
from tools.gchat_tool import send_gchat, send_failure_alert
from tools.report_tool import generate_report

# Load prompt
PROMPT_PATH = Path(__file__).parent / "prompts" / "weekly_analysis.txt"
WEEKLY_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = (
    "You are a data analyst that works EXCLUSIVELY through tool calls. "
    "You have exactly 4 tools: query_supabase, generate_report, upload_to_drive, send_gchat. "
    "You MUST use these tools to complete your work. "
    "You CANNOT write files, create scripts, use Bash, or execute code. "
    "After querying data, you MUST call generate_report with the data as a JSON string. "
    "Do not attempt any alternative approach to report generation."
)

RUNS_DIR = Path(__file__).parent / "runs"
RUNS_DIR.mkdir(exist_ok=True)

MAX_TURNS = 20


def write_run_log(run_log: dict):
    """Write run log to JSON file."""
    run_log["duration_seconds"] = (
        datetime.now() - datetime.fromisoformat(run_log["timestamp"])
    ).total_seconds()
    log_path = RUNS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    log_path.write_text(json.dumps(run_log, indent=2, default=str), encoding="utf-8")
    print(f"Run log written: {log_path}")


async def main():
    run_log = {
        "timestamp": datetime.now().isoformat(),
        "model": "claude-opus-4-6",
        "sdk": "claude-agent-sdk",
        "errors": [],
        "sections": [],
    }
    try:
        # 1. Refresh Supabase data
        print("Syncing Meta Ads data to Supabase...")
        subprocess_kwargs: dict = {}
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = 0x08000000
        sync_script = Path(__file__).parent.parent / "scripts" / "sync_meta_ads_to_supabase.py"
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            capture_output=True, text=True, check=True,
            **subprocess_kwargs,
        )
        if "failed" in result.stdout.lower():
            run_log["errors"].append(f"Sync partial failure: {result.stdout[-500:]}")
        print("Sync complete.")
        run_log["sections"].append("sync")

        # 2. Create MCP server with custom tools
        server = create_sdk_mcp_server(
            "bei-analytics",
            tools=[query_supabase, generate_report, upload_to_drive, send_gchat],
        )

        # 3. Configure agent
        options = ClaudeAgentOptions(
            mcp_servers={"bei": server},
            allowed_tools=[
                "mcp__bei__query_supabase",
                "mcp__bei__generate_report",
                "mcp__bei__upload_to_drive",
                "mcp__bei__send_gchat",
            ],
            system_prompt=SYSTEM_PROMPT,
            permission_mode="bypassPermissions",
            model="claude-opus-4-6",
            max_turns=MAX_TURNS,
            cwd=str(Path(__file__).parent),
        )

        # 4. Run the agent
        print(f"Starting analyst agent (model=claude-opus-4-6, max_turns={MAX_TURNS})")
        async with ClaudeSDKClient(options=options) as client:
            await client.query(WEEKLY_PROMPT)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            preview = block.text[:200]
                            print(f"  Agent: {preview}...")
                elif isinstance(message, ResultMessage):
                    print(f"  Result: stop_reason={message.stop_reason}")
                    run_log["sections"].append("agent_complete")

        # 5. Verify DOCX was generated
        docx_files = globmod.glob(str(RUNS_DIR / "*.docx"))
        if docx_files:
            run_log["sections"].append("report_verified")
            print(f"Report generated: {docx_files}")
        else:
            run_log["errors"].append("No DOCX report found in runs/ after agent completed")
            print("WARNING: No DOCX report generated")

        print(f"\nAgent completed. Sections: {run_log['sections']}")

    except Exception as e:
        run_log["errors"].append(str(e))
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            send_failure_alert(f"BEI Analytics Agent FAILED: {e}")
        except Exception as alert_err:
            print(f"Failed to send alert: {alert_err}")
            run_log["errors"].append(f"Alert failed: {alert_err}")
        raise
    finally:
        write_run_log(run_log)


if __name__ == "__main__":
    asyncio.run(main())
