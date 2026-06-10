#!/usr/bin/env python3
"""
watch_inbox.py — Watch inbox/ for project folders and run the local analyzer.

Drop one folder per property into inbox/ (e.g. inbox/52 Hawkin/) containing the
balance sheet, income statement, and general ledger PDFs. The watcher:

  1. Polls the inbox every POLL_SECONDS.
  2. Waits until a project's files have been stable for STABLE_SECONDS
     (so half-copied files are never processed).
  3. Runs analyze_project.py -> outputs/<project>/board_summary.pdf etc.
  4. Records a fingerprint in outputs/<project>/.last_run.json so unchanged
     folders are never rerun — but re-copied folders are (the fingerprint
     includes the folder's own mtime, since Windows preserves inner file
     timestamps on copy).
  5. Logs to logs/watcher.log and per-project outputs/<project>/run.log.

No AI, no network: plain Python. Run once-off with --once.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
INBOX = ROOT / "inbox"
OUTPUTS = ROOT / "outputs"
LOGS = ROOT / "logs"
CONFIG = ROOT / "config" / "project_config.json"
ANALYZER = Path(__file__).resolve().parent / "analyze_project.py"

POLL_SECONDS = 5
STABLE_SECONDS = 15
SUPPORTED_SUFFIXES = {".csv", ".xlsx", ".xlsm", ".pdf"}


def log(msg: str):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / "watcher.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def fingerprint(folder: Path) -> dict:
    folder_stat = folder.stat()
    files = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        stat = path.stat()
        files.append({
            "name": path.name,
            "size": stat.st_size,
            "mtime": round(stat.st_mtime, 3),
        })
    return {
        "folder_mtime": round(folder_stat.st_mtime, 3),
        "files": files,
    }


def is_stable(folder: Path) -> bool:
    newest = folder.stat().st_mtime
    for path in folder.iterdir():
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
    return (time.time() - newest) >= STABLE_SECONDS


def last_run(project: str) -> dict:
    state = OUTPUTS / project / ".last_run.json"
    if state.exists():
        try:
            return json.loads(state.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_run(project: str, fp: dict, status: str):
    out = OUTPUTS / project
    out.mkdir(parents=True, exist_ok=True)
    (out / ".last_run.json").write_text(json.dumps({
        "fingerprint": fp,
        "status": status,
        "last_run_epoch": time.time(),
    }, indent=2), encoding="utf-8")


def run_project(folder: Path) -> bool:
    project = folder.name
    output_dir = OUTPUTS / project
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(ANALYZER),
        "--input-dir", str(folder),
        "--config", str(CONFIG),
        "--output-dir", str(output_dir),
        "--project-name", project,
    ]
    log(f"[run] {project}")
    result = subprocess.run(command, check=False, text=True,
                            capture_output=True)
    with open(output_dir / "run.log", "w", encoding="utf-8") as f:
        f.write(f"command: {' '.join(command)}\n")
        f.write(f"time: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"returncode: {result.returncode}\n")
        f.write("\n--- stdout ---\n" + (result.stdout or ""))
        f.write("\n--- stderr ---\n" + (result.stderr or ""))

    if result.returncode == 0:
        log(f"[done] {project} -> {output_dir / 'board_summary.pdf'}")
        return True
    log(f"[error] {project} exited {result.returncode} — see "
        f"{output_dir / 'run.log'} and exceptions.csv")
    return False


def scan_once():
    if not INBOX.is_dir():
        return
    for folder in sorted(INBOX.iterdir()):
        if not folder.is_dir() or folder.name.startswith((".", "_")):
            continue
        fp = fingerprint(folder)
        if not fp["files"]:
            continue
        prior = last_run(folder.name)
        if (prior.get("fingerprint") == fp
                and prior.get("status") == "success"):
            continue
        if not is_stable(folder):
            continue
        ok = run_project(folder)
        save_run(folder.name, fingerprint(folder),
                 "success" if ok else "error")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="Scan a single time and exit")
    args = ap.parse_args()

    INBOX.mkdir(parents=True, exist_ok=True)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    log(f"Watching: {INBOX}")
    if args.once:
        scan_once()
        return 0
    while True:
        try:
            scan_once()
        except Exception as exc:  # keep the watcher alive no matter what
            log(f"[watcher-error] {exc!r}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
