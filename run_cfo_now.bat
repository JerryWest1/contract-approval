@echo off
REM One-click: process everything new in inbox\ right now, show the result, done.
cd /d "%~dp0"
python .claude\skills\property-cfo-analysis\scripts\watch_inbox.py --once
pause
