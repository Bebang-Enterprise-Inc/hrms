"""BEI Analytics Agent — autonomous weekly Meta Ads analysis.

Uses the Anthropic Python SDK directly (not the Agent SDK) to avoid
CLI authentication issues in Docker. Implements a manual agentic loop
with 4 custom tools: query_supabase, generate_report, upload_to_drive,
send_gchat.
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

import anthropic

# Import tool implementations (plain async functions, no MCP wrapping needed)
from tools.supabase_tool import query_supabase_impl
from tools.drive_tool import upload_to_drive_impl
from tools.gchat_tool import send_gchat_impl, send_failure_alert
from tools.report_tool import generate_report_impl

# Load prompt from file
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

# Tool definitions for the Anthropic API
TOOLS = [
    {
        "name": "query_supabase",
        "description": "Query a Supabase Meta Ads analytics view. Returns JSON rows.",
        "input_schema": {
            "type": "object",
            "properties": {
                "view": {
                    "type": "string",
                    "description": "View name (e.g. v_meta_campaign_summary, v_meta_flagged_ads, v_meta_boost_candidates, v_meta_weekly_trend, meta_organic_posts, v_meta_ad_inventory)",
                },
                "filters": {
                    "type": "string",
                    "description": "Optional Supabase REST filters like 'status=eq.ACTIVE'",
                },
                "select": {
                    "type": "string",
                    "description": "Optional column selection like 'campaign_name,spend,cpa'. Default: '*'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Row limit. Default: 100",
                },
            },
            "required": ["view"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Generate a branded BEI Weekly Meta Ads DOCX report. "
            "Pass ALL data as a single JSON string in the data_json parameter. "
            "Returns the file path for upload."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data_json": {
                    "type": "string",
                    "description": "JSON string with report data (week_ending, campaigns, flagged_ads, etc.)",
                },
            },
            "required": ["data_json"],
        },
    },
    {
        "name": "upload_to_drive",
        "description": "Upload a file to Google Drive shared folder. Returns the file link.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Local file path to upload",
                },
                "folder_id": {
                    "type": "string",
                    "description": "Google Drive folder ID (optional)",
                },
                "filename": {
                    "type": "string",
                    "description": "Display name for the file (optional, defaults to basename)",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "send_gchat",
        "description": "Send a message to Sam's Google Chat notification space.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message text to send",
                },
            },
            "required": ["message"],
        },
    },
]

# Tool dispatch map — maps tool names to async implementation functions
TOOL_DISPATCH = {
    "query_supabase": query_supabase_impl,
    "generate_report": generate_report_impl,
    "upload_to_drive": upload_to_drive_impl,
    "send_gchat": send_gchat_impl,
}

# Run log directory
RUNS_DIR = Path(__file__).parent / "runs"
RUNS_DIR.mkdir(exist_ok=True)

# Token tracking
_token_counts = {"input": 0, "output": 0}

# Token ceiling guard
MAX_TOKENS = 750_000
MAX_TURNS = 20


def track_tokens(response):
    """Track token usage from API response."""
    if hasattr(response, "usage"):
        _token_counts["input"] += response.usage.input_tokens
        _token_counts["output"] += response.usage.output_tokens


def check_token_ceiling():
    """Abort if token count exceeds safety ceiling."""
    total = _token_counts["input"] + _token_counts["output"]
    if total > MAX_TOKENS:
        raise RuntimeError(
            f"Token ceiling exceeded: {total:,} > {MAX_TOKENS:,}. "
            "Aborting to prevent runaway usage."
        )


def write_run_log(run_log: dict):
    """Write run log to JSON file."""
    run_log["tokens"] = _token_counts.copy()
    run_log["duration_seconds"] = (
        datetime.now() - datetime.fromisoformat(run_log["timestamp"])
    ).total_seconds()

    log_path = RUNS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    log_path.write_text(json.dumps(run_log, indent=2, default=str), encoding="utf-8")
    print(f"Run log written: {log_path}")


async def execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool by name and return the result as a string."""
    impl = TOOL_DISPATCH.get(name)
    if not impl:
        return f"Error: Unknown tool '{name}'"

    try:
        result = await impl(tool_input)
        # Result is a dict with "content" key (MCP format)
        if isinstance(result, dict):
            content = result.get("content", [])
            if content and isinstance(content, list):
                texts = [c["text"] for c in content if c.get("type") == "text"]
                return "\n".join(texts) if texts else json.dumps(result)
            return json.dumps(result)
        return str(result)
    except Exception as e:
        return f"Error executing {name}: {e}"


