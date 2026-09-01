# Full-stack E2E: Docker + cloud (WSL) + frontends + fresh QEMU OpenWrt
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Cloud = Join-Path $Root "cloud"
$EnvFile = Join-Path $Cloud ".env"
$DeviceId = "NDS-Billing-Gateway"
$DeviceSecret = "nds-qemu-secret-16"

function Import-DotEnv([string]$Path) {
  if (-not (Test-Path $Path)) { return }
  Get-Content $Path | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
  }
}

Write-Host "=== Stop old QEMU ==="
wsl.exe -d Ubuntu-22.04 -- bash -lc "pkill -f 'qemu-system-x86_64.*nds-qemu' 2>/dev/null || true"

Write-Host "=== Docker + DB ==="
if (-not (Test-Path $EnvFile)) {
  Copy-Item (Join-Path $Cloud ".env.example") $EnvFile
}
Import-DotEnv $EnvFile
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker is not running. Start Docker Desktop first." }

Push-Location $Cloud
docker compose up -d
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  $prevEap = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  docker compose exec -T mysql mysqladmin ping -h localhost -unds -pnds123 2>$null | Out-Null
  $ErrorActionPreference = $prevEap
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) { Pop-Location; throw "MySQL not ready" }
go run ./cmd/seed
Pop-Location

Write-Host "=== Register QEMU router (Windows cloud if up) ==="
$regBody = @{ device_id = $DeviceId; name = "QEMU E2E"; secret = $DeviceSecret } | ConvertTo-Json
try {
  Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/v1/device/register" -Body $regBody -ContentType "application/json"
  Write-Host "Router registered: $DeviceId"
} catch {
  Write-Host "Windows cloud register skipped (will register in WSL)"
}

$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
$npm = if ($npmCmd) { $npmCmd.Source } else { "npm" }

Write-Host "=== Start admin-web :3000 + user-web :3001 ==="
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'admin-web'); & '$npm' run dev"
)
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location (Join-Path '$Root' 'user-web'); & '$npm' run dev"
)

Write-Host "=== Generate dev TLS cert ==="
wsl.exe -d Ubuntu-22.04 -- bash -lc "mkdir -p /mnt/d/Users/Documents/project/openwrt/cloud/data && test -f /mnt/d/Users/Documents/project/openwrt/cloud/data/dev.crt || openssl req -x509 -newkey rsa:2048 -keyout /mnt/d/Users/Documents/project/openwrt/cloud/data/dev.key -out /mnt/d/Users/Documents/project/openwrt/cloud/data/dev.crt -days 365 -nodes -subj /CN=portal.local"

Write-Host "=== Start cloud on Windows :8080 / :8443 ==="
$Cert = Join-Path $Cloud "data\dev.crt"
$Key = Join-Path $Cloud "data\dev.key"
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "Set-Location '$Cloud'; `$env:TLS_CERT='$Cert'; `$env:TLS_KEY='$Key'; Get-Content .env | ForEach-Object { if (`$_ -match '^\s*#|^\s*$') { return }; `$n,`$v = `$_ -split '=',2; Set-Item Env:`$n `$v }; go run ./cmd/server"
)

Write-Host "=== Bridge Windows cloud into WSL for QEMU (10.0.2.2) ==="
Start-Sleep -Seconds 4
wsl.exe -d Ubuntu-22.04 -- bash /mnt/d/Users/Documents/project/openwrt/build/bridge-cloud-to-wsl.sh

Write-Host "=== Register router via WSL cloud ==="
wsl.exe -d Ubuntu-22.04 -- bash /mnt/d/Users/Documents/project/openwrt/build/register-qemu-device.sh

Write-Host "=== Start fresh QEMU (E2E) ==="
Start-Process wsl.exe -ArgumentList @(
  "-d", "Ubuntu-22.04",
  "--", "bash", "/mnt/d/Users/Documents/project/openwrt/build/qemu-e2e.sh"
)

Write-Host ""
Write-Host "E2E stack started:"
Write-Host "  Admin UI   http://localhost:3000  (admin / admin123)"
Write-Host "  User H5    http://localhost:3001"
Write-Host "  Cloud API  WSL :8080 / :8443 (QEMU guest -> https://10.0.2.2:8443)"
Write-Host "  QEMU       new WSL window, auto-provision after ~2 min"
Write-Host ""
Write-Host "Checklist:"
Write-Host "  1. Admin -> Routers: NDS-Billing-Gateway online"
Write-Host "  2. QEMU console shows NDS_E2E_READY and cloud-probe 200/302"
Write-Host "  3. User H5 register/recharge, admin adjust quota, verify deauth"
