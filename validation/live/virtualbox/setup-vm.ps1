<#
.SYNOPSIS
    Automated VirtualBox VM setup for KavachBench live validation runs.

.DESCRIPTION
    Creates a Windows VM, shares the KavachBench project folder, provisions
    Python/Git/Claude Code, and runs the manual-baseline validation.

.REQUIREMENTS
    - Windows 10/11 ISO (provide path via -IsoPath parameter)
    - Administrator PowerShell
    - Internet access for Chocolatey/packages

.EXAMPLE
    .\setup-vm.ps1 -IsoPath "D:\ISOs\Win11_23H2_x64.iso" -VmName "KavachBench-Sandbox"
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$IsoPath,

    [string]$VmName = "KavachBench-Sandbox",
    [int]$MemoryMB = 8192,
    [int]$CpuCount = 4,
    [int]$DiskGB = 80,
    [string]$HostProjectPath = "D:\Projects\KavachBench",
    [string]$GuestProjectPath = "C:\KavachBench",
    [switch]$SkipProvision,
    [switch]$RunValidation
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Msg" -ForegroundColor Cyan }
function Write-Warn { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] WARNING: $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ERROR: $Msg" -ForegroundColor Red }

# Check admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Run as Administrator. Re-launch PowerShell as Admin."
    exit 1
}

# Find VirtualBox
$VBoxManage = "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe"
if (-not (Test-Path $VBoxManage)) {
    Write-Log "VirtualBox not found. Installing via Chocolatey..."
    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Log "Installing Chocolatey..."
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [Environment]::GetEnvironmentVariable("PATH", "User")
    }
    choco install virtualbox -y --no-progress
    if (-not (Test-Path $VBoxManage)) {
        Write-Err "VirtualBox install failed. Install manually from virtualbox.org"
        exit 1
    }
    Write-Log "VirtualBox installed."
}

# Verify ISO
if (-not (Test-Path $IsoPath)) {
    Write-Err "ISO not found: $IsoPath"
    exit 1
}

Write-Log "=== Creating VM: $VmName ==="

# Create VM
& $VBoxManage createvm --name $VmName --ostype "Windows11_64" --register
& $VBoxManage modifyvm $VmName --memory $MemoryMB --cpus $CpuCount --vram 128 --graphicscontroller vmsvga --accelerate3d on
& $VBoxManage modifyvm $VmName --boot1 dvd --boot2 disk --boot3 none --boot4 none
& $VBoxManage modifyvm $VmName --nic1 nat --nictype1 82540EM
& $VBoxManage modifyvm $VmName --audio none
& $VBoxManage modifyvm $VmName --usb on --usbehci on --usbxhci on

# Create disk
$DiskPath = "$env:USERPROFILE\VirtualBox VMs\$VmName\$VmName.vdi"
& $VBoxManage createmedium disk --filename $DiskPath --size ($DiskGB * 1024) --format VDI
& $VBoxManage storagectl $VmName --name "SATA Controller" --add sata --controller IntelAhci
& $VBoxManage storageattach $VmName --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium $DiskPath
& $VBoxManage storageattach $VmName --storagectl "SATA Controller" --port 1 --device 0 --type dvddrive --medium $IsoPath

# Shared folder (auto-mount at boot)
Write-Log "Configuring shared folder: $HostProjectPath -> $GuestProjectPath"
if (-not (Test-Path $HostProjectPath)) {
    Write-Err "Host project path not found: $HostProjectPath"
    exit 1
}
& $VBoxManage sharedfolder add $VmName --name "KavachBench" --hostpath $HostProjectPath --automount --auto-mount-point $GuestProjectPath --readonly off

# Start VM
Write-Log "Starting VM (Windows installer will launch)..."
& $VBoxManage startvm $VmName --type gui

Write-Warn "============================================"
Write-Warn "MANUAL STEP REQUIRED: Complete Windows install in the VM window."
Write-Warn "1. Install Windows (choose Custom, use the virtual disk)"
Write-Warn "2. Create a local user (e.g., 'kavach') with password"
Write-Warn "3. After desktop loads, install Guest Additions:"
Write-Warn "   Devices -> Insert Guest Additions CD image -> run VBoxWindowsAdditions.exe"
Write-Warn "4. Reboot the VM"
Write-Warn "5. Verify shared folder appears at: $GuestProjectPath"
Write-Warn "============================================"
Write-Host "Press ENTER when Windows install + Guest Additions + reboot are DONE..."
Read-Host

# Verify shared folder
Write-Log "Checking shared folder inside VM..."
$CheckShared = & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "dir $GuestProjectPath 2>&1"
if ($LASTEXITCODE -ne 0 -or $CheckShared -notmatch "KavachBench") {
    Write-Warn "Shared folder not visible yet. Trying to mount manually..."
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "net use Z: \\vboxsrv\KavachBench /persistent:yes 2>&1"
}

if (-not $SkipProvision) {
    Write-Log "=== Provisioning VM (Python, Git, Claude Code) ==="

    # Enable script execution
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- powershell -Command "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"

    # Install Chocolatey in VM
    Write-Log "Installing Chocolatey in VM..."
    $ChocoInstall = @"
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
"@
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- powershell -Command $ChocoInstall
    Start-Sleep 10

    # Refresh PATH
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "refreshenv"

    # Install Python, Git, VS Code (for Claude)
    Write-Log "Installing Python, Git, VS Code via Chocolatey..."
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "choco install python git vscode -y --no-progress"
    Start-Sleep 5
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "refreshenv"

    # Verify
    Write-Log "Verifying installations..."
    & $VBoxManage guestcontrol $VmName run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "python --version && git --version && code --version"
}

if ($RunValidation -or $SkipProvision) {
    Write-Log "=== Running validation inside VM ==="
    # The shared folder is at $GuestProjectPath
    # Run the manual baseline: python analysis/summarize_manual.py etc.
    # But first, install Kavach CLI inside VM (need to copy binary or build)
    Write-Warn "To run full validation, you need kavach.exe inside the VM."
    Write-Warn "Option A: Copy D:/Projects/KAVACH/target/release/kavach.exe to $GuestProjectPath/harness/"
    Write-Warn "Option B: Build Kavach inside VM (needs Rust toolchain: choco install rust)"
    Write-Warn "Then run: cd $GuestProjectPath && python analysis/summarize_manual.py"
}

Write-Log "=== VM Setup Complete ==="
Write-Host "VM Name: $VmName"
Write-Host "Shared folder: $GuestProjectPath (maps to $HostProjectPath)"
Write-Host "To connect: VBoxManage startvm $VmName --type gui"
Write-Host "To run commands: VBoxManage guestcontrol $VmName run --username kavach --password kavach -- cmd /c \"your-command\""