#!/usr/bin/env python3
"""
nj_foreclosure_runner.py — Weekly NJ Foreclosure audit runner.

Every Monday at 2 PM (within a 5-minute window) this script launches
Claude Code headlessly to:

    find newest CSV in NJForeclosures Google Drive folder
        -> parse & flag rows (Tax / Condo / Mortgage rules)
        -> build HTML email report
        -> send to Jerry@westmarq.com

It runs forever, checking every minute. Safe to leave running in the
background (this is what the Windows setup registers to start at log-on).

Idempotency: checks nj_audit.log — if the same filename was already
audited this week, Claude will skip it (guardrail in AUTOMATION.md).
"""
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- Config -----------------------------------------------------------------
BASE         = Path(__file__).resolve().parent
LOG_FILE     = BASE / "nj_audit.log"
POLL_SECONDS = 60           # check every minute
RUN_WEEKDAY  = 0            # Monday (0=Mon … 6=Sun)
RUN_HOUR     = 14           # 2 PM
RUN_MINUTE   = 0
WINDOW_MIN   = 5            # fire within this many minutes of RUN_HOUR:RUN_MINUTE

PROMPT = (
    "Follow NJ_FORECLOSURE_AUTOMATION.md in this repository exactly."
)


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def claude_executable():
    """Resolve the Claude Code CLI. Prefer the path pinned by setup_nj_audit.ps1
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


def is_run_window(now: datetime) -> bool:
    """Return True if we are within WINDOW_MIN minutes of the scheduled time."""
    if now.weekday() != RUN_WEEKDAY:
        return False
    minutes_since = (now.hour - RUN_HOUR) * 60 + (now.minute - RUN_MINUTE)
    return 0 <= minutes_since < WINDOW_MIN


def already_ran_today(now: datetime) -> bool:
    """Check nj_audit.log — did we already complete a run today?"""
    today = now.strftime("%Y-%m-%d")
    if not LOG_FILE.exists():
        return False
    with open(LOG_FILE, encoding="utf-8") as f:
        for line in f:
            if today in line and ("Audited" in line or "ERROR" in line):
                return True
    return False


def run_audit():
    log("Starting NJ Foreclosure audit...")
    inprogress = BASE / ".nj_audit_inprogress"
    inprogress.write_text(datetime.now().isoformat(), encoding="utf-8")
    cmd = build_claude_cmd(PROMPT)
    try:
        with open(BASE / "nj_audit_run.log", "w", encoding="utf-8") as logf:
            result = subprocess.run(
                cmd, cwd=str(BASE), stdout=logf, stderr=subprocess.STDOUT,
                timeout=900,
            )
        if result.returncode == 0:
            log("NJ Foreclosure audit completed successfully.")
        else:
            log(f"WARN — Claude exited {result.returncode}; see nj_audit_run.log.")
    except FileNotFoundError:
        log("ERROR: Claude Code CLI not found. Re-run windows\\setup_nj_audit.ps1 so it "
            "can pin the path (claude_path.txt), or install the CLI.")
    except subprocess.TimeoutExpired:
        log("WARN — audit timed out after 15 min; see nj_audit_run.log.")
    finally:
        inprogress.unlink(missing_ok=True)


def main():
    log("NJ Foreclosure runner started. Will run every Monday at 2:00 PM.")
    while True:
        try:
            now = datetime.now()
            if is_run_window(now) and not already_ran_today(now):
                if not (BASE / ".nj_audit_inprogress").exists():
                    run_audit()
        except Exception as e:
            log(f"ERROR in check loop: {e!r}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("NJ Foreclosure runner stopped.")
        sys.exit(0)
