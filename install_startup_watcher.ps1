# One-time install: dependencies + auto-start at log-on (no admin needed).
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root "start_watcher_hidden.ps1"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
  Write-Host "Python not found. Install it first:  winget install Python.Python.3.12" -ForegroundColor Yellow
  exit 1
}

Write-Host "Installing Python libraries (pypdf, reportlab)..." -ForegroundColor Cyan
& $Python.Source -m pip install --quiet --upgrade pypdf reportlab

New-Item -ItemType Directory -Force -Path (Join-Path $Root "inbox")   | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "outputs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs")    | Out-Null

$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Real Estate CFO Report Watcher.lnk"

$Wsh = New-Object -ComObject WScript.Shell
$Shortcut = $Wsh.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Starts the Real Estate CFO report inbox watcher"
$Shortcut.Save()

Start-Process -WindowStyle Hidden -FilePath "powershell.exe" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-WindowStyle",
  "Hidden",
  "-File",
  $Script
)

Write-Host ""
Write-Host "Installed and started. The watcher now runs at every log-on." -ForegroundColor Green
Write-Host "Shortcut: $ShortcutPath"
Write-Host ""
Write-Host "Use it: drop a folder like 'inbox\52 Hawkin' containing the 3 PDFs." -ForegroundColor Cyan
Write-Host "The report appears in 'outputs\52 Hawkin\board_summary.pdf' (~30s)." -ForegroundColor Cyan
