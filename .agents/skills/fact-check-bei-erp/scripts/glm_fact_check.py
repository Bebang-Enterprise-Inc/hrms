"""
GLM-5 Fact-Checker — Validates claims in DECISIONS.md files against source documents.

Uses Z.AI GLM-5 via Coding Plan subscription endpoint (hard-capped at 3 concurrent workers).
GLM-5 is the ONLY engine. Any API failure = HARD STOP (exit 10). No fallback.

Usage:
    python glm_fact_check.py <decisions_file> --sources <source_dir> [--output <output.md>] [--parallel 3]

Example:
    python glm_fact_check.py "data/_CONSOLIDATED/01_FINANCE/DECISIONS.md" \
        --sources "scratchpad/fact-check-sources/" \
        --output "scratchpad/fact-check-sources/01_FINANCE_GLM_AUDIT.md"

Exit codes:
    0  = All good (no contradictions or not-found)
    1  = Has CONTRADICTED decisions
    2  = Has NOT_FOUND decisions
    10 = HARD STOP — GLM-5 API failed (ERROR/PARSE_ERROR)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Z.AI Coding Plan endpoint (NOT the standard /api/paas/v4 which requires pay-as-you-go)
ZAI_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
DEFAULT_PARALLEL_WORKERS = 3
MAX_PARALLEL_WORKERS = 3
MAX_API_RETRIES = 6


def get_api_key():
    """Get ZAI_API_KEY from Doppler."""
    result = subprocess.run(
        ['C:/Users/Sam/bin/doppler.exe', 'secrets', 'get', 'ZAI_API_KEY',
         '--plain', '--project', 'bei-erp', '--config', 'dev'],
        capture_output=True, text=True, creationflags=CREATE_NO_WINDOW
    )
    key = result.stdout.strip()
    if not key:
        print("ERROR: Could not get ZAI_API_KEY from Doppler", file=sys.stderr)
        sys.exit(1)
    return key


def call_glm(api_key, messages, model="glm-4.7", max_tokens=1024, temperature=0.1):
    """Call GLM API with retry logic."""
    import requests

    for attempt in range(MAX_API_RETRIES):
        try:
            resp = requests.post(
                ZAI_ENDPOINT,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                },
                json={
                    'model': model,
                    'messages': messages,
                    'max_tokens': max_tokens,
                    'temperature': temperature
                },
                timeout=120
            )

            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
            elif resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After", "").strip()
                if retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = min(90, (2 ** attempt) + 2)

                if attempt < MAX_API_RETRIES - 1:
                    print(
                        f"  API {resp.status_code}, retrying in {wait}s (attempt {attempt + 1}/{MAX_API_RETRIES})...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue

                print(
                    f"  API {resp.status_code} after {MAX_API_RETRIES} attempts: {resp.text[:200]}",
                    file=sys.stderr,
                )
                return None
            else:
                print(f"  API error {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
                return None
        except Exception as e:
            print(f"  Request error: {e}", file=sys.stderr)
            if attempt < MAX_API_RETRIES - 1:
                wait = min(30, attempt + 2)
                print(
                    f"  Retrying after request error in {wait}s (attempt {attempt + 1}/{MAX_API_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue
            return None

    return None


def load_sources(source_dir):
    """Load all source files into a dict of {filename: content}."""
    sources = {}
    source_path = Path(source_dir)
    for f in source_path.glob("*.md"):
        # Skip audit output files
        if "NLI_AUDIT" in f.name or "manual_verification" in f.name or "GLM_AUDIT" in f.name or "CONSOLIDATED" in f.name:
            continue
        try:
            content = f.read_text(encoding='utf-8', errors='replace')
            sources[f.name] = content
        except Exception as e:
            print(f"  Warning: Could not read {f.name}: {e}", file=sys.stderr)
    for f in source_path.glob("*.csv"):
        try:
            content = f.read_text(encoding='utf-8', errors='replace')
            sources[f.name] = content[:50000]  # Truncate large CSVs
        except Exception:
            pass
    return sources


def extract_decisions(decisions_file):
    """Extract individual decisions from a DECISIONS.md file."""
    content = Path(decisions_file).read_text(encoding='utf-8', errors='replace')
    lines = content.split('\n')

    decisions = []
    current_section = ""

    for i, line in enumerate(lines):
        # Track section headers
        if line.startswith('## '):
            current_section = line.strip('# ').strip()
            continue

        # Match table rows with decision IDs (e.g., | CS-001 | ... |)
        match = re.match(r'^\|\s*([A-Z]+-\d+)\s*\|(.+)$', line)
        if match:
            decision_id = match.group(1)
            rest = match.group(2)
            # Split remaining columns
            cols = [c.strip() for c in rest.split('|')]
            # Table format: | ID | Decision | Value | Confirmed By | Date | Source |
            if len(cols) >= 5:
                decisions.append({
                    'id': decision_id,
                    'section': current_section,
                    'decision': cols[0] if cols[0] else '',
                    'value': cols[1] if len(cols) > 1 else '',
                    'confirmed_by': cols[2] if len(cols) > 2 else '',
                    'date': cols[3] if len(cols) > 3 else '',
                    'source': cols[4] if len(cols) > 4 else '',
                    'line': i + 1,
                    'raw': line.strip()
                })

    return decisions


def find_relevant_source(decision, sources):
    """Find the most relevant source file for a decision based on its citation."""
    source_ref = decision.get('source', '')

    # Extract filename patterns from source reference (handle mangled em dash)
    patterns = re.findall(r'`([^`]+\.(?:md|csv))`', source_ref)
    if not patterns:
        # Try without backticks
        patterns = re.findall(r'(\w+[-_]\w+\.(?:md|csv))', source_ref)

    # Also extract short names like CONTEXT.md, finance-apex.md
    short_patterns = re.findall(r'(\w[\w-]*\.md)', source_ref)

    all_patterns = patterns + short_patterns

    # Also try fuzzy matching: "HRMS Setup Checklist" -> "HRMS_Setup_Checklist"
    # Convert plain-text citation to potential filename by replacing spaces with underscores
    confirmed_by = decision.get('confirmed_by', '')
    source_field = decision.get('source', '')
    for text in [source_ref, confirmed_by, source_field]:
        # Match multi-word names that could be filenames (e.g. "HRMS Setup Checklist")
        candidates = re.findall(r'([A-Z][\w]+(?:\s+[\w]+){1,5})', text)
        for candidate in candidates:
            fuzzy_name = candidate.strip().replace(' ', '_') + '.md'
            if fuzzy_name not in all_patterns:
                all_patterns.append(fuzzy_name)

    # Find matching source files
    matched_sources = {}
    for pattern in all_patterns:
        # Strip date suffixes and path prefixes for matching
        base_name = pattern.split('/')[-1]
        # Remove date suffix like _2026-02-12
        base_clean = re.sub(r'_\d{4}-\d{2}-\d{2}', '', base_name)

        for src_name, src_content in sources.items():
            src_clean = re.sub(r'_\d{4}-\d{2}-\d{2}', '', src_name)
            if src_clean == base_clean or base_name == src_name:
                matched_sources[src_name] = src_content
            elif base_clean.replace('.md', '') in src_name.replace('.md', ''):
                matched_sources[src_name] = src_content

    # Fallback: if no filename matched, use keyword overlap to find best sources
    if not matched_sources:
        claim_text = f"{decision.get('decision', '')} {decision.get('value', '')}".lower()
        claim_words = set(re.findall(r'\w{4,}', claim_text))  # words >= 4 chars
        if claim_words:
            scored = []
            for src_name, src_content in sources.items():
                src_words = set(re.findall(r'\w{4,}', src_content[:10000].lower()))
                overlap = len(claim_words & src_words)
                if overlap > 0:
                    scored.append((overlap, src_name, src_content))
            scored.sort(reverse=True)
            # Take top 3 most relevant sources
            for _, name, content in scored[:3]:
                matched_sources[name] = content

    return matched_sources


def extract_relevant_passages(content, keywords, max_chars=6000, context_lines=5):
    """Extract passages from content that contain decision keywords.

    Instead of blindly taking first N chars, find paragraphs containing keywords
    and return those with surrounding context.
    """
    lines = content.split('\n')
    keywords_lower = [k.lower() for k in keywords if len(k) >= 4]
    if not keywords_lower:
        return content[:max_chars]

    # Score each line by keyword hits
    scored_lines = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        hits = sum(1 for kw in keywords_lower if kw in line_lower)
        if hits > 0:
            scored_lines.append((i, hits))

    if not scored_lines:
        # No keyword matches — fall back to first N chars
        return content[:max_chars]

    # Sort by hit count (highest first), take top regions
    scored_lines.sort(key=lambda x: -x[1])

    # Collect unique line ranges around top hits
    collected = set()
    passages = []
    chars_used = 0

    for line_idx, _ in scored_lines:
        if chars_used >= max_chars:
            break
        start = max(0, line_idx - context_lines)
        end = min(len(lines), line_idx + context_lines + 1)

        # Skip if we already collected this region
        if any(i in collected for i in range(start, end)):
            continue

        passage = '\n'.join(lines[start:end])
        passage_len = len(passage)

        if chars_used + passage_len > max_chars:
            # Take what fits
            remaining = max_chars - chars_used
            passage = passage[:remaining]
            passages.append(f"[...lines {start+1}-{end}...]\n{passage}")
            chars_used += len(passage)
            break

        passages.append(f"[...lines {start+1}-{end}...]\n{passage}")
        chars_used += passage_len
        collected.update(range(start, end))

    return '\n\n'.join(passages)


def verify_decision(api_key, decision, relevant_sources, model):
    """Use GLM to verify a single decision against its source documents."""
    # Extract keywords from the decision for smart passage matching
    claim_text = f"{decision.get('decision', '')} {decision.get('value', '')} {decision.get('confirmed_by', '')}"
    keywords = re.findall(r'\b\w{4,}\b', claim_text)

    # Build source context using keyword-aware extraction
    source_text = ""
    for name, content in relevant_sources.items():
        # Smart extraction: find passages containing decision keywords
        passages = extract_relevant_passages(content, keywords, max_chars=8000)
        source_text += f"\n--- SOURCE: {name} ---\n{passages}\n"

    if not source_text.strip():
        return {
            'verdict': 'NO_SOURCE',
            'confidence': 0,
            'explanation': 'No matching source files found for cited references.',
            'issues': []
        }

    # Truncate total source to 30K chars (increased from 20K)
    source_text = source_text[:30000]

    prompt = f"""Fact-check this claim against sources. Be CONCISE in your reasoning.

