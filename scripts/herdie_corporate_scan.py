#!/usr/bin/env python3
"""
Herdie Hernandez Corporate Role Scanner
========================================
Downloads AOI/GIS/Bylaws/Secretary Certs from Google Drive,
extracts text via Gemini 2.5 Flash, searches for Herdie's roles.

Usage: python scripts/herdie_corporate_scan.py [--skip-download] [--skip-extract] [--search-only]
"""

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(r"F:\Dropbox\Projects\BEI-ERP")
INDEX_FILE = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/CORPORATE_DOCS_DRIVE_INDEX_2026-03-29.txt"
DOWNLOAD_DIR = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/downloads"
EXTRACT_DIR = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/extracted"
OUTPUT_DIR = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES"
CREDS_FILE = BASE / "credentials/task-manager-service.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# ---------------------------------------------------------------------------
# Step 0: Parse the index file
# ---------------------------------------------------------------------------
def parse_index(index_path: Path) -> list[dict]:
    """Parse the drive index file into a list of {filename, size_kb, file_id}."""
    entries = []
    seen_ids = set()
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("Total unique"):
                continue
            # Format: filename | sizeKB | google_drive_file_id
            parts = line.rsplit("|", 2)
            if len(parts) < 3:
                continue
            filename = parts[0].strip()
            try:
                size_kb = int(parts[1].strip().replace("KB", "").strip())
            except ValueError:
                size_kb = 0
            file_id = parts[2].strip()

            # Deduplicate by file_id
            if file_id in seen_ids:
                continue
            seen_ids.add(file_id)

            entries.append({
                "filename": filename,
                "size_kb": size_kb,
                "file_id": file_id,
            })
    return entries


def filter_relevant(entries: list[dict]) -> list[dict]:
    """Filter to AOI, GIS, Bylaws, Secretary Certificates only."""
    patterns = [
        r'\bAOI\b',
        r'\bGIS\b',
        r'[Bb]y[- ]?[Ll]aws?',
        r'[Ss]ecretary\s*[Cc]ert',
        r'Articles?\s*of\s*Incorporat',
        r'General\s*Information\s*Sheet',
    ]
    combined = re.compile("|".join(patterns), re.IGNORECASE)

    relevant = []
    for e in entries:
        if combined.search(e["filename"]):
            # Skip 0KB files (folders) and very large files (>50MB likely not docs)
            if e["size_kb"] > 0:
                relevant.append(e)
    return relevant


# ---------------------------------------------------------------------------
# Step 1: Download from Google Drive
# ---------------------------------------------------------------------------
def get_drive_service(impersonate_email: str):
    """Create a Google Drive service using domain-wide delegation."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_file(
        str(CREDS_FILE), scopes=SCOPES
    )
    delegated = credentials.with_subject(impersonate_email)
    service = build("drive", "v3", credentials=delegated)
    return service


def download_file(service, file_id: str, dest_path: Path) -> bool:
    """Download a single file from Google Drive."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    try:
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        with open(dest_path, "wb") as f:
            f.write(fh.getvalue())
        return True
    except Exception as e:
        print(f"  ERROR downloading {file_id}: {e}")
        return False


def download_all(entries: list[dict], skip_existing: bool = True) -> dict[str, Path]:
    """Download all files, return mapping of file_id -> local_path."""
    print(f"\n{'='*60}")
    print(f"STEP 1: Downloading {len(entries)} files from Google Drive")
    print(f"{'='*60}")

    # Try admin@bebang.ph first, fall back to sam@bebang.ph
    service = None
    for email in ["admin@bebang.ph", "sam@bebang.ph"]:
        try:
            service = get_drive_service(email)
            # Test with first file
            service.files().get(
                fileId=entries[0]["file_id"],
                supportsAllDrives=True,
                fields="id,name"
            ).execute()
            print(f"  Using impersonation: {email}")
            break
        except Exception as e:
            print(f"  {email} failed: {e}")
            service = None

    if not service:
        print("ERROR: Could not authenticate with either account!")
        sys.exit(1)

    downloaded = {}
    failed = []
    skipped = 0

    for i, entry in enumerate(entries):
        # Sanitize filename
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', entry["filename"])
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"
        dest = DOWNLOAD_DIR / safe_name

        if skip_existing and dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            downloaded[entry["file_id"]] = dest
            if (i + 1) % 20 == 0:
                print(f"  Progress: {i+1}/{len(entries)} (skipped {skipped} existing)")
            continue

        ok = download_file(service, entry["file_id"], dest)
        if ok:
            downloaded[entry["file_id"]] = dest
        else:
            failed.append(entry)

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(entries)} downloaded, {len(failed)} failed, {skipped} skipped")

        # Rate limit
        time.sleep(0.1)

    print(f"\n  Done: {len(downloaded)} downloaded, {len(failed)} failed, {skipped} skipped")
    if failed:
        print(f"  Failed files: {[f['filename'] for f in failed[:10]]}")

    return downloaded


