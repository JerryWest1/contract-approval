$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root ".claude\skills\property-cfo-analysis\scripts\watch_inbox.py"
$Python = (Get-Command python -ErrorAction Stop).Source
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Existing = Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -like "python*") -and $_.CommandLine -and $_.CommandLine -like "*watch_inbox.py*"
}

if ($Existing) {
  exit 0
}

Start-Process `
  -WindowStyle Hidden `
  -FilePath $Python `
  -ArgumentList @($Script) `
  -WorkingDirectory $Root `
  -RedirectStandardOutput (Join-Path $LogDir "watcher.stdout.log") `
  -RedirectStandardError (Join-Path $LogDir "watcher.stderr.log")
