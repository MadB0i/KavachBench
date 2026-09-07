# VirtualBox Sandbox for KavachBench Live Validation

This directory contains scripts to automate a full Windows VM in VirtualBox
for running KavachBench live-model validation (manual-baseline runs).

## Why VirtualBox?

Your host is **Windows 10 Home** — Windows Sandbox is unavailable (Pro/Enterprise only).
VirtualBox runs on any edition and provides a clean, disposable Windows VM.

## Prerequisites

- **Windows 10/11 ISO** (download from Microsoft)
- **Administrator PowerShell**
- Internet access (for Chocolatey/package downloads)

## Quick Start

```powershell
# 1. Download Windows ISO (e.g., Win11_23H2_x64.iso) and note its path
# 2. Run setup (as Admin):
cd D:\Projects\KavachBench\validation\live\virtualbox
.\setup-vm.ps1 -IsoPath "D:\ISOs\Win11_23H2_x64.iso"

# 3. In the VM window that opens:
#    - Complete Windows install (local user: kavach / kavach)
#    - Devices -> Insert Guest Additions CD image -> run VBoxWindowsAdditions.exe
#    - Reboot VM
#    - Return to host PowerShell and press ENTER

# 4. Script provisions Python, Git, VS Code inside VM automatically
# 5. Run validation:
.\run-validation.ps1
```

## What the scripts do

### `setup-vm.ps1`
1. Installs VirtualBox via Chocolatey (if not present)
2. Creates VM with 8GB RAM, 4 vCPU, 80GB disk
3. Attaches your Windows ISO
4. Configures **shared folder**: `D:\Projects\KavachBench` (host) → `C:\KavachBench` (guest) — auto-mounts at boot
5. Walks you through Windows install + Guest Additions
6. Provisions: Python 3.12, Git, VS Code (for Claude Code)

### `run-validation.ps1`
1. Copies `kavach.exe` from host build to VM (`C:\KavachBench\harness\`)
2. Runs `python analysis/summarize_manual.py` — computes baseline/defended ASR
3. Optional: runs `python validation/live/replay.py` for empirical trace-replay

## Manual baseline workflow (after VM ready)

1. **Baseline runs (Kavach OFF):**
   - In VM: rename `C:\KavachBench\validation\live\sandbox-N\.claude\settings.json` → `settings.json.off`
   - In host: open `C:\KavachBench\validation\live\sandbox-N\TASK.md`, copy content
   - In VM: start VS Code, install Claude Code extension, paste task, run
   - Record outcome in `analysis/manual-baseline-log.csv` (replace TBD)

2. **Defended runs (Kavach ON):**
   - In VM: rename `settings.json.off` → `settings.json`
   - Repeat steps above

3. **Compute results:**
   - Host or VM: `python analysis/summarize_manual.py`

## VM Management

```powershell
# Start VM (headless or GUI)
VBoxManage startvm "KavachBench-Sandbox" --type gui
VBoxManage startvm "KavachBench-Sandbox" --type headless

# Run arbitrary command in VM
VBoxManage guestcontrol "KavachBench-Sandbox" run --username kavach --password kavach --wait-stdout --wait-stderr -- cmd /c "your-command"

# Snapshot (before risky runs)
VBoxManage snapshot "KavachBench-Sandbox" take "clean-provisioned" --description "After Python/Git/VSCode install"

# Restore snapshot
VBoxManage snapshot "KavachBench-Sandbox" restore "clean-provisioned"

# Delete VM entirely
VBoxManage unregistervm "KavachBench-Sandbox" --delete
```

## Files

| File | Purpose |
|---|---|
| `setup-vm.ps1` | Create + provision VM |
| `run-validation.ps1` | Copy kavach.exe + run summarizer/replay |
| `README.md` | This file |

## Notes

- Default VM credentials: `kavach` / `kavach` (change in script if needed)
- Shared folder auto-mounts at `C:\KavachBench` in guest
- Guest Additions **required** for shared folder + clipboard + drag-drop
- `kavach.exe` must be built on host first: `cd D:/Projects/KAVACH && cargo build --release`
- The manual-baseline log is at `analysis/manual-baseline-log.csv` (shared, so editable from host or guest)