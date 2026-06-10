@echo off
REM Double-click this the first time, and again after the monthly MFA prompt.
REM A browser window opens - sign into AppFolio and complete MFA. The window
REM closes by itself once you reach the dashboard.
cd /d "%~dp0"
node download-reports.js login
pause
