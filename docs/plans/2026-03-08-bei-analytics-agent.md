# BEI Analytics Agent — Weekly Meta Ads Intelligence

**Date:** 2026-03-08
**Owner:** Sam Karazi
**Status:** DEPLOYED v3 (EC2 live, first run successful 2026-03-09)
**Audit:** 2026-03-08 v2 (GO) → v3 patch: EC2 + Max setup-token, re-audit pending

## Objective

Build an autonomous AI agent using the Claude Agent SDK (Python) that runs every Sunday evening, analyzes the week's Meta Ads + organic post performance from Supabase, generates a branded DOCX report using a reusable template, uploads it to Google Drive, and sends a summary + link to Google Chat.

This replaces the manual "run `/meta-ads weekly` → review data → make decisions" loop with a proactive analyst that does the thinking and presents findings ready for Monday decision-making.

### What This Is NOT

- Not a replacement for Blip Sentinel (Blip stays for real-time threshold alerts — it's free and instant)
- Not a chatbot or interactive agent (it's a scheduled batch job)
- Not a full marketing automation platform (it analyzes and recommends, doesn't auto-execute)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  BEI Analytics Agent (Claude Agent SDK, Python)         │
│                                                         │
│  Trigger: Supercronic cron on EC2 (Sun 7pm PHT/11am UTC)│
│  Model: Sonnet (weekly), via Claude Max setup-token      │
│                                                         │
│  Custom MCP Tools (@tool decorator, in-process):        │
│  ├── query_supabase(view, filters)  ← REST API          │
│  ├── upload_to_drive(path, folder)  ← Service Account   │
│  └── send_gchat(message)            ← Bot scope          │
│                                                         │
│  Built-in Tools (from SDK):                             │
│  ├── Read, Write        ← DOCX generation                │
│  ├── Glob, Grep         ← Find template, verify output  │
│  └── Skill              ← /docx-designer-bei-erp        │
│                                                         │
│  Outputs:                                               │
│  ├── DOCX report → Google Drive shared folder           │
│  ├── Google Chat summary with Drive link                │
│  └── JSON log → tmp/analytics-agent/runs/               │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Supabase Views ──→ Agent queries 6 views ──→ Claude reasons about data
                                                      │
                                    ┌─────────────────┼──────────────────┐
                                    ▼                 ▼                  ▼
                            DOCX Report      GChat Summary        Run Log
                            (branded,        (3-5 key            (cost, tokens,
                             detailed)       findings +           duration)
                                │            Drive link)
                                ▼
                          Google Drive
                          (shared folder)
```

## Scope

### In-Scope

- Agent scaffold with Claude Agent SDK (`ClaudeSDKClient` + custom `@tool` functions)
- Three custom tools: `query_supabase`, `upload_to_drive`, `send_gchat`
- DOCX report template script (reusable, agent patches if needed)
- Data sync refresh before analysis (calls existing `sync_meta_ads_to_supabase.py`)
- Google Drive upload via service account (domain-wide delegation)
- Google Chat notification via bot scope (reuse Blip Sentinel's pattern)
- EC2 deployment alongside Blip Sentinel (Docker container + Supercronic cron)
- Claude Max authentication via `claude setup-token` (long-lived token, $0/run)
- Cost tracking per run (tokens, duration, model)
- Run logging to `analytics-agent/runs/YYYY-MM-DD.json`

### Out-of-Scope

- Auto-executing changes to Meta Ads account (pause/activate/budget) — recommendations only
- Interactive chat mode or Slack/Teams integration
- Real-time monitoring (that's Blip Sentinel's job)
- Sales data correlation (Phase 2 — requires sales views to be stable first)

## Non-Negotiable Rules

- **NEVER auto-execute** Meta Ads changes — present recommendations with reasoning, Sam decides
- **Brand rule carries over** — agent must never suggest discounts, promos, BOGO in report text
- **Cost ceiling** — agent must abort if estimated cost exceeds $15/run (log the abort reason). Note: With Claude Max subscription, token cost is $0 but the ceiling still applies as a runaway-loop guard (measured by token count, not dollars).
- **Template-first** — agent uses the pre-built DOCX template script; only patches it if the script fails or data shape changes. Do NOT regenerate the full script each week.
- **Secrets via Docker .env on EC2** — SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, META_ACCESS_TOKEN. Claude auth via `setup-token` (Max subscription, $0/run). Do NOT set ANTHROPIC_API_KEY — the setup-token provides Max auth.
- **Run log is mandatory** — every run produces a JSON log with: timestamp, duration, tokens, cost, model, sections generated, errors
- **No Bash tool** — agent must NOT have Bash in allowed_tools. All file operations via Read/Write/Edit. This prevents unrestricted shell access on unattended runs.
- **Failure notification** — if the agent crashes or sync fails, send a Google Chat alert before exiting. Silent failures are unacceptable for a weekly batch job.

## Existing Assets to Reuse

| Asset | Location | Classification |
|-------|----------|---------------|
| Supabase schema + views (7 tables, 5 views) | `supabase/migrations/20260308_meta_ads_analytics.sql` | REFERENCE |
| Meta Ads sync script | `scripts/sync_meta_ads_to_supabase.py` | REFERENCE — call before analysis |
| DOCX generator pattern | `tmp/ad_audit_2026-03-08/create_interactive_plan_docx.py` | EXTEND — extract into reusable template |
| BEI brand palette | `.claude/skills/docx-designer-bei-erp/references/bei-brand-docx.md` | REFERENCE |
| DOCX helper functions | Global `docx-designer/references/helpers.md` + `components.md` | REFERENCE |
| Google Chat notifier | `blip-sentinel/notifier.py` (send_blip_message pattern) | REFERENCE — extract Chat API call |
| Google service account | `credentials/task-manager-service.json` | REFERENCE |
| Engagement scoring formula | `likes*1 + comments*3 + shares*5` | REFERENCE |
| Performance thresholds | CPA >200, CTR <0.5%, freq >2.5 | REFERENCE |

## Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Claude Agent SDK (Python) | INSTALLED | `claude-agent-sdk` v0.1.48. Note: `claude-code-sdk` is deprecated — `claude-agent-sdk` is the correct successor. |
| Claude CLI | INSTALLED locally | v2.1.71 — authenticated with Claude Max subscription. Must also install on EC2. |
| Claude Max subscription | ACTIVE | Agent uses `claude setup-token` for long-lived headless auth ($0/run). Do NOT set ANTHROPIC_API_KEY. |
| `claude setup-token` | NOT YET GENERATED | Run locally to generate long-lived token, deploy to EC2. Required for headless Max auth. |
| EC2 instance | RUNNING | `i-026b7477d27bd46d6` — Blip Sentinel's instance, available for co-hosting |
| Supabase Meta Ads data | READY | All 6 sync types successful (2026-03-08) |
| Google service account | READY | DWD with Drive + Chat scopes. Must copy `credentials/task-manager-service.json` to EC2 container. |
| python-docx | INSTALLED locally | Must include in Docker image (`pip install python-docx`) |
| Doppler secrets | READY locally | EC2 uses Docker `.env` file instead of Doppler CLI. Secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, META_ACCESS_TOKEN |

## Implementation Tasks

| # | Task | Depends | Classification | Verification |
|---|------|---------|---------------|--------------|
| 1 | Install Claude Agent SDK | — | BUILD | `pip show claude-agent-sdk` returns v0.1.48+ |
| 2 | Create project scaffold at `analytics-agent/` | 1 | BUILD | Directory exists with `__init__.py`, `agent.py`, `tools/`, `templates/` |
| 3 | Build `query_supabase` tool (with view allowlist) | 1 | BUILD | Tool queries `v_meta_campaign_summary`, rejects non-allowlisted views |
| 4 | Build `upload_to_drive` tool | — | BUILD | Upload a test file, get shareable link back |
| 5 | Build `send_gchat` tool | — | BUILD | Send test message to Blip notification space |
| 6 | Build DOCX report template (substantial refactor from 40KB source) | — | EXTEND | Template script generates DOCX with placeholder data. Note: source is 40KB one-off script — budget 2-4 hours for extraction. |
| 7 | Write agent prompt (system + weekly analysis) | 3 | BUILD | Prompt references all 6 Supabase views and brand rules |
| 7.5 | Build `send_failure_alert` helper (direct Chat API, no agent) | 5 | BUILD | Sends Chat message when agent crashes. Must work outside agent context. |
| 8 | Wire agent loop with error handling (`query()` + async generator) | 2-7.5 | BUILD | End-to-end run produces DOCX + Chat notification. Uses `query()` with async generator prompt for custom MCP tools. Failures send Chat alert. |
| 9 | Add cost tracking and run logging | 8 | BUILD | `runs/YYYY-MM-DD.json` has tokens, duration, errors |
| 10 | Add token-count ceiling guard | 9 | BUILD | Agent aborts when token count exceeds threshold (~$15 equivalent) |
| 11 | Make agent.py cross-platform (Linux + Windows) | 8 | BUILD | Remove Windows-only `creationflags`, use env vars for paths, read secrets from env with Doppler fallback |
| 12 | Create Dockerfile + docker-compose.yml | 11 | BUILD | Container builds, agent runs inside container with cron |
| 13 | Generate `claude setup-token` and deploy to EC2 | 12 | BUILD | Token generated locally, stored securely on EC2 |
| 14 | Deploy container to EC2 alongside Blip Sentinel | 13 | BUILD | `docker compose up -d` on EC2, cron fires Sunday 11am UTC |
| 15 | First live run on EC2 + verify full pipeline | 14 | BUILD | DOCX in Drive, link in Chat, run log written — from EC2, not local |
| 16 | Second run to verify template reuse | 15 | BUILD | Agent reuses template, doesn't rewrite |

## Detailed Design

### Task 2: Project Scaffold

```
analytics-agent/
├── agent.py                    # Main entry: sync → query → analyze → report → upload → notify
├── tools/
│   ├── __init__.py
│   ├── supabase_tool.py        # @tool query_supabase
│   ├── drive_tool.py           # @tool upload_to_drive
│   └── gchat_tool.py           # @tool send_gchat
├── templates/
│   └── weekly_report.py        # Reusable DOCX generator (agent patches if needed)
├── prompts/
│   └── weekly_analysis.txt     # System prompt for the analyst agent
└── runs/                       # JSON run logs (gitignored)
```

### Task 3: query_supabase Tool

```python
ALLOWED_VIEWS = {
    "v_meta_campaign_summary", "v_meta_flagged_ads", "v_meta_boost_candidates",
    "v_meta_weekly_trend", "v_meta_ad_inventory", "meta_organic_posts",
}

@tool("query_supabase", "Query a Supabase Meta Ads analytics view", {
    "view": str,       # view name — MUST be in ALLOWED_VIEWS allowlist
    "filters": str,    # optional: Supabase REST filters like "status=eq.ACTIVE"
    "select": str,     # optional: column selection
    "limit": int,      # optional: row limit, default 100
})
async def query_supabase(args):
    if args["view"] not in ALLOWED_VIEWS:
        return {"error": f"View '{args['view']}' not in allowlist. Allowed: {ALLOWED_VIEWS}"}
    # Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from Doppler
    # Service role key bypasses RLS — allowlist enforcement is critical
    # Returns JSON array of rows
    ...
```

Supported views:
- `v_meta_campaign_summary` — campaign rollups with spend, purchases, CPA
- `v_meta_flagged_ads` — ads needing attention
- `v_meta_boost_candidates` — organic posts ranked for boosting
- `v_meta_weekly_trend` — week-over-week metrics
- `v_meta_ad_inventory` — full ad details (use with filters, not full dump)
- `meta_organic_posts` — raw organic posts with engagement scores

### Task 4: upload_to_drive Tool

```python
@tool("upload_to_drive", "Upload file to Google Drive shared folder", {
    "file_path": str,     # local path to file
    "folder_id": str,     # Drive folder ID (default: shared reports folder)
    "filename": str,      # name in Drive
})
async def upload_to_drive(args):
    # Uses service account with DWD (credentials/task-manager-service.json)
    # Impersonates sam@bebang.ph for Drive access
    # Sets sharing: anyone with link can view
    # Returns: {"file_id": "...", "web_view_link": "https://drive.google.com/..."}
    ...
```

### Task 5: send_gchat Tool

```python
@tool("send_gchat", "Send message to Sam's Google Chat notification space", {
    "message": str,    # Google Chat formatted text (supports basic markdown)
})
async def send_gchat(args):
    # Uses bot scope (not DWD) — same pattern as blip-sentinel/notifier.py
    # Space: spaces/AAQABiNmpBg (BLIP_NOTIFICATION_SPACE)
    # Rate limit: 1 msg/min (simple, no circuit breaker needed for weekly runs)
    # Returns: {"message_id": "...", "sent": true}
    ...
```

### Task 6: DOCX Report Template

Extract from today's `create_interactive_plan_docx.py` into a reusable template that accepts a data dict:

```python
def generate_weekly_report(data: dict, output_path: str):
    """
    Generate branded BEI weekly Meta Ads report.

    data = {
        "week_ending": "2026-03-08",
        "campaigns": [...],          # from v_meta_campaign_summary
        "flagged_ads": [...],        # from v_meta_flagged_ads
        "boost_candidates": [...],   # from v_meta_boost_candidates
        "weekly_trend": [...],       # from v_meta_weekly_trend
        "ai_analysis": str,          # Claude's narrative analysis
        "recommendations": [...],    # Claude's top recommendations
        "total_spend": float,
        "total_purchases": int,
        "avg_cpa": float,
    }
    """
```

**Template sections:**
1. **Cover page** — "Weekly Meta Ads Intelligence" + date + BEI logo
2. **Executive Summary** — AI-generated 3-5 bullet narrative (what happened, why, what to do)
3. **Campaign Performance Table** — all active campaigns with 7d metrics, color-coded by health
4. **Flagged Ads** — ads needing attention with flag reasons
5. **Organic Post Winners** — top 5 boost candidates with engagement scores
6. **Week-over-Week Trend** — spend, purchases, CPA comparison
7. **Recommendations** — AI-generated action items with priority and reasoning
8. **Appendix: Full Data** — detailed tables for reference

**Agent patching rule:** The agent has Read + Edit access to the template. If the script fails (e.g., data shape changed, new view columns), the agent can patch it. But it should NOT rewrite the entire script — only fix the specific failure. This is enforced in the prompt.

### Task 7: Agent Prompt

The system prompt tells the agent:
- You are a Meta Ads analyst for Bebang Halo-Halo (premium QSR, 45+ stores, Philippines)
- Your job: analyze this week's ad performance and produce an executive briefing
- NEVER suggest discounts/promos/BOGO — Bebang is premium
- Query all 6 Supabase views, compare to last week's data
- Focus on: what changed, what's working, what's wasting money, what organic posts should be boosted
- Generate the report using the template (Read it, run it, verify with markitdown)
- Upload to Drive, send Chat notification with top 3 findings + link
- If the template script fails, patch the specific issue — do NOT rewrite from scratch

### Task 8: Agent Loop (agent.py)

```python
async def main():
    run_log = {"timestamp": datetime.now().isoformat(), "errors": []}
    try:
        # 1. Refresh Supabase data (cross-platform subprocess)
        subprocess_kwargs = {}
        if platform.system() == "Windows":
            subprocess_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "scripts" / "sync_meta_ads_to_supabase.py")],
            capture_output=True, text=True, check=True,
            **subprocess_kwargs,
        )
        if "failed" in result.stdout.lower():
            run_log["errors"].append(f"Sync partial failure: {result.stdout[-500:]}")

        # 2. Run the analyst agent
        server = create_sdk_mcp_server(
            name="bei-analytics", version="1.0.0",
            tools=[query_supabase, upload_to_drive, send_gchat]
        )

        options = ClaudeAgentOptions(
            mcp_servers={"bei": server},
            allowed_tools=[
                "mcp__bei__query_supabase",
                "mcp__bei__upload_to_drive",
                "mcp__bei__send_gchat",
                "Read", "Write", "Edit", "Glob", "Grep",
            ],
            permission_mode="bypassPermissions",
            model="sonnet",
            max_turns=30,
        )

        async def prompt_generator():
            yield WEEKLY_PROMPT

        async for msg in query(prompt=prompt_generator(), options=options):
            track_tokens(msg)
            check_token_ceiling()

    except Exception as e:
        run_log["errors"].append(str(e))
        try:
            send_failure_alert(f"BEI Analytics Agent FAILED: {e}")
        except Exception as alert_err:
            run_log["errors"].append(f"Alert failed: {alert_err}")
        raise
    finally:
        write_run_log(run_log)
