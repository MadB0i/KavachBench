<#
.SYNOPSIS
    Enforce + verify Kavach ON/OFF state for all 10 live-validation sandboxes.

.DESCRIPTION
    Runs INSIDE the machine that hosts the sandboxes (VM guest or host).
    For each sandbox-N-off dir it ensures the hook is DISABLED
    (.claude/settings.json renamed to settings.json.off); for each
    sandbox-N-on dir it ensures the hook is ENABLED (settings.json present).
    Then runs verify_kavach_state.py preflight for every dir and prints a
    PASS/FAIL table. File-scoped only: no reboot, no network, no system
    changes, no snapshot, no agent sessions.

.EXAMPLE
    cd C:\KavachBench
    powershell -NoProfile -ExecutionPolicy Bypass -File validation\live\toggle-all.ps1
#>
param(
    [string]$ProjectRoot,
    [string]$RunIdPrefix = "toggle-all"
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$pairs = @(
    @{ Short = "1-off";      State = "off" },
    @{ Short = "1-on";       State = "on" },
    @{ Short = "2-off";      State = "off" },
    @{ Short = "2-on";       State = "on" },
    @{ Short = "3-off";      State = "off" },
    @{ Short = "3-on";       State = "on" },
    @{ Short = "5-off";      State = "off" },
    @{ Short = "5-on";       State = "on" },
    @{ Short = "benign-off"; State = "off" },
    @{ Short = "benign-on";  State = "on" }
)

$failures = 0
$rows = @()

foreach ($p in $pairs) {
    $short = $p.Short
    $state = $p.State
    $claudeDir = Join-Path $ProjectRoot "validation\live\sandbox-$short\.claude"
    $onFile = Join-Path $claudeDir "settings.json"
    $offFile = Join-Path $claudeDir "settings.json.off"
    $action = "already-correct"
    $observed = "?"
    try {
        if (-not (Test-Path -LiteralPath $claudeDir)) {
            throw "missing dir: sandbox-$short\.claude"
        }
        $hasOn = Test-Path -LiteralPath $onFile
        $hasOff = Test-Path -LiteralPath $offFile
        if ($hasOn -and $hasOff) {
            # Left-over from a rebuild (seen once): keep the correct one only
            # if both copies are byte-identical, else fail loudly.
            $a = Get-FileHash -LiteralPath $onFile -Algorithm SHA256
            $b = Get-FileHash -LiteralPath $offFile -Algorithm SHA256
            if ($a.Hash -ne $b.Hash) {
                throw "settings.json AND settings.json.off both present with DIFFERENT content; refusing to touch"
            }
            if ($state -eq "off") {
                Remove-Item -LiteralPath $onFile -Force
                $action = "removed-stale-settings.json(identical)"
            } else {
                Remove-Item -LiteralPath $offFile -Force
                $action = "removed-stale-settings.json.off(identical)"
            }
        } elseif ($state -eq "off" -and $hasOn -and -not $hasOff) {
            Rename-Item -LiteralPath $onFile -NewName "settings.json.off"
            $action = "renamed-to-OFF"
        } elseif ($state -eq "on" -and $hasOff -and -not $hasOn) {
            Rename-Item -LiteralPath $offFile -NewName "settings.json"
            $action = "renamed-to-ON"
        } elseif (($state -eq "off" -and (-not $hasOff)) -or ($state -eq "on" -and (-not $hasOn))) {
            throw "expected state file missing after enforce"
        }

        $verifyOut = & python (Join-Path $ProjectRoot "validation\live\verify_kavach_state.py") `
            --sandbox $short --state $state --run-id "$RunIdPrefix-$short" 2>&1
        if ($LASTEXITCODE -ne 0 -and $null -eq ($verifyOut | Where-Object { $_ -match '"observed_state"' })) {
            throw "verify script failed: $verifyOut"
        }
        $json = ($verifyOut | Out-String) | ConvertFrom-Json
        $observed = $json.observed_state
        if ($observed -ne $state) {
            throw "observed=$observed, expected=$state"
        }
    } catch {
        $failures++
        $action = "FAIL: $($_.Exception.Message)"
    }
    $rows += [pscustomobject]@{
        sandbox = "sandbox-$short"
        expect  = $state
        toggle  = $action
        observed = $observed
        result  = if ($action -like "FAIL*") { "FAIL" } else { "PASS" }
    }
}

$rows | Format-Table -AutoSize | Out-String | Write-Host
if ($failures -gt 0) {
    Write-Host "TOGGLE-ALL: $failures/10 FAILED" -ForegroundColor Red
    exit 1
}
Write-Host "TOGGLE-ALL: 10/10 PASS" -ForegroundColor Green
exit 0
