# Snapshot loop for long-tail neg-risk arb persistence study.
#
# Runs scripts/snapshot_gamma.py every $IntervalSeconds (default 900s = 15min)
# until killed. Each run is self-contained: a failed run is logged and the
# loop continues -- a partial 14-day window with gaps is better than a clean
# but truncated window.
#
# Usage (run from repo root, leave PowerShell window open):
#   .\run_snapshot_loop.ps1
#
# Optional:
#   .\run_snapshot_loop.ps1 -IntervalSeconds 600   # 10-min cadence
#   .\run_snapshot_loop.ps1 -Pages 4               # cheaper, fewer markets
#
# Log: data/snapshots/loop.log (appended).
# Stop: Ctrl+C in the PowerShell window.

param(
    [int]$IntervalSeconds = 900,
    [int]$Pages = 6
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$LogDir = Join-Path $ScriptDir "data\snapshots"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "loop.log"

function Write-Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK') $msg"
    Write-Host $line
    Add-Content -Path $LogPath -Value $line -Encoding UTF8
}

Write-Log "loop start  interval=${IntervalSeconds}s  pages=${Pages}  cwd=$ScriptDir"

while ($true) {
    $runStart = Get-Date
    Write-Log "run begin"
    try {
        # -u so each line of stdout flushes immediately into the log
        & python -u "scripts/snapshot_gamma.py" --pages $Pages 2>&1 | ForEach-Object {
            Add-Content -Path $LogPath -Value $_ -Encoding UTF8
        }
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) {
            Write-Log "run end EXIT=$exitCode (partial or failed)"
        }
    } catch {
        Write-Log "run THREW: $_"
    }
    $elapsed = [int]((Get-Date) - $runStart).TotalSeconds
    $sleep = $IntervalSeconds - $elapsed
    if ($sleep -lt 5) { $sleep = 5 }
    Write-Log "run done in ${elapsed}s, sleeping ${sleep}s"
    Start-Sleep -Seconds $sleep
}
