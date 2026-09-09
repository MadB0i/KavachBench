<#
.SYNOPSIS
    Automated VirtualBox VM setup for KavachBench live validation runs.

.DESCRIPTION
    Creates a Windows VM, copies a disposable KavachBench project snapshot into
    the guest-local disk, provisions Python/Git/Claude Code, and disables the
    network before validation by default.

.REQUIREMENTS
    - Windows 10/11 ISO (provide path via -IsoPath parameter)
    - Administrator PowerShell
    - Internet access for Chocolatey/packages

.EXAMPLE
    .\setup-vm.ps1 -IsoPath "D:\ISOs\Win11_23H2_x64.iso" -GuestUser "sandbox" -GuestPass "<disposable-password>"
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
    [string]$GuestUser,
    [string]$GuestPass,
    [switch]$SkipProvision,
    [switch]$RunValidation,
    [switch]$KeepNetwork
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Msg" -ForegroundColor Cyan }
function Write-Warn { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] WARNING: $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "[$(Get-Date -Format 'HH:mm:ss')] ERROR: $Msg" -ForegroundColor Red }

if ([string]::IsNullOrWhiteSpace($GuestUser)) {
    $GuestUser = Read-Host "Disposable VM account username"
}
if ([string]::IsNullOrWhiteSpace($GuestPass)) {
    $SecureGuestPass = Read-Host "Disposable VM account password" -AsSecureString
    $PassPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureGuestPass)
    try {
        $GuestPass = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($PassPtr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($PassPtr)
    }
}
if ([string]::IsNullOrWhiteSpace($GuestUser) -or [string]::IsNullOrWhiteSpace($GuestPass)) {
    Write-Err "A non-empty disposable guest username and password are required."
    exit 1
}

function Run-InGuest { param([string]$Cmd) & $VBoxManage guestcontrol $VmName run --username $GuestUser --password $GuestPass --wait-stdout --wait-stderr -- cmd /c $Cmd }

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
& $VBoxManage modifyvm $VmName --clipboard-mode disabled --drag-and-drop disabled

# Create disk
$DiskPath = "$env:USERPROFILE\VirtualBox VMs\$VmName\$VmName.vdi"
& $VBoxManage createmedium disk --filename $DiskPath --size ($DiskGB * 1024) --format VDI
& $VBoxManage storagectl $VmName --name "SATA Controller" --add sata --controller IntelAhci
& $VBoxManage storageattach $VmName --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium $DiskPath
& $VBoxManage storageattach $VmName --storagectl "SATA Controller" --port 1 --device 0 --type dvddrive --medium $IsoPath

# The host repository is copied once into the guest-local disk below. No
# VirtualBox shared folder is configured: a compromised guest must not have a
# live read-write path back into the host checkout.
Write-Log "Preparing guest-local project snapshot source: $HostProjectPath"
if (-not (Test-Path $HostProjectPath)) {
    Write-Err "Host project path not found: $HostProjectPath"
    exit 1
}

# Start VM
Write-Log "Starting VM (Windows installer will launch)..."
& $VBoxManage startvm $VmName --type gui

Write-Warn "============================================"
Write-Warn "MANUAL STEP REQUIRED: Complete Windows install in the VM window."
Write-Warn "1. Install Windows (choose Custom, use the virtual disk)"
Write-Warn "2. Create the local user '$GuestUser' with the disposable password supplied to this script"
Write-Warn "3. After desktop loads, install Guest Additions:"
Write-Warn "   Devices -> Insert Guest Additions CD image -> run VBoxWindowsAdditions.exe"
Write-Warn "4. Reboot the VM"
Write-Warn "5. Leave clipboard and drag/drop disabled; the project will be copied to the guest disk"
Write-Warn "============================================"
Write-Host "Press ENTER when Windows install + Guest Additions + reboot are DONE..."
Read-Host

# Copy a minimal, disposable project snapshot into the guest-local disk.
Write-Log "Copying disposable project snapshot into guest-local disk..."
Run-InGuest "mkdir $GuestProjectPath 2>nul"
$ArchivePath = Join-Path $env:TEMP "KavachBench-$VmName.zip"
$ArchiveItems = @(
    (Join-Path $HostProjectPath "analysis"),
    (Join-Path $HostProjectPath "benchmarks"),
    (Join-Path $HostProjectPath "harness"),
    (Join-Path $HostProjectPath "validation"),
    (Join-Path $HostProjectPath "README.md"),
    (Join-Path $HostProjectPath ".gitignore")
)
Compress-Archive -Path $ArchiveItems -DestinationPath $ArchivePath -Force
try {
    & $VBoxManage guestcontrol $VmName copyto $ArchivePath --username $GuestUser --password $GuestPass --target-directory $GuestProjectPath
    Run-InGuest "powershell -NoProfile -Command Expand-Archive -LiteralPath '$GuestProjectPath\KavachBench-$VmName.zip' -DestinationPath '$GuestProjectPath' -Force; Remove-Item -LiteralPath '$GuestProjectPath\KavachBench-$VmName.zip' -Force"
} finally {
    Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue
}

if (-not $SkipProvision) {
    Write-Log "=== Provisioning VM (Python, Git, Claude Code) ==="

    # Enable script execution
    Run-InGuest "powershell -NoProfile -Command Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"

    # Install Chocolatey in VM
    Write-Log "Installing Chocolatey in VM..."
    $ChocoInstall = @"
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
"@
    & $VBoxManage guestcontrol $VmName run --username $GuestUser --password $GuestPass --wait-stdout --wait-stderr -- powershell -Command $ChocoInstall
    Start-Sleep 10

    # Refresh PATH
    Run-InGuest "refreshenv"

    # Install Python, Git, VS Code (for Claude)
    Write-Log "Installing Python, Git, VS Code via Chocolatey..."
    Run-InGuest "choco install python git vscode -y --no-progress"
    Start-Sleep 5
    Run-InGuest "refreshenv"

    # Verify
    Write-Log "Verifying installations..."
    Run-InGuest "python --version && git --version && code --version"
}

if (-not $KeepNetwork) {
    Write-Log "Disabling VM network before validation..."
    & $VBoxManage modifyvm $VmName --nic1 none
} else {
    Write-Warn "Network remains enabled because -KeepNetwork was supplied; do not use this for payload runs."
}

if ($RunValidation -or $SkipProvision) {
    Write-Log "=== Running validation inside VM ==="
    # The project is guest-local at $GuestProjectPath.
    # Run the manual baseline: python analysis/summarize_manual.py etc.
    # But first, install Kavach CLI inside VM (need to copy binary or build)
    Write-Warn "To run full validation, you need kavach.exe inside the VM."
    Write-Warn "Copy the Kavach binary into $GuestProjectPath/harness/ using run-validation.ps1"
    Write-Warn "Option B: Build Kavach inside VM (needs Rust toolchain: choco install rust)"
    Write-Warn "Then run: cd $GuestProjectPath && python analysis/summarize_manual.py"
}

Write-Log "=== VM Setup Complete ==="
Write-Host "VM Name: $VmName"
Write-Host "Guest-local project: $GuestProjectPath"
Write-Host "Network: $(if ($KeepNetwork) { 'enabled by explicit -KeepNetwork' } else { 'disabled' })"
Write-Host "To connect: VBoxManage startvm $VmName --type gui"
Write-Host "To run commands: VBoxManage guestcontrol $VmName run --username <guest-user> --password <guest-password> -- cmd /c \"your-command\""
