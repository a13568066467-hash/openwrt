# Full lab setup: cloud on this PC + Newifi router via SSH
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
python "$Root\scripts\apply-newifi-setup.py"
if ($LASTEXITCODE -ne 0) {
    python "$Root\scripts\fix-opennds-now.py"
}
Write-Host ""
Write-Host "Phone: connect NDS-WiFi, browser open: http://status.client"
Write-Host "       (neverssl.com needs WAN/internet DNS — use status.client in lab)"
