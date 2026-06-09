#!/usr/bin/env python3
"""
upload_to_drive.py — Binary-safe upload of a file to Google Drive.

The chat-style Drive connector corrupts binary files (PDFs arrive truncated).
This uploads the real bytes via the Google Drive API using a service account,
which handles binary correctly and works with Shared Drives.

Auth (one of):
  * GOOGLE_SERVICE_ACCOUNT_JSON  — the service-account key, as JSON text
  * GOOGLE_APPLICATION_CREDENTIALS — path to the service-account .json file

Usage:
  python3 upload_to_drive.py --file "<path.pdf>" --drive "LIGHTHOUSE" \
      --folder "52 Hawkin Road, Medford"

  # drive/folder may be given as names (resolved by lookup) or as IDs.

If a file with the same name already exists in the folder, its contents are
replaced (no duplicates). Prints the shareable link on success.
"""
import argparse
import json
import os
import sys

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    sys.exit("Missing libraries. Install with:\n"
             "    pip install google-api-python-client google-auth")

SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"


def get_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        raw = raw.strip()
        try:
            info = json.loads(raw)            # plain (single-line) JSON
        except json.JSONDecodeError:
            import base64                      # or a base64-encoded key
            info = json.loads(base64.b64decode(raw))
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not path or not os.path.exists(path):
            sys.exit("No credentials. Set GOOGLE_SERVICE_ACCOUNT_JSON (JSON text) "
                     "or GOOGLE_APPLICATION_CREDENTIALS (file path).")
        creds = service_account.Credentials.from_service_account_file(path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def looks_like_id(value):
    # Drive IDs are long, no spaces; shared-drive IDs often start with 0A.
    return value and " " not in value and len(value) >= 12 and "/" not in value


def resolve_drive_id(svc, drive):
    if not drive:
        return None
    if looks_like_id(drive):
        return drive
    resp = svc.drives().list(pageSize=100, fields="drives(id,name)").execute()
    for d in resp.get("drives", []):
        if d["name"].strip().lower() == drive.strip().lower():
            return d["id"]
    sys.exit(f"Shared drive not found by name: {drive!r}")


def resolve_folder_id(svc, folder, drive_id):
    if looks_like_id(folder):
        return folder
    q = f"name = '{folder}' and mimeType = '{FOLDER_MIME}' and trashed = false"
    params = dict(q=q, fields="files(id,name)", pageSize=10,
                  supportsAllDrives=True, includeItemsFromAllDrives=True)
    if drive_id:
        params.update(corpora="drive", driveId=drive_id)
    files = svc.files().list(**params).execute().get("files", [])
    if not files:
        sys.exit(f"Folder not found by name: {folder!r}")
    return files[0]["id"]


def find_existing(svc, name, parent_id, drive_id):
    q = f"name = '{name}' and '{parent_id}' in parents and trashed = false"
    params = dict(q=q, fields="files(id,name)", pageSize=5,
                  supportsAllDrives=True, includeItemsFromAllDrives=True)
    if drive_id:
        params.update(corpora="drive", driveId=drive_id)
    files = svc.files().list(**params).execute().get("files", [])
    return files[0]["id"] if files else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Binary-safe upload to Google Drive.")
    ap.add_argument("--file", required=True, help="Local file to upload")
    ap.add_argument("--folder", required=True, help="Destination folder (name or ID)")
    ap.add_argument("--drive", help="Shared drive (name or ID); omit for My Drive")
    ap.add_argument("--name", help="Name to save as (default: the file's name)")
    ap.add_argument("--mimetype", default="application/pdf")
    args = ap.parse_args(argv)

    if not os.path.exists(args.file):
        sys.exit(f"File not found: {args.file}")
    name = args.name or os.path.basename(args.file)

    svc = get_service()
    drive_id = resolve_drive_id(svc, args.drive)
    folder_id = resolve_folder_id(svc, args.folder, drive_id)
    media = MediaFileUpload(args.file, mimetype=args.mimetype, resumable=True)

    existing = find_existing(svc, name, folder_id, drive_id)
    if existing:
        f = svc.files().update(fileId=existing, media_body=media,
                               supportsAllDrives=True,
                               fields="id,webViewLink").execute()
        action = "Replaced"
    else:
        f = svc.files().create(body={"name": name, "parents": [folder_id]},
                               media_body=media, supportsAllDrives=True,
                               fields="id,webViewLink").execute()
        action = "Uploaded"
    print(f"{action}: {name}")
    print(f"Link: {f.get('webViewLink')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