# ---------------------------------------------------------------------------
# Step 2: Extract text via Gemini 2.5 Flash
# ---------------------------------------------------------------------------
async def extract_single(client, filepath: Path, semaphore: asyncio.Semaphore) -> tuple[Path, str | None]:
    """Extract text from a single PDF using Gemini."""
    from google import genai
    from google.genai import types

    out_name = filepath.stem + ".md"
    out_path = EXTRACT_DIR / out_name

    # Skip if already extracted
    if out_path.exists() and out_path.stat().st_size > 100:
        return out_path, None

    async with semaphore:
        try:
            # Upload file
            uploaded = await asyncio.to_thread(
                client.files.upload,
                file=str(filepath),
            )

            # Wait for processing
            for _ in range(30):  # max 30 seconds
                status = await asyncio.to_thread(
                    client.files.get,
                    name=uploaded.name,
                )
                if status.state.name == "ACTIVE":
                    break
                await asyncio.sleep(1)

            # Extract text
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_uri(
                                file_uri=uploaded.uri,
                                mime_type="application/pdf",
                            ),
                            types.Part.from_text(
                                text="Extract ALL text from this document VERBATIM. This is a Philippine SEC corporate document. "
                                "Preserve all names, TIN numbers, share amounts, addresses, and officer titles exactly as written. "
                                "If this is a scanned document, use OCR to extract all visible text."
                            ),
                        ]
                    )
                ],
            )

            text = response.text if response.text else ""

            # Clean up uploaded file
            try:
                await asyncio.to_thread(client.files.delete, name=uploaded.name)
            except:
                pass

            if text:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(f"# Extraction: {filepath.name}\n\n")
                    f.write(text)
                return out_path, None
            else:
                return out_path, "Empty extraction"

        except Exception as e:
            return out_path, str(e)


async def extract_all(downloaded_paths: list[Path]) -> list[Path]:
    """Extract text from all PDFs using Gemini with concurrency."""
    from google import genai

    print(f"\n{'='*60}")
    print(f"STEP 2: Extracting {len(downloaded_paths)} PDFs via Gemini 2.5 Flash")
    print(f"{'='*60}")

    client = genai.Client(api_key=GEMINI_API_KEY)
    semaphore = asyncio.Semaphore(8)

    tasks = [extract_single(client, p, semaphore) for p in downloaded_paths]

    extracted = []
    failed = []
    skipped = 0
    done_count = 0

    for coro in asyncio.as_completed(tasks):
        out_path, error = await coro
        done_count += 1

        if error is None:
            extracted.append(out_path)
            if out_path.exists() and out_path.stat().st_size > 100:
                # Could be pre-existing (skipped)
                pass
        else:
            failed.append((out_path.name, error))

        if done_count % 20 == 0:
            print(f"  Progress: {done_count}/{len(downloaded_paths)} extracted, {len(failed)} failed")

    print(f"\n  Done: {len(extracted)} extracted, {len(failed)} failed")
    if failed:
        for name, err in failed[:10]:
            print(f"    FAILED: {name}: {err}")

    return extracted


