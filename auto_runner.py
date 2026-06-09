#!/usr/bin/env python3
"""
auto_runner.py — Watch the deals/ folder and auto-run the CFO analysis.

When you create a folder under deals/ (e.g. "deals/52 Hawkin Road") and drop the
balance sheet, income statement, and general ledger into it (directly, or into an
inputs/ subfolder), this watcher notices, waits until the files have finished
copying, then launches Claude Code headlessly to:

    read the files  ->  build deal.json  ->  run analyze.py + generate_pdf.py
                    ->  drop <Property>_Board_Summary.pdf back into the folder.

It runs forever, checking every few seconds. Safe to leave running in the
background (this is what the Windows setup registers to start at log-on).

Re-run a property: delete its *_Board_Summary.pdf (and .cfo_processed marker)
and the watcher will process it again the next time the files settle.
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Config -----------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DEALS = BASE / "deals"
POLL_SECONDS = 5           # how often to scan
SETTLE_SECONDS = 20        # files must be unchanged this long before we run
MIN_FILES = 2              # need at least this many source docs to start
SOURCE_EXTS = {".pdf", ".xlsx", ".xls", ".csv", ".png", ".jpg", ".jpeg"}
SKIP_PREFIXES = ("_", ".")  # ignore deals/_TEMPLATE and hidden folders

PROMPT = (
    "Act as the real-estate CFO using the property-cfo-analysis skill. "
    "Analyze the property in the folder 'deals/{name}'. Read every financial "
    "file in 'deals/{name}/inputs' and directly in 'deals/{name}' — the balance "
    "sheet, income statement, and general ledger. Extract every owner cost and "
    "each dated loan/advance into 'deals/{name}/deal.json' following the skill "
    "schema: capitalized costs are basis entries with accrues_interest=false; "
    "loan/hard-money draws use basis=false and accrue 12% simple interest "
    "actual/365 from each draw date; net any income already received (e.g. "
    "forfeited U&O / rent) as a negative basis entry; set selling_cost_pct=0.06; "
    "include 3-4 target_sale_prices bracketing the breakeven. Then run "
    "scripts/analyze.py and scripts/generate_pdf.py to write the one-page board "
    "PDF into 'deals/{name}'. Never fabricate figures; note any assumptions in "
    "the deal.json notes field."
)


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        with open(BASE / "auto_runner.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def source_files(folder: Path):
    files = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in SOURCE_EXTS:
            files.append(p)
    inputs = folder / "inputs"
    if inputs.is_dir():
        for p in inputs.iterdir():
            if p.is_file() and p.suffix.lower() in SOURCE_EXTS:
                files.append(p)
    return files


def already_done(folder: Path):
    if (folder / ".cfo_processed").exists():
        return True
    return any(folder.glob("*_Board_Summary.pdf"))


def files_settled(files):
    if not files:
        return False
    newest = max(f.stat().st_mtime for f in files)
    return (time.time() - newest) >= SETTLE_SECONDS


def claude_executable():
    """Resolve the Claude Code CLI. Prefer the path pinned by setup.ps1
    (claude_path.txt) since the background watcher may not inherit PATH."""
    cfg = BASE / "claude_path.txt"
    if cfg.exists():
        p = cfg.read_text(encoding="utf-8").strip()
        if p:
            return p
    return "claude"


def build_claude_cmd(prompt: str):
    exe = claude_executable()
    low = exe.lower()
    args = ["-p", prompt, "--dangerously-skip-permissions"]
    if low.endswith((".cmd", ".bat")):
        return ["cmd", "/c", exe, *args]
    if low.endswith(".ps1"):
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", exe, *args]
    return [exe, *args]


def run_claude(folder: Path):
    name = folder.name
    log(f"Processing '{name}' ({len(source_files(folder))} files)...")
    inprogress = folder / ".cfo_inprogress"
    inprogress.write_text(datetime.now().isoformat(), encoding="utf-8")
    cmd = build_claude_cmd(PROMPT.format(name=name))
    try:
        with open(folder / "cfo_run.log", "w", encoding="utf-8") as logf:
            result = subprocess.run(
                cmd, cwd=str(BASE), stdout=logf, stderr=subprocess.STDOUT,
                timeout=900,
            )
        if result.returncode == 0 and any(folder.glob("*_Board_Summary.pdf")):
            (folder / ".cfo_processed").write_text(
                datetime.now().isoformat(), encoding="utf-8")
            log(f"DONE '{name}' — board PDF created.")
        else:
            log(f"WARN '{name}' — Claude exited {result.returncode}; "
                f"see deals/{name}/cfo_run.log. Will retry after files change.")
    except FileNotFoundError:
        log("ERROR: Claude Code CLI not found. Re-run windows\\setup.ps1 so it "
            "can pin the path (claude_path.txt), or install the CLI.")
    except subprocess.TimeoutExpired:
        log(f"WARN '{name}' — timed out after 15 min; see cfo_run.log.")
    finally:
        inprogress.unlink(missing_ok=True)


def scan_once():
    if not DEALS.is_dir():
        return
    for folder in sorted(DEALS.iterdir()):
        if not folder.is_dir() or folder.name.startswith(SKIP_PREFIXES):
            continue
        if already_done(folder) or (folder / ".cfo_inprogress").exists():
            continue
        files = source_files(folder)
        if len(files) >= MIN_FILES and files_settled(files):
            run_claude(folder)


def main():
    log(f"CFO auto-runner started. Watching: {DEALS}")
    log(f"(poll {POLL_SECONDS}s, settle {SETTLE_SECONDS}s, min {MIN_FILES} files)")
    while True:
        try:
            scan_once()
        except Exception as e:  # keep the watcher alive no matter what
            log(f"ERROR in scan loop: {e!r}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("CFO auto-runner stopped.")
        sys.exit(0)
