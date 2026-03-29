#!/usr/bin/env python3
"""Download and extract additional generic-named corporate docs."""

import asyncio
import io
import os
import re
import time
from pathlib import Path

BASE = Path(r"F:\Dropbox\Projects\BEI-ERP")
INDEX_FILE = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/CORPORATE_DOCS_DRIVE_INDEX_2026-03-29.txt"
DOWNLOAD_DIR = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/downloads"
EXTRACT_DIR = BASE / "data/Audits/Herdie/01_Evidence/Corporate_Docs/ALL_ENTITIES/extracted"
CREDS_FILE = BASE / "credentials/task-manager-service.json"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def get_extra_files():
    """Get files with generic names we haven't downloaded yet."""
    seen_ids = set()
    # Dedup by size to avoid downloading the same content multiple times
    seen_sizes = {}
    candidates = []

    for line in open(INDEX_FILE, 'r', encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('Total'):
            continue
        parts = line.rsplit('|', 2)
        if len(parts) < 3:
            continue
        filename = parts[0].strip()
        try:
            size_kb = int(parts[1].strip().replace('KB', '').strip())
        except:
            size_kb = 0
        file_id = parts[2].strip()

        if file_id in seen_ids:
            continue
        seen_ids.add(file_id)
        if size_kb == 0:
            continue

        fn_upper = filename.upper()

        # Generic AOI files
        is_generic_aoi = fn_upper in ['ARTICLES OF INCORPORATION.PDF']
        # signed BCVC AOI
        is_signed_aoi = 'signed' in filename.lower() and 'article' in filename.lower() and 'incorporat' in filename.lower()
        # Generic GIS
        is_generic_gis = fn_upper.startswith('GIS') and fn_upper not in ['GIS BEI.PDF', 'GIS PDF.PDF', 'GIS 2025_TRICERN.PDF', 'GIS-2025_NORTH EDSA.PDF']
        # Board resolutions (could have Herdie)
        is_board_res = 'BOARD' in fn_upper and 'RESOLUTION' in fn_upper

        if is_generic_aoi or is_signed_aoi or is_generic_gis or is_board_res:
            # Dedup by filename+size
            dedup_key = f"{fn_upper}|{size_kb}"
            if dedup_key in seen_sizes:
                continue
            seen_sizes[dedup_key] = True

            # Use file_id as part of filename to avoid collision
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
            if not safe_name.lower().endswith('.pdf') and not safe_name.lower().endswith('.docx'):
                safe_name += '.pdf'
            # Append short file_id to avoid name collision
            base, ext = os.path.splitext(safe_name)
            safe_name = f"{base}__{file_id[:8]}{ext}"

            candidates.append({
                'filename': filename,
                'safe_name': safe_name,
                'size_kb': size_kb,
                'file_id': file_id,
            })

    return candidates


def download_files(candidates):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_file(str(CREDS_FILE), scopes=SCOPES)
    delegated = credentials.with_subject("admin@bebang.ph")
    service = build("drive", "v3", credentials=delegated)

    downloaded = []
    for i, c in enumerate(candidates):
        dest = DOWNLOAD_DIR / c['safe_name']
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  [{i+1}/{len(candidates)}] SKIP (exists): {c['safe_name']}")
            downloaded.append(dest)
            continue

        try:
            request = service.files().get_media(fileId=c['file_id'], supportsAllDrives=True)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            with open(dest, 'wb') as f:
                f.write(fh.getvalue())
            downloaded.append(dest)
            print(f"  [{i+1}/{len(candidates)}] OK: {c['safe_name']} ({c['size_kb']}KB)")
        except Exception as e:
            print(f"  [{i+1}/{len(candidates)}] FAIL: {c['safe_name']}: {e}")
        time.sleep(0.1)

    return downloaded


async def extract_files(paths):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    semaphore = asyncio.Semaphore(8)

    async def extract_one(filepath):
        out_name = filepath.stem + ".md"
        out_path = EXTRACT_DIR / out_name
        if out_path.exists() and out_path.stat().st_size > 100:
            return out_path, None

        async with semaphore:
            try:
                uploaded = await asyncio.to_thread(client.files.upload, file=str(filepath))
                for _ in range(30):
                    status = await asyncio.to_thread(client.files.get, name=uploaded.name)
                    if status.state.name == "ACTIVE":
                        break
                    await asyncio.sleep(1)

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=[types.Content(parts=[
                        types.Part.from_uri(file_uri=uploaded.uri, mime_type="application/pdf"),
                        types.Part.from_text(text="Extract ALL text from this document VERBATIM. This is a Philippine SEC corporate document. Preserve all names, TIN numbers, share amounts, addresses, and officer titles exactly as written. If this is a scanned document, use OCR to extract all visible text."),
                    ])],
                )

                text = response.text if response.text else ""
                try:
                    await asyncio.to_thread(client.files.delete, name=uploaded.name)
                except:
                    pass

                if text:
                    with open(out_path, 'w', encoding='utf-8') as f:
                        f.write(f"# Extraction: {filepath.name}\n\n")
                        f.write(text)
                    return out_path, None
                return out_path, "Empty"
            except Exception as e:
                return out_path, str(e)

    tasks = [extract_one(p) for p in paths if p.suffix.lower() == '.pdf']
    results = []
    for coro in asyncio.as_completed(tasks):
        out, err = await coro
        if err:
            print(f"  EXTRACT FAIL: {out.name}: {err}")
        else:
            print(f"  EXTRACT OK: {out.name}")
            results.append(out)
    return results


def main():
    candidates = get_extra_files()
    print(f"Extra files to download: {len(candidates)}")
    for c in candidates:
        print(f"  {c['filename']} ({c['size_kb']}KB) -> {c['safe_name']}")

    print("\nDownloading...")
    downloaded = download_files(candidates)
    print(f"\nDownloaded: {len(downloaded)}")

    pdf_paths = [p for p in downloaded if p.suffix.lower() == '.pdf']
    print(f"\nExtracting {len(pdf_paths)} PDFs...")
    asyncio.run(extract_files(pdf_paths))

    print("\nDone! Now re-run herdie_deep_analysis.py to include new files.")


if __name__ == '__main__':
    main()
