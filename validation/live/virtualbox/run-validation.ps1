<#
.SYNOPSIS
    Run KavachBench validation inside the VirtualBox VM.

.DESCRIPTION
    Copies kavach.exe to VM, runs the manual-baseline log summarizer,
    and optionally runs full trace-replay.

.REQUIREMENTS
    - VM created and running with shared folder mounted
    - kavach.exe available at D:/Projects/KAVACH/target/release/kavach.exe
#>
param(
    [string]$VmName = "KavachBench-Sandbox",
    [string]$GuestUser = "kavach",
    [string]$GuestPass = "kavach",
    [string]$HostKavachPath = "D:\Projects\KAVACH\target\release\kavach.exe",
    [string]$GuestProjectPath = "C:\KavachBench",
    [switch]$FullReplay
)

$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
if (-not (Test-Path $VBoxManage)) { Write-Error "VBoxManage not found"; exit 1 }
if (-not (Test-Path $HostKavachPath)) { Write-Error "kavach.exe not found at $HostKavachPath"; exit 1 }

function Run-InVm { param([string]$Cmd) & $VBoxManage guestcontrol $VmName run --username $GuestUser --password $GuestPass --wait-stdout --wait-stderr -- cmd /c $Cmd }

# Copy kavach.exe to VM
Write-Host "Copying kavach.exe to VM..."
Run-InVm "mkdir $GuestProjectPath\harness 2>nul"
$VBoxManage guestcontrol $VmName copyto $HostKavachPath --username $GuestUser --password $GuestPass --target-directory $GuestProjectPath\harness

# Verify
Write-Host "Verifying kavach.exe in VM..."
Run-InVm "$GuestProjectPath\harness\kavach.exe --version"

# Run summarizer (reads manual-baseline-log.csv, outputs ASR)
Write-Host "Running baseline summarizer..."
Run-InVm "cd $GuestProjectPath && python analysis/summarize_manual.py"

if ($FullReplay) {
    Write-Host "Running trace-replay (empirical defense-in-depth)..."
    Run-InVm "cd $GuestProjectPath && python validation/live/replay.py"
}

Write-Host "Done."