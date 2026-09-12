<#
.SYNOPSIS
    Restore the clean VirtualBox snapshot and boot the VM for manual work.

.DESCRIPTION
    Powers off the VM when it is running, restores the named snapshot, and
    starts the VM in GUI mode. The script deliberately stops after startvm;
    all sandbox interaction remains manual.

.EXAMPLE
    .\restore-and-boot.ps1

.NOTES
    Defaults match the validation VM currently named `ok` and the snapshot
    `clean-baseline`. Override either value if the VirtualBox Manager uses a
    different name.
##>
[CmdletBinding()]
param(
    [string]$VmName = "ok",
    [string]$SnapshotName = "clean-baseline",
    [string]$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $VBoxManage)) {
    $resolved = Get-Command VBoxManage.exe -ErrorAction SilentlyContinue
    if ($resolved) {
        $VBoxManage = $resolved.Source
    } else {
        throw "VBoxManage not found. Expected: $VBoxManage"
    }
}

function Invoke-VBoxManage {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & $VBoxManage @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "VBoxManage failed (exit $LASTEXITCODE): $($Arguments -join ' ')"
    }
}

function Get-VmState {
    $info = & $VBoxManage showvminfo $VmName --machinereadable 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect VM '$VmName'. Check the VM name with: VBoxManage list vms"
    }

    $stateLine = $info | Where-Object { $_ -match '^VMState=' } | Select-Object -First 1
    if (-not $stateLine) {
        throw "VBoxManage did not return a VMState for '$VmName'."
    }
    return (($stateLine -replace '^VMState="', '') -replace '"$', '')
}

Write-Host "VM: $VmName"
Write-Host "Snapshot: $SnapshotName"
Write-Host "VBoxManage: $VBoxManage"

$state = Get-VmState
Write-Host "Current state: $state"

if ($state -in @("running", "paused", "stuck")) {
    Write-Host "Powering off VM..."
    Invoke-VBoxManage @("controlvm", $VmName, "poweroff")

    for ($attempt = 1; $attempt -le 30; $attempt++) {
        Start-Sleep -Seconds 1
        if ((Get-VmState) -eq "poweroff") {
            break
        }
    }

    if ((Get-VmState) -ne "poweroff") {
        throw "VM '$VmName' did not reach poweroff state within 30 seconds."
    }
} elseif ($state -ne "poweroff" -and $state -ne "saved") {
    throw "VM '$VmName' is in unsupported state '$state'. Stop it manually before retrying."
}

Write-Host "Restoring snapshot '$SnapshotName'..."
Invoke-VBoxManage @("snapshot", $VmName, "restore", $SnapshotName)

Write-Host "Starting VM in GUI mode..."
Invoke-VBoxManage @("startvm", $VmName, "--type", "gui")

Write-Host "VM started. Continue with the manual sandbox session; this script will not run any tests."
