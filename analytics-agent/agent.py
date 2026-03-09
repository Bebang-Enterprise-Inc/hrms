import asyncio
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, create_sdk_mcp_server

from tools.supabase_tool import query_supabase
from tools.drive_tool import upload_to_drive
from tools.gchat_tool import send_gchat, send_failure_alert
from tools.report_tool import generate_report

# Load prompt from file
PROMPT_PATH = Path(__file__).parent / "prompts" / "weekly_analysis.txt"
WEEKLY_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

# Run log directory
RUNS_DIR = Path(__file__).parent / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# Token tracking
_token_counts = {"input": 0, "output": 0}

def track_tokens(msg):
    """Track token usage from SDK messages."""
    if hasattr(msg, "usage"):
        _token_counts["input"] += getattr(msg.usage, "input_tokens", 0)
        _token_counts["output"] += getattr(msg.usage, "output_tokens", 0)

def write_run_log(run_log: dict):
    """Write run log to JSON file."""
    run_log["tokens"] = _token_counts.copy()
    run_log["duration_seconds"] = (
        datetime.now() - datetime.fromisoformat(run_log["timestamp"])
    ).total_seconds()

    log_path = RUNS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    log_path.write_text(json.dumps(run_log, indent=2, default=str), encoding="utf-8")
    print(f"Run log written: {log_path}")

# Token ceiling guard (safety limit for Claude Max, ~750K tokens per run)
MAX_TOKENS = 750_000

def check_token_ceiling():
    """Abort if token count exceeds safety ceiling."""
    total = _token_counts["input"] + _token_counts["output"]
    if total > MAX_TOKENS:
        raise RuntimeError(
            f"Token ceiling exceeded: {total:,} > {MAX_TOKENS:,}. "
            "Aborting to prevent runaway usage."
        )

async def main():
    run_log = {
        "timestamp": datetime.now().isoformat(),
        "model": "opus",
        "errors": [],
        "sections": [],
    }
    try:
        # 1. Refresh Supabase data
        print("Syncing Meta Ads data to Supabase...")
        subprocess_kwargs: dict = {}
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "sync_meta_ads_to_supabase.py")],
            capture_output=True, text=True, check=True,
            **subprocess_kwargs,
        )
        if "failed" in result.stdout.lower():
            run_log["errors"].append(f"Sync partial failure: {result.stdout[-500:]}")
            print(f"WARNING: Sync had partial failures")

        # 2. Run the analyst agent
        server = create_sdk_mcp_server(
            name="bei-analytics", version="1.0.0",
            tools=[query_supabase, upload_to_drive, send_gchat, generate_report]
        )

        options = ClaudeAgentOptions(
            mcp_servers={"bei": server},
            allowed_tools=[
                "mcp__bei__query_supabase",
                "mcp__bei__upload_to_drive",
                "mcp__bei__send_gchat",
                "mcp__bei__generate_report",
                "Read", "Write", "Edit", "Glob", "Grep",
            ],
            permission_mode="bypassPermissions",
            model="opus",
            max_turns=30,
        )

        # Custom MCP tools require streaming input mode (async generator)
        async def prompt_generator():
            print(f"Prompt generator: about to yield {len(WEEKLY_PROMPT)} chars")
            yield WEEKLY_PROMPT
            print("Prompt generator: finished")

        print(f"Starting analyst agent with options: model={options.model}, max_turns={options.max_turns}")
        print(f"MCP servers: {list(options.mcp_servers.keys())}")
        print(f"Allowed tools: {options.allowed_tools}")

        msg_count = 0
        async for msg in query(prompt=prompt_generator(), options=options):
            msg_count += 1
            print(f"Message {msg_count}: type={type(msg).__name__}, has_usage={hasattr(msg, 'usage')}")
            track_tokens(msg)
            check_token_ceiling()

        print(f"Agent loop completed. Total messages: {msg_count}, tokens: {_token_counts}")
        # Check runs/ for generated DOCX to verify report was actually created
        import glob as globmod
        docx_files = globmod.glob(str(RUNS_DIR / "*.docx"))
        completed = ["sync", "analysis"]
        if docx_files:
            completed.append("report")
            print(f"Report generated: {docx_files}")
        else:
            run_log["errors"].append("No DOCX report found in runs/ after agent completed")
            print("WARNING: No DOCX report generated")
        # Note: upload and notify are verified by agent tool call success
        # but we can't check from here — mark them as attempted
        completed.extend(["upload_attempted", "notify_attempted"])
        run_log["sections"] = completed
        print("Agent completed successfully.")

    except Exception as e:
        run_log["errors"].append(str(e))
        print(f"ERROR: {e}")
        # Send failure notification via Google Chat (direct API, not agent)
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