# ---------------------------------------------------------------------------
# Step 3: Search for Herdie
# ---------------------------------------------------------------------------
def search_extractions() -> list[dict]:
    """Search all extracted .md files for Herdie references."""
    print(f"\n{'='*60}")
    print("STEP 3: Searching extractions for Herdie Hernandez")
    print(f"{'='*60}")

    patterns = [
        re.compile(r'Hernandez', re.IGNORECASE),
        re.compile(r'Hernando', re.IGNORECASE),
        re.compile(r'Herdie', re.IGNORECASE),
        re.compile(r'129[- ]?368[- ]?335', re.IGNORECASE),  # TIN
    ]

    matches = []
    md_files = sorted(EXTRACT_DIR.glob("*.md"))
    print(f"  Scanning {len(md_files)} extracted files...")

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except:
            continue

        # Check if any pattern matches
        found_patterns = []
        for p in patterns:
            if p.search(content):
                found_patterns.append(p.pattern)

        if not found_patterns:
            continue

        # Now parse details
        source_filename = md_file.stem  # Original PDF name (without .md)

        # Try to identify company name from content
        company_name = extract_company_name(content, source_filename)

        # Identify Herdie's roles
        roles = extract_herdie_roles(content)

        # Extract shares
        shares = extract_herdie_shares(content)

        # Extract entity code from filename
        entity_code = extract_entity_code(source_filename)

        matches.append({
            "source_file": md_file.name,
            "source_pdf": source_filename,
            "company_name": company_name,
            "entity_code": entity_code,
            "roles": roles,
            "shares": shares,
            "matched_patterns": found_patterns,
        })

        print(f"  MATCH: {company_name} - Roles: {', '.join(roles)} - {source_filename}")

    print(f"\n  Total matches: {len(matches)} files mentioning Hernandez/Hernando/Herdie")
    return matches


def extract_company_name(content: str, filename: str) -> str:
    """Try to extract the company/corporation name from the document content."""
    # Common patterns in SEC docs
    patterns = [
        # AOI patterns
        r'(?:Articles of Incorporation|ARTICLES OF INCORPORATION)\s*(?:of|OF)\s+([A-Z][A-Z\s&.,\'-]+(?:INC|CORP|OPC|LLC|CORPORATION|INCORPORATED)\.?)',
        r'(?:CORPORATE NAME|Corporate Name)[:\s]+([A-Z][A-Z\s&.,\'-]+(?:INC|CORP|OPC|LLC|CORPORATION|INCORPORATED)\.?)',
        # GIS patterns
        r'(?:SEC Registration|COMPANY NAME|Company Name)[:\s]+([A-Z][A-Z\s&.,\'-]+(?:INC|CORP|OPC|LLC|CORPORATION|INCORPORATED)\.?)',
        r'(?:General Information Sheet|GENERAL INFORMATION SHEET)\s*(?:of|OF|for|FOR)\s+([A-Z][A-Z\s&.,\'-]+)',
        # Broad pattern
        r'(?:hereby organize|HEREBY ORGANIZE)\s+(?:a|A)\s+(?:corporation|CORPORATION)\s+(?:under the name|UNDER THE NAME)\s+(?:of\s+)?["\']?([A-Z][A-Z\s&.,\'-]+)',
    ]

    for pat in patterns:
        m = re.search(pat, content)
        if m:
            name = m.group(1).strip().strip('"\'.,')
            if len(name) > 5:
                return name

    # Fall back to filename parsing
    return clean_company_from_filename(filename)


def clean_company_from_filename(filename: str) -> str:
    """Extract company name from filename."""
    # Remove common prefixes/suffixes
    name = filename
    for remove in ["AOI", "GIS", "By-Laws", "Bylaws", "Secretary Certificate",
                    "Annual", "2316", "2023", "2024", "2025", "2026",
                    "(Signed)", "(Not Signed)", "01.", "02.", "03.", "04.", "05.",
                    "1.", "2.", "3.", "4.", "5.", ".pdf", "_", "-"]:
        name = name.replace(remove, " ")
    name = re.sub(r'\s+', ' ', name).strip()
    return name if name else filename


