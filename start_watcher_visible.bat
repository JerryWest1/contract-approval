@echo off
REM Runs the CFO inbox watcher in a visible window (security-software friendly).
REM Leave it open (minimized is fine). Close the window to stop watching.
cd /d "%~dp0"
title CFO Inbox Watcher
echo CFO inbox watcher running. Drop property folders into inbox\ ...
python .claude\skills\property-cfo-analysis\scripts\watch_inbox.py
pause