CLAIM: [{decision['id']}] {decision['decision']} — {decision['value']}
ATTRIBUTED TO: {decision['confirmed_by']} | DATE: {decision['date']}

SOURCES:
{source_text}

Output ONLY this JSON (no markdown, no explanation before it):
{{"verdict":"SUPPORTED|PARTIAL|NOT_FOUND|CONTRADICTED","confidence":0.0-1.0,"explanation":"one sentence","issues":["issue1"]}}

SUPPORTED=source states/implies the claim. PARTIAL=core fact matches but attribution/date/detail differs. NOT_FOUND=source lacks this info. CONTRADICTED=source says different."""

    # GLM-5 uses reasoning tokens that consume max_tokens budget
    # With 200K context window and ~2K input, we can afford generous output budget
    tokens = 16384 if 'glm-5' in model else 512
    response = call_glm(api_key, [{'role': 'user', 'content': prompt}], model=model, max_tokens=tokens)

    if not response:
        return {'verdict': 'ERROR', 'confidence': 0, 'explanation': 'API call failed', 'issues': []}

    # Parse JSON from response
    try:
        # Try to extract JSON from response (may be wrapped in markdown)
        json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return {'verdict': 'PARSE_ERROR', 'confidence': 0, 'explanation': response[:200], 'issues': []}
    except json.JSONDecodeError:
        return {'verdict': 'PARSE_ERROR', 'confidence': 0, 'explanation': response[:200], 'issues': []}


def main():
    parser = argparse.ArgumentParser(description='GLM Fact-Checker for DECISIONS.md files')
    parser.add_argument('decisions_file', help='Path to DECISIONS.md file')
    parser.add_argument('--sources', required=True, help='Directory containing source files')
    parser.add_argument('--output', help='Output audit report path (default: next to decisions file)')
    parser.add_argument('--model', default='glm-5', help='GLM model (default: glm-5)')
    parser.add_argument(
        '--parallel',
        type=int,
        default=DEFAULT_PARALLEL_WORKERS,
        help=f'Number of parallel workers (hard cap: {MAX_PARALLEL_WORKERS})',
    )
    args = parser.parse_args()

    if not args.output:
        base = Path(args.decisions_file).stem
        args.output = str(Path(args.sources) / f"{base}_GLM_AUDIT.md")

    print(f"GLM Fact-Checker")
    print(f"  Model: {args.model}")
    print(f"  Endpoint: {ZAI_ENDPOINT}")
    print(f"  Decisions: {args.decisions_file}")
    print(f"  Sources: {args.sources}")
    print(f"  Output: {args.output}")

    requested_workers = max(1, args.parallel)
    workers = max(1, min(requested_workers, MAX_PARALLEL_WORKERS))
    if requested_workers != workers:
        print(
            f"  Requested parallel={requested_workers} capped to {workers} to reduce GLM rate-limit failures"
        )
    print(f"  Parallel: {workers} workers")
    print()

    api_key = get_api_key()
    print(f"  API key loaded ({len(api_key)} chars)")

    # Load sources
    sources = load_sources(args.sources)
    print(f"  Loaded {len(sources)} source files: {', '.join(sorted(sources.keys()))}")

    # Extract decisions
    decisions = extract_decisions(args.decisions_file)
    print(f"  Found {len(decisions)} decisions to verify")
    print()

    if not decisions:
        print("ERROR: No decisions found. Check file format.", file=sys.stderr)
        sys.exit(1)

    # Verify each decision
    results = [None] * len(decisions)
    counts = {'SUPPORTED': 0, 'PARTIAL': 0, 'NOT_FOUND': 0, 'CONTRADICTED': 0, 'NO_SOURCE': 0, 'ERROR': 0, 'PARSE_ERROR': 0}

    # Pre-compute source matching (fast, no API calls)
    decision_sources = []
    for decision in decisions:
        relevant = find_relevant_source(decision, sources)
        decision_sources.append(relevant)

    print(f"  Workers: {workers} parallel" if workers > 1 else "  Workers: sequential")
    print()

    errors_found = []

    if workers == 1:
        # Sequential mode
        for i, decision in enumerate(decisions):
            print(f"  [{i+1}/{len(decisions)}] {decision['id']}: {decision['decision'][:60]}...", end='', flush=True)
            result = verify_decision(api_key, decision, decision_sources[i], args.model)
            result['decision'] = decision
            result['sources_matched'] = list(decision_sources[i].keys())
            results[i] = result
            verdict = result['verdict']
            counts[verdict] = counts.get(verdict, 0) + 1
            print(f" -> {verdict} ({result['confidence']:.2f})")
            if verdict in ('ERROR', 'PARSE_ERROR'):
                errors_found.append(f"{decision['id']}: {result['explanation'][:100]}")
                print(f"\n  HARD STOP: GLM-5 failed on {decision['id']}. Aborting run.", file=sys.stderr)
                print(f"  Reason: {result['explanation'][:200]}", file=sys.stderr)
                print(f"\n  FAILED — {len(errors_found)} error(s). Fix GLM-5 issues before retrying.", file=sys.stderr)
                sys.exit(10)
            time.sleep(1.2)
    else:
        # Parallel mode with ThreadPoolExecutor
        import threading
        lock = threading.Lock()
        completed = [0]
        abort_flag = threading.Event()

        def process_decision(idx):
            if abort_flag.is_set():
                return idx, {'verdict': 'SKIPPED', 'confidence': 0, 'explanation': 'Aborted due to prior error', 'issues': [], 'decision': decisions[idx], 'sources_matched': []}
            decision = decisions[idx]
            relevant = decision_sources[idx]
            # Small stagger to avoid burst rate limits
            time.sleep(idx * 0.3)
            if abort_flag.is_set():
                return idx, {'verdict': 'SKIPPED', 'confidence': 0, 'explanation': 'Aborted due to prior error', 'issues': [], 'decision': decision, 'sources_matched': []}
            result = verify_decision(api_key, decision, relevant, args.model)
            result['decision'] = decision
            result['sources_matched'] = list(relevant.keys())
            with lock:
                completed[0] += 1
                n = completed[0]
            verdict = result['verdict']
            if verdict in ('ERROR', 'PARSE_ERROR'):
                abort_flag.set()
            print(f"  [{n}/{len(decisions)}] {decision['id']}: {decision['decision'][:40]}... -> {verdict} ({result['confidence']:.2f})")
            return idx, result

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_decision, i): i for i in range(len(decisions))}
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                verdict = result['verdict']
                counts[verdict] = counts.get(verdict, 0) + 1
                if verdict in ('ERROR', 'PARSE_ERROR'):
                    errors_found.append(f"{result['decision']['id']}: {result['explanation'][:100]}")

    # Hard stop check after parallel completion
    if errors_found:
        print(f"\n  HARD STOP: GLM-5 failed on {len(errors_found)} decision(s):", file=sys.stderr)
        for err in errors_found:
            print(f"    - {err}", file=sys.stderr)
        print(f"\n  FAILED — Fix GLM-5 issues before retrying. No fallback.", file=sys.stderr)
        sys.exit(10)

    # Generate report
    total = len(decisions)
    supported = counts.get('SUPPORTED', 0)
    partial = counts.get('PARTIAL', 0)
    not_found = counts.get('NOT_FOUND', 0)
    contradicted = counts.get('CONTRADICTED', 0)
    no_source = counts.get('NO_SOURCE', 0)
    errors = counts.get('ERROR', 0) + counts.get('PARSE_ERROR', 0)

    report = f"""# GLM Fact-Check Audit Report

