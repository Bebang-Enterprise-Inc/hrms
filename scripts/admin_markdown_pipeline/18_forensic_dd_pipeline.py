"""Forensic DD-grade OCR pipeline. Mistral OCR 3 + Gemini 3.1 Pro v2 → staging.

Processes admin PDFs at configurable concurrency, writing per-file staging plus
a canonical markdown file. Disagreements on critical fields are flagged for
Claude Opus 4.7 arbitration (see 18b_apply_arbitration.py).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from google import genai
from google.genai import types as genai_types
from google.oauth2 import service_account
from googleapiclient.discovery import build as gapi_build
from googleapiclient.http import MediaIoBaseDownload
from mistralai import Mistral
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
CREDS_PATH = REPO_ROOT / "credentials" / "task-manager-service.json"
DEDUPE_CSV = REPO_ROOT / "data" / "admin_drive_audit" / "03_dedupe_plan.csv"
REGISTRY_CSV = REPO_ROOT / "data" / "admin_drive_audit" / "company_registry.csv"
MD_ROOT = REPO_ROOT / "data" / "admin_markdown"
STAGING = MD_ROOT / "_staging"
MANIFEST = MD_ROOT / "_manifest.jsonl"
ERRORS = MD_ROOT / "_errors.jsonl"
ARB_LOG = MD_ROOT / "_arbitration_log.jsonl"

MISTRAL_MODEL = "mistral-ocr-latest"
GEMINI_PRO = "gemini-3.1-pro-preview"
IMPERSONATE = "sam@bebang.ph"
MAX_RETRIES = 2

CRITICAL_FIELDS = [
    "document_type", "business_name", "trade_name", "permit_number",
    "tin", "ocn", "psic_code", "issuing_authority",
    "issue_date", "expiry_date", "location_address", "registered_address",
    "signatories",
]


class Signatory(BaseModel):
    name: str
    title: str = ""


class BeiPermit(BaseModel):
    document_type: str = Field(
        description=(
            "One of: BIR_2303, SEC_AOI, SEC_BYLAWS, SEC_GIS, SEC_COI, SEC_CERT, "
            "SEC_BOARD_RES, SEC_COVER, SEC_FORM_SUMMARY, MAYORS_PERMIT, "
            "BARANGAY_CLEARANCE, BUILDING_PERMIT, FSIC, SANITARY, DOLE, LEASE, "
            "CONTRACT, INSURANCE, RECEIPT, CERT_OCCUPANCY, SALES_INVOICE, OTHER"
        )
    )
    business_name: str = ""
    trade_name: Optional[str] = None
    permit_number: Optional[str] = None
    tin: Optional[str] = None
    ocn: Optional[str] = None
    psic_code: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    location_address: Optional[str] = None
    registered_address: Optional[str] = None
    signatories: list[Signatory] = Field(default_factory=list)
    extraction_confidence: float = 0.0
    uncertain_fields: list[str] = Field(default_factory=list)


MISTRAL_FLAT_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string", "description": "One of: BIR_2303, SEC_AOI, SEC_BYLAWS, SEC_GIS, SEC_COI, SEC_CERT, SEC_BOARD_RES, SEC_COVER, SEC_FORM_SUMMARY, MAYORS_PERMIT, BARANGAY_CLEARANCE, BUILDING_PERMIT, FSIC, SANITARY, DOLE, LEASE, CONTRACT, INSURANCE, RECEIPT, CERT_OCCUPANCY, SALES_INVOICE, OTHER"},
        "business_name": {"type": "string"},
        "trade_name": {"type": "string"},
        "permit_number": {"type": "string"},
        "tin": {"type": "string", "description": "TIN with branch code"},
        "ocn": {"type": "string", "description": "BIR 2303 OCN, 20 digits"},
        "psic_code": {"type": "string", "description": "PSIC, 5 digits"},
        "issuing_authority": {"type": "string"},
        "issue_date": {"type": "string", "description": "ISO YYYY-MM-DD"},
        "expiry_date": {"type": "string", "description": "ISO YYYY-MM-DD"},
        "location_address": {"type": "string"},
        "registered_address": {"type": "string"},
        "signatories": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "title": {"type": "string"}}}, "description": "Every signatory: cover + body + notary + IDs"},
        "extraction_confidence": {"type": "number"},
        "uncertain_fields": {"type": "array", "items": {"type": "string"}},
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_maybe_truncated_json(text: str) -> dict:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    repaired = text.strip()
    depth_obj = depth_arr = 0
    in_str = escape = False
    for ch in repaired:
        if escape:
            escape = False; continue
        if ch == "\\":
            escape = True; continue
        if ch == '"':
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == "{": depth_obj += 1
        elif ch == "}": depth_obj -= 1
        elif ch == "[": depth_arr += 1
        elif ch == "]": depth_arr -= 1
    if in_str:
        last_quote = repaired.rfind('"')
        if last_quote >= 0:
            repaired = repaired[:last_quote]
    repaired = re.sub(r",\s*$", "", repaired.rstrip())
    for _ in range(max(depth_arr, 0)):
        repaired += "]"
    for _ in range(max(depth_obj, 0)):
        repaired += "}"
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return {"_parse_error": text[:400]}


def _norm(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join(sorted(_norm(x) for x in v))
    if isinstance(v, dict):
        if "name" in v:
            return _norm(v.get("name", ""))
        return json.dumps(v, sort_keys=True)
    if isinstance(v, BaseModel):
        return _norm(v.model_dump())
    s = str(v).strip().upper()
    s = re.sub(r"[\s,.;:\-_/()\[\]']+", " ", s)
    return s.strip()


def _fields_disagree(field: str, a: Any, b: Any) -> bool:
    na, nb = _norm(a), _norm(b)
    if na == nb:
        return False
    if not na or not nb:
        return True
    if field == "signatories":
        set_a = {x.strip() for x in na.split("|") if x.strip()}
        set_b = {x.strip() for x in nb.split("|") if x.strip()}
        if not set_a or not set_b:
            return True
        return set_a != set_b
    if field in {"tin", "ocn", "psic_code", "permit_number"}:
        return na != nb
    if na in nb or nb in na:
        return False
    return na != nb


def _md_path_for(row: dict) -> Path:
    entity = row.get("entity_code") or "UNKNOWN"
    permit = row.get("permit_code") or "UNKNOWN"
    dest_name = row.get("dest_name") or row.get("name") or "UNKNOWN.pdf"
    base = Path(dest_name).stem
    return MD_ROOT / entity / permit / f"{base}.md"


def _append_jsonl(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _load_manifest_ids() -> set[str]:
    done: set[str] = set()
    if not MANIFEST.exists():
        return done
    with MANIFEST.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "ok" and rec.get("file_id"):
                done.add(rec["file_id"])
    return done


def _load_registry() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not REGISTRY_CSV.exists():
        return out
    with REGISTRY_CSV.open("r", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            suffix = (row.get("corp_suffix") or "").strip()
            prefix = (row.get("store_prefix") or "").strip()
            abbr = (row.get("abbr") or "").strip()
            for key in {suffix, prefix, abbr}:
                if key:
                    out.setdefault(key.upper(), row)
    return out


def _drive_client():
    creds = service_account.Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    ).with_subject(IMPERSONATE)
    return gapi_build("drive", "v3", credentials=creds, cache_discovery=False)


def _download_pdf(drive, file_id: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest.stat().st_size
    request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    buf.seek(0)
    data = buf.read()
    dest.write_bytes(data)
    return len(data)


def run_mistral_sync(pdf_path: Path, client: Mistral) -> dict:
    t0 = time.perf_counter()
    content_bytes = pdf_path.read_bytes()
    up = client.files.upload(file={"file_name": pdf_path.name, "content": content_bytes}, purpose="ocr")
    signed = client.files.get_signed_url(file_id=up.id)
    t_up = time.perf_counter() - t0

    t1 = time.perf_counter()
    kwargs: dict[str, Any] = {
        "model": MISTRAL_MODEL,
        "document": {"type": "document_url", "document_url": signed.url},
        "document_annotation_format": {
            "type": "json_schema",
            "json_schema": {"schema": MISTRAL_FLAT_SCHEMA, "name": "BeiPermit", "strict": False},
        },
    }
    try:
        resp = client.ocr.process(**kwargs, table_format="markdown", extract_header=True, extract_footer=True, confidence_scores_granularity="page")
    except TypeError:
        resp = client.ocr.process(**kwargs)
    t_ocr = time.perf_counter() - t1

    raw = resp.model_dump() if hasattr(resp, "model_dump") else resp
    pages = raw.get("pages") or []
    body_parts: list[str] = []
    for i, page in enumerate(pages):
        conf = None
        cs = page.get("confidence_scores") if isinstance(page, dict) else None
        if isinstance(cs, dict):
            conf = cs.get("average_page_confidence_score")
        body_parts.append(f"## Page {i}  (confidence={conf})\n\n{page.get('markdown','')}\n")
    body_md = "\n".join(body_parts)

    structured_raw = raw.get("document_annotation")
    if isinstance(structured_raw, str):
        structured_raw = _parse_maybe_truncated_json(structured_raw)
    structured = structured_raw if isinstance(structured_raw, dict) else {}

    return {
        "structured": structured,
        "body_md": body_md,
        "meta": {
            "model": MISTRAL_MODEL,
            "upload_s": round(t_up, 2),
            "ocr_s": round(t_ocr, 2),
            "pages": len(pages),
            "cost_usd": round(len(pages) * 0.002, 4),
        },
    }


def _genai_client() -> genai.Client:
    return genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))


def run_gemini_sync(pdf_path: Path, client: genai.Client) -> dict:
    t0 = time.perf_counter()
    uploaded = client.files.upload(file=str(pdf_path))
    t_up = time.perf_counter() - t0

    structured_prompt = (
        "You are auditing a Philippine corporate or government compliance document "
        "for a forensic due-diligence data room. Read every page. Extract ALL schema "
        "fields.\n"
        "- document_type: pick the single best enum value.\n"
        "- tin: keep the branch code.\n"
        "- ocn: BIR 2303 OCN is typically 20 digits.\n"
        "- psic_code: 5 digits.\n"
        "- dates as ISO YYYY-MM-DD.\n"
        "- signatories: include EVERY signatory (cover, body, notary, IDs).\n"
        "- if a field is not visible, return null and list it in uncertain_fields."
    )

    schema = BeiPermit.model_json_schema()
    t1 = time.perf_counter()
    try:
        sresp = client.models.generate_content(
            model=GEMINI_PRO,
            contents=[uploaded, structured_prompt],
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema,
                thinking_config=genai_types.ThinkingConfig(thinking_level="high"),
                media_resolution="media_resolution_high",
                max_output_tokens=16384,
                temperature=0.0,
            ),
        )
        structured_text = sresp.text or ""
    except Exception as e:
        structured_text = json.dumps({"error": f"pro-structured failed: {e}"})
    t_struct = time.perf_counter() - t1

    structured = _parse_maybe_truncated_json(structured_text)

    body_prompt = (
        "Transcribe the document to clean markdown. Preserve headings, tables, and page "
        "boundaries. Use '## Page N' between pages. Do not summarize; do not drop text."
    )
    t2 = time.perf_counter()
    try:
        bresp = client.models.generate_content(
            model=GEMINI_PRO,
            contents=[uploaded, body_prompt],
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_level="medium"),
                media_resolution="media_resolution_high",
                max_output_tokens=32768,
                temperature=0.0,
            ),
        )
        body_md = bresp.text or ""
    except Exception as e:
        body_md = f"[Gemini body call failed: {e}]"
    t_body = time.perf_counter() - t2

    return {
        "structured": structured,
        "body_md": body_md,
        "meta": {
            "model": GEMINI_PRO,
            "upload_s": round(t_up, 2),
            "structured_s": round(t_struct, 2),
            "body_s": round(t_body, 2),
        },
    }


def detect_disagreements(m: dict, g: dict) -> list[dict]:
    return [
        {"field": f, "mistral": m.get(f), "gemini": g.get(f)}
        for f in CRITICAL_FIELDS
        if _fields_disagree(f, m.get(f), g.get(f))
    ]


def canonical_fields(m: dict, g: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in CRITICAL_FIELDS:
        mv, gv = m.get(f), g.get(f)
        if _fields_disagree(f, mv, gv):
            if f == "signatories":
                union: dict[str, dict] = {}
                for item in (mv or []) + (gv or []):
                    if isinstance(item, dict):
                        key = _norm(item.get("name", ""))
                        if key:
                            union.setdefault(key, item)
                out[f] = list(union.values()) if union else None
            else:
                out[f] = None
        else:
            out[f] = mv if _norm(mv) else gv
    return out


def _yaml_escape(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, list):
        return "[]" if not v else json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _frontmatter(pairs: list[tuple[str, Any]]) -> str:
    lines = ["---"]
    for k, v in pairs:
        lines.append(f"{k}: {_yaml_escape(v)}")
    lines.append("---")
    return "\n".join(lines)


def write_final_md(row, mistral_out, gemini_out, disagreements, registry) -> Path:
    m_struct = mistral_out.get("structured") or {}
    g_struct = gemini_out.get("structured") or {}
    canon = canonical_fields(m_struct, g_struct)
    entity_code = row.get("entity_code") or "UNKNOWN"
    store_prefix = entity_code.replace("CORP_", "").replace("STORE_", "")
    entry = registry.get(store_prefix.upper()) or registry.get(entity_code.upper())
    entity_legal_name = (entry or {}).get("full_company_name") or entity_code
    store_map = (entry or {}).get("mosaic_store_name") or ""
    file_id = row.get("file_id") or ""
    drive_url = f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""
    validation_method = "opus_arbitrated_pending" if disagreements else "dual_match"
    dd_ready = not disagreements

    pairs: list[tuple[str, Any]] = [
        ("source_drive_id", file_id),
        ("source_drive_url", drive_url),
        ("source_path", row.get("full_path", "")),
        ("source_md5", row.get("md5", "")),
        ("source_modified", row.get("modifiedTime", "")),
        ("size_bytes", int(row.get("size") or 0)),
        ("entity_code", entity_code),
        ("entity_legal_name", entity_legal_name),
        ("entity_store_mapping", store_map),
        ("permit_code", row.get("permit_code", "")),
        ("document_type", canon.get("document_type") or m_struct.get("document_type") or g_struct.get("document_type") or ""),
        ("canonical_tin", canon.get("tin")),
        ("canonical_ocn", canon.get("ocn")),
        ("canonical_psic_code", canon.get("psic_code")),
        ("canonical_business_name", canon.get("business_name")),
        ("canonical_trade_name", canon.get("trade_name")),
        ("canonical_permit_number", canon.get("permit_number")),
        ("canonical_issuing_authority", canon.get("issuing_authority")),
        ("canonical_issue_date", canon.get("issue_date")),
        ("canonical_expiry_date", canon.get("expiry_date")),
        ("canonical_location_address", canon.get("location_address")),
        ("canonical_registered_address", canon.get("registered_address")),
        ("canonical_signatories", canon.get("signatories") or []),
        ("mistral_document_type", m_struct.get("document_type")),
        ("mistral_tin", m_struct.get("tin")),
        ("mistral_ocn", m_struct.get("ocn")),
        ("mistral_psic_code", m_struct.get("psic_code")),
        ("mistral_business_name", m_struct.get("business_name")),
        ("mistral_issue_date", m_struct.get("issue_date")),
        ("mistral_expiry_date", m_struct.get("expiry_date")),
        ("mistral_signatories", m_struct.get("signatories") or []),
        ("mistral_confidence", m_struct.get("extraction_confidence") or 0.0),
        ("gemini_pro_document_type", g_struct.get("document_type")),
        ("gemini_pro_tin", g_struct.get("tin")),
        ("gemini_pro_ocn", g_struct.get("ocn")),
        ("gemini_pro_psic_code", g_struct.get("psic_code")),
        ("gemini_pro_business_name", g_struct.get("business_name")),
        ("gemini_pro_issue_date", g_struct.get("issue_date")),
        ("gemini_pro_expiry_date", g_struct.get("expiry_date")),
        ("gemini_pro_signatories", g_struct.get("signatories") or []),
        ("gemini_pro_confidence", g_struct.get("extraction_confidence") or 0.0),
        ("validation_method", validation_method),
        ("disagreements", [d["field"] for d in disagreements]),
        ("opus_arbitration_reasoning", ""),
        ("opus_source_of_truth", ""),
        ("extraction_date", _now_iso()),
        ("extraction_models", [MISTRAL_MODEL, GEMINI_PRO] + (["claude-opus-4-7"] if disagreements else [])),
        ("extraction_cost_usd", round((mistral_out.get("meta", {}).get("cost_usd") or 0.0) + (0.03 if g_struct else 0.0), 4)),
        ("dd_ready", dd_ready),
    ]

    body = (mistral_out.get("body_md") or "").strip()
    if not body:
        body = (gemini_out.get("body_md") or "").strip()
    md = _frontmatter(pairs) + "\n\n# OCR body (Mistral)\n\n" + body + "\n"
    out_path = _md_path_for(row)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    return out_path


@dataclass
class PipelineCtx:
    drive: Any
    mistral: Mistral
    gemini: genai.Client
    registry: dict[str, dict]
    force: bool


async def process_row(ctx: PipelineCtx, row: dict, semaphore: asyncio.Semaphore) -> dict:
    file_id = row["file_id"]
    async with semaphore:
        stage_dir = STAGING / file_id
        stage_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = stage_dir / "source.pdf"

        attempt = 0
        last_err: Optional[str] = None
        while attempt <= MAX_RETRIES:
            attempt += 1
            t_all = time.perf_counter()
            try:
                await asyncio.to_thread(_download_pdf, ctx.drive, file_id, pdf_path)
                mistral_fut = asyncio.to_thread(run_mistral_sync, pdf_path, ctx.mistral)
                gemini_fut = asyncio.to_thread(run_gemini_sync, pdf_path, ctx.gemini)
                mistral_out, gemini_out = await asyncio.gather(mistral_fut, gemini_fut)

                disagreements = detect_disagreements(
                    mistral_out.get("structured") or {},
                    gemini_out.get("structured") or {},
                )

                (stage_dir / "mistral.json").write_text(
                    json.dumps(mistral_out.get("structured") or {}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (stage_dir / "mistral.md").write_text(mistral_out.get("body_md") or "", encoding="utf-8")
                (stage_dir / "gemini.json").write_text(
                    json.dumps(gemini_out.get("structured") or {}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (stage_dir / "gemini.md").write_text(gemini_out.get("body_md") or "", encoding="utf-8")
                summary = {
                    "file_id": file_id,
                    "name": row.get("name"),
                    "dest_path": row.get("dest_path"),
                    "permit_code": row.get("permit_code"),
                    "entity_code": row.get("entity_code"),
                    "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                    "pdf_bytes": pdf_path.stat().st_size,
                    "mistral_meta": mistral_out.get("meta"),
                    "gemini_meta": gemini_out.get("meta"),
                    "disagreements": disagreements,
                    "needs_arbitration": bool(disagreements),
                    "ts": _now_iso(),
                }
                (stage_dir / "summary.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                md_path = write_final_md(row, mistral_out, gemini_out, disagreements, ctx.registry)
                elapsed = time.perf_counter() - t_all
                manifest_rec = {
                    "file_id": file_id,
                    "name": row.get("name"),
                    "status": "ok",
                    "md_path": str(md_path.relative_to(REPO_ROOT)),
                    "staging": str(stage_dir.relative_to(REPO_ROOT)),
                    "needs_arbitration": bool(disagreements),
                    "disagreement_fields": [d["field"] for d in disagreements],
                    "elapsed_s": round(elapsed, 2),
                    "ts": _now_iso(),
                }
                _append_jsonl(MANIFEST, manifest_rec)
                print(
                    f"[OK {elapsed:5.1f}s] {row.get('name','?')[:60]} "
                    f"({'ARB ' + str(len(disagreements)) if disagreements else 'dual'})"
                )
                return manifest_rec
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                traceback.print_exc()
                if attempt > MAX_RETRIES:
                    break
                await asyncio.sleep(min(2 ** attempt, 30))

        err_rec = {
            "file_id": file_id,
            "name": row.get("name"),
            "status": "error",
            "error": last_err,
            "ts": _now_iso(),
        }
        _append_jsonl(ERRORS, err_rec)
        _append_jsonl(MANIFEST, {**err_rec, "status": "error"})
        print(f"[ERR] {row.get('name','?')[:60]} — {last_err}")
        return err_rec


def _load_rows(picks_path, limit, skip=0):
    winners: list[dict] = []
    with DEDUPE_CSV.open("r", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_winner") == "1" and row.get("mime") == "application/pdf":
                winners.append(row)
    winners.sort(key=lambda r: r["file_id"])
    print(f"total PDF winners: {len(winners)}")

    if picks_path and picks_path.exists():
        picks = json.loads(picks_path.read_text(encoding="utf-8"))
        pick_ids = [p.get("file_id") if isinstance(p, dict) else p for p in picks]
        pick_ids = [pid for pid in pick_ids if pid]
        order = {pid: i for i, pid in enumerate(pick_ids)}
        rows = [r for r in winners if r["file_id"] in order]
        rows.sort(key=lambda r: order[r["file_id"]])
        print(f"loaded {len(rows)} rows from picks {picks_path}")
    else:
        rows = winners

    if skip:
        rows = rows[skip:]
        print(f"skipping first {skip}, remaining {len(rows)}")
    if limit:
        rows = rows[:limit]
    return rows


async def main_async(args):
    rows = _load_rows(
        Path(args.picks) if args.picks else None,
        args.limit,
        skip=args.skip,
    )
    if not rows:
        print("no rows to process")
        return

    done = set() if args.force else _load_manifest_ids()
    if done:
        before = len(rows)
        rows = [r for r in rows if r["file_id"] not in done]
        print(f"skip {before - len(rows)} already-processed files (use --force to redo)")

    if not rows:
        print("nothing to do after resume filter")
        return

    print(f"processing {len(rows)} files @ {args.concurrency}x concurrency")
    drive = _drive_client()
    mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
    gemini = _genai_client()
    registry = _load_registry()
    ctx = PipelineCtx(drive=drive, mistral=mistral, gemini=gemini, registry=registry, force=args.force)

    sem = asyncio.Semaphore(args.concurrency)
    t_start = time.perf_counter()
    results = await asyncio.gather(*(process_row(ctx, r, sem) for r in rows))
    elapsed = time.perf_counter() - t_start

    ok = [r for r in results if r.get("status") == "ok"]
    err = [r for r in results if r.get("status") != "ok"]
    arb = [r for r in ok if r.get("needs_arbitration")]
    print(f"\n===== DONE {elapsed:.1f}s =====")
    print(f"ok                : {len(ok)}")
    print(f"errors            : {len(err)}")
    print(f"needs arbitration : {len(arb)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--picks", help="JSON file of picks (pilot).")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--skip", type=int, default=0, help="Skip first N rows.")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
