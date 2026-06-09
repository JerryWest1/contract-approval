<#
  setup.ps1 — One-time setup for the Property CFO auto-runner on Windows.

  What it does:
    1. Verifies Python is installed (tells you how to install it if not).
    2. Installs the Python libraries the report needs (reportlab, openpyxl).
    3. Checks that Claude Code ('claude') is on your PATH.
    4. Registers a background task that starts the folder-watcher every time
       you log in, so dropping files into a deals\ folder auto-builds the PDF.

  Run it once, from PowerShell, inside the project folder:
      powershell -ExecutionPolicy Bypass -File .\windows\setup.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Write-Host "Project folder: $RepoRoot" -ForegroundColor Cyan

# 1. Python ------------------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python is not installed." -ForegroundColor Yellow
    Write-Host "Install it, then re-run this script:" -ForegroundColor Yellow
    Write-Host "    winget install Python.Python.3.12" -ForegroundColor White
    Write-Host "(or download from https://www.python.org/downloads/ and check 'Add to PATH')."
    exit 1
}
Write-Host "Found Python: $($py.Source)" -ForegroundColor Green

$pythonw = Join-Path (Split-Path $py.Source) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $py.Source }  # fallback

# 2. Python libraries --------------------------------------------------------
Write-Host "Installing report libraries (reportlab, openpyxl)..." -ForegroundColor Cyan
& $py.Source -m pip install --quiet --upgrade reportlab openpyxl
Write-Host "Libraries installed." -ForegroundColor Green

# 3. Claude Code -------------------------------------------------------------
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    Write-Host "WARNING: 'claude' (Claude Code) was not found on your PATH." -ForegroundColor Yellow
    Write-Host "The watcher needs it to read the PDFs. Open a new terminal after" -ForegroundColor Yellow
    Write-Host "installing/logging into Claude Code, then re-run this script." -ForegroundColor Yellow
} else {
    Write-Host "Found Claude Code: $($claude.Source)" -ForegroundColor Green
}

# 4. Background task at log-on ----------------------------------------------
$TaskName = "PropertyCFO-Watcher"
$script = Join-Path $RepoRoot "auto_runner.py"

$action  = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Watches the deals\ folder and auto-builds the CFO board PDF when files are dropped." | Out-Null

Start-ScheduledTask -TaskName $TaskName
Write-Host ""
Write-Host "Done. The CFO watcher is now running and will start automatically at log-on." -ForegroundColor Green
Write-Host ""
Write-Host "Try it: open the 'deals' folder, make a new folder named after a" -ForegroundColor Cyan
Write-Host "property, and drop the 3 files in. The board PDF appears there in ~30s." -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop it:   Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
Write-Host "Activity log: $RepoRoot\auto_runner.log" -ForegroundColor DarkGray
