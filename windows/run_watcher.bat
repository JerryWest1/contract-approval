@echo off
REM Starts the CFO auto-runner. Double-click to run it in a visible window
REM (you'll see activity and can close it to stop). The scheduled task uses
REM pythonw.exe instead, so it runs silently in the background.
cd /d "%~dp0.."
python auto_runner.py
pause