def extract_herdie_roles(content: str) -> list[str]:
    """Extract Herdie's specific roles from the document."""
    roles = set()
    content_lower = content.lower()

    # Check if Hernandez/Hernando/Herdie appears near role keywords
    # Look for lines containing both the name and role indicators
    lines = content.split('\n')

    herdie_pattern = re.compile(r'(?:hernandez|hernando|herdie)', re.IGNORECASE)

    for i, line in enumerate(lines):
        if not herdie_pattern.search(line):
            # Also check nearby lines (context window of 3 lines)
            context = '\n'.join(lines[max(0,i-3):min(len(lines),i+4)])
            if not herdie_pattern.search(context):
                continue
            # Only use context if current line has a role keyword
            if not any(kw in line.lower() for kw in ['director', 'officer', 'incorporator', 'shareholder',
                                                       'stockholder', 'secretary', 'president', 'treasurer',
                                                       'chairman', 'vice', 'member', 'board']):
                continue

        line_lower = line.lower()

        if 'incorporator' in line_lower:
            roles.add('Incorporator')
        if 'director' in line_lower or 'board of director' in line_lower:
            roles.add('Director')
        if 'chairman' in line_lower:
            roles.add('Chairman')
        if 'president' in line_lower and 'vice' not in line_lower:
            roles.add('President')
        if 'vice president' in line_lower or 'vice-president' in line_lower:
            roles.add('Vice President')
        if 'secretary' in line_lower and 'corporate secretary' in line_lower:
            roles.add('Corporate Secretary')
        elif 'secretary' in line_lower:
            roles.add('Secretary')
        if 'treasurer' in line_lower:
            roles.add('Treasurer')
        if 'shareholder' in line_lower or 'stockholder' in line_lower:
            roles.add('Shareholder')
        if 'subscriber' in line_lower:
            roles.add('Subscriber/Incorporator')
        if 'officer' in line_lower:
            roles.add('Officer')

    # If we found the name but no specific roles, mark as "Named in document"
    if not roles:
        roles.add('Named in document')

    return sorted(roles)


def extract_herdie_shares(content: str) -> str:
    """Extract share information near Herdie's name."""
    # Look for share amounts near Hernandez
    herdie_sections = []
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if re.search(r'(?:hernandez|hernando|herdie)', line, re.IGNORECASE):
            context = '\n'.join(lines[max(0,i-2):min(len(lines),i+3)])
            herdie_sections.append(context)

    for section in herdie_sections:
        # Look for share numbers
        share_match = re.search(r'(\d[\d,]*)\s*(?:shares?|shs?)', section, re.IGNORECASE)
        if share_match:
            return share_match.group(1) + " shares"

        # Look for amounts
        amount_match = re.search(r'(?:P|PHP|₱)\s*([\d,]+(?:\.\d{2})?)', section)
        if amount_match:
            return "P" + amount_match.group(1)

    return ""


def extract_entity_code(filename: str) -> str:
    """Try to extract entity code from filename."""
    # Common patterns: BEI, BKI, BCFC, DMD, etc.
    codes = re.findall(r'\b([A-Z]{2,5})\b', filename.upper())
    # Filter out common non-codes
    ignore = {'AOI', 'GIS', 'PDF', 'INC', 'OPC', 'SEC', 'COI', 'THE', 'AND', 'FOR', 'NOT'}
    codes = [c for c in codes if c not in ignore]
    return codes[0] if codes else ""


