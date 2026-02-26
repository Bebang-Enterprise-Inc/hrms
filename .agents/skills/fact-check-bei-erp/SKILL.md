---
name: fact-check-bei-erp
description: Use when validating factual claims in DECISIONS.md, documents, contracts, spreadsheets, or datasets against source evidence using GLM-5.
---

# fact-check-bei-erp

Validates factual claims across DECISIONS tables, documents, legal contracts, and spreadsheet/data files against mixed-format evidence using Z.AI GLM-5.

## Engine: GLM-5 ONLY

- **No fallback.** If GLM-5 API fails, run is FAILED.
- **No silent degradation.** Any `ERROR` verdict is a hard stop (exit `10`).
- MiniCheck (`fact_audit.py`) remains optional second-layer checking only. Never use it as substitute for GLM-5.

## When to Use

- Validating `DECISIONS.md` tables against evidence files
- Fact-checking narrative docs (`.md`, `.txt`, `.docx`, `.pdf`)
- Fact-checking legal/contract files (especially term/date/obligation consistency)
- Verifying spreadsheet/data claims (`.xlsx`, `.xls`, `.csv`, `.json`)

## Arguments

Parse from user `/fact-check` invocation:

| Argument | Required | Description |
|----------|----------|-------------|
| `target` | Yes | File containing claims to verify (`DECISIONS.md`, doc, contract, spreadsheet, dataset) |
| `--sources` | Yes | Directory with source evidence files |
| `--mode` | No | `auto` (default), `decisions`, `document`, `contract`, `dataset` |
| `--output` | No | Output report path (auto-generated if omitted) |
| `--parallel` | No | Worker count (default `3`, hard cap `3`) |
| `--top-k` | No | Top evidence chunks per claim (default `8`) |
| `--numeric-tolerance` | No | Absolute tolerance for numeric checks in dataset mode (default `0.0`) |
| `--api-key-env` | No | Env var for API key (default `ZAI_API_KEY`) |
| `--doppler-project` / `--doppler-config` | No | Optional secret retrieval fallback when env var is missing |

## Usage Examples

```bash
# DECISIONS table
/fact-check "data/_CONSOLIDATED/01_FINANCE/DECISIONS.md"

# Contract audit (explicit contract mode)
/fact-check "contracts/master_service_agreement.docx" \
  --sources "contracts/source-packet/" \
  --mode contract

# Spreadsheet/data audit
/fact-check "reports/kpi_summary.xlsx" \
  --sources "reports/raw-data/" \
  --mode dataset \
  --numeric-tolerance 0.01
```

## How It Works

1. **Detect Mode** from target file or explicit `--mode`
2. **Extract Claims** from DECISIONS rows or document/contract/dataset sentences
3. **Load Evidence** recursively from sources (`.md/.txt/.csv/.json/.xlsx/.xls/.docx/.pdf`)
4. **Retrieve Evidence** via lexical overlap + numeric/date matching
5. **Verify with GLM-5** returning structured JSON verdict + citations
6. **Report** with `SUPPORTED/PARTIAL/NOT_FOUND/CONTRADICTED/INSUFFICIENT_CONTEXT`

## Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| SUPPORTED | Source confirms the claim | None |
| PARTIAL | Core fact matches but some details differ | Review and correct details |
| NOT_FOUND | Source lacks supporting evidence | Add source or remove claim |
| CONTRADICTED | Source conflicts with claim | Fix immediately |
| INSUFFICIENT_CONTEXT | Retrieved evidence is insufficient to conclude | Provide better sources/citations |
| ERROR | GLM/API/parse failure | **HARD STOP — run fails** |

## Failure Policy

Any `ERROR` verdict = FAILED run (exit `10`). Do not fallback to other models.

## Implementation

When user invokes `/fact-check`, execute:

```bash
python scripts/fact_check_universal.py "<target_file>" \
    --sources "<source_dir>" \
    --output "<output_path>" \
    --model glm-5 \
    --parallel 3
```

### Output Path Convention

If `--output` is omitted:
```
<sources>/<target_stem>_UNIVERSAL_GLM_AUDIT.md
```

### After Run

1. Read the generated audit report
2. If any `ERROR` exists -> report FAILED and stop
3. Present summary table to user
4. Highlight `CONTRADICTED` and `NOT_FOUND` items first
5. Include cited evidence locators in remediation guidance

## Rate Limits

- **GLM-5 Coding Plan:** run up to 3 concurrent requests in this environment
- **Default parallel workers:** 3
- **Hard cap:** any value above `3` is automatically clamped to `3`
- **API key:** `ZAI_API_KEY` env var (portable default)

## Optional: MiniCheck Second Layer

After GLM-5 passes clean, you can optionally run MiniCheck for double verification:
```bash
python scripts/fact_audit.py "<report.docx>" \
    --sources "<source_dir>" --threshold 0.5
```
This is manual-only. Never automatic. Never a fallback.

## Legacy Compatibility

- `scripts/glm_fact_check.py` remains available for legacy DECISIONS-only workflows.
- Prefer `scripts/fact_check_universal.py` for all new work.

## Source Files

| File | Purpose |
|------|---------|
| `scripts/fact_check_universal.py` | **Primary engine** - universal GLM-5 checker with evidence locators |
| `scripts/glm_fact_check.py` | Legacy DECISIONS-only checker |
| `scripts/fact_audit.py` | Optional MiniCheck NLI second layer (manual only) |
| `scripts/install_deps.py` | MiniCheck dependency installer |
