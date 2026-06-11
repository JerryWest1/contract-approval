@echo off
REM Runs the reports through YOUR already-running Chrome (started via
REM start-chrome-debug.bat), reusing your existing AppFolio login.
cd /d "%~dp0"
set "USE_CHROME=1"
node download-reports.js
if %errorlevel% neq 0 (
  echo.
  echo ============================================================
  echo  Something went wrong.
  echo  If it could not attach to Chrome: close ALL Chrome windows,
  echo  double-click start-chrome-debug.bat, log into AppFolio in
  echo  that Chrome, then run this again.
  echo ============================================================
  pause
) else (
  echo.
  echo Done. Reports saved to the CFO Report Inbox.
  timeout /t 5 >nul
)