**Report:** `{Path(args.decisions_file).name}`
**Sources:** `{args.sources}`
**Date:** {time.strftime('%Y-%m-%d %H:%M')} | **Engine:** Z.AI {args.model} | **Endpoint:** Coding Plan

## Summary

| Verdict | Count | % |
|---------|-------|---|
| SUPPORTED | {supported} | {supported*100//total if total else 0}% |
| PARTIAL | {partial} | {partial*100//total if total else 0}% |
| NOT_FOUND | {not_found} | {not_found*100//total if total else 0}% |
| CONTRADICTED | {contradicted} | {contradicted*100//total if total else 0}% |
| NO_SOURCE | {no_source} | {no_source*100//total if total else 0}% |
| ERROR | {errors} | {errors*100//total if total else 0}% |
| **Total** | **{total}** | **100%** |

"""

    # CONTRADICTED claims (highest priority)
    if contradicted > 0:
        report += "## CONTRADICTED Claims (Source Says Different)\n\n"
        for r in results:
            if r['verdict'] == 'CONTRADICTED':
                d = r['decision']
                report += f"### {d['id']} (Line {d['line']})\n"
                report += f"**Claim:** {d['decision']} — {d['value'][:100]}\n"
                report += f"**Cited:** {d['source']}\n"
                report += f"**Confidence:** {r['confidence']:.2f}\n"
                report += f"**Explanation:** {r['explanation']}\n"
                if r['issues']:
                    report += f"**Issues:** {'; '.join(r['issues'])}\n"
                report += f"**Sources checked:** {', '.join(r['sources_matched'])}\n\n"

    # NOT_FOUND claims
    if not_found > 0:
        report += "## NOT_FOUND Claims (Not In Source)\n\n"
        for r in results:
            if r['verdict'] == 'NOT_FOUND':
                d = r['decision']
                report += f"### {d['id']} (Line {d['line']})\n"
                report += f"**Claim:** {d['decision']} — {d['value'][:100]}\n"
                report += f"**Cited:** {d['source']}\n"
                report += f"**Confidence:** {r['confidence']:.2f}\n"
                report += f"**Explanation:** {r['explanation']}\n"
                report += f"**Sources checked:** {', '.join(r['sources_matched'])}\n\n"

    # PARTIAL claims
    if partial > 0:
        report += "## PARTIAL Claims (Partially Supported)\n\n"
        for r in results:
            if r['verdict'] == 'PARTIAL':
                d = r['decision']
                report += f"### {d['id']} (Line {d['line']})\n"
                report += f"**Claim:** {d['decision']} — {d['value'][:100]}\n"
                report += f"**Confidence:** {r['confidence']:.2f}\n"
                report += f"**Explanation:** {r['explanation']}\n"
                if r['issues']:
                    report += f"**Issues:** {'; '.join(r['issues'])}\n"
                report += "\n"

    # ERROR claims (for debugging)
    if errors > 0:
        report += f"## ERROR Claims ({errors})\n\n"
        report += "These decisions failed due to API timeout or response parsing issues.\n\n"
        report += "| # | ID | Decision | Error |\n"
        report += "|---|-----|----------|-------|\n"
        for i, r in enumerate(results):
            if r['verdict'] in ('ERROR', 'PARSE_ERROR'):
                d = r['decision']
                report += f"| {i+1} | {d['id']} | {d['decision'][:50]} | {r['explanation'][:80]} |\n"
        report += "\n"

    # SUPPORTED claims (collapsed)
    if supported > 0:
        report += f"## SUPPORTED Claims ({supported})\n\n"
        report += "<details>\n<summary>Click to expand</summary>\n\n"
        report += "| # | ID | Decision | Confidence | Sources |\n"
        report += "|---|-----|----------|------------|--------|\n"
        for i, r in enumerate(results):
            if r['verdict'] == 'SUPPORTED':
                d = r['decision']
                report += f"| {i+1} | {d['id']} | {d['decision'][:50]} | {r['confidence']:.2f} | {', '.join(r['sources_matched'])} |\n"
        report += "\n</details>\n"

    # Write report
    Path(args.output).write_text(report, encoding='utf-8')
    print(f"\nReport written to: {args.output}")
    print(f"\nFinal: {supported} SUPPORTED, {partial} PARTIAL, {not_found} NOT_FOUND, {contradicted} CONTRADICTED")

    # Exit code: 0 = all good, 1 = has contradictions, 2 = has not_found
    if contradicted > 0:
        sys.exit(1)
    elif not_found > 0:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