```

**Key changes v2 → v3:**
- All v2 changes retained (async generator, no Bash, error handling, failure alerts)
- `creationflags` now conditional on `platform.system() == "Windows"` (cross-platform)
- Secrets read from env vars first, Doppler CLI fallback (see Task 11 detail)
- Google credentials path from `GOOGLE_CREDENTIALS_PATH` env var
- Runs on both Windows (local dev) and Linux (EC2 Docker)

### Task 11: Cross-Platform agent.py

Changes to make agent.py work on both Windows (local dev) and Linux (EC2 Docker):

```python
# Remove Windows-only creationflags — use platform detection
import platform
subprocess_kwargs = {}
if platform.system() == "Windows":
    subprocess_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

result = subprocess.run(
    [sys.executable, sync_script_path],
    capture_output=True, text=True, check=True,
    **subprocess_kwargs,
)

# Read secrets from env vars (Docker .env) with Doppler CLI fallback (local dev)
def get_secret(name):
    val = os.environ.get(name)
    if val:
        return val
    # Fallback: Doppler CLI (local Windows dev)
    result = subprocess.run(
        ["doppler", "secrets", "get", name, "--plain", "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

# Google credentials path from env var or default
CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials/task-manager-service.json")
```

### Task 12: Dockerfile + docker-compose.yml

```dockerfile
FROM python:3.12-slim

# Install Claude CLI
RUN curl -fsSL https://claude.ai/install.sh | sh

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install supercronic for cron
RUN apt-get update && apt-get install -y curl && \
    curl -fsSLO https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 && \
    chmod +x supercronic-linux-amd64 && mv supercronic-linux-amd64 /usr/local/bin/supercronic

# Copy agent code
COPY analytics-agent/ /app/analytics-agent/
COPY scripts/sync_meta_ads_to_supabase.py /app/scripts/
COPY supercronic-crontab /app/

WORKDIR /app
CMD ["supercronic", "/app/supercronic-crontab"]
```

```yaml
# docker-compose.yml
services:
  analytics-agent:
    build: .
    container_name: bei-analytics-agent
    env_file: .env
    volumes:
      - ./credentials:/app/credentials:ro
      - ./runs:/app/analytics-agent/runs
      - claude-auth:/root/.claude
    restart: unless-stopped

volumes:
  claude-auth:
    # Persists claude setup-token auth across container restarts
```

```
# supercronic-crontab
# Sunday 11:00 UTC = 7:00 PM PHT
0 11 * * 0 cd /app && python analytics-agent/agent.py >> /app/analytics-agent/runs/cron.log 2>&1
```

### Task 13: Claude setup-token Deployment

```bash
# 1. On local machine: generate long-lived token
claude setup-token
# Follow prompts — generates token tied to Max subscription

# 2. Copy auth to EC2
# Option A: SCP the credentials file
scp ~/.claude/.credentials.json ubuntu@EC2:~/analytics-agent/claude-auth/

# Option B: Set as env var in .env
# CLAUDE_AUTH_TOKEN=<token-value>
```

### Task 14: EC2 Deployment

Same pattern as Blip Sentinel:
1. Push to `production` branch
2. SSM to EC2: `git clone --depth 1` to `/tmp/hrms-deploy`
3. Copy agent files to `/home/ubuntu/analytics-agent/`
4. Copy `.env` and `credentials/` (preserve across deploys)
5. `docker compose build --no-cache && docker compose up -d`
6. Verify: `docker logs bei-analytics-agent` shows cron registered

## Cost Estimate

| Component | Per Run | Monthly (4 runs) |
|-----------|---------|-------------------|
| Supabase sync (Meta API) | Free (within rate limits) | Free |
| Sonnet analysis + DOCX generation | **$0** (Claude Max subscription) | **$0** |
| Google Drive API | Free | Free |
| Google Chat API | Free | Free |
| **Total** | **$0** | **$0** |

**Claude Max subscription:** The agent runs on EC2 via Claude CLI authenticated with `setup-token` (long-lived headless auth from Max plan). No API key billing. The $15 cost ceiling is retained as a runaway-loop guard (measured by token count equivalent, not actual dollars).

**If Max token expires:** Re-run `claude setup-token` locally and redeploy to EC2. Fallback: set ANTHROPIC_API_KEY in .env (~$3-5/run with Sonnet).

## Google Drive Setup

| Setting | Value |
|---------|-------|
| Folder | Create `BEI Reports/Meta Ads Weekly` in Sam's Drive |
| Service account | `credentials/task-manager-service.json` |
| Impersonate | `sam@bebang.ph` (DWD) |
| Sharing | Agent sets "anyone with link can view" on each uploaded file |
| Naming | `Meta_Ads_Weekly_YYYY-MM-DD.docx` |

## Verification Checklist

### Component Tests (local — DONE in v2)
- [x] `pip show claude-agent-sdk` returns v0.1.48+
- [x] `ANTHROPIC_API_KEY` is NOT set in environment (agent uses Max via CLI)
- [x] `query_supabase` tool returns data from all 6 allowlisted views
- [x] `query_supabase` tool REJECTS non-allowlisted view names
- [x] `upload_to_drive` uploads a test file and returns a shareable link
- [x] `send_gchat` sends a message to `spaces/AAQABiNmpBg`
- [x] `send_failure_alert` sends crash notification (test with forced exception)
- [x] DOCX template generates a report with placeholder data
- [x] DOCX template generates a report with real Supabase data
- [x] Token ceiling guard aborts on excessive usage
- [x] `Bash` is NOT in allowed_tools (security check)

### EC2 Deployment Tests (v3 — DONE 2026-03-09)
- [x] agent.py runs on Linux (no Windows-only code paths)
- [x] Secrets read from env vars (Docker .env), Doppler fallback on Windows
- [x] Google credentials path configurable via `GOOGLE_CREDENTIALS_PATH` env var
- [x] Dockerfile builds successfully
- [x] `claude setup-token` generates valid long-lived token (valid 1yr, stored in Doppler)
- [x] Claude CLI on EC2 authenticates with setup-token (Max subscription)
- [x] Container starts with Supercronic cron registered
- [x] Full agent run on EC2: sync → query → analyze → DOCX → Drive → Chat (339s, 0 errors)
- [x] Run log written to persistent volume (`./runs/`)
- [ ] Agent crash on EC2 produces Chat alert (not silent failure) — deferred, requires intentional crash test
- [ ] Cron fires on Sunday 11:00 UTC (= 7pm PHT) — will verify next Sunday (2026-03-15)
- [x] Second run reuses template (doesn't rewrite) — verified by 2nd successful run
- [x] Container survives restart (`restart: unless-stopped` + `init: true`)

## Phase 2 (Future)

- **Sales correlation** — add Supabase sales views, correlate ad spend → revenue by store/channel
- **Daily micro-briefing** — Haiku-powered 3-line morning check (just anomalies, $0.10/run)
- **Auto-action with confirmation** — agent proposes changes, Sam confirms via Chat reply, agent executes
- **Historical trend DB** — store run logs + weekly metrics for month-over-month analysis

## Audit Results (2026-03-08)

**Method:** 4-domain parallel audit + code verification + adversarial fact-check
**Verdict:** GO (all blockers resolved in plan v2)

### Blockers Found & Resolved

| # | Blocker | Original | Fact-Check | Resolution |
|---|---------|----------|------------|------------|
| 1 | `query()` can't use custom MCP tools | CRITICAL | **FALSE** — `query()` supports custom tools, needs async generator prompt | Fixed: use `prompt_generator()` async generator |
| 2 | Claude Max vs API key contradiction | CRITICAL | PARTIAL — plan was internally consistent (API billing), conflict is with user intent | Resolved: removed ANTHROPIC_API_KEY, using Max via CLI |
| 3 | No error handling or failure notification | CRITICAL | SUPPORTED | Fixed: try/except/finally + `send_failure_alert()` (Task 7.5) |
| 4 | bypassPermissions + Bash = unrestricted shell | CRITICAL | SUPPORTED | Fixed: removed Bash from allowed_tools |
| 5 | Sync script exits 0 on partial failures | WARNING | SUPPORTED | Fixed: stdout check for "failed" keyword in agent loop |
| 6 | No Meta token refresh strategy | WARNING | SUPPORTED | Accepted risk — manual refresh every 60 days, agent logs token errors |
| 7 | query_supabase has no view allowlist | WARNING | PARTIAL — low risk for single-user batch | Fixed: added ALLOWED_VIEWS as defense-in-depth |
| 8 | DOCX template extraction is non-trivial | WARNING | PARTIAL — estimation issue, not blocker | Re-estimated Task 6 (40KB/903-line source, budget 3-4 hours) |

### False Positives Eliminated

| Claim | Source | Truth |
|-------|--------|-------|
| Package name wrong (`claude-code-sdk`) | system-arch C1 | STALE — `claude-agent-sdk` v0.1.48 is correct; `claude-code-sdk` is deprecated |
| `query()` can't use custom MCP tools | supabase-sdk SDK-05 | FALSE — `query()` supports custom tools per official docs; needs async generator prompt |
| Credentials not gitignored | system-arch C4 | STALE — `credentials/` is gitignored (lines 48-49 of .gitignore) |

### Audit Output Files

All detailed findings: `output/plan-audit/bei-analytics-agent/`

---
*Plan created: 2026-03-08 | v2: audited GO | v3: EC2+Max deployment (2026-03-08) | Agent SDK: v0.1.48 | Target: EC2 live run 2026-03-15*