# ---------------------------------------------------------------------------
# Step 4: Write results
# ---------------------------------------------------------------------------
def write_results(matches: list[dict]):
    """Write results to MD and JSON files."""
    print(f"\n{'='*60}")
    print("STEP 4: Writing results")
    print(f"{'='*60}")

    # Deduplicate by company name (merge roles from multiple docs)
    companies = {}
    for m in matches:
        key = m["company_name"].upper().strip()
        if key not in companies:
            companies[key] = {
                "company_name": m["company_name"],
                "entity_code": m["entity_code"],
                "roles": set(m["roles"]),
                "shares": m["shares"],
                "source_files": [m["source_pdf"]],
            }
        else:
            companies[key]["roles"].update(m["roles"])
            if m["shares"] and not companies[key]["shares"]:
                companies[key]["shares"] = m["shares"]
            if m["source_pdf"] not in companies[key]["source_files"]:
                companies[key]["source_files"].append(m["source_pdf"])
            if m["entity_code"] and not companies[key]["entity_code"]:
                companies[key]["entity_code"] = m["entity_code"]

    # Sort by company name
    sorted_companies = sorted(companies.values(), key=lambda x: x["company_name"])

    # Write Markdown
    md_path = OUTPUT_DIR / "HERDIE_ALL_COMPANIES_2026-03-29.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Herdie Hernandez -- All Corporate Roles\n\n")
        f.write(f"**Generated:** 2026-03-29\n")
        f.write(f"**Source:** {len(matches)} document matches across {len(companies)} unique entities\n")
        f.write(f"**Search terms:** Hernandez, Hernando, Herdie, TIN 129-368-335-000\n\n")

        f.write("| # | Entity Name | Entity Code | Role(s) | Shares | Source Document(s) |\n")
        f.write("|---|-------------|-------------|---------|--------|--------------------|\n")

        for i, comp in enumerate(sorted_companies, 1):
            roles_str = ", ".join(sorted(comp["roles"]))
            sources_str = "; ".join(comp["source_files"][:3])
            if len(comp["source_files"]) > 3:
                sources_str += f" (+{len(comp['source_files'])-3} more)"
            f.write(f"| {i} | {comp['company_name']} | {comp['entity_code']} | {roles_str} | {comp['shares']} | {sources_str} |\n")

        f.write(f"\n**Total entities: {len(sorted_companies)}**\n")

    print(f"  Written: {md_path}")

    # Write JSON
    json_path = OUTPUT_DIR / "HERDIE_ALL_COMPANIES_2026-03-29.json"
    json_data = []
    for i, comp in enumerate(sorted_companies, 1):
        json_data.append({
            "index": i,
            "entity_name": comp["company_name"],
            "entity_code": comp["entity_code"],
            "roles": sorted(comp["roles"]),
            "shares": comp["shares"],
            "source_documents": comp["source_files"],
        })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"  Written: {json_path}")

    return md_path, json_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    skip_download = "--skip-download" in sys.argv
    skip_extract = "--skip-extract" in sys.argv
    search_only = "--search-only" in sys.argv

    if not GEMINI_API_KEY and not search_only:
        print("ERROR: GEMINI_API_KEY not set!")
        sys.exit(1)

    # Parse index
    print("Parsing drive index...")
    all_entries = parse_index(INDEX_FILE)
    print(f"  Total entries: {len(all_entries)}")

    relevant = filter_relevant(all_entries)
    print(f"  Relevant (AOI/GIS/Bylaws/SecCert): {len(relevant)}")

    # Deduplicate by content hash (filename + size)
    seen = set()
    deduped = []
    for e in relevant:
        key = f"{e['filename']}|{e['size_kb']}"
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    print(f"  After dedup: {len(deduped)}")

    # Step 1: Download
    if not skip_download and not search_only:
        downloaded = download_all(deduped)
    else:
        print("\nSkipping download (using existing files)")
        downloaded = {}
        for f in DOWNLOAD_DIR.glob("*.pdf"):
            downloaded[f.stem] = f

    # Step 2: Extract
    if not skip_extract and not search_only:
        pdf_paths = sorted(DOWNLOAD_DIR.glob("*.pdf"))
        print(f"\n  Found {len(pdf_paths)} PDFs to extract")
        extracted = asyncio.run(extract_all(pdf_paths))
    else:
        print("\nSkipping extraction (using existing files)")

    # Step 3: Search
    matches = search_extractions()

    # Step 4: Write
    if matches:
        md_path, json_path = write_results(matches)
        print(f"\n{'='*60}")
        print(f"COMPLETE!")
        print(f"  Entities found: {len(set(m['company_name'].upper() for m in matches))}")
        print(f"  MD report: {md_path}")
        print(f"  JSON data: {json_path}")
        print(f"{'='*60}")
    else:
        print("\nNo matches found for Herdie Hernandez in any extracted documents.")


if __name__ == "__main__":
    main()
