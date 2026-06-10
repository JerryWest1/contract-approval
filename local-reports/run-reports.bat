@echo off
REM Double-click this to download the CFO reports into the CFO Report Inbox.
cd /d "%~dp0"
node download-reports.js
if %errorlevel% neq 0 (
  echo.
  echo ============================================================
  echo  Something went wrong.
  echo  If it says you are NOT logged in, double-click login.bat
  echo  and sign into AppFolio once, then run this again.
  echo ============================================================
  pause
) else (
  echo.
  echo Done. Reports saved to the CFO Report Inbox.
  timeout /t 5 >nul
)
