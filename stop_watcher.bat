@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like '*watch_inbox.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo Stopped running watcher processes. Startup automation remains installed.
pause
