# Launch openwrt-feed firmware in QEMU (interactive serial console)
# Prereq: WSL Ubuntu-22.04 + built x86_64 image (build/build.sh x86_64)
$ErrorActionPreference = "Stop"

$QemuScript = "/mnt/d/Users/Documents/project/openwrt/build/qemu-run.sh"

Write-Host "=== Starting OpenWrt QEMU (openwrt-feed) ==="
Write-Host "A new WSL window will open. Login as root to inspect."
Write-Host ""

Start-Process wsl.exe -ArgumentList @(
  "-d", "Ubuntu-22.04",
  "--", "bash", $QemuScript
)

Write-Host "QEMU started."
Write-Host "Quit: Ctrl+A then X in the QEMU window"
Write-Host "Full stack test: powershell -File scripts\start-dev.ps1"