async def run_agent(client: anthropic.AsyncAnthropic) -> list[str]:
    """Run the agentic loop. Returns list of completed sections."""
    messages = [{"role": "user", "content": WEEKLY_PROMPT}]
    completed_sections = []
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        print(f"\n--- Turn {turn}/{MAX_TURNS} ---")

        response = await client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        track_tokens(response)
        check_token_ceiling()

        print(f"  Stop reason: {response.stop_reason}")
        print(f"  Content blocks: {len(response.content)}")
        print(f"  Tokens so far: input={_token_counts['input']:,}, output={_token_counts['output']:,}")

        # Log any text blocks
        for block in response.content:
            if block.type == "text" and block.text.strip():
                # Truncate for logging
                preview = block.text[:200] + "..." if len(block.text) > 200 else block.text
                print(f"  Text: {preview}")

        # If Claude is done (no more tool calls), break
        if response.stop_reason == "end_turn":
            print("Agent finished (end_turn).")
            break

        # Extract tool use blocks
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            print("No tool calls and not end_turn — breaking.")
            break

        # Append assistant's response
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool and collect results
        tool_results = []
        for tool_block in tool_use_blocks:
            print(f"  Calling tool: {tool_block.name} (id={tool_block.id})")

            # Track which sections are being executed
            if tool_block.name == "query_supabase":
                view = tool_block.input.get("view", "")
                print(f"    View: {view}, filters: {tool_block.input.get('filters', '')}")
                if "analysis" not in completed_sections:
                    completed_sections.append("analysis")
            elif tool_block.name == "generate_report":
                data_len = len(tool_block.input.get("data_json", ""))
                print(f"    Data length: {data_len} chars")
                completed_sections.append("report_called")
            elif tool_block.name == "upload_to_drive":
                print(f"    File: {tool_block.input.get('file_path', '')}")
                completed_sections.append("upload")
            elif tool_block.name == "send_gchat":
                msg_preview = tool_block.input.get("message", "")[:100]
                print(f"    Message: {msg_preview}...")
                completed_sections.append("notify")

            result_text = await execute_tool(tool_block.name, tool_block.input)

            # Truncate result for logging
            result_preview = result_text[:300] + "..." if len(result_text) > 300 else result_text
            print(f"    Result: {result_preview}")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": result_text,
            })

        # Append tool results as user message
        messages.append({"role": "user", "content": tool_results})

    else:
        print(f"WARNING: Hit max turns ({MAX_TURNS})")

    return completed_sections


async def main():
    run_log = {
        "timestamp": datetime.now().isoformat(),
        "model": "claude-opus-4-6",
        "sdk": "anthropic",
        "errors": [],
        "sections": [],
    }
    try:
        # 1. Refresh Supabase data
        print("Syncing Meta Ads data to Supabase...")
        subprocess_kwargs: dict = {}
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        sync_script = Path(__file__).parent.parent / "scripts" / "sync_meta_ads_to_supabase.py"
        result = subprocess.run(
            [sys.executable, str(sync_script)],
            capture_output=True, text=True, check=True,
            **subprocess_kwargs,
        )
        if "failed" in result.stdout.lower():
            run_log["errors"].append(f"Sync partial failure: {result.stdout[-500:]}")
            print("WARNING: Sync had partial failures")
        print("Sync complete.")

        # 2. Run the analyst agent via Anthropic API
        client = anthropic.AsyncAnthropic()  # Uses ANTHROPIC_API_KEY env var
        print(f"Starting analyst agent (model=claude-opus-4-6, max_turns={MAX_TURNS})")
        print(f"Prompt length: {len(WEEKLY_PROMPT)} chars")
        print(f"Tools: {[t['name'] for t in TOOLS]}")

        completed = ["sync"]
        agent_sections = await run_agent(client)
        completed.extend(agent_sections)

        # Verify DOCX was generated
        docx_files = globmod.glob(str(RUNS_DIR / "*.docx"))
        if docx_files:
            completed.append("report_verified")
            print(f"Report generated: {docx_files}")
        else:
            run_log["errors"].append("No DOCX report found in runs/ after agent completed")
            print("WARNING: No DOCX report generated")

        run_log["sections"] = completed
        print(f"\nAgent completed. Sections: {completed}")
        print(f"Tokens: {_token_counts}")

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
