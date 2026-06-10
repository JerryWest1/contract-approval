@echo off
REM Double-click this to download the CFO reports into the CFO Report Inbox.
REM A popup asks which property to run for. Leave it blank for ALL properties.
cd /d "%~dp0"

set "PROPERTY="
for /f "usebackq delims=" %%p in (`powershell -NoProfile -Command "Add-Type -AssemblyName Microsoft.VisualBasic; [Microsoft.VisualBasic.Interaction]::InputBox('Enter the property name exactly as it appears in AppFolio.' + [char]13 + [char]10 + 'Leave blank for ALL properties (consolidated).','AppFolio CFO Reports','')"`) do set "PROPERTY=%%p"

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
