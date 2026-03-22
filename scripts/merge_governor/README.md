# Governor-ERP: AI Merge Governor

Serializes production merges with AI review, per-branch staging, and conflict detection.

## Quick Start

```bash
# Dry-run mode (no staging/production changes)
python -m scripts.merge_governor.governor_erp --dry-run

# Live mode with CLI backend ($0 — Max subscription)
python -m scripts.merge_governor.governor_erp

# Live mode with SDK backend (pay-per-token)
export ANTHROPIC_API_KEY="..."
python -m scripts.merge_governor.governor_erp --ai-backend sdk

# Skip AI review (emergency)
python -m scripts.merge_governor.governor_erp --skip-review
```

## Architecture

```
Builder sessions (5-8 parallel Claude Code instances)
    │ create PRs against production
    ▼
MERGE GOVERNOR (single Python process)
├── PR Watcher (polls gh pr list every 30s)
├── Staging Manager (per-branch containers on EC2)
├── AI Review Gate (dual backends: CLI + SDK)
├── Merge Serializer (FIFO queue, one merge at a time)
└── Health Server (/healthz on localhost:8000)
```

## Commands

| Command | Action |
|---------|--------|
| `status` / `s` | Show governor status |
| `queue` / `q` | Show merge queue |
| `merge <PR#>` | Force-queue a PR |
| `skip <PR#>` | Remove from queue |
| `pause` | Halt merge queue |
| `resume` | Resume queue |
| `history` | Show last 10 merges |
| `ports` | Show port assignments |
| `help` / `?` | Show help |

Anything else is forwarded to AI for natural language processing.

## AI Backends

| Backend | Flag | Cost | Notes |
|---------|------|------|-------|
| CLI | `--ai-backend cli` (default) | $0 | Uses `claude --print` (Max subscription) |
| SDK | `--ai-backend sdk` | Pay-per-token | Uses Anthropic API key |

## Staging Infrastructure

- **EC2:** `i-0a9a6ed652533d6c4` (t3.large, 8GB RAM)
- **Ports:** 8001-8010 for branch containers
- **MariaDB:** Shared instance (one DB, multiple Frappe sites)
- **Scripts:** Deployed to `/home/ubuntu/governor-staging/` via SSM

## Files

| File | Purpose |
|------|---------|
| `governor_erp.py` | Main entrypoint |
| `state_manager.py` | Atomic-write state persistence |
| `port_allocator.py` | Port registry (8001-8010) |
| `pr_watcher.py` | PR polling |
| `chat_handler.py` | Two-tier chat (keyword + LLM) |
| `reviewer.py` | Review orchestrator + caching |
| `ai_backend_cli.py` | Backend A (claude --print) |
| `ai_backend_sdk.py` | Backend B (Anthropic API) |
| `conflict_detector.py` | File conflict detection |
| `merge_serializer.py` | FIFO merge queue + L1 smoke |
| `staging_manager.py` | Staging container lifecycle |
| `ssm_helper.py` | AWS SSM command runner |
| `health_server.py` | /healthz HTTP endpoint |
| `benchmark.py` | Backend comparison harness |

## Auto-Start

```powershell
# Install (runs at system startup)
.\install_autostart.ps1

# Remove
.\uninstall_autostart.ps1
```

## Tests

```bash
python -m pytest scripts/merge_governor/tests/ -q -p no:logfire
```
# Governor live proof - Sun Mar 22 16:03:30 MPST 2026
