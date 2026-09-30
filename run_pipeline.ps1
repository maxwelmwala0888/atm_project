# run_pipeline.ps1 - one-command ATM pipeline
# Usage:  .\run_pipeline.ps1
#         .\run_pipeline.ps1 -SkipGeneration     # skip 01 + 01b if data already exists
#         .\run_pipeline.ps1 -Only 04,05         # run just steps 04 and 05

param(
    [switch]$SkipGeneration,
    [int[]]$Only
)

$ErrorActionPreference = "Stop"
$root    = $PSScriptRoot
$logDir  = Join-Path $root "logs"
$dataDir = Join-Path $root "data\raw"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stamp    = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile  = Join-Path $logDir "pipeline_$stamp.log"

function Write-Log {
    param([string]$msg, [string]$color = "White")
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $logFile -Value $line
}

function Run-Step {
    param([string]$name, [string]$script)
    $path = Join-Path $root $script
    if (-not (Test-Path $path)) {
        Write-Log "MISSING - $script" "Red"; return $false
    }
    Write-Log "START   $name  ($script)" "Cyan"
    $t0 = Get-Date
    & python $path 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "FAILED  $name  (exit $LASTEXITCODE)" "Red"; return $false
    }
    $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
    Write-Log ("DONE    {0}  ({1}s)" -f $name, $secs) "Green"
    return $true
}

function Should-Run {
    param([int]$n)
    if (-not $Only) { return $true }
    return $Only -contains $n
}

# ---------- header ----------
Write-Log ("=" * 70)
Write-Log "ATM NETWORK ANALYTICS - PIPELINE RUN"
Write-Log ("=" * 70)
Write-Log "Root   : $root"
Write-Log "Log    : $logFile"
Write-Log ("=" * 70)

# ---------- verify python ----------
try {
    $pyver = (& python --version 2>&1)
    Write-Log "Python : $pyver"
} catch {
    Write-Log "Python not found in PATH." "Red"; exit 1
}

# ---------- steps ----------
$steps = @(
    @{ n=1;  name="Generate base data";       script="scripts\01_generate_data.py";       skipIf=$SkipGeneration },
    @{ n=2;  name="Generate faults/refills";  script="scripts\01b_generate_faults.py";   skipIf=$SkipGeneration },
    @{ n=3;  name="Explore data";             script="scripts\02_explore_data.py";       skipIf=$false },
    @{ n=4;  name="Cash forecast (Prophet)";  script="scripts\03_train_cash_forecast.py";skipIf=$false },
    @{ n=5;  name="Fault prediction (XGB)";   script="scripts\04_train_fault_prediction.py"; skipIf=$false },
    @{ n=6;  name="Branch clustering (KMeans)";script="scripts\05_branch_clustering.py"; skipIf=$false }
)

$failed = @()
foreach ($s in $steps) {
    if (-not (Should-Run $s.n)) { continue }
    if ($s.skipIf) { Write-Log "SKIP    $($s.name)  (flag)"; continue }
    if (-not (Run-Step $s.name $s.script)) { $failed += $s.name }
}

# ---------- summary ----------
Write-Log ("=" * 70)
if ($failed.Count -eq 0) {
    Write-Log "PIPELINE COMPLETE - all steps passed" "Green"
} else {
    Write-Log ("PIPELINE FAILED - {0} step(s): {1}" -f $failed.Count, ($failed -join ", ")) "Red"
}
Write-Log "Processed outputs:"
Get-ChildItem (Join-Path $root "data\processed") -ErrorAction SilentlyContinue |
    Select-Object Name, @{N="KB";E={[math]::Round($_.Length/1KB,1)}} |
    Format-Table | Out-String | ForEach-Object { Write-Log $_ }
Write-Log "Models:"
Get-ChildItem (Join-Path $root "models") -ErrorAction SilentlyContinue |
    Select-Object Name, @{N="KB";E={[math]::Round($_.Length/1KB,1)}} |
    Format-Table | Out-String | ForEach-Object { Write-Log $_ }
Write-Log ("=" * 70)

if ($failed.Count -gt 0) { exit 1 }
