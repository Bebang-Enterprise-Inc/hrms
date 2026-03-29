# Pipeline Plan: Marketing Manager (Job ID 91200000) - 150 Applicants

## Step-by-Step Pipeline

### Phase 1: Login + GraphQL Capture

1. Launch Playwright with `chromium.launchPersistentContext('recruitment/.seek-browser-data/', { headless: true, acceptDownloads: true })` to preserve session across runs.
2. Navigate to `https://ph.employer.seek.com/jobs` to trigger the OAuth login flow on `authenticate.seek.com`.
3. Fill `input[id="emailAddress"]` with sam@bebang.ph, `input[id="password"]` with password from Doppler (never hardcoded), click `button:has-text("Sign in")`, wait 8 seconds for OAuth redirect.
4. Navigate to `https://ph.employer.seek.com/candidates/?jobid=91200000` with cache disabled via CDP (`Network.setCacheDisabled`).
5. Intercept the `Applications` GraphQL request via `page.on('request')` to capture `queryTemplate` and `authToken` (Bearer token from the Authorization header).

### Phase 2: Fetch ALL Candidates via GraphQL Replay

1. Replay the captured GraphQL query for **each of the 7 status folders**: INBOX, PRESCREEN, SHORTLIST, INTERVIEW, OFFER, ACCEPT, NOT_SUITABLE.
2. For each folder, paginate from page 1 up to 20 (break when `apps.result` is empty or `pageNum >= totalPages`).
3. Use `context.request.post()` for the GraphQL call -- NOT `page.evaluate(fetch())`, because fetch inside page context does not carry the Authorization header.
4. Include required auxiliary variables: `nationalitiesInput2`, `displayLabelInput2`, `countryNameInput2`, `displayDescriptionInput2`.
5. Deduplicate all candidates by `adcentreProspectId` using a Map.
6. After all folders are scraped, check for session loss after every `page.goto()` using the `ensureLoggedIn()` pattern (detect URL containing 'login' or 'authenticate', re-login if so).

**Expected output:** ~150 unique candidate objects with full profile data (name, email, phone, work history, education, skills, screening Q&A, fit assessment, resume metadata).

### Phase 3: Save Structured Data

1. Write `recruitment/marketing-manager/all_candidates.json` -- raw GraphQL SSOT.
2. Generate `recruitment/marketing-manager/candidates_summary.csv` -- spreadsheet-ready with columns for name, email, phone, current role, employer, applied date, status folder, fit level, screening answers pass/fail.
3. Generate individual `recruitment/marketing-manager/profiles/{Sanitized_Name}.md` files -- one per candidate with structured career history, education, skills, screening Q&A.

### Phase 4: Resume Downloads (Parallelized)

#### Chunk Size and Agent Count

