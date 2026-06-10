$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "Real Estate CFO Report Watcher.lnk"

if (Test-Path $ShortcutPath) {
  Remove-Item -LiteralPath $ShortcutPath -Force
}

Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and $_.CommandLine -like "*watch_inbox.py*"
} | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force
}

Write-Host "Removed Startup watcher and stopped running watcher processes."
