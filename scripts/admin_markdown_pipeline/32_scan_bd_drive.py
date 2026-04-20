"""Full recursive scan of 'Business Development' shared drive.

Writes:
- .scratch/bd_drive_all_files.csv (every file with full path)
- .scratch/bd_drive_compliance.csv (PDF/doc filtered to compliance-relevant)
- .scratch/bd_drive_missing.csv (files NOT already in our DD package, by md5)
"""
from __future__ import annotations
import csv, sys, time
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
CREDS = ROOT / "credentials" / "task-manager-service.json"
DD = ROOT / "CEO" / "Valuation" / "admin_compliance_dd"
SCRATCH = ROOT / ".scratch"
SCRATCH.mkdir(parents=True, exist_ok=True)

BD_DRIVE_ID = "0AApBff2Le1AWUk9PVA"

# Compliance-relevant mime types
COMPLIANCE_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "image/jpeg",
    "image/png",
    "image/heic",
}

FOLDER_MIME = "application/vnd.google-apps.folder"


def build_drive():
    creds = service_account.Credentials.from_service_account_file(
        str(CREDS),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    ).with_subject("sam@bebang.ph")
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def retry(fn, tries=3, delay=2):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if i == tries - 1:
                raise
            time.sleep(delay * (i + 1))


def list_children(drive, parent_id: str) -> list[dict]:
    """List all immediate children of a folder, paginated."""
    results = []
    page = None
    while True:
        resp = retry(lambda: drive.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            corpora="drive",
            driveId=BD_DRIVE_ID,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            pageSize=1000,
            pageToken=page,
            fields="nextPageToken, files(id,name,mimeType,size,md5Checksum,parents,modifiedTime,createdTime,owners)",
        ).execute())
        results.extend(resp.get("files", []))
        page = resp.get("nextPageToken")
        if not page:
            break
    return results


def walk(drive, parent_id: str, parent_path: str, out_rows: list, depth: int = 0) -> None:
    children = list_children(drive, parent_id)
    for c in children:
        path = f"{parent_path}/{c['name']}" if parent_path else c["name"]
        out_rows.append({
            "id": c["id"],
            "name": c["name"],
            "mimeType": c["mimeType"],
            "size": c.get("size", ""),
            "md5": c.get("md5Checksum", ""),
            "modifiedTime": c.get("modifiedTime", ""),
            "createdTime": c.get("createdTime", ""),
            "path": path,
            "is_folder": 1 if c["mimeType"] == FOLDER_MIME else 0,
            "depth": depth,
        })
        if c["mimeType"] == FOLDER_MIME:
            walk(drive, c["id"], path, out_rows, depth + 1)


def main() -> None:
    print(f"Scanning Business Development drive ({BD_DRIVE_ID})...")
    drive = build_drive()
    rows: list[dict] = []
    walk(drive, BD_DRIVE_ID, "Business Development", rows)

    print(f"Total items: {len(rows)}")

    # Write all
    all_csv = SCRATCH / "bd_drive_all_files.csv"
    with all_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "name", "mimeType", "size", "md5", "modifiedTime", "createdTime", "path", "is_folder", "depth"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {all_csv}")

    # Filter compliance
    comp = [r for r in rows if not r["is_folder"] and r["mimeType"] in COMPLIANCE_MIMES]
    print(f"Compliance-relevant files: {len(comp)}")
    comp_csv = SCRATCH / "bd_drive_compliance.csv"
    with comp_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "name", "mimeType", "size", "md5", "modifiedTime", "path"])
        w.writeheader()
        for r in comp:
            w.writerow({k: r[k] for k in ["id", "name", "mimeType", "size", "md5", "modifiedTime", "path"]})
    print(f"wrote {comp_csv}")

    # Cross-reference with existing DD manifest
    existing_md5 = set()
    existing_ids = set()
    manifest_csv = DD / "_MASTER_MANIFEST.csv"
    if manifest_csv.exists():
        with manifest_csv.open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                m = (r.get("source_md5") or "").strip().strip('"')
                if m:
                    existing_md5.add(m)
                did = (r.get("source_drive_id") or "").strip().strip('"')
                if did:
                    existing_ids.add(did)
    print(f"\nAlready-ingested md5: {len(existing_md5)}, drive_ids: {len(existing_ids)}")

    # Missing = compliance files we haven't seen before
    missing = []
    for r in comp:
        md5 = (r.get("md5") or "").strip()
        drive_id = r["id"]
        # Present if either md5 matches or drive_id matches
        if md5 and md5 in existing_md5:
            continue
        if drive_id in existing_ids:
            continue
        missing.append(r)

    print(f"\n=== MISSING FROM DD PACKAGE: {len(missing)} files ===\n")
    miss_csv = SCRATCH / "bd_drive_missing.csv"
    with miss_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "name", "mimeType", "size", "md5", "modifiedTime", "path"])
        w.writeheader()
        for r in missing:
            w.writerow({k: r[k] for k in ["id", "name", "mimeType", "size", "md5", "modifiedTime", "path"]})
    print(f"wrote {miss_csv}")

    # Summary by folder path
    from collections import Counter
    by_folder = Counter()
    for r in missing:
        folder = "/".join(r["path"].split("/")[:-1])
        by_folder[folder] += 1
    print(f"\nMissing files by top folder:")
    for folder, n in sorted(by_folder.items(), key=lambda x: -x[1])[:30]:
        print(f"  {n:4}  {folder}")

    # By filename/extension
    ext_counter = Counter()
    for r in missing:
        ext = r["name"].rsplit(".", 1)[-1].lower() if "." in r["name"] else "(none)"
        ext_counter[ext] += 1
    print(f"\nMissing files by extension:")
    for e, n in ext_counter.most_common():
        print(f"  {e:8}  {n}")


if __name__ == "__main__":
    main()
