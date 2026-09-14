<#
.SYNOPSIS
    Run 10 OpenCode headless sessions (sandbox x plugin-state).

.DESCRIPTION
    For each of {1,2,3,5,benign} x {on,off}:
      1. Toggle .opencode/plugins/kavach.ts presence (on = present, off = absent)
      2. Read the sandbox TASK.md as the prompt
      3. Invoke `opencode run --dir <sandbox> <prompt>`
      4. Dump raw transcript to results/live/sandbox-N-state.transcript.txt

    Does NOT classify, summarize, or post-process output.

.PARAMETER TimeoutSec
    Max seconds to wait per sandbox before kill. Default 1200 (20 min).

.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -File run-all-10.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File run-all-10.ps1 -TimeoutSec 600
#>
param(
    [string]$ProjectRoot = $PSScriptRoot,
    [int]$TimeoutSec = 1200
)

$ErrorActionPreference = "Stop"

$liveDir    = Join-Path $ProjectRoot "validation\live"
$resultsDir = Join-Path $ProjectRoot "results\live"
if (-not (Test-Path -LiteralPath $resultsDir)) {
    New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
}

$combos = @(
    @{ Num = "1";       State = "on"  },
    @{ Num = "1";       State = "off" },
    @{ Num = "2";       State = "on"  },
    @{ Num = "2";       State = "off" },
    @{ Num = "3";       State = "on"  },
    @{ Num = "3";       State = "off" },
    @{ Num = "5";       State = "on"  },
    @{ Num = "5";       State = "off" },
    @{ Num = "benign";  State = "on"  },
    @{ Num = "benign";  State = "off" }
)

$pluginSource = Join-Path $liveDir "sandbox-1-on\.opencode\plugins\kavach.ts"

foreach ($c in $combos) {
    $n     = $c.Num
    $state = $c.State
    $label = "sandbox-$n-$state"
    $sandboxDir = Join-Path $liveDir $label
    $taskFile   = Join-Path $sandboxDir "TASK.md"
    $outFile    = Join-Path $resultsDir "$label.transcript.txt"

    Write-Host "`n=== $label ===" -ForegroundColor Cyan

    # --- per-sandbox try/catch so one failure never kills the loop --------
    try {

        # --- sanity checks ---------------------------------------------------
        if (-not (Test-Path -LiteralPath $sandboxDir)) {
            Write-Host "  SKIP: directory not found $sandboxDir" -ForegroundColor Yellow
            continue
        }
        if (-not (Test-Path -LiteralPath $taskFile)) {
            Write-Host "  SKIP: TASK.md missing in $sandboxDir" -ForegroundColor Yellow
            continue
        }

        # --- toggle plugin ---------------------------------------------------
        $pluginsDir = Join-Path $sandboxDir ".opencode\plugins"
        $kavachFile = Join-Path $pluginsDir "kavach.ts"

        if ($state -eq "on") {
            if (-not (Test-Path -LiteralPath $kavachFile)) {
                if (-not (Test-Path -LiteralPath $pluginSource)) {
                    Write-Host "  ERROR: source kavach.ts not found at $pluginSource" -ForegroundColor Red
                    continue
                }
                if (-not (Test-Path -LiteralPath $pluginsDir)) {
                    New-Item -ItemType Directory -Path $pluginsDir -Force | Out-Null
                }
                Copy-Item -LiteralPath $pluginSource -Destination $kavachFile -Force
                Write-Host "  Plugin ON  (copied kavach.ts)" -ForegroundColor Green
            } else {
                Write-Host "  Plugin ON  (already present)" -ForegroundColor Green
            }
        } else {
            if (Test-Path -LiteralPath $kavachFile) {
                Remove-Item -LiteralPath $kavachFile -Force
                Write-Host "  Plugin OFF (removed kavach.ts)" -ForegroundColor Green
            } else {
                Write-Host "  Plugin OFF (already absent)" -ForegroundColor Green
            }
        }

        # --- read TASK.md ----------------------------------------------------
        $prompt = (Get-Content -LiteralPath $taskFile -Raw).Trim()
        Write-Host "  Prompt length: $($prompt.Length) chars"

        # --- run opencode headless -------------------------------------------
        Write-Host "  Running (timeout ${TimeoutSec}s) ..."

        # Escape double-quotes in prompt for cmd.exe
        $safePrompt = $prompt -replace '"', '""'

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "cmd.exe"
        $psi.Arguments = "/c opencode run --dir `"$sandboxDir`" --auto `"$safePrompt`""
        $psi.UseShellExecute  = $false
        $psi.CreateNoWindow   = $true
        $psi.RedirectStandardOutput  = $true
        $psi.RedirectStandardError   = $true
        $psi.StandardOutputEncoding  = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding   = [System.Text.Encoding]::UTF8
        $proc = [System.Diagnostics.Process]::Start($psi)

        # Read streams async to avoid deadlock with WaitForExit
        $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
        $stderrTask = $proc.StandardError.ReadToEndAsync()

        $exited = $proc.WaitForExit($TimeoutSec * 1000)

        if (!$exited) {
            Write-Host "  TIMEOUT after ${TimeoutSec}s -- killing process tree" -ForegroundColor Yellow
            try {
                taskkill /F /T /PID $proc.Id 2>$null
            } catch {}
            Start-Sleep -Seconds 3
        }

        # Await async reads
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        $body = $stderr + $stdout

        # --- write final transcript with status header ----------------------
        $statusTag = if ($exited) { "completed (exit=$($proc.ExitCode))" } else { "TIMEOUT (killed)" }
        $header = "--- STATUS: $statusTag timeout=${TimeoutSec}s ---`n"

        if ($null -ne $body) {
            [System.IO.File]::WriteAllText($outFile, $header + $body, [System.Text.Encoding]::UTF8)
        } else {
            [System.IO.File]::WriteAllText($outFile, $header + "(no output captured)`n", [System.Text.Encoding]::UTF8)
        }

        $sizeKB = [math]::Round((Get-Item -LiteralPath $outFile).Length / 1024, 1)
        $finalStatus = if ($exited) { "completed" } else { "TIMEOUT" }
        Write-Host "  exit=$($proc.ExitCode)  status=$finalStatus  size=${sizeKB}KB  -> results\live\$label.transcript.txt" -ForegroundColor Green

    } catch {
        # --- catch-all: log error and CONTINUE to next sandbox ---------------
        Write-Host "  ERROR in ${label}: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  Continuing to next sandbox..." -ForegroundColor Yellow
        # Write a minimal error transcript so the slot is not empty
        try {
            $errHeader = "--- STATUS: ERROR ---`n"
            $errBody   = "$($_.Exception.Message)`n$($_.ScriptStackTrace)`n"
            [System.IO.File]::WriteAllText($outFile, $errHeader + $errBody, [System.Text.Encoding]::UTF8)
        } catch {}
    }

} # end foreach

Write-Host "`n=== ALL DONE ===" -ForegroundColor Cyan
