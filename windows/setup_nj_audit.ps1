<#
  setup_nj_audit.ps1 — One-time setup for the NJ Foreclosure weekly audit runner.
  No administrator rights required.

  What it does:
    1. Verifies Python is installed.
    2. Installs the Python libraries the audit needs (openpyxl).
    3. Locates the Claude Code CLI and pins its path (claude_path.txt) so the
       background runner can always find it.
    4. Adds a Startup shortcut so the runner starts at every log-in,
       and starts it right now.

  Run it once, from PowerShell, inside the project folder:
      powershell -ExecutionPolicy Bypass -File .\windows\setup_nj_audit.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$script   = Join-Path $RepoRoot "nj_foreclosure_runner.py"
Write-Host "Project folder: $RepoRoot" -ForegroundColor Cyan

# 1. Python ------------------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python is not installed. Install it, then re-run this script:" -ForegroundColor Yellow
    Write-Host "    winget install Python.Python.3.12" -ForegroundColor White
    exit 1
}
Write-Host "Found Python: $($py.Source)" -ForegroundColor Green
$pythonw = Join-Path (Split-Path $py.Source) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $py.Source }

# 2. Python libraries --------------------------------------------------------
Write-Host "Installing required libraries (openpyxl)..." -ForegroundColor Cyan
& $py.Source -m pip install --quiet --upgrade openpyxl
Write-Host "Libraries installed." -ForegroundColor Green

# 3. Locate Claude Code CLI and pin it --------------------------------------
$claudeCmd = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claudeCmd) {
    $candidates = @(
        "$env:APPDATA\npm\claude.cmd",
        "$env:APPDATA\npm\claude.ps1",
        "$env:LOCALAPPDATA\Programs\claude\claude.exe",
        "$env:USERPROFILE\.local\bin\claude.exe",
        "$env:USERPROFILE\.local\bin\claude.cmd"
    )
    foreach ($c in $candidates) { if (Test-Path $c) { $claudeCmd = $c; break } }
}
if (-not $claudeCmd) {
    Write-Host "Searching for the Claude CLI (this can take a moment)..." -ForegroundColor Cyan
    $roots = @("$env:APPDATA\npm", "$env:LOCALAPPDATA", "$env:USERPROFILE\.local") | Where-Object { Test-Path $_ }
    $hit = Get-ChildItem -Path $roots -Recurse -Include claude.cmd,claude.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { $claudeCmd = $hit.FullName }
}

if ($claudeCmd) {
    Set-Content -Path (Join-Path $RepoRoot "claude_path.txt") -Value $claudeCmd -Encoding ASCII
    Write-Host "Found Claude Code CLI: $claudeCmd" -ForegroundColor Green
} else {
    Write-Host "WARNING: Could not find the Claude Code CLI." -ForegroundColor Yellow
    Write-Host "If you use the Claude desktop app only, install the command-line tool:" -ForegroundColor Yellow
    Write-Host "    npm install -g @anthropic-ai/claude-code" -ForegroundColor White
    Write-Host "Then run 'claude' once to log in, and re-run this setup script." -ForegroundColor Yellow
}

# 4. Auto-start at log-on via the Startup folder (no admin needed) -----------
$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup 'NJForeclosureAudit.lnk'
$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($lnkPath)
$sc.TargetPath = $pythonw
$sc.Arguments  = "`"$script`""
$sc.WorkingDirectory = $RepoRoot
$sc.WindowStyle = 7
$sc.Description = "NJ Foreclosure weekly audit runner"
$sc.Save()
Write-Host "Auto-start installed: $lnkPath" -ForegroundColor Green

# Start it now (hidden, no console window).
Start-Process -FilePath $pythonw -ArgumentList "`"$script`"" -WorkingDirectory $RepoRoot -WindowStyle Hidden
Write-Host ""
Write-Host "Done. The NJ Foreclosure runner is running and will start automatically at log-on." -ForegroundColor Green
Write-Host ""
Write-Host "Schedule: every Monday at 2:00 PM it will find the newest CSV in the" -ForegroundColor Cyan
Write-Host "NJForeclosures Google Drive folder, audit it, and email the report to" -ForegroundColor Cyan
Write-Host "Jerry@westmarq.com." -ForegroundColor Cyan
Write-Host ""
Write-Host "Stop it:      delete '$lnkPath' and end 'pythonw.exe' in Task Manager." -ForegroundColor DarkGray
Write-Host "Activity log: $RepoRoot\nj_audit.log" -ForegroundColor DarkGray
Write-Host "Run log:      $RepoRoot\nj_audit_run.log" -ForegroundColor DarkGray
