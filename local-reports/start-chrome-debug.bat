@echo off
REM Starts YOUR normal Chrome with remote debugging enabled (port 9222) so the
REM report script can reuse your existing AppFolio login.
REM
REM NOTE: Chrome must not already be running, or the flag is ignored.
REM Close all Chrome windows first, then double-click this.
REM
REM Security note: while Chrome runs with this flag, other programs on THIS
REM computer could control the browser via port 9222. Fine on a private PC.

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" (
  echo Could not find chrome.exe - edit this file and set the CHROME path.
  pause
  exit /b 1
)

start "" "%CHROME%" --remote-debugging-port=9222
echo Chrome started with debugging enabled. Now run run-reports-chrome.bat
timeout /t 5 >nul