- **150 candidates / 6 agents = 25 candidates per chunk.**
- 6 agents is the skill's recommended max for parallelization. Each browser instance uses ~700MB RAM, so 6 agents = ~4.2GB total.
- Expected time: ~3 minutes (based on the skill's benchmark of 270 candidates in 3 min with 6 agents).

#### Chunk Preparation

```python
# Split into 6 chunk files
chunk_size = (150 + 5) // 6  # = 26 (last chunk gets remainder)
# Output: recruitment/chunk_0.json through recruitment/chunk_5.json
```

Each chunk JSON contains objects with `jobId`, `folder`, `pid` (adcentreProspectId), and `name`.

#### Per-Agent Execution

Each of the 6 agents gets a prompt to:
1. Login to ph.employer.seek.com (sam@bebang.ph).
2. For each candidate in its chunk file, navigate to: `https://ph.employer.seek.com/candidates/?jobid=91200000&selected={pid}&tab=resume`
3. Wait 4 seconds for SPA to render the PDF viewer.
4. Call `ensureLoggedIn(page)` after every `page.goto()`.
5. Locate the download button via `button[aria-label="Download document"]` (the 4th icon button in the resume toolbar -- NOT by text, class, or position).
6. Use `Promise.all([page.waitForEvent('download'), dlBtn.click()])` pattern.
7. Save to `recruitment/marketing-manager/resumes/{Sanitized_Name}.{ext}`.
8. **Skip if file already exists** (check for .pdf/.doc/.docx/.rtf).
9. If no download button visible, skip -- candidate applied via SEEK profile only (no uploaded file). Their career data is already in the GraphQL response.

### Phase 5: Text Extraction

Run `python scripts/extract_resumes.py` which routes by file type:
- PDF -> PyMuPDF (fast, local)
- DOCX -> python-docx
- DOC -> PyMuPDF
- Fallback: Gemini API for PDFs with <100 chars extracted

Output: `recruitment/marketing-manager/extracted/{Name}.txt` + `_manifest.json`

### Phase 6: Cleanup

1. Kill orphaned Playwright browsers: `Get-Process | Where-Object { $_.Path -match 'ms-playwright' } | Stop-Process -Force`
2. Remove temporary chunk files (`recruitment/chunk_*.json`).
3. Ensure every script has `await context.close(); await browser.close()` in a finally block.

---

## Output Files Produced

```
recruitment/
  marketing-manager/
    all_candidates.json          # Raw GraphQL data (SSOT) -- ~150 records
    candidates_summary.csv       # Flat spreadsheet with key fields
    profiles/                    # ~150 .md files, one per candidate
      John_Smith.md
      ...
    resumes/                     # Downloaded resume files (PDF/DOCX/DOC)
      John_Smith.pdf
      ...
    extracted/                   # Plain text from resumes
      John_Smith.txt
      _manifest.json
      ...
  chunk_0.json ... chunk_5.json  # Temporary (deleted after Phase 6)
```

---

## Gotchas to Watch For

| Gotcha | Why It Matters | Mitigation |
|--------|---------------|------------|
| **Session loss after every `page.goto()`** | SEEK's OAuth redirects can silently log you out on any navigation | Run `ensureLoggedIn()` after EVERY `page.goto()` -- check URL for 'login' or 'authenticate' |
| **GraphQL only returns ONE status folder at a time** | Initial page load returns INBOX only; URL params like `?statusFolder=inbox` do NOT work | Must replay the GraphQL query once per each of the 7 status folders |
| **`page.evaluate(fetch())` loses auth** | fetch() inside page context does NOT carry the Bearer token | Always use `context.request.post()` for API calls |
| **`waitUntil: 'networkidle'` hangs** | SEEK's SPA never fully settles | Use `waitUntil: 'load'` and add a manual 4-second wait |
| **Cloudflare Turnstile anti-bot** | headless:true may be blocked on some runs | Fall back to `headless: false` with `launchPersistentContext` if login fails repeatedly |
| **Download button selector fragility** | Text, class, and position change across SEEK deployments | Use ONLY `button[aria-label="Download document"]` -- the aria-label is stable |
| **Candidates with no resume file** | Some apply via SEEK profile only | Check `metadata.result.hasResume` or handle missing download button gracefully (skip) |
| **Playwright v1.57+ memory bug** | 20GB memory bug with Chrome for Testing | Pin to Playwright v1.56.x |
| **Orphaned browser processes** | Playwright browsers survive script crashes | Always close in finally block + run orphan cleanup in Phase 6 |
| **Job ID must be integer in GraphQL** | String job ID causes silent empty results | Pass `91200000` as integer, not `"91200000"` |
| **6 concurrent logins = possible rate limit** | SEEK may throttle parallel OAuth flows | Stagger agent starts by 5-10 seconds if login failures occur |
| **Deduplication required** | Same candidate can appear in multiple status folders | Deduplicate by `adcentreProspectId` using a Map |

---

## Assumptions Made

1. **Job ID 91200000 is valid and accessible** from the sam@bebang.ph employer account. The skill only lists two known job IDs (91094834, 91090632); this is a new one.
2. **Folder name:** Using `marketing-manager` as the job folder slug (skill convention is kebab-case of job title).
3. **Password** will be obtained from conversation context or Doppler at runtime -- never hardcoded.
4. **150 applicants** distributed across the 7 status folders; exact distribution unknown until Phase 2 completes.
5. **Existing scripts** (`seek_final_v2.mjs`, `seek_dl_missing.mjs`, `extract_resumes.py`) are still functional and can be adapted for this job ID with minimal changes.
6. **RAM availability:** 4.2GB for 6 parallel browser instances is within machine capacity.
