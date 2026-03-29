"""
Extract text from all files in 3MD Investigation folder using Gemini API.
- Images (JPEG/PNG): Gemini 2.0 Flash
- PDFs: Gemini 2.5 Flash
Output: one .md per file + manifest JSON
"""

import os
import sys
import json
import time
import pathlib
import mimetypes
from datetime import datetime

from google import genai

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GEMINI_API_KEY", "")
INPUT_DIR = pathlib.Path(r"F:\Downloads\3MD Investigation")
OUTPUT_DIR = pathlib.Path(r"F:\Dropbox\Projects\BEI-ERP\data\Audits\Herdie\_local_extracted\3MD_Investigation")

IMAGE_MODEL = "gemini-2.0-flash"
PDF_MODEL = "gemini-2.5-flash-preview-05-20"

ANTI_HALLUCINATION_PROMPT = (
    "Extract ALL text, numbers, tables, and data VERBATIM from this image/document. "
    "This is a billing/contract document — every number matters. "
    "Do NOT interpret or summarize. If text is illegible write [ILLEGIBLE]. "
    "For tables, preserve the table structure using markdown tables. "
    "For multi-page documents, clearly separate each page with '--- Page N ---' markers."
)

# ── Setup ───────────────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
client = genai.Client(api_key=API_KEY)

# ── Collect files ───────────────────────────────────────────────────────
files = sorted(INPUT_DIR.iterdir())
image_exts = {".jpeg", ".jpg", ".png"}
pdf_exts = {".pdf"}

manifest = {
    "extraction_date": datetime.now().isoformat(),
    "source_dir": str(INPUT_DIR),
    "output_dir": str(OUTPUT_DIR),
    "tag": "3md_billing",
    "model_image": IMAGE_MODEL,
    "model_pdf": PDF_MODEL,
    "files": []
}

def slugify(name: str) -> str:
    """Turn filename into a safe slug for the .md output."""
    return name.replace(" ", "_").replace(".", "_").replace("(", "").replace(")", "")

def extract_image(filepath: pathlib.Path) -> str:
    """Extract text from an image file using Gemini vision."""
    mime = mimetypes.guess_type(str(filepath))[0] or "image/jpeg"

    # Upload the file
    print(f"  Uploading {filepath.name} ({filepath.stat().st_size / 1024:.0f} KB)...")
    uploaded = client.files.upload(file=filepath)

    print(f"  Extracting with {IMAGE_MODEL}...")
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=[
            ANTI_HALLUCINATION_PROMPT,
            uploaded,
        ],
    )
    return response.text

def extract_pdf(filepath: pathlib.Path) -> str:
    """Extract text from a PDF using Gemini."""
    print(f"  Uploading {filepath.name} ({filepath.stat().st_size / 1024 / 1024:.1f} MB)...")
    uploaded = client.files.upload(file=filepath)

    # Wait for processing
    while uploaded.state.name == "PROCESSING":
        print("  Waiting for PDF processing...")
        time.sleep(3)
        uploaded = client.files.get(name=uploaded.name)

    if uploaded.state.name == "FAILED":
        return f"[PDF PROCESSING FAILED: {uploaded.state}]"

    print(f"  Extracting with {PDF_MODEL}...")
    response = client.models.generate_content(
        model=PDF_MODEL,
        contents=[
            ANTI_HALLUCINATION_PROMPT,
            uploaded,
        ],
    )
    return response.text

def write_output(filename: str, extracted_text: str, model_used: str, file_type: str, source_size: int):
    """Write extraction result as markdown with YAML frontmatter."""
    slug = slugify(filename)
    out_path = OUTPUT_DIR / f"{slug}.md"

    frontmatter = f"""---
source_file: "{filename}"
extraction_date: "{datetime.now().isoformat()}"
model: "{model_used}"
file_type: "{file_type}"
source_size_bytes: {source_size}
tag: "3md_billing"
---

# Extraction: {filename}

{extracted_text}
"""
    out_path.write_text(frontmatter, encoding="utf-8")
    return out_path

# ── Main extraction loop ───────────────────────────────────────────────
total = len(files)
success = 0
errors = 0

for i, f in enumerate(files, 1):
    if not f.is_file():
        continue

    ext = f.suffix.lower()
    print(f"\n[{i}/{total}] {f.name}")

    try:
        if ext in image_exts:
            text = extract_image(f)
            model_used = IMAGE_MODEL
            file_type = "image"
        elif ext in pdf_exts:
            text = extract_pdf(f)
            model_used = PDF_MODEL
            file_type = "pdf"
        else:
            print(f"  SKIPPED (unsupported type: {ext})")
            continue

        out_path = write_output(f.name, text, model_used, file_type, f.stat().st_size)
        print(f"  OK -> {out_path.name} ({len(text)} chars)")

        manifest["files"].append({
            "source": f.name,
            "output": out_path.name,
            "model": model_used,
            "file_type": file_type,
            "source_size_bytes": f.stat().st_size,
            "extracted_chars": len(text),
            "status": "success"
        })
        success += 1

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    except Exception as e:
        print(f"  ERROR: {e}")
        manifest["files"].append({
            "source": f.name,
            "output": None,
            "model": model_used if ext in pdf_exts else IMAGE_MODEL,
            "file_type": "pdf" if ext in pdf_exts else "image",
            "source_size_bytes": f.stat().st_size,
            "extracted_chars": 0,
            "status": f"error: {str(e)}"
        })
        errors += 1
        time.sleep(2)  # Longer delay after error

# ── Write manifest ──────────────────────────────────────────────────────
manifest["summary"] = {
    "total_files": total,
    "success": success,
    "errors": errors,
    "total_extracted_chars": sum(f["extracted_chars"] for f in manifest["files"])
}

manifest_path = OUTPUT_DIR / "_3md_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n{'='*60}")
print(f"DONE: {success} success, {errors} errors")
print(f"Manifest: {manifest_path}")
print(f"Total extracted chars: {manifest['summary']['total_extracted_chars']:,}")
